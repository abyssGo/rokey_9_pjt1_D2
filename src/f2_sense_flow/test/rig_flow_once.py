"""flow 의 process_one 을 **용기 1개**에 실기로 — HMI·서비스 없이 터미널에서 (INT-F2 = FLOW-04).

    soc && python3 src/f2_sense_flow/test/rig_flow_once.py check                              # 로봇 없이: 어떤 모듈이 진짜/가짜인지 · 빈 껍데기
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3          # 그릇 1개 — F3(세제·닦기)만 가짜
    soc && python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3 -n 3                           # 연속 3개 (반납 구역에 3개)
    python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f1,f2,f3 --no-robot                       # 대본만 (로봇 없이)

왜 flow_node 가 아니라 이것인가: flow_node 는 /flow/start 를 기다리고 plan(그릇 2 · 컵 2) 전체를 돈다. 첫 실기는 **그릇 1개**를
    같은 코드(flow.py process_one — PICK → WEIGH → SEAT → SOAP → WIPE → RINSE → RACK · 실패 정책 · 기록)로 돌리되, 멈추면 사람이
    터미널에서 재개/중단을 고른다. 통합의 "뼈대" 는 따로 만들지 않는다 — 제품 경로(flow.py) 가 뼈대다(INT-F2 · SKEL-01 논의).
    끝나면 flow_node + HMI 로 같은 것을 한 번 더 돌리면 L3(INT-3a) 다.

f1.tool 은 **진짜**다(V-08 10/10). --mock f3 으로 돌려도 로봇이 **실제로 수세미를 집었다 반납한다** —
    가짜인 것은 f3 의 세제·닦기(soap · wipe_*)뿐이다. 아래 문지기는 f1.tool 이 다시 빈 껍데기가 될 때를 위해 남겨 둔다.
🚨 실패로 PAUSED 되면 로봇은 그 자리(정책대로 후퇴 뒤). Enter = 그 단계부터 다시 · a = 이 용기를 접고 격리(HOME → 격리 → HOME) · q = 끝(안 움직임).
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys
import time

import cobot_common as cc
from cobot_common.config import parse_use_mock
from f2_sense_flow.flow import Flow, Signals, load_features
from f2_sense_flow.preflight import go_home_safely, require_controller, warn_if_cable_tight

FEATURES = ('f1', 'f2', 'f3')


class HumanSignals(Signals):
    """PAUSED 에서 사람이 고른다 — flow.wait_resume 이 take('abort') → take('resume') 순으로 묻는다."""

    def __init__(self, log):
        super().__init__()
        self.log = log
        self._asked = False

    def take(self, name):
        if name == 'abort' and not self._asked:
            self._asked = True
            self.log.warn('⏸ PAUSED — Enter = 그 단계부터 다시 · a = 이 용기 접고 격리 · q = 끝')
            try:
                ans = input().strip().lower()
            except EOFError:
                ans = 'q'
            if ans == 'q':
                raise KeyboardInterrupt
            self.raise_('abort' if ans == 'a' else 'resume')
        v = super().take(name)
        if v:
            self._asked = False
        return v


def _make_flow(cfg, log, features, robot):
    """flow_node.main 과 **같은 주입** — 후퇴·힘 끄기·정지·중단 예외."""
    events = []
    f = Flow(cfg, log, features=features,
             publish_event=lambda ev: (events.append(ev), log.info(f'📣 event {ev["result"]} · {ev["code"]} · {ev["duration_s"]} s')),
             safe_retreat=cc.safe_retreat if robot else None,
             force_off=cc.force_off if robot else None,
             no_retreat_errors=(cc.MoveIncomplete,) if robot else (),
             is_paused=cc.is_paused if robot else None,
             halt=cc.halt if robot else None,
             clear_halt=cc.clear_halt if robot else None,
             halt_errors=(cc.MotionHalted,) if robot else ())
    return f, events


STAGES = [   # flow.process_one 의 steps 순서 그대로 (번호 = 튜닝 때 단계를 가리키는 번호 · WEIGH 이동 단계 제거 뒤 12개)
    (1, 'PICK',  'f1.pick',          '반납 자리에서 집기(슬롯 1 → 2)'),
    (2, 'WEIGH', 'f2.leftover_loop', 'HOME 거쳐 무게 자세 → 재기 → 잔반이면 잔반통 털기(스플라인) → 재측정'),
    (3, 'SEAT',  'f1.place',         '스펀지 홈에 놓기'),
    (4, 'SOAP',  'f1.tool PICK',     '툴(수세미/솔) 집기'),
    (5, 'SOAP',  'f3.soap',          '세제 묻히기(홀더 안 비틀기·왕복)'),
    (6, 'WIPE',  'f3.wipe_*',        '닦기(그릇 나선 / 컵 위아래+회전)'),
    (7, 'WIPE',  'f1.tool RETURN',   '툴 반납(집은 자리로 곧게 · 감시 없음 · 마지막 15 mm 살짝 느리게)'),
    (8, 'RINSE', 'f1.pick(홈)',      '재파지(그릇 벽 / 컵 옆면 · 곧게 내려 잡기 · 감시 0)'),
    (9, 'RINSE', 'f2.dip',           '헹굼 담금(2회)'),
    (10, 'RINSE', 'f2.shake',        '물 털기(RINSE_SHAKE 자세 · J4 3회)'),
    (11, 'RACK',  'f1.rack_place',   '팔레트 적재(수조 위 → 경유점 → 칸 → 곧게 내려 놓기 → 빠져나오기)'),
    (12, 'RACK',  'f1.move_to HOME', 'HOME 복귀'),
]


def _print_stages(log):
    log.info('단계 번호표 (용기 1개 · 12단계 · 컵은 2단계가 flow.weigh_kinds 에 따라 빠질 수 있음)')
    for n, grp, fn, what in STAGES:
        log.info(f'  [{n:>2}] {grp:<5} {fn:<18} {what}')


def _install_step_gate(f, log):
    """flow.call_fn 을 감싸 단계마다 번호·이름을 찍고 Enter 를 기다린다(q = KeyboardInterrupt → 정지 명령 뒤 종료)."""
    orig = f.call_fn
    state = {'n': 0}

    def gated(mod_key, fn_name, *args):
        state['n'] += 1
        n = state['n']
        label = next((f'[{k:>2}] {grp} {fn}' for k, grp, fn, _ in STAGES if k == n), f'[{n:>2}]')
        print(f'\n▶ 다음 단계 {label} — {mod_key}.{fn_name}{args}')
        if input('   Enter = 실행 / q = 그만 > ').strip().lower() == 'q':
            raise KeyboardInterrupt
        t0 = time.monotonic()
        r = orig(mod_key, fn_name, *args)
        q = ' · '.join(f'J{i + 1} {v:.1f}' for i, v in enumerate(cc.joints()))      # 튜닝용: 단계 끝 관절 각도(J6 감김 확인)
        log.info(f'   ← 단계 {n} 끝 · {time.monotonic() - t0:.1f} s · {getattr(r, "code", r)} · 관절 {q}')
        return r
    f.call_fn = gated


def main():
    ap = argparse.ArgumentParser(description='flow.process_one 을 용기 1개에 실기로')
    ap.add_argument('which', nargs='?', default='run', choices=['run', 'check'])
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--zone', help='반납 구역 (기본 flow.plan 의 그 종류 첫 구역)')
    ap.add_argument('--mock', default='f3', help='가짜로 돌릴 기능, 쉼표 (기본 f3 — 툴·닦기는 가짜)')
    ap.add_argument('-n', type=int, default=1, help='연속 몇 개 (반납 구역에 그만큼)')
    ap.add_argument('--no-robot', action='store_true', help='전부 가짜일 때만')
    ap.add_argument('--step', action='store_true',
                    help='튜닝용: 단계마다 번호·이름을 찍고 Enter 를 기다린다(q = 그만) — 없앨 동작·빨리 할 동작을 번호로 고르기')
    ap.add_argument('--list', action='store_true', help='단계 번호표만 찍고 끝낸다(로봇 안 움직임)')
    ap.add_argument('--nudge', action='store_true',
                     help='PAUSED 에서 키보드로 안 묻는다 — 넛지(로봇팔 가볍게 밀기)·HMI 로만 재개(E37 실기용)')
    a = ap.parse_args()
    use_mock = [m for m in parse_use_mock(a.mock) if m in FEATURES] if a.mock else []
    robot = not (a.no_robot or set(FEATURES) <= set(use_mock))
    if a.which == 'check':
        robot = False                                            # check 는 로봇·드라이버 없이 설정만 본다
    if a.no_robot and robot:
        sys.exit('--no-robot 은 --mock f1,f2,f3 일 때만')

    if a.list:
        for n, grp, fn, what in STAGES:
            print(f'  [{n:>2}] {grp:<5} {fn:<18} {what}')
        return
    cc.init('rig_flow_once', robot=robot)
    log = cc.io_node().get_logger()
    try:
        if robot:
            require_controller(cc.io_node(), cc.cfg(), log)          # TS-07
            warn_if_cable_tight(cc.cfg(), log)                        # 🔗 케이블 장력(경고만)
        features = load_features(use_mock, log)
        cfg = cc.cfg()
        f, events = _make_flow(cfg, log, features, robot)
        zone = a.zone or next(p['zone'] for p in f.plan if p['kind'] == a.kind)

        if a.which == 'check' or ('f3' not in use_mock and 'f1' not in use_mock):
            # 🚨 f1.tool 이 빈 껍데기면 SOAP 에서 "툴 잡았다" 고 거짓 대답 → 진짜 f3 가 툴 없이 누른다
            from cobot_api import ToolResult
            tool_fn = getattr(features['f1'], 'tool', None)
            stub = False
            if 'f1' not in use_mock and callable(tool_fn):
                try:
                    r = tool_fn('SPONGE', 'PICK') if not robot else None   # robot 이면 실제로 부르지 않는다 — 빈 껍데기는 아래 check 로
                    stub = isinstance(r, ToolResult) and r.ok and r.width_mm == 0.0
                except Exception:                     # noqa: BLE001 — 진짜 구현은 로봇 없이 예외
                    stub = False
            if a.which == 'check':
                log.info(f'모듈: ' + ' · '.join(f'{k}={"가짜" if k in use_mock else "진짜"}' for k in FEATURES) + f' · robot={robot}')
                log.info(f'plan {f.plan} · weigh_kinds {f.weigh_kinds} · zone {zone} · rack {f.rack_order.get(a.kind)}')
                log.info('빈 껍데기 확인은 rig_int12.py check 로 (pick · rack_place · tool)')
                return
            if stub:
                sys.exit('🚨 f1.tool 이 빈 껍데기인데 f3 이 진짜다 — 툴 없이 닦으러 간다. --mock f3 으로 돌린다')

        if robot:
            log.info('E15 — 먼저 HOME 으로 간다')
            cc.force_off()
            go_home_safely(None, log, False)
        if a.step:
            _print_stages(log)
            _install_step_gate(f, log)
        sig = Signals() if a.nudge else HumanSignals(log)
        if a.nudge:
            log.info('--nudge — PAUSED 에서 키보드로 안 묻는다. 넛지(로봇팔 가볍게 밀기)로 재개한다')
        f.zone_id, f.kind = zone, a.kind
        for i in range(1, a.n + 1):
            log.info(f'━━ 용기 {i}/{a.n} · {a.kind} · {zone} · 팔레트 {f._next_slot()} ━━')
            t0 = time.monotonic()
            outcome = f.process_one(sig)
            log.info(f'━━ 결과 {outcome} · {time.monotonic() - t0:.1f} s · 완료 그릇 {f.done_bowl} 컵 {f.done_cup} 격리 {f.isolated} · 기록 {f.records.path}')
            if outcome != 'go_on':
                break
        log.info('event 요약: ' + ', '.join(f'{e["result"]}({e["code"]})' for e in events))
    except KeyboardInterrupt:
        log.warn('Ctrl+C / q — 로봇은 그 자리에 선다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
