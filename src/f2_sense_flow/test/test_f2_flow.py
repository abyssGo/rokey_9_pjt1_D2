"""flow(두뇌) 시험 — 🚨 로봇·브링업·ROS 없이 돈다.

flow.py 가 ROS 를 import 하지 않게 나눠 둔 덕분이다(SDD 산출물 분리).
TC-10(실패 정책)의 바탕이 된다.
"""
import pytest

from cobot_api import (EMPTY_ZONE, FORCE_LIMIT, OK, RACK_FULL, ROBOT_ERROR, SEAT_FAIL,
                       TIMEOUT, Result)
from f2_sense_flow.flow import ISOLATE, NEXT_ZONE, PAUSE, RETRY, Flow, Signals


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


CFG = {'flow': {
    'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2},
             {'zone': 'RET_C', 'kind': 'CUP', 'count': 2}],
    'policy': {'EMPTY_ZONE': 'next_zone', 'SEAT_FAIL': 'isolate', 'RACK_FULL': 'pause',
               'FORCE_LIMIT': 'retry:1->isolate', 'TIMEOUT': 'retry:3->isolate'},
    'step_delay_s': 0.0,
    'done_hold_s': 0.0,     # 시험에서는 기다리지 않는다
}}


@pytest.fixture
def flow():
    return Flow(CFG, FakeLog())


# ────────────────────────────────── 실패 정책
def test_policy_from_yaml(flow):
    assert flow.policy_for(EMPTY_ZONE) == (NEXT_ZONE, 0)
    assert flow.policy_for(SEAT_FAIL) == (ISOLATE, 0)
    assert flow.policy_for(RACK_FULL) == (PAUSE, 0)


def test_retry_policy_parses_count(flow):
    """params.yaml 형식 "retry:N->isolate" 를 (RETRY, N) 으로 읽는다 (SDD §4.3)."""
    assert flow.policy_for(FORCE_LIMIT) == (RETRY, 1)
    assert flow.policy_for(TIMEOUT) == (RETRY, 3)


def test_unknown_code_is_pause(flow):
    """모르는 코드는 **안전하게 멈춘다**. 조용히 넘어가면 안 된다."""
    assert flow.policy_for('아무거나') == (PAUSE, 0)
    assert any('pause' in m for _, m in flow.log.lines)


def test_bad_policy_value_is_pause():
    """오타·형식 오류도 멈춘다. retry 형식이 살짝 틀려도 그냥 넘어가면 안 된다."""
    for bad in ('오타난값', 'retry:1', 'retry->isolate', 'retry:x->isolate'):
        f = Flow({'flow': {'policy': {'SEAT_FAIL': bad}}}, FakeLog())
        assert f.policy_for(SEAT_FAIL) == (PAUSE, 0), bad


# ────────────────────────────────── 예외 보호 (SDD §5.1)
def test_call_returns_result_on_success(flow):
    r = flow.call(lambda: Result())
    assert r.ok and r.code == OK and flow.last_code == OK


def test_call_converts_exception_to_result(flow):
    """예외가 나도 None 이 아니라 Result.fail(ROBOT_ERROR) 를 돌려준다."""
    retreated = []
    f = Flow(CFG, FakeLog(), safe_retreat=lambda: retreated.append(1))

    def 터지는함수():
        raise RuntimeError('드라이버 응답 없음')

    r = f.call(터지는함수)
    assert r is not None                       # 🚨 None 이면 호출부가 매번 분기해야 한다
    assert not r.ok and r.code == ROBOT_ERROR
    assert retreated == [1]                    # 안전 자세로 물러났다
    assert '터지는함수' in f.message


def test_call_does_not_crash_the_cell(flow):
    """함수 하나의 예외가 셀 전체를 멈추면 안 된다 — 다음 호출이 정상이어야 한다."""
    flow.call(lambda: 1 / 0)
    assert flow.call(lambda: Result()).ok


# ────────────────────────────────── 🚨 바깥 호출이 터져도 셀이 죽지 않는다
# 코드 검토에서 실제로 죽는 것이 확인된 결함이다 (flow_node 가 exit 1 로 종료).
# cobot_common.safe_retreat 는 지금 NotImplementedError 뼈대라 **실제로 터진다.**

def _boom(*a):
    raise NotImplementedError('아직 구현 전이다')


def test_retreat_failure_does_not_escape():
    """기능 함수도 후퇴도 둘 다 터져도 call() 밖으로 예외가 새면 안 된다."""
    f = Flow(CFG, FakeLog(), safe_retreat=_boom)
    r = f.call(_boom)                       # 기능 함수가 터진다 → 후퇴도 터진다
    assert not r.ok and r.code == ROBOT_ERROR
    assert any('safe_retreat 실패' in m for _, m in f.log.lines)


def test_retreat_failure_sets_robot_error():
    """후퇴가 실패하면 '로봇 위치를 모른다'를 남긴다 — 사람이 봐야 한다."""
    f = Flow(CFG, FakeLog(), safe_retreat=_boom)
    assert f._retreat() is False
    assert f.last_code == ROBOT_ERROR and '후퇴 실패' in f.message


def test_retreat_success_returns_true():
    f = Flow(CFG, FakeLog(), safe_retreat=lambda: None)
    assert f._retreat() is True


def test_publish_event_failure_does_not_escape():
    """이벤트 발행이 터져도 공정은 계속된다 (종료 중 publish 는 실제로 터진다)."""
    f = Flow(CFG, FakeLog(), publish_event=_boom)
    f.emit_event('DONE')                    # 예외가 나면 여기서 테스트가 깨진다
    assert any('publish_event 실패' in m for _, m in f.log.lines)


def test_guard_returns_false_on_failure():
    f = Flow(CFG, FakeLog())
    assert f._guard(lambda: None, what='정상') is True
    assert f._guard(_boom, what='터짐') is False


# ────────────────────────────────── 상태
def test_snapshot_has_all_flowstate_fields(flow):
    """FlowState.msg 의 13개 필드가 빠짐없이 있어야 HMI 가 안 깨진다."""
    s = flow.snapshot()
    for k in ('step', 'kind', 'zone_id', 'done_bowl', 'done_cup', 'isolated',
              'target_bowl', 'target_cup', 'sponge_uses', 'soap_dips', 'rinse_dips',
              'last_code', 'message'):
        assert k in s


def test_targets_from_plan(flow):
    assert flow.target_bowl == 2 and flow.target_cup == 2


def test_paused_remembers_previous_step(flow):
    flow.step = 'WEIGH'
    flow.to_paused()
    assert flow.step == 'PAUSED' and flow._prev_step == 'WEIGH'


# ────────────────────────────────── 깃발
def test_signal_take_clears_once():
    sig = Signals()
    sig.raise_('start')
    assert sig.take('start') is True
    assert sig.take('start') is False          # 한 번만 반응한다


def test_signal_peek_keeps():
    sig = Signals()
    sig.raise_('stop')
    assert sig.peek('stop') and sig.peek('stop')
    sig.clear('stop')
    assert not sig.peek('stop')


# ────────────────────────────────── 🚨 보호 통로 자체가 죽지 않는가
# 그 검토 뒤 전수 점검에서 나온 것들. call() 안에도 보호 밖 코드가 있었다.

def test_call_survives_non_result_return():
    """기능 함수가 Result 가 아닌 것을 돌려줘도 call() 이 죽으면 안 된다.

    뼈대 단계에서 흔하다(return 없음 → None, 실수로 tuple·bool).
    전에는 r.code 접근이 try 밖이라 call() **자신**이 AttributeError 로 죽었다.
    """
    f = Flow(CFG, FakeLog())
    for bad in (None, (1, 2), True, 'OK'):
        r = f.call(lambda b=bad: b)
        assert isinstance(r, Result) and not r.ok and r.code == ROBOT_ERROR


def test_call_fn_survives_missing_function():
    """진짜 모듈에 함수가 아직 없어도(만들어지는 중) 크래시가 아니라 Result 여야 한다."""
    import types
    f = Flow(CFG, FakeLog())
    f.f = {'f1': types.SimpleNamespace()}          # pick 이 없는 모듈
    r = f.call_fn('f1', 'pick', 'RET_B', 'BOWL')
    assert not r.ok and r.code == ROBOT_ERROR


def test_call_fn_survives_missing_module():
    f = Flow(CFG, FakeLog())
    f.f = {}
    r = f.call_fn('f1', 'pick', 'RET_B', 'BOWL')
    assert not r.ok and r.code == ROBOT_ERROR


# ────────────────────────────────── 설정이 이상해도 생성자가 죽지 않는가
def test_bad_plan_entries_are_skipped():
    """plan 항목이 망가져도 생성자에서 죽지 않고 쓸 수 있는 것만 남긴다."""
    cfg = {'flow': {'plan': [
        {'zone': 'RET_B', 'kind': 'BOWL', 'count': 2},
        {'zone': 'RET_C'},                       # kind·count 없음
        {'zone': 'RET_C', 'kind': 'SPOON', 'count': 1},   # 모르는 종류
        {'zone': 'RET_C', 'kind': 'CUP', 'count': 'two'}, # 숫자가 아님
    ]}}
    f = Flow(cfg, FakeLog())
    assert len(f.plan) == 1 and f.target_bowl == 2 and f.target_cup == 0


def test_empty_config_does_not_crash():
    """YAML 에 키만 있고 값이 비면 None 이 들어온다 — 그래도 살아야 한다."""
    f = Flow({'flow': {'plan': None, 'policy': None, 'rack_order': None,
                       'counts': None, 'step_delay_s': None}}, FakeLog())
    assert f.plan == [] and f.policy == {} and f.step_delay_s == 0.0
    assert f.counts == {'soap_dips': 3, 'rinse_dips': 1, 'rinse_shakes': 3}


def test_bad_step_delay_falls_back():
    f = Flow({'flow': {'step_delay_s': '빠르게'}}, FakeLog())
    assert f.step_delay_s == 0.0


def test_zero_is_a_valid_setting():
    """🚨 0 도 유효한 설정값이다.

    `cfg.get(k) or 기본값` 으로 읽으면 0 이 거짓이라 기본값으로 바뀐다 —
    시험을 0 으로 두려다 발견한 결함이다.
    """
    f = Flow({'flow': {'done_hold_s': 0, 'step_delay_s': 0, 'leftover_max_rounds': 0}}, FakeLog())
    assert f.done_hold_s == 0.0
    assert f.step_delay_s == 0.0
    assert f.rounds == 0


def test_missing_number_uses_default():
    f = Flow({'flow': {}}, FakeLog())
    assert f.done_hold_s == 1.0 and f.step_delay_s == 0.0 and f.rounds == 2


def test_bad_state_pub_hz_falls_back():
    """0·음수면 타이머를 만들 수 없다(1/0) — Io 생성 전에 걸러야 한다."""
    for bad in (0, -1, '빠르게', None):
        f = Flow({'flow': {'state_pub_hz': bad}}, FakeLog())
        assert f.state_pub_hz == 2.0, bad
    assert Flow({'flow': {'state_pub_hz': 5}}, FakeLog()).state_pub_hz == 5.0


def test_guard_survives_broken_logger():
    """통로 자신이 새면 안 된다 — 로그가 터져도 _guard 는 False 를 돌려준다."""
    class BrokenLog(FakeLog):
        def error(self, m):
            raise RuntimeError('로그도 터진다')

    f = Flow(CFG, BrokenLog())
    assert f._guard(_boom, what='둘 다 터짐') is False
