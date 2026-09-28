"""실패 정책이 params.yaml 설정대로 동작하는지 — TC-10 의 바탕.

🚨 로봇·브링업·ROS 없이 돈다. flow.py 가 ROS 를 import 하지 않게 나눠 둔 덕분이다.
실제 TC-10 은 flow_node 를 띄워 HMI·Ctrl+C 까지 확인한다(9/22 UT-FLOW).
"""
import threading
import types

import pytest

from cobot_api import F1Api, F2Api, F3Api, GRIP_FAIL, PICK, TOOL_LOST, Result
from f2_sense_flow import flow as flow_module
from f2_sense_flow import mock
from f2_sense_flow.flow import _POLL_S, Flow, Signals, load_features

# 깃발을 들여다보는 간격(_POLL_S)의 몇 배만 기다려 보고 "아직 안 풀렸다" 를 판정한다.
SETTLE_S = _POLL_S * 6
# 🚨 스레드를 쓰는 시험은 **반드시** 상한을 둔다 — 안 풀리는 버그가 무한 대기가 되면 안 된다.
TIMEOUT_S = _POLL_S * 100

CFG = {'flow': {
    'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2},
             {'zone': 'RET_C', 'kind': 'CUP', 'count': 2}],
    'rack_order': {'BOWL': ['RACK_B1', 'RACK_B2'],
                   'CUP': ['RACK_C1', 'RACK_C2']},
    'policy': {'EMPTY_ZONE': 'next_zone', 'LEFTOVER_REMAIN': 'isolate', 'SEAT_FAIL': 'isolate',
               'FORCE_LIMIT': 'retry:1->isolate', 'TIMEOUT': 'retry:1->isolate',
               'RACK_JAM': 'retry:1->isolate', 'TOOL_FAIL': 'retry:1->isolate',
               'RACK_FULL': 'pause', 'ROBOT_ERROR': 'pause',
               'GRIP_FAIL': 'pause',           # 9/20 결정 E12 — params.yaml 과 같은 값
               'TOOL_LOST': 'pause'},          # 9/23 결정 E37 — params.yaml 과 같은 값
    'counts': {'soap_dips': 3, 'rinse_dips': 1, 'rinse_shakes': 3},
    'step_delay_s': 0.0,
    'done_hold_s': 0.0,     # 시험에서는 기다리지 않는다
}}


class Quiet:
    def info(self, m): pass
    def warn(self, m): pass
    def error(self, m): pass


class AutoResume(Signals):
    """시험용 — resume 을 자동으로 눌러 준다.

    운영 중에는 PAUSED 에서 사람이 재개할 때까지 기다리는 게 맞다(SDD §5.1).
    하지만 시험에서는 예상 못 한 PAUSE 가 **무한 대기**가 되어 버그를 숨긴다.
    자동으로 재개시켜 두면 "왜 멈췄나"가 assert 실패로 드러난다.
    """

    def take(self, name):
        if name == 'resume':
            return True
        return super().take(name)


def run(fail_on):
    """가짜 기능으로 plan 한 바퀴. (이벤트 결과들, flow) 를 돌려준다."""
    mock.configure(fail_on)
    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())
    return [e['result'] for e in events], f


@pytest.fixture(autouse=True)
def _clean():
    yield
    mock.reset()


def test_no_failure_completes_all():
    results, f = run([])
    assert results == ['DONE'] * 4
    assert (f.done_bowl, f.done_cup, f.isolated) == (2, 2, 0)


def test_seat_fail_isolates():
    """SEAT_FAIL → isolate. 격리하고 다음 용기로 간다."""
    results, f = run(['place:SEAT_FAIL'])
    assert results == ['ISOLATED'] * 4
    assert f.isolated == 4 and f.done_bowl == 0


def test_empty_zone_skips_rest_of_zone():
    """🚨 EMPTY_ZONE 은 용기 1개가 아니라 **구역 전체**를 포기한다 (IRD §8).

    구역이 2개이므로 SKIPPED 는 4건이 아니라 2건이어야 한다.
    """
    results, f = run(['pick:EMPTY_ZONE'])
    assert results == ['SKIPPED', 'SKIPPED']
    assert f.isolated == 0


def test_retry_recovers():
    """retry:1->isolate — 한 번 실패해도 재시도가 성공하면 정상 완료."""
    results, f = run(['rack_place:RACK_JAM:1'])
    assert results == ['DONE'] * 4
    assert f.isolated == 0


def test_retry_does_not_rerun_earlier_steps():
    """🚨 재시도가 성공한 뒤 **그다음 단계로** 가야 한다 — 앞 단계로 되돌아가면 안 된다.

    9/21 에 찾은 결함: 재시도를 세는 변수가 바깥의 단계 인덱스와 이름이 같아(둘 다 i)
    재시도가 성공하면 단계 인덱스가 재시도 횟수로 덮였다. rack_place(마지막에서 두 번째)가
    한 번 실패했다 성공하면 **steps[1] 로 뛰어** 무게·안착·닦기·헹굼·적재를 한 바퀴 더 돌았다.

    실기에서 무슨 일이 나나: 용기는 이미 팔레트에 들어가 있으므로 **빈 그리퍼로** 저울에 가고,
    스펀지 홈에 허공을 안착시키고, 이미 찬 칸에 다시 삽입한다. 그런데도 결과는 'DONE' 이다.

    위의 test_retry_recovers 는 이벤트 결과만 보므로 이 결함을 **통과시킨다** →
    여기서는 기능 함수가 몇 번 불렸는지를 센다.
    """
    def count(fail_on):
        mock.configure(fail_on)
        calls, events = [], []
        f = Flow(CFG, Quiet(), publish_event=events.append)
        f.f = load_features(['f1', 'f2', 'f3'])
        orig = f.call_fn
        f.call_fn = lambda mod, fname, *a: (calls.append(fname), orig(mod, fname, *a))[1]
        f.run_plan(AutoResume())
        mock.reset()
        return calls, [e['result'] for e in events]

    base, ok = count([])
    assert ok == ['DONE'] * 4

    calls, results = count(['rack_place:RACK_JAM:1'])
    assert results == ['DONE'] * 4
    # 늘어나도 되는 것은 **실패해서 다시 부른 rack_place 한 번**뿐이다
    assert len(calls) == len(base) + 1, (
        f'재시도 뒤 앞 단계로 되돌아갔다 — {len(calls) - len(base)} 회 더 불렀다\n{calls}')
    assert calls.count('rack_place') == base.count('rack_place') + 1


def test_retry_exhausted_isolates():
    """재시도를 다 써도 실패하면 격리."""
    results, f = run(['rack_place:RACK_JAM'])
    assert results == ['ISOLATED'] * 4
    assert f.isolated == 4


def test_retreat_failure_stops_retry_and_pauses():
    """🚨 후퇴가 실패하면 **재시도하지 않는다** — 로봇이 어디 있는지 모르는 채로
    같은 동작을 다시 하면 위험하다. 격리(옮기기)도 하지 않고 사람을 기다린다.
    """
    def boom():
        raise NotImplementedError('아직 구현 전이다')

    mock.configure(['rack_place:RACK_JAM'])          # 재시도 정책을 타게 만든다
    f = Flow(CFG, Quiet(), safe_retreat=boom)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())                         # 예외가 새면 여기서 깨진다
    assert f.last_code == 'ROBOT_ERROR'
    assert f.isolated == 0, '로봇 위치를 모르는데 격리로 옮기면 안 된다'


def test_rack_slot_assignment():
    """팔레트 칸은 rack_order 순서대로 배정된다."""
    f = Flow(CFG, Quiet())
    f.kind = 'BOWL'
    assert f._next_slot() == 'RACK_B1'
    f.done_bowl = 1
    assert f._next_slot() == 'RACK_B2'


def _recorder(mod, api, called):
    """약속(F?Api)에 있는 함수만 감싸서 호출 이름을 기록한다.

    모듈의 모든 callable 을 감싸면 클래스·상수까지 건드려 깨진다 — 약속된 이름만 쓴다.
    """
    ns = types.SimpleNamespace()
    for name in (n for n in dir(api) if not n.startswith('_')):
        fn = getattr(mod, name)
        setattr(ns, name, (lambda n, g: lambda *a: (called.append(n), g(*a))[1])(name, fn))
    return ns


def test_full_order_calls_every_function():
    """IRD §8 순서대로 f1·f2·f3 함수가 모두 불린다 (빠뜨린 단계가 없는지)."""
    called = []
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    f = Flow(CFG, Quiet())
    f.f = {'f1': _recorder(mods['f1'], F1Api, called),
           'f2': _recorder(mods['f2'], F2Api, called),
           'f3': _recorder(mods['f3'], F3Api, called)}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]
    f.run_plan(AutoResume())
    assert f.step != 'PAUSED', '예상 못 한 PAUSE — 어딘가에서 예외가 났다'
    for need in ('pick', 'move_to', 'leftover_loop', 'place', 'tool',
                 'soap', 'wipe_bowl', 'dip', 'shake', 'rack_place'):
        assert need in called, f'{need} 가 안 불렸다'


# ────────────────────────────────── stop 위치 (9/20 V-20 결함 · SDD §5.1)
class StopAfter(AutoResume):
    """resume 을 눌러 줄 때 "그때까지 몇 단계가 갔는지" 를 기록하는 시험용 깃발."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.calls_at_pause = None

    def take(self, name):
        if name == 'resume' and self.calls_at_pause is None:
            self.calls_at_pause = len(self.calls)
        return super().take(name)


def test_stop_pauses_between_steps():
    """🚨 정지 버튼은 **단계 사이마다** 먹어야 한다 — 용기 하나를 끝까지 하고서가 아니라.

    V-20(황인재 9/20)에서 "stop 뒤에도 RINSE·RACK 을 더 갔다" 로 드러난 결함.
    실기에서는 함수 하나가 수십 초라, 이게 없으면 정지 버튼이 소프트 E-STOP 이 못 된다.
    """
    mock.configure([])
    f = Flow(CFG, Quiet())
    f.f = load_features(['f1', 'f2', 'f3'])
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = StopAfter()
    orig = f.call_fn

    def counting(mod_key, fn_name, *args):
        r = orig(mod_key, fn_name, *args)
        sig.calls.append(fn_name)
        if len(sig.calls) == 3:              # 용기 중간(3단계째)에서 정지 버튼을 누른다
            sig.raise_('stop')
        return r

    f.call_fn = counting
    f.run_plan(sig)

    assert sig.calls_at_pause is not None, 'stop 을 눌렀는데 PAUSED 가 안 됐다'
    assert sig.calls_at_pause == 3, \
        f'stop 뒤에 {sig.calls_at_pause - 3} 단계를 더 갔다 — 단계 사이에서 멈춰야 한다'
    assert f.step != 'PAUSED', 'resume 뒤 끝까지 가야 한다'
    assert len(sig.calls) == 12, f'resume 뒤 남은 단계를 다 못 갔다 ({len(sig.calls)}/12)'   # 🔄 9/23 WEIGH 이동 단계 제거 → 12


def test_stop_does_not_touch_the_gripper():
    """🚨 멈출 때 그리퍼에 **아무 명령도 보내지 않는다** (SDD §5.1 · 황인재 9/20).

    든 채 멈추는 구간이 생기는데, 힘을 바꾸면 드라이버가 다시 파지하면서 놓칠 수 있다.
    기능 함수가 끝날 때 HOLD → NORMAL 로 되돌리므로 단계 사이는 이미 NORMAL 이다.
    """
    import inspect

    from f2_sense_flow import flow as flow_mod

    src = inspect.getsource(flow_mod.Flow.process_one) + inspect.getsource(flow_mod.Flow.run_plan)
    body = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('#'))
    for banned in ('grip_level', 'release(', 'grip('):
        assert banned not in body, f'정지 경로에서 그리퍼를 건드린다: {banned}'


# ────────────────────────────────── 미리 눌린 resume (감사 결함 A)
def _in_thread(fn):
    """fn 을 딴 스레드에서 돌리고 (끝났는지 알려 주는 Event, 반환값 리스트) 를 준다.

    🚨 시험용이다. 운영에서 로봇 함수는 메인 스레드에서만 부른다(SDD §3.2) —
       여기서는 가짜 모듈만 돌리고, "기다리는 쪽" 을 시험이 붙잡지 않으려고 쓴다.
    """
    done, out = threading.Event(), []

    def body():
        try:
            out.append(fn())
        finally:
            done.set()

    threading.Thread(target=body, daemon=True).start()
    return done, out


def test_pre_pressed_resume_does_not_release_next_pause():
    """🚨 **멈추기 전에** 눌린 resume 이 다음 PAUSED 를 풀면 안 된다.

    resume 깃발은 소비될 때까지 남는다. 운전 중에 눌렸거나 한 번의 정지에서 두 번 눌린
    resume 이 그대로 걸려 있다가, 다음에 진짜로 PAUSED 가 되는 순간 사람이 아무것도 안 했는데
    재개시켜 버린다. ROBOT_ERROR·RACK_FULL 처럼 사람이 확인해야 하는 정지(SDD §7)가
    0 초 만에 풀리면 안 된다 — wait_resume 은 **멈춘 뒤에 눌린** 재개만 받는다.
    """
    f = Flow(CFG, Quiet())
    sig = Signals()
    sig.raise_('resume')                     # 운전 중(아직 PAUSED 가 아닐 때) 눌린 재개

    # 실제 코드가 부르는 방식 그대로 — to_paused 가 'PAUSED' 로 바꾸기 **전**에 resume 을 지운다.
    # (지우는 자리를 wait_resume 으로 옮기면 그 사이에 들어온 정당한 resume 이 조용히 사라진다)
    f.to_paused('시험', sig)
    done, _ = _in_thread(lambda: f.wait_resume(sig))

    assert not done.wait(SETTLE_S), '미리 눌린 resume 으로 정지가 풀렸다 — 사람이 누르지 않았다'
    assert f.step == 'PAUSED'

    sig.raise_('resume')                     # 이제 사람이 진짜로 누른다
    assert done.wait(TIMEOUT_S), '사람이 resume 을 눌렀는데도 재개되지 않았다'
    assert f.step != 'PAUSED'


def test_pre_pressed_resume_does_not_skip_stop_between_steps():
    """미리 눌린 resume 이 **단계 사이 stop**(9/20 V-20 수정)까지 무력화하면 안 된다.

    운전 중에 resume, 그 뒤에 stop 을 누른 상황 — 정지 버튼이 소프트 E-STOP 노릇을 하려면
    사람이 다시 누를 때까지 그 자리에 서 있어야 한다.
    """
    mock.configure([])
    f = Flow(CFG, Quiet())
    f.f = load_features(['f1', 'f2', 'f3'])
    f.zone_id, f.kind = 'RET_B', 'BOWL'

    sig = Signals()
    sig.raise_('resume')                     # 운전 중에 미리 눌린 재개
    sig.raise_('stop')                       # 그 뒤에 정지 버튼

    done, out = _in_thread(lambda: f.process_one(sig))

    assert not done.wait(SETTLE_S), '미리 눌린 resume 이 stop 을 그냥 통과시켰다'
    assert f.step == 'PAUSED'

    sig.raise_('resume')
    assert done.wait(TIMEOUT_S), 'resume 을 눌렀는데 용기를 끝까지 처리하지 않았다'
    assert out == ['go_on'] and f.done_bowl == 1


# ────────────────────────────────── 재시도 중 코드가 바뀐 경우 (감사 결함 B)
class PauseWatcher(AutoResume):
    """PAUSED 를 몇 번 거쳤는지 세는 시험용 깃발 (resume 은 AutoResume 처럼 눌러 준다)."""

    def __init__(self):
        super().__init__()
        self.resumes = 0

    def take(self, name):
        if name == 'resume':
            self.resumes += 1
        return super().take(name)


def test_new_code_in_retry_uses_new_policy():
    """🚨 재시도에서 **다른 코드**로 실패하면 그 코드의 정책으로 마무리한다.

    1차 RACK_JAM(retry:1->isolate) → 재시도에서 기능 함수가 예외를 던져 ROBOT_ERROR.
    첫 실패 코드로 정한 옛 정책(isolate)을 그대로 쓰면 params.yaml 의 ROBOT_ERROR: pause 를
    무시하고 격리해 버린다 — 로봇 위치를 모르는 채 격리함까지 이송하게 된다.
    SDD §7 은 ROBOT_ERROR 를 "그 자리 정지 → PAUSED + 알림, 사람이 복구" 로 못 박는다.
    """
    mock.configure(['rack_place:RACK_JAM'])          # 1차는 RACK_JAM 으로 실패
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def rack_place(rack_slot, kind):
        tries.append(rack_slot)
        if len(tries) > 1:                           # 재시도에서 드라이버가 터진다 → ROBOT_ERROR
            raise RuntimeError('드라이버 응답 없음')
        return mods['f1'].rack_place(rack_slot, kind)

    f1 = types.SimpleNamespace(**{n: getattr(mods['f1'], n)
                                  for n in dir(F1Api) if not n.startswith('_')})
    f1.rack_place = rack_place

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': f1, 'f2': mods['f2'], 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = PauseWatcher()
    f.run_plan(sig)

    assert len(tries) == 2, f'재시도 정책(retry:1)을 안 탔다 (시도 {len(tries)}회)'
    assert f.last_code == 'ROBOT_ERROR'
    assert f.isolated == 0, 'ROBOT_ERROR 를 격리로 처리하면 안 된다 — 로봇 위치를 모른다'
    assert sig.resumes >= 1, 'ROBOT_ERROR 인데 PAUSED 를 거치지 않았다 (SDD §7)'
    # 9/20 PM 결정: ROBOT_ERROR 로 멈춘 용기**만** ERROR 로 기록한다
    # (GRIP_FAIL·RACK_FULL 은 재개하면 마저 해서 DONE 이 된다 — 아래 시험)
    assert [e['result'] for e in events] == ['ERROR'], 'ROBOT_ERROR 로 멈춘 용기는 ERROR 로 남는다'


def test_resume_redoes_the_failed_step():
    """🚨 GRIP_FAIL 로 멈춘 뒤 재개하면 **실패한 그 단계부터 다시** 한다 (IRD §8 · 9/20 결정 E12).

    전에는 재개해도 GO_ON(다음 용기)이라 **그 용기를 버렸다** — 사람이 가서 다시 쥐여 줬는데도
    버리는 셈이라, 재개 버튼과 중단 버튼이 똑같이 동작했다.
    """
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def dip(station, count, kind):
        tries.append(station)
        if len(tries) == 1:                          # 첫 담금에서 미끄러짐
            return Result.fail(GRIP_FAIL)
        return mods['f2'].dip(station, count, kind)

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.dip = dip

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes >= 1, 'GRIP_FAIL 인데 PAUSED 를 거치지 않았다 (E12)'
    assert len(tries) == 2, f'재개 뒤 같은 단계를 다시 하지 않았다 (dip {len(tries)}회)'
    assert f.isolated == 0, 'GRIP_FAIL 은 격리가 아니다 — 놓친 용기는 손에 없을 수 있다 (E12)'
    assert [e['result'] for e in events] == ['DONE'], '마저 해서 끝났으면 DONE 이다'


def test_tool_lost_repicks_before_retrying_step(monkeypatch):
    """🆕 E37 — TOOL_LOST 로 멈추면 재개 전에 f1.tool(PICK) 을 다시 부른 뒤 실패한 단계부터 다시.

    GRIP_FAIL 과 달리 손에 아무것도 없는 게 아니라 **툴을 놓친** 것이라, 그냥 다시 하면
    빈손으로 닦으려 든다 — 재개 전에 반드시 다시 집어야 한다(handle_failure).
    """
    monkeypatch.setattr(flow_module.cc, 'start_nudge_watch', lambda: None)
    monkeypatch.setattr(flow_module.cc, 'check_nudge', lambda *a: False)   # 여기선 HMI 재개(AutoResume)만 본다

    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    wipe_tries = []
    tool_calls = []

    def wipe_bowl():
        wipe_tries.append(1)
        if len(wipe_tries) == 1:                     # 첫 번째 닦기 중 놓침
            return Result.fail(TOOL_LOST)
        return mods['f3'].wipe_bowl()

    def tool(tool_id, action):
        tool_calls.append((tool_id, action))
        return mods['f1'].tool(tool_id, action)

    f3 = types.SimpleNamespace(**{n: getattr(mods['f3'], n) for n in dir(F3Api) if not n.startswith('_')})
    f3.wipe_bowl = wipe_bowl
    f1 = types.SimpleNamespace(**{n: getattr(mods['f1'], n) for n in dir(F1Api) if not n.startswith('_')})
    f1.tool = tool

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': f1, 'f2': mods['f2'], 'f3': f3}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes >= 1, 'TOOL_LOST 인데 PAUSED 를 거치지 않았다'
    assert len(wipe_tries) == 2, f'재개 뒤 같은 단계(wipe_bowl)를 다시 하지 않았다 ({len(wipe_tries)}회)'
    pick_calls = [c for c in tool_calls if c[1] == PICK]
    assert len(pick_calls) == 2, f'놓친 뒤 재PICK 을 안 했다 (tool PICK {len(pick_calls)}회 — 원래 1 + 재PICK 1 = 2)'
    assert f.isolated == 0, 'TOOL_LOST 는 격리가 아니다'
    assert [e['result'] for e in events] == ['DONE'], '마저 해서 끝났으면 DONE 이다'


def test_resume_after_robot_error_goes_to_next_container():
    """🚨 ROBOT_ERROR 만은 재개해도 **그 단계를 다시 하지 않는다** (IRD §8 · SDD §7).

    로봇이 어디 있는지 모르는 채 같은 동작을 다시 하면 위험하다 → 다음 용기부터, 그 용기는 ERROR.
    """
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def dip(station, count, kind):
        tries.append(station)
        raise RuntimeError('드라이버 응답 없음')       # 기능 함수에서 샌 예외 → ROBOT_ERROR

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.dip = dip

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    f.run_plan(PauseWatcher())

    assert len(tries) == 1, 'ROBOT_ERROR 인데 같은 단계를 다시 했다 — 위험하다'
    assert [e['result'] for e in events] == ['ERROR']
    assert f.isolated == 0, 'ROBOT_ERROR 를 격리로 옮기면 안 된다'


# ────────────────────────────────── 후퇴하면 안 되는 실패 (9/21 PM 요청 · SDD §7)
def _flow_with(retreats, force_offs, no_retreat, fail_with):
    """f2.leftover_loop 이 주어진 예외를 던지는 Flow 를 만든다."""
    mods = load_features(['f1', 'f2', 'f3'])

    def leftover_loop(kind, max_rounds):
        raise fail_with('이동이 도중에 섰다')

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.leftover_loop = leftover_loop
    f = Flow(CFG, Quiet(),
             safe_retreat=lambda: retreats.append(1),
             force_off=lambda: force_offs.append(1),
             no_retreat_errors=no_retreat)
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]
    return f


def test_move_incomplete_does_not_retreat():
    """🚨 이동이 도중에 서면(MoveIncomplete) **후퇴하지 않는다.**

    로봇이 어디 있는지 모르는데 Z 를 올리는 후퇴를 하면 더 꼬인다
    (9/21 08:40 케이블 꼬임과 같은 길) → 힘·순응만 끄고 사람이 확인한다.
    """
    from cobot_common.motion import MoveIncomplete
    retreats, force_offs = [], []
    f = _flow_with(retreats, force_offs, (MoveIncomplete,), MoveIncomplete)
    before_signal = []

    class Sig(PauseWatcher):                        # 사람이 첫 신호(재개·넛지)를 주는 순간까지의 후퇴 횟수를 찍는다
        def take(self, name):
            v = super().take(name)
            if name == 'resume' and v and not before_signal:
                before_signal.append(len(retreats))
            return v

    f.run_plan(Sig())

    assert before_signal == [0], '위치를 모르는데 사람 신호 **전에** 후퇴했다'
    assert force_offs, '힘·순응은 꺼야 한다'
    # 🆕 E52(황인재 9/25): 사람이 확인하고 신호를 준 **뒤**에는 곧게 위로 → HOME 으로 출발점을 만든다(다음 PICK 이 아무 자리에서 출발하지 않게)
    assert len(retreats) == 1, f'사람 신호 뒤 HOME 출발 전에 한 번 후퇴해야 한다 ({len(retreats)}회)'
    assert f.last_code == 'ROBOT_ERROR'


def test_other_errors_still_retreat():
    """🚨 반대쪽 — 힘 상한처럼 **접촉에서 벗어나야 하는** 실패는 설계대로 후퇴한다."""
    retreats, force_offs = [], []
    f = _flow_with(retreats, force_offs, (), RuntimeError)
    f.run_plan(PauseWatcher())

    assert retreats, '후퇴했어야 한다'
    assert f.last_code == 'ROBOT_ERROR'


# ────────────────────────────────── FLOW-03 중단(/flow/abort) · 결정 E11
class AutoAbort(Signals):
    """시험용 — PAUSED 가 되면 재개 대신 **중단**을 누른다."""

    def take(self, name):
        if name == 'abort':
            return True
        return super().take(name)


def _flow_for_abort(calls, fail_on=('leftover_loop:LEFTOVER_REMAIN',)):
    """LEFTOVER_REMAIN(정책 isolate)을 pause 로 바꿔 PAUSED 를 만들고, 거기서 중단을 누른다."""
    mock.configure(list(fail_on))
    mods = load_features(['f1', 'f2', 'f3'])

    def spy(name, fn):
        def wrapped(*a):
            calls.append((name, a))
            return fn(*a)
        return wrapped

    f1 = types.SimpleNamespace(**{n: spy(n, getattr(mods['f1'], n))
                                  for n in dir(F1Api) if not n.startswith('_')})
    cfg = {'flow': dict(CFG['flow'])}
    cfg['flow']['policy'] = dict(CFG['flow']['policy'], LEFTOVER_REMAIN='pause')
    events = []
    f = Flow(cfg, Quiet(), publish_event=events.append)
    f.f = {'f1': f1, 'f2': mods['f2'], 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]
    return f, events


def test_abort_cleans_up_in_the_decided_order():
    """🚨 중단 정리 순서 = **HOME 먼저** → 툴 반납 → 격리 → HOME (IRD §6 · 결정 E11).

    HOME 이 먼저인 이유: E7 로 이동에서 안전 높이 경유가 없어져 **지금 자리에서 다음 자리로
    곧장** 간다. 중단은 아무 때나 눌리므로 티칭 경로의 출발점에서 시작해야 한다.
    """
    calls = []
    f, events = _flow_for_abort(calls)
    f.run_plan(AutoAbort())

    order = [(n, a) for n, a in calls if n in ('move_to', 'place', 'tool')]
    tail = order[-3:]
    assert tail[0] == ('move_to', ('HOME', True)), f'HOME 이 맨 먼저여야 한다 — {tail}'
    assert tail[1] == ('place', ('ISOLATE', 'BOWL')), f'격리 구역에 놓아야 한다 — {tail}'
    assert tail[2] == ('move_to', ('HOME', False)), f'HOME 으로 끝나야 한다 — {tail}'
    assert f.isolated == 1
    assert [e['result'] for e in events] == ['ISOLATED'], '중단한 용기는 ISOLATED 로 남는다'


def test_abort_returns_the_tool_it_was_holding():
    """🚨 툴을 쥔 채 중단하면 **반납**하고 간다 — 홀더에 안 돌려놓으면 다음 용기가 못 쓴다."""
    calls = []
    f, events = _flow_for_abort(calls, fail_on=['wipe_bowl:FORCE_LIMIT'])
    f.policy['FORCE_LIMIT'] = 'pause'                # 툴을 쥔 단계에서 멈추게
    f.run_plan(AutoAbort())

    tools = [a for n, a in calls if n == 'tool']
    assert ('SPONGE', 'RETURN') in tools, f'쥔 툴을 반납하지 않았다 — {tools}'
    assert f.holding_tool is None


def test_abort_keeps_going_when_a_cleanup_step_fails():
    """🚨 치우는 중에 한 단계가 실패해도 **멈추지 않는다** — 더 나아가 치우는 편이 낫다."""
    calls = []
    f, events = _flow_for_abort(calls)
    mods = f.f
    f1 = mods['f1']
    orig = f1.place

    def place(station, kind=None):
        calls.append(('place', (station, kind)))
        return Result.fail('SEAT_FAIL')               # 격리 구역에 놓기가 실패한다

    f1.place = place
    f.run_plan(AutoAbort())

    assert ('move_to', ('HOME', False)) in calls, '놓기가 실패해도 HOME 으로는 가야 한다'
    assert [e['result'] for e in events] == ['ISOLATED']
    assert orig is not None


# ── 🚨 이동 **도중** 중단 (halt_errors 경로) — wait_resume 을 거치지 않는다 (PM 검토 PR #50)
class _Halted(RuntimeError):
    """cc.MotionHalted 대역 — 중단이 하던 이동을 끊었을 때 올라오는 예외."""


def _flow_halted_midmove(sig, n_containers=1):
    """leftover_loop 안에서 사람이 stop·abort 를 누르고 이동이 끊긴 상황을 만든다."""
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    fired = []

    def leftover_loop(kind, max_rounds):
        if not fired:                                # 첫 용기에서만 한 번
            fired.append(True)
            sig.raise_('stop')                       # /flow/stop → cc.pause()
            sig.raise_('abort')                      # /flow/abort → cc.halt()
            raise _Halted('중단으로 이동이 끊겼다')
        return mods['f2'].leftover_loop(kind, max_rounds)

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.leftover_loop = leftover_loop

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append, halt_errors=(_Halted,))
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': n_containers}]
    return f, events


def test_abort_midmove_clears_the_flags():
    """🚨 이동 도중 중단은 wait_resume 을 **안 거친다** → abort_container 가 깃발을 내려야 한다.

    안 내리면 stop·abort 가 남아 다음 용기·다음 실행까지 따라간다(PM 검토 PR #50).
    """
    sig = AutoResume()
    f, events = _flow_halted_midmove(sig, n_containers=2)
    f.run_plan(sig)

    assert [e['result'] for e in events] == ['ISOLATED', 'DONE'], \
        '첫 용기는 중단으로 격리, 둘째 용기는 정상이어야 한다'
    assert (sig.peek('stop'), sig.peek('abort')) == (False, False), \
        f"깃발이 남았다 — stop={sig.peek('stop')} abort={sig.peek('abort')}"


def test_abort_retreats_before_going_home():
    """🚨 중단은 **수조 안**(헹굼 구간)에서도 눌린다 → HOME 으로 가기 전에 곧게 올라와야 한다.

    9/22 17:27 실기: 수조 안 자세(z −13.6)에서 HOME 으로 간 관절 이동이 테이블을 가로질러
    그리퍼가 상판을 쓸었다 → 비상정지 · 툴 전원이 끊겨 그리퍼 드라이버까지 죽었다.
    """
    order = []
    sig = AutoResume()
    f, _ = _flow_halted_midmove(sig, n_containers=1)
    f._safe_retreat = lambda: order.append('safe_retreat')
    real_move_to = f.f['f1'].move_to

    def move_to(station, carrying, kind=None):
        order.append(f'move_to:{station}')
        return real_move_to(station, carrying, kind)

    f.f['f1'] = types.SimpleNamespace(**{n: getattr(f.f['f1'], n) for n in dir(F1Api) if not n.startswith('_')})
    f.f['f1'].move_to = move_to
    f.abort_container(sig)

    assert order and order[0] == 'safe_retreat', f'HOME 보다 후퇴가 먼저여야 한다: {order}'
    assert order[1] == 'move_to:HOME'


def test_leftover_abort_flag_does_not_fire_next_run():
    """🚨 마지막 용기에서 중단하면 소비해 줄 다음 용기가 없다 → 깃발이 **다음 실행**까지 남는다.

    그러면 다음 실행에서 GRIP_FAIL(정책 pause — E12 "멈추고 사람이 확인")이 나는 순간
    **사람이 아무것도 안 눌렀는데** 중단 정리가 돌아 로봇이 HOME → 격리 → HOME 으로 움직인다.
    """
    sig = AutoResume()
    f1st, _ = _flow_halted_midmove(sig, n_containers=1)   # 마지막 용기에서 중단
    f1st.run_plan(sig)
    assert (sig.peek('stop'), sig.peek('abort')) == (False, False), '실행이 끝났는데 깃발이 남았다'

    # 2회차 — GRIP_FAIL 로 멈추면 **사람을 기다려야** 한다(중단 정리가 돌면 안 된다)
    #    🚨 GRIP_FAIL 은 pause → 재개하면 **그 단계부터 다시** 다(E12·IRD §8).
    #       그래서 계속 실패하게 두면 시험이 무한히 돈다 → **첫 번째만** 실패시킨다.
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    once = []

    def shake(mode, count, kind):
        if not once:
            once.append(True)
            return Result.fail(GRIP_FAIL)
        return mods['f2'].shake(mode, count, kind)

    f2fake = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                      for n in dir(F2Api) if not n.startswith('_')})
    f2fake.shake = shake

    events = []
    cfg = {'flow': dict(CFG['flow'])}
    cfg['flow']['policy'] = dict(CFG['flow']['policy'], GRIP_FAIL='pause')
    f2nd = Flow(cfg, Quiet(), publish_event=events.append)
    f2nd.f = {'f1': mods['f1'], 'f2': f2fake, 'f3': mods['f3']}
    f2nd.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    watcher = PauseWatcher()
    f2nd.run_plan(watcher)
    assert watcher.resumes >= 1, 'GRIP_FAIL 인데 PAUSED 를 거치지 않았다 — 중단 깃발이 살아 있었다'
    assert f2nd.isolated == 0, '사람이 안 눌렀는데 중단 정리가 돌았다'


# ────────────────────────────────────────────── 예외 주입 (TC-10 · UT-FLOW ③)
def test_boom_injects_a_real_exception():
    """🚨 코드 BOOM 은 Result 가 아니라 **예외**를 던진다.

    왜 필요한가: 실패 **코드**만 주입해서는 "기능 함수가 터지는 길" 을 한 번도 안 지난다 —
    코드는 함수가 스스로 돌려준 것이라 이미 정상 경로다. flow 가 예외를 ROBOT_ERROR 로
    바꿔 PAUSED 로 가는지는 진짜 예외로만 확인된다(SDD §9.3 TC-10).
    """
    mock.configure(['soap:BOOM'])
    with pytest.raises(RuntimeError):
        mock.code_for('soap')
    assert mock.code_for('wipe_bowl') is None      # 다른 함수는 멀쩡하다


def test_boom_becomes_robot_error_and_pauses():
    """터진 뒤 flow 는 ROBOT_ERROR 로 바꾸고 멈춘다 (params.yaml ROBOT_ERROR: pause)."""
    results, f = run(['soap:BOOM'])
    assert f.last_code == 'ROBOT_ERROR'
    assert results and all(r == 'ERROR' for r in results), results


def test_boom_with_count_only_throws_that_many_times():
    """횟수를 주면 그만큼만 터진다 — 재시도로 회복되는 길도 볼 수 있다."""
    mock.configure(['soap:BOOM:1'])
    with pytest.raises(RuntimeError):
        mock.code_for('soap')
    assert mock.code_for('soap') is None


# ────────────────────────────────── 🆕 FLOW-05 (결정 E25) — 컵은 무게 단계를 건너뛴다
def _calls_by_kind(cfg_extra):
    """가짜 기능으로 plan 한 바퀴 돌며 (종류, step, 함수) 를 모은다."""
    import copy
    mock.configure([])
    cfg = copy.deepcopy(CFG)
    cfg['flow'].update(cfg_extra)
    f = Flow(cfg, Quiet(), publish_event=lambda ev: None)
    f.f = load_features(['f1', 'f2', 'f3'])
    seen = []
    orig = f.call_fn

    def spy(mod, fname, *a):
        seen.append((f.kind, f.step, fname))
        return orig(mod, fname, *a)
    f.call_fn = spy
    f.run_plan(AutoResume())
    return seen, f


def test_flow05_cup_skips_weigh_bowl_keeps_it():
    """E25: 컵은 move_to('WEIGH') · leftover_loop 를 **한 번도** 부르지 않고 PICK → SEAT. 그릇은 예전 그대로."""
    seen, f = _calls_by_kind({'weigh_kinds': ['BOWL']})
    cup = [(st, fn) for k, st, fn in seen if k == 'CUP']
    bowl = [(st, fn) for k, st, fn in seen if k == 'BOWL']
    assert not [x for x in cup if x[0] == 'WEIGH'], f'컵이 WEIGH 를 거쳤다: {cup}'
    assert ('WEIGH', 'leftover_loop') not in cup and ('WEIGH', 'move_to') not in cup
    assert cup[:2] == [('PICK', 'pick'), ('SEAT', 'place')], cup[:3]       # PICK 다음이 곧장 SEAT
    assert ('WEIGH', 'leftover_loop') in bowl and ('WEIGH', 'move_to') not in bowl   # 🔄 9/23: WEIGH 이동 단계는 뺐다(weigh 가 HOME 경유로 스스로 감)
    assert (f.done_bowl, f.done_cup, f.isolated) == (2, 2, 0)              # 나머지 단계는 다 돈다
    assert len(bowl) == 12 * 2 and len(cup) == 11 * 2                    # 🔄 9/23 그릇 12(WEIGH 이동 제거) · 컵 11(WEIGH 전부 생략)


def test_flow05_missing_key_keeps_old_behaviour():
    """키가 없으면 예전처럼 둘 다 잰다 — 옛 설정 파일로도 돌아간다."""
    seen, _ = _calls_by_kind({})
    assert ('CUP', 'WEIGH', 'leftover_loop') in seen


def test_flow05_unknown_kind_is_ignored_with_warning():
    log = FakeLogLines()
    f = Flow({'flow': {'weigh_kinds': ['BOWL', 'PLATE']}}, log)
    assert f.weigh_kinds == ['BOWL']
    assert any('PLATE' in m for m in log.warns)


class FakeLogLines:
    def __init__(self): self.warns = []
    def info(self, m): pass
    def warn(self, m): self.warns.append(m)
    def error(self, m): pass



def test_empty_zone_home_failure_pauses_then_resumes_and_retries():
    """마지막 EMPTY_ZONE 뒤 HOME 실패 시 PAUSED에서 resume을 기다리고 HOME을 다시 시도한다."""
    import copy

    mock.configure([
        'pick:EMPTY_ZONE',
        'move_to:ROBOT_ERROR:1',
    ])

    try:
        f = Flow(copy.deepcopy(CFG), Quiet(), publish_event=lambda ev: None)
        f.f = load_features(['f1', 'f2', 'f3'])

        home_results = []
        paused_reasons = []

        orig_call = f.call_fn
        orig_paused = f.to_paused

        def spy_call(mod, fname, *args):
            r = orig_call(mod, fname, *args)
            if mod == 'f1' and fname == 'move_to' and args[:2] == ('HOME', False):
                home_results.append(r)
            return r

        def spy_paused(reason, sig):
            paused_reasons.append(reason)
            return orig_paused(reason, sig)

        f.call_fn = spy_call
        f.to_paused = spy_paused

        f.run_plan(AutoResume())

        assert len(home_results) == 2
        assert not home_results[0].ok
        assert home_results[0].code == 'ROBOT_ERROR'
        assert home_results[1].ok
        assert paused_reasons == [
            'EMPTY_ZONE 후 HOME 복귀 실패 (ROBOT_ERROR)'
        ]
        assert f.message == '처리 대상 없음 — HOME 복귀 완료'
        assert f.step == 'IDLE'

    finally:
        mock.reset()


# ────────────────────────────────── 🆕 E52 (황인재 9/25 · 9/26 구현) — 로봇 오류 2단 신호 · 격리 정리 통일 · 툴 집기 실패는 멈춤
def _spy_f1(mods, calls):
    """f1 의 모든 함수를 감싸 (이름, 인자) 를 calls 에 남긴다."""
    def spy(name, fn):
        def wrapped(*a):
            calls.append((name, a))
            return fn(*a)
        return wrapped
    return types.SimpleNamespace(**{n: spy(n, getattr(mods['f1'], n)) for n in dir(F1Api) if not n.startswith('_')})


def _one_bowl(f1=None, f2=None, f3=None, policy=None):
    mods = load_features(['f1', 'f2', 'f3'])
    cfg = {'flow': dict(CFG['flow'])}
    if policy:
        cfg['flow']['policy'] = dict(CFG['flow']['policy'], **policy)
    events = []
    f = Flow(cfg, Quiet(), publish_event=events.append)
    f.f = {'f1': f1 or mods['f1'], 'f2': f2 or mods['f2'], 'f3': f3 or mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]
    return f, events, mods


def _ns(api, mod):
    return types.SimpleNamespace(**{n: getattr(mod, n) for n in dir(api) if not n.startswith('_')})


def test_robot_error_while_holding_opens_gripper_then_waits_for_second_signal(monkeypatch):
    """로봇 오류 + 쥔 것 있음 → 신호 1: **그리퍼만** 열림(팔은 안 움직임) → 사람이 받음 → 신호 2: 곧게 위로 → HOME → ERROR → 다음 용기.

    황인재 9/25: 로봇이 제 위치를 모를 수 있으니 격리 구역으로 옮기지 않고 사람이 받아 처리한다.
    """
    released, watches = [], []
    monkeypatch.setattr(flow_module.cc, 'release', lambda: released.append(1))
    monkeypatch.setattr(flow_module.cc, 'start_nudge_watch', lambda: watches.append(1))   # 넛지 감시를 켠 횟수 = 넛지를 받은 대기 횟수
    monkeypatch.setattr(flow_module.cc, 'check_nudge', lambda *a: False)
    mods = load_features(['f1', 'f2', 'f3'])
    calls = []
    f1 = _spy_f1(mods, calls)
    f2 = _ns(F2Api, mods['f2'])

    def dip(station, count, kind):
        raise RuntimeError('드라이버 응답 없음')               # 헹굼 담금 — 용기를 쥔 채 터진다
    f2.dip = dip
    at_signal = []

    class Sig(PauseWatcher):
        def take(self, name):
            v = super().take(name)
            if name == 'resume' and v:
                at_signal.append((len(released), [c for c in calls if c == ('move_to', ('HOME', False))]))
            return v

    f, events, _ = _one_bowl(f1=f1, f2=f2)
    sig = Sig()
    f.run_plan(sig)

    assert sig.resumes == 2, f'쥔 것이 있으면 사람 신호가 2번이어야 한다 ({sig.resumes}번)'
    assert released == [1], f'그리퍼를 한 번만 열어야 한다 ({len(released)}번)'
    assert at_signal[0][0] == 0, '첫 신호 **전에** 그리퍼를 열면 안 된다'
    assert at_signal[1][0] == 1 and at_signal[1][1] == [], '둘째 신호 전에는 그리퍼만 열려 있고 팔은 안 움직여야 한다'
    assert calls.count(('move_to', ('HOME', False))) == 1, '둘째 신호 뒤 HOME 으로 가야 한다'
    assert [(e['result'], e['code']) for e in events] == [('ERROR', 'ROBOT_ERROR')]
    assert f.isolated == 0 and f.holding is None and f.holding_tool is None
    assert watches == [1], f'넛지는 첫 신호에만 — 둘째 신호(받은 뒤)는 재개 버튼만 받아야 한다(황인재 9/27 · 팔이 바로 움직임) ({len(watches)}회)'


def test_robot_error_with_empty_hand_needs_one_signal_and_mentions_the_bed(monkeypatch):
    """로봇 오류 + 빈손(용기는 스펀지 홈에) → 신호 1번 → HOME → ERROR. 그리퍼는 열지 않고, 안내에 홈 위 용기를 꺼내라고 적는다."""
    released = []
    monkeypatch.setattr(flow_module.cc, 'release', lambda: released.append(1))
    mods = load_features(['f1', 'f2', 'f3'])
    calls = []
    f1 = _spy_f1(mods, calls)

    def tool(tool_id, action):
        raise RuntimeError('툴 집기 중 드라이버 응답 없음')     # SEAT 뒤 · 빈손 · 용기는 홈에
    f1.tool = tool

    f, events, _ = _one_bowl(f1=f1)
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 1, f'빈손이면 신호 1번이어야 한다 ({sig.resumes}번)'
    assert released == [], '빈손인데 그리퍼를 열었다'
    assert '스펀지 홈' in f.message, f'홈 위 용기를 꺼내라는 안내가 없다: {f.message}'
    assert calls.count(('move_to', ('HOME', False))) == 1
    assert [(e['result'], e['code']) for e in events] == [('ERROR', 'ROBOT_ERROR')]


def test_robot_error_mid_pick_uses_gripper_width_when_record_says_empty(monkeypatch):
    """집는 **도중** 오류 — 기록은 빈손(pick 이 끝나지 않았다)인데 그리퍼는 이미 닫혀 있다(옆면 70.3) → 2단 신호로 그리퍼를 열어 받게 한다.

    9/27 황인재 질문(컵을 옆으로 잡았을 때도 처리되나) 에서 찾은 빈틈: 폭으로 한 번 더 본다.
    """
    released = []
    monkeypatch.setattr(flow_module.cc, 'release', lambda: released.append(1))
    monkeypatch.setattr(flow_module.cc, 'grip_width', lambda: 70.3)          # 옆면 재파지 폭 — 열림 기준 100 보다 작다
    mods = load_features(['f1', 'f2', 'f3'])
    calls = []
    f1 = _spy_f1(mods, calls)
    picks = []

    def pick(zone, kind):
        picks.append(zone)
        if zone == 'SPONGE_BED_B':                     # 홈에서 다시 집다가(닫은 뒤) 보호정지
            raise RuntimeError('이동이 도중에 섰다')
        return mods['f1'].pick(zone, kind)
    f1.pick = pick

    f, events, _ = _one_bowl(f1=f1)
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 2, f'그리퍼가 닫혀 있으면 기록이 빈손이라도 신호 2번이어야 한다 ({sig.resumes})'
    assert released == [1]
    assert '무언가' in f.message or '용기' in f.message
    assert [(e['result'], e['code']) for e in events] == [('ERROR', 'ROBOT_ERROR')]


def test_robot_error_open_gripper_is_treated_as_empty(monkeypatch):
    """그리퍼가 활짝 열려 있으면(110 > 100) 폭 검사도 빈손 → 신호 1번."""
    released = []
    monkeypatch.setattr(flow_module.cc, 'release', lambda: released.append(1))
    monkeypatch.setattr(flow_module.cc, 'grip_width', lambda: 110.6)
    mods = load_features(['f1', 'f2', 'f3'])
    f1 = _ns(F1Api, mods['f1'])

    def tool(tool_id, action):
        raise RuntimeError('툴 집기 중 드라이버 응답 없음')
    f1.tool = tool
    f, events, _ = _one_bowl(f1=f1)
    sig = PauseWatcher()
    f.run_plan(sig)
    assert sig.resumes == 1 and released == []
    assert [e['result'] for e in events] == ['ERROR']


def test_leftover_remain_isolates_physically_via_home():
    """잔반 남음(정책 isolate) → 멈추지 않고 곧게 위로 → HOME → 격리 → HOME. 용기를 든 채라 홈에서 다시 집지 않는다. 기록 코드는 원인."""
    mock.configure(['leftover_loop:LEFTOVER_REMAIN'])
    mods = load_features(['f1', 'f2', 'f3'])
    calls = []
    f1 = _spy_f1(mods, calls)
    f, events, _ = _one_bowl(f1=f1)
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 0, '잔반 남음은 사람을 부르지 않는다(E52 · isolate)'
    seq = [(n, a) for n, a in calls if n in ('move_to', 'place', 'pick', 'tool')]
    assert seq[-3:] == [('move_to', ('HOME', True)), ('place', ('ISOLATE', 'BOWL')), ('move_to', ('HOME', False))], seq
    assert ('pick', ('SPONGE_BED_B', 'BOWL')) not in seq, '용기를 든 채인데 홈에서 다시 집었다'
    assert [(e['result'], e['code']) for e in events] == [('ISOLATED', 'LEFTOVER_REMAIN')]


def test_force_limit_exhausted_returns_tool_regrips_from_bed_and_isolates():
    """힘 상한(retry:1->isolate) 소진 → 툴 반납 → **스펀지 홈에서 용기 다시 집기** → HOME → 격리 → HOME. 사람 없이. 기록 코드 FORCE_LIMIT."""
    mock.configure(['wipe_bowl:FORCE_LIMIT'])
    mods = load_features(['f1', 'f2', 'f3'])
    calls = []
    f1 = _spy_f1(mods, calls)
    f, events, _ = _one_bowl(f1=f1)
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 0
    seq = [(n, a) for n, a in calls if n in ('move_to', 'place', 'pick', 'tool')]
    i = seq.index(('tool', ('SPONGE', 'RETURN')))
    assert seq[i:] == [('tool', ('SPONGE', 'RETURN')), ('pick', ('SPONGE_BED_B', 'BOWL')), ('move_to', ('HOME', True)),
                       ('place', ('ISOLATE', 'BOWL')), ('move_to', ('HOME', False))], seq[i:]
    assert [(e['result'], e['code']) for e in events] == [('ISOLATED', 'FORCE_LIMIT')]
    assert f.isolated == 1 and f.holding is None and f.on_bed is False


def test_tool_fail_pauses_and_retries_tool_pick_without_isolation():
    """툴 집기 실패(정책 pause) → 멈춤(안내: 홀더 확인 → 넛지) → 재개 → **툴 집기부터 다시** → DONE. 격리 X."""
    mods = load_features(['f1', 'f2', 'f3'])
    tool_calls = []
    f1 = _ns(F1Api, mods['f1'])

    def tool(tool_id, action):
        tool_calls.append((tool_id, action))
        if action == PICK and sum(1 for c in tool_calls if c[1] == PICK) == 1:
            return Result.fail('TOOL_FAIL')
        return mods['f1'].tool(tool_id, action)
    f1.tool = tool

    f, events, _ = _one_bowl(f1=f1, policy={'TOOL_FAIL': 'pause'})
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 1
    assert sum(1 for c in tool_calls if c[1] == PICK) == 2, tool_calls
    assert f.isolated == 0 and [e['result'] for e in events] == ['DONE']
    assert '홀더' in f.message, f'홀더를 확인하라는 안내가 없다: {f.message}'


def test_tool_lost_repick_failure_pauses_again_instead_of_isolating(monkeypatch):
    """툴 놓침 → 재PICK 실패 → (전엔 TOOL_FAIL 정책으로 격리) 이제는 **다시 멈춰** 사람을 부르고, 다음 신호에 또 집는다 → DONE."""
    mods = load_features(['f1', 'f2', 'f3'])
    wipe_tries, tool_calls = [], []
    f3 = _ns(F3Api, mods['f3'])
    f1 = _ns(F1Api, mods['f1'])

    def wipe_bowl():
        wipe_tries.append(1)
        return Result.fail(TOOL_LOST) if len(wipe_tries) == 1 else mods['f3'].wipe_bowl()

    def tool(tool_id, action):
        tool_calls.append((tool_id, action))
        if action == PICK and sum(1 for c in tool_calls if c[1] == PICK) == 2:   # 재PICK 첫 시도 — 홀더에 잘못 꽂혔다
            return Result.fail('TOOL_FAIL')
        return mods['f1'].tool(tool_id, action)
    f3.wipe_bowl, f1.tool = wipe_bowl, tool

    f, events, _ = _one_bowl(f1=f1, f3=f3)
    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes == 2, f'놓침 멈춤 1 + 재PICK 실패 멈춤 1 = 2 ({sig.resumes})'
    assert sum(1 for c in tool_calls if c[1] == PICK) == 3, tool_calls
    assert len(wipe_tries) == 2 and f.isolated == 0
    assert [e['result'] for e in events] == ['DONE']
