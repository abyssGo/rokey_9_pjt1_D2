# -*- coding: utf-8 -*-
"""flow — 공정의 두뇌 (민범진). 상태 머신·구역 계획·실패 정책.

주의: 이 파일은 ROS 를 import 하지 않는다.
   통신(서비스·토픽·타이머)은 flow_node.py 가 맡는다. 여기는 "무엇을 어떤 순서로, 실패하면 어떻게"만 다룬다.
   그래서 로봇·브링업·ROS 없이 pytest 로 정책을 시험할 수 있다(TC-10).

바깥과 닿는 곳은 생성자로 주입받는 것뿐이다:
    cfg            설정(dict) — cobot_common.config.load() 결과
    log            로그 객체 (.info/.warn/.error)
    publish_event  용기 1개가 끝날 때 부를 함수. dict 한 개를 받는다
    safe_retreat   위험할 때 물러나는 함수 (cobot_common.safe_retreat)
    그 밖의 로봇 상태 함수(force_off · is_paused · halt · clear_halt · pause · resume)도 같은 방식으로 flow_node 가 넣어 준다.

문서: docs/03_설계_SDD.md §5.1(상태 머신) · docs/02_인터페이스_IRD.md §8(호출 순서·실패 정책)
표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import re
import threading
import time

import cobot_common as cc
from cobot_api import OK, PICK, ROBOT_ERROR, TOOL_FAIL, TOOL_LOST, Result

from .logger import Consumables, Records, now_iso

# ── 실패 정책 (params.yaml flow.policy 의 값 문자열) ─────────────────────
NEXT_ZONE = 'next_zone'          # 구역 종료 → 다음 구역 (기록 SKIPPED)
ISOLATE = 'isolate'              # 격리함에 넣고 다음 용기
RETRY = 'retry'                  # 후퇴 후 N회 재시도 → 그래도 실패면 격리
PAUSE = 'pause'                  # 멈추고 사람을 기다린다

_RETRY_RE = re.compile(r'^retry:(\d+)->isolate$')   # "retry:1->isolate" (SDD §4.3 · IRD §8)

_POLL_S = 0.05                   # 깃발을 들여다보는 간격

# process_one 의 결과 — run_plan 이 다음에 뭘 할지
GO_ON = 'go_on'                  # 이 구역의 다음 용기로
SKIP_ZONE = 'skip_zone'          # 이 구역은 그만, 다음 구역으로 (EMPTY_ZONE)
HALT = 'halt'                    # 전부 중단 (Ctrl+C 등)
# wait_resume 이 돌려주는 값 — 사람이 PAUSED 에서 무엇을 눌렀나
RESUMED = 'resumed'              # 재개 (이어서) — HMI 버튼
RESUMED_NUDGE = 'resumed_nudge'  # 재개 — 넛지(힘). 컨트롤러 쪽 SOS 해제가 아직 안 끝났을 수 있어 구분한다
ABORTED = 'aborted'              # 중단 (이 용기를 접고 다음 용기)
# handle_failure 만 돌려주는 값 — run_plan 까지 올라가지 않고 process_one 이 그 자리에서 쓴다
RETRY_STEP = 'retry_step'        # 재개 — 실패한 그 단계부터 다시 (IRD §8)
RETRY_TOOL_PICK = 'retry_tool_pick'   # 재개 — 툴 놓침 뒤: 곧게 빠져나와 '툴 집기' 단계부터 다시(툴 집기 → 세제 → 닦기)
# 멈춤에서 넛지(로봇팔 가볍게 밀기)로도 재개되는 코드 — 사람이 현장에서 바로 손대는 상황들(E52).
#    툴 놓침(홀더에 꽂고 넛지) · 툴 집기 실패(홀더 확인하고 넛지) · 로봇 오류(확인하고 넛지 — 쥔 것이 있으면 첫 넛지는 그리퍼만 연다)
_NUDGE_CODES = (TOOL_LOST, TOOL_FAIL, ROBOT_ERROR)

# 기능 이름 → (진짜 모듈 경로, 가짜 모듈 경로)
_MODULES = {
    'f1': ('f1_handling.handling', 'f2_sense_flow.mock.mock_f1'),
    'f2': ('f2_sense_flow.sense', 'f2_sense_flow.mock.mock_f2'),
    'f3': ('f3_wipe.wipe', 'f2_sense_flow.mock.mock_f3'),
}


def load_features(use_mock, log=None):
    """use_mock 에 있는 기능은 가짜 모듈을, 나머지는 진짜 모듈을 쓴다 (IRD §10).

    진짜 패키지가 아직 없으면 무엇을 해야 하는지 알려 주고 멈춘다 —
    알 수 없는 ImportError 로 끝나지 않게 한다.
    """
    import importlib
    mods = {}
    for name, (real, fake) in _MODULES.items():
        path = fake if name in use_mock else real
        try:
            mods[name] = importlib.import_module(path)
        except ModuleNotFoundError as e:
            if name in use_mock:
                raise
            raise RuntimeError(
                f'{name} 의 진짜 모듈 {path} 이 없다 ({e.name}). '
                f'아직 안 만들어졌으면 params.yaml 의 flow.use_mock 에 "{name}" 을 넣거나 '
                f'런치 인자 use_mock 에 넣는다.') from e
        if log:
            log.info(f'  {name} → {path}{" (가짜)" if name in use_mock else ""}')
    return mods


class Signals:
    """HMI 버튼이 세우는 깃발. 통신 스레드가 세우고 메인 스레드가 읽는다.

    주의: 두 스레드가 같이 만지므로 Lock 으로 감싼다(한 번에 한 스레드만).
       콜백은 여기 깃발만 세우고 로봇 함수를 부르지 않는다 (SDD §3.2 규칙 ③).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.start = False
        self.stop = False
        self.resume = False
        self.abort = False               # 중단 — PAUSED 에서만 (IRD §6 · 결정 E11)

    def raise_(self, name):
        """깃발을 세운다(name = 'start' · 'stop' · 'resume' · 'abort'). 통신 스레드의 콜백이 부른다."""
        with self._lock:
            setattr(self, name, True)

    def take(self, name):
        """깃발을 읽고 내린다(한 번만 반응하도록)."""
        with self._lock:
            v = getattr(self, name)
            setattr(self, name, False)
            return v

    def peek(self, name):
        """깃발을 내리지 않고 읽기만 한다 — 단계 사이에서 stop 을 볼 때처럼, 소비는 다른 곳(to_paused·wait_resume)이 한다."""
        with self._lock:
            return getattr(self, name)

    def clear(self, name):
        """깃발을 내린다 — 지난 실행·지난 정지에서 남은 resume·stop·abort 가 다음 정지를 혼자 풀지 않게(to_paused 주석)."""
        with self._lock:
            setattr(self, name, False)


class Flow:
    """상태 머신 + 구역 계획 + 실패 정책 — 용기 하나를 단계표대로 돌리고, 실패하면 params.yaml 의 flow.policy 대로 마무리한다.

    상태(self.step · flow_node 가 /flow/state 로 HMI 에 내보낸다):
        IDLE      start 를 기다린다(시작 전 · plan 이 끝나 DONE 을 보여 준 뒤)
        PICK · WEIGH · SEAT · SOAP · WIPE · RINSE · RACK
                  용기 1개의 단계(process_one 의 단계표 순서 · WEIGH 는 flow.weigh_kinds 에 없는 종류면 건너뛴다)
        ISOLATE   치우고 격리 구역으로 보내는 중(_cleanup_and_isolate — 중단과 정책 격리가 같은 길)
        PAUSED    사람을 기다린다(to_paused → wait_resume)
        DONE      plan 이 끝났다 — done_hold_s 동안 보여 주고 IDLE 로

    PAUSED 로 가는 곳:
        · stop 버튼(또는 이동 도중 정지 is_paused) — 용기 사이(run_plan)와 단계 사이(process_one)에서 본다
        · 단계 실패의 정책이 pause 일 때(handle_failure) · 케이블 장력 이상(handle_cable_tight) · EMPTY_ZONE 뒤 HOME 복귀 실패(run_plan)
    PAUSED 에서 돌아오는 길(wait_resume 의 반환값):
        · RESUMED / RESUMED_NUDGE(재개 버튼 · 넛지) — 단계 사이 정지면 멈춘 그 단계부터, 용기 사이면 다음 용기의 PICK 부터,
          실패 pause 면 실패한 그 단계부터(RETRY_STEP · TOOL_LOST 는 툴을 다시 집은 뒤). 로봇 오류(ROBOT_ERROR)만은 격리하지 않고
          그 자리에서 사람이 치운 뒤 HOME 으로 가서 다음 용기(_robot_error_pause · 이벤트 ERROR).
        · ABORTED(중단 버튼) — abort_container → 치우고 격리(ISOLATE) → HOME → 다음 용기(이벤트 ISOLATED).
          용기 사이의 중단은 치울 것이 없어 그냥 다음 용기.

    process_one 이 run_plan 에 돌려주는 값:
        GO_ON      이 구역의 다음 용기로(성공 DONE · 격리 ISOLATED · 로봇 오류 ERROR 모두)
        SKIP_ZONE  이 구역은 그만, 다음 구역으로(EMPTY_ZONE → 정책 next_zone → 이벤트 SKIPPED)
        HALT       전부 중단(run_plan 이 바로 끝난다 — 지금은 돌려주는 곳이 없는 예약값)
    handle_failure · handle_cable_tight 만 돌려주는 값:
        RETRY_STEP 실패한 그 단계부터 다시(process_one 이 단계 인덱스를 올리지 않는다)
    """

    def __init__(self, cfg, log, publish_event=None, safe_retreat=None, features=None,
                 force_off=None, no_retreat_errors=(),
                 is_paused=None, halt=None, clear_halt=None, halt_errors=(),
                 pause=None, resume=None, grip_width=None):
        self.cfg = (cfg or {}).get('flow', {})
        self.f = features or {}                  # {'f1': 모듈, 'f2': 모듈, 'f3': 모듈}
        self.log = log
        self._publish_event = publish_event or (lambda ev: None)
        self._safe_retreat = safe_retreat or (lambda: None)
        self._grip_width = grip_width or getattr(cc, 'grip_width', None)   # 닦기 재시도 전 툴 쥠 확인(_tool_held)
        # 주의: 후퇴를 하면 안 되는 예외들 (SDD §7). flow 는 로봇을 모르므로
        #    클래스와 함수를 flow_node 가 넣어 준다 — cc.MoveIncomplete · cc.force_off.
        #    이동이 도중에 서면 로봇이 어디 있는지 모른다 → Z 를 올리는 후퇴가 더 위험하다
        #    (실기 케이블 꼬임과 같은 길). 힘·순응만 끄고 그 자리에서 사람을 기다린다.
        self._force_off = force_off or (lambda: None)
        self._no_retreat_errors = tuple(no_retreat_errors or ())
        # FLOW-03 — 정지·재개·중단 (IRD §6). flow 는 로봇을 모르므로 flow_node 가 넣어 준다.
        #    cc.is_paused : 이동 도중 멈춰 있는가 (메인 스레드는 그때 기능 함수 안에 갇혀 있다)
        #    cc.halt      : 그 자세 그대로 강제 정지 — 중단할 때 하던 이동을 끊는다
        self._is_paused = is_paused or (lambda: False)
        self._halt = halt or (lambda: None)
        self._clear_halt = clear_halt or (lambda: None)
        self._pause = pause or (lambda: None)
        self._resume = resume or (lambda: None)
        self.holding_tool = None         # 쥐고 있는 툴 이름 — 중단 정리에서 반납한다
        # 그리퍼에 쥔 것(None · 'TOOL' · 'CONTAINER')과 용기가 스펀지 홈에 앉아 있는지(SEAT 뒤 ~ RINSE 재파지 전) — E52.
        #    로봇 오류 2단 넛지(쥔 것이 있으면 첫 넛지는 그리퍼만 열기)와 격리 정리(홈 위 용기 다시 집기)가 이 값을 본다. _track 이 갱신.
        self.holding = None
        self.on_bed = False
        # 주의: cc.MotionHalted — 중단을 누르면 하던 이동이 이걸로 끊긴다. 평범한 실패가 아니라
        #    중단 흐름으로 보낸다. ROBOT_ERROR 로 처리하면 사람이 또 확인해야 한다.
        self._halt_errors = tuple(halt_errors or ())
        self._halted = False
        self._cable_tight = False

        # 주의: 설정은 여기서 한 번에 읽고 검증한다.
        #    YAML 에 키만 있고 값이 비면 None 이 들어온다(`or` 로 받아야 한다).
        #    공정 도중에 KeyError·TypeError 로 죽으면 용기를 쥔 채 멈춘다.
        self.plan = self._check_plan(self.cfg.get('plan') or [])
        self.policy = self.cfg.get('policy') or {}
        self.rack_order = self.cfg.get('rack_order') or {}
        self.counts = self._check_counts(self.cfg.get('counts') or {})
        self.rounds = self._num('leftover_max_rounds', 2, int)
        # FLOW-05 (결정 E25): 무게 단계(leftover_loop)를 하는 종류.
        #    제한: 임시 건너뛰기 — 시나리오 변경이 아니다. 컵 무게 측정이 미완성이라 동결 전에 컵만 잠시 뺀 것.
        #    완성되면 params 의 flow.weigh_kinds 를 [BOWL, CUP] 으로 되돌린다(코드 변경 없음). 키가 없으면 예전대로 전부.
        self.weigh_kinds = self._check_weigh_kinds(self.cfg.get('weigh_kinds'))
        # DONE 을 화면에 보여 주는 시간. /flow/state 주기(state_pub_hz)보다 길어야 한 번은 잡힌다
        self.done_hold_s = self._num('done_hold_s', 1.0, float)
        self.step_delay_s = self._num('step_delay_s', 0.0, float)
        # /flow/state 발행 주기. 0·음수면 타이머를 만들 수 없다(1/0) → 기본값으로 되돌린다
        self.state_pub_hz = self._num('state_pub_hz', 2.0, float)
        if self.state_pub_hz <= 0:
            self.log.warn(f'flow.state_pub_hz 가 {self.state_pub_hz} 다 — 0 보다 커야 한다 → 2.0 으로 본다')
            self.state_pub_hz = 2.0

        # ── 상태 (flow_node 가 2 Hz 로 읽어 /flow/state 로 내보낸다) ──
        self.step = 'IDLE'
        self.kind = ''
        self.zone_id = ''
        self.last_code = OK
        self.message = ''
        self.rack_slot = ''                      # 이번 용기가 들어간 팔레트 칸
        self.done_bowl = 0
        self.done_cup = 0
        self.isolated = 0
        self.sponge_uses = 0
        self.soap_dips = 0
        self.rinse_dips = 0
        self._prev_step = 'IDLE'

        # FLOW-02 — 용기 1개마다 records.csv 한 줄 (SR-16 · TC-12)
        #    주의: 기록이 실패해도 공정은 멈추지 않는다 — 부르는 것도 _guard 를 거친다.
        #    (self.cfg 는 이미 cfg['flow'] 다 — 생성자 첫 줄)
        self.records = Records(self.cfg.get('records_path') or 'records.csv', log)
        self.consumables = Consumables(self.cfg.get('consumables'), log)
        self._tally = {}                         # 이번 용기의 단계별 값 (_collect 가 채운다)
        self._t0 = None                          # 이번 용기를 시작한 시각

        self.target_bowl = sum(e['count'] for e in self.plan if e['kind'] == 'BOWL')
        self.target_cup = sum(e['count'] for e in self.plan if e['kind'] == 'CUP')

    # ────────────────────────────────── 설정 검증 (생성자에서만)
    def _num(self, key, default, cast):
        """숫자 설정 하나를 읽는다. 없거나 숫자가 아니면 기본값 + 경고.

        주의: `cfg.get(k) or 기본값` 으로 쓰면 0 을 설정할 수 없다(0 은 거짓이라 기본값으로 바뀐다).
           그래서 None 인지만 따로 본다.
        """
        raw = self.cfg.get(key)
        if raw is None:
            return default
        try:
            return cast(raw)
        except (TypeError, ValueError):
            self.log.warn(f'flow.{key} 가 숫자가 아니다 ({raw!r}) → {default} 으로 본다')
            return default

    def _check_plan(self, plan):
        """plan 항목을 검사해 쓸 수 있는 것만 남긴다. 나쁜 항목은 버리고 알려 준다."""
        good = []
        for i, e in enumerate(plan):
            try:
                zone, kind, count = str(e['zone']), str(e['kind']), int(e['count'])
            except (TypeError, KeyError, ValueError) as err:
                self.log.error(f'flow.plan[{i}] 을 읽을 수 없다 ({err!r}) — 이 항목은 건너뛴다')
                continue
            if kind not in ('BOWL', 'CUP') or count < 0:
                self.log.error(f'flow.plan[{i}] 값이 이상하다 (kind={kind}, count={count}) — 건너뛴다')
                continue
            good.append({'zone': zone, 'kind': kind, 'count': count})
        if not good:
            self.log.warn('flow.plan 에 쓸 수 있는 항목이 없다 — start 를 눌러도 아무것도 하지 않는다')
        return good

    def _check_weigh_kinds(self, raw):
        """flow.weigh_kinds — 무게 단계를 하는 종류 목록. 없으면 ['BOWL', 'CUP'](예전 동작), 이상하면 경고 + 전부."""
        if raw is None:
            return ['BOWL', 'CUP']
        try:
            kinds = [str(k).upper() for k in raw]
        except TypeError:
            self.log.warn(f'flow.weigh_kinds 가 목록이 아니다 ({raw!r}) → 전부 무게를 잰다')
            return ['BOWL', 'CUP']
        bad = [k for k in kinds if k not in ('BOWL', 'CUP')]
        if bad:
            self.log.warn(f'flow.weigh_kinds 에 모르는 종류 {bad} — 무시한다')
        return [k for k in kinds if k in ('BOWL', 'CUP')]

    def _check_counts(self, counts):
        """횟수 설정이 빠졌으면 시작할 때 알려 주고 기본값으로 채운다."""
        out = {}
        for key, default in (('soap_dips', 3), ('rinse_dips', 1), ('rinse_shakes', 3)):
            try:
                out[key] = int(counts[key])
            except (TypeError, KeyError, ValueError):
                self.log.warn(f'flow.counts.{key} 가 없거나 숫자가 아니다 → {default} 으로 본다')
                out[key] = default
        return out

    # ────────────────────────────────── 상태 스냅샷
    def snapshot(self):
        """flow_node 가 FlowState 메시지로 옮겨 담을 값 모음.

        제한: 락이 없다. 통신 스레드가 읽는 동안 메인 스레드가 값을 바꿀 수 있어,
           한 스냅샷 안에서 step 과 카운터가 서로 다른 순간의 값일 수 있다.
           파이썬 속성 읽기는 원자적이라 깨진 값은 안 나오고, 2 Hz 로 다시 보내므로
           0.5 초 안에 맞춰진다. 표시용이라 그대로 둔다(락을 잡으면 통신 스레드가
           메인 스레드의 로봇 동작을 기다리게 되어 더 나쁘다).
        """
        # 주의: 이동 도중 멈추면 메인 스레드가 기능 함수 안에 갇혀 있어 step 을 못 바꾼다.
        #    그대로 두면 HMI 가 'WEIGH' 를 계속 보여 준다 → 깃발을 보고 PAUSED 로 알린다(IRD §6).
        step = 'PAUSED' if self._is_paused() else self.step
        return dict(
            step=step, kind=self.kind, zone_id=self.zone_id,
            done_bowl=self.done_bowl, done_cup=self.done_cup, isolated=self.isolated,
            target_bowl=self.target_bowl, target_cup=self.target_cup,
            sponge_uses=self.sponge_uses, soap_dips=self.soap_dips, rinse_dips=self.rinse_dips,
            last_code=self.last_code, message=self.message,
        )

    # ────────────────────────────────── 바깥 세계를 부르는 통로
    def _guard(self, fn, *args, what):
        """주입받은 콜러블(safe_retreat·publish_event)을 부르는 유일한 통로.

        주의: Flow 는 이것들을 직접 부르지 않는다. 프로세스가 하나라 여기서 새어 나간
           예외 하나가 셀 전체를 멈춘다. 리뷰에서 실제로 죽는 것이 확인됐다
           (뼈대 시절 cobot_common.safe_retreat 의 NotImplementedError → 프로세스 종료).
        """
        try:
            fn(*args)
            return True
        except Exception as e:                # noqa: BLE001 — 무엇이 터지든 셀을 멈추면 안 된다
            try:
                self.log.error(f'{what} 실패 — {e!r}')
            except Exception:                 # noqa: BLE001 — 로그가 터져도 통로는 안 샌다
                pass
            return False

    def _tool_held(self, tool_id):
        """쥔 툴이 아직 손에 있는가 — 툴 집기(f1 _tool_pick)와 같은 판정: |읽은 폭 − 영점 − 기대 폭| ≤ 허용오차.
        True/False, 판단할 수 없으면 None(폭을 못 읽음 · 고정 폭 프리셋 · 설정 없음 — 이때 닦기 함수가 시작할 때 폭을 읽다 멈춘다)."""
        if not tool_id or not callable(self._grip_width):
            return None
        try:
            preset = cc.cfg()['cell']['presets'][tool_id]
            if preset.get('grip_target_mm') is not None:
                return None
            want, tol, zero = float(preset['grip_width_mm']), float(preset['width_tol_mm']), float(preset['grip_zero_mm'])
            width = float(self._grip_width())
        except Exception as e:                         # noqa: BLE001 — 판단 못 하면 None
            self.log.warn(f'재시도 전 툴 쥠 확인 불가({e!r})')
            return None
        held = abs(width - zero - want) <= tol
        self.log.info(f'재시도 전 툴 확인: {tool_id} 폭 {width:.2f} mm (기대 {zero + want:.2f} ± {tol:g}) → '
                      f'{"쥐고 있음" if held else "손에 없음"}')
        return held

    def _retreat(self):
        """안전 자세로 물러난다. 실패하면 False.

        주의: 후퇴가 실패하면 로봇이 어디 있는지 알 수 없다. 그 상태로 같은 동작을
           다시 하면 위험하므로, 부르는 쪽은 재시도하지 말고 PAUSED 로 사람을 기다린다.
        """
        if self._guard(self._safe_retreat, what='safe_retreat'):
            return True
        self.last_code = ROBOT_ERROR
        self.message = '후퇴 실패 — 로봇 위치를 알 수 없다. 사람이 확인해야 한다'
        return False

    # ────────────────────────────────── 예외 보호 (SDD §5.1)
    def call(self, fn, *args):
        """기능 함수는 반드시 여기를 지나서 부른다. 항상 Result 를 돌려준다.

        프로세스가 하나라 함수 하나의 예외가 셀 전체를 멈춘다.
        예외가 나면 로그 → Result.fail(ROBOT_ERROR) 로 바꾸고 → safe_retreat() → PAUSED.
        """
        name = getattr(fn, '__name__', str(fn))
        try:
            r = fn(*args)
            # 주의: 반환값 확인도 try 안에서 한다. 뼈대 단계의 함수가 None·tuple 을 돌려주면
            #    r.code 접근이 call() 자신을 죽인다(보호 통로가 뚫리는 셈).
            if not isinstance(r, Result):
                raise TypeError(f'Result 가 아니라 {type(r).__name__} 을 돌려줬다')
            code, ok = r.code, r.ok
        except Exception as e:                    # noqa: BLE001 — 어떤 예외든 셀을 멈추면 안 된다
            # 주의: KeyboardInterrupt 는 BaseException 이라 여기 안 걸린다 — 그게 맞다.
            #    Ctrl+C 는 그대로 위로 올라가 main() 의 finally 가 cc.shutdown() 을 부른다.
            try:
                self.log.error(f'{name} 에서 예외 — {e!r}')
                self.message = f'{name}: {e}'
            except Exception:                     # noqa: BLE001 — 로그가 터져도 여기서 끝낸다
                self.message = f'{name}: (메시지를 만들 수 없음)'
            # 주의: 두 갈래다 (SDD §7)
            #    ① 이동이 도중에 선 예외(cc.MoveIncomplete) → 후퇴하지 않는다.
            #       로봇이 어디 있는지 모르는데 Z 를 올리면 더 꼬인다 → 힘·순응만 끄고 사람이 확인.
            #    ② 그 밖(힘 상한 ForceLimitError 등) → 설계대로 후퇴한다. 접촉에서 벗어나야 한다.
            if self._halt_errors and isinstance(e, self._halt_errors):
                # 중단(/flow/abort)이 하던 이동을 끊었다 — 실패가 아니라 사람이 시킨 것이다.
                #    후퇴하지 않는다(곧 HOME 으로 간다). process_one 이 중단 정리로 넘긴다.
                self.log.warn(f'{name} — 중단 요청으로 끊겼다')
                self.message = '중단 요청으로 멈췄습니다'
                self._halted = True
            elif e.__class__.__name__ == 'CableTightError':
                # 케이블 장력 이상 — 후퇴하지 않고 그 자리에서 PAUSED 진입, 넛지 재개 대기
                self.log.warn(f'{name} — 케이블 장력 이상 감지: {e}')
                self.message = str(e)
                self._cable_tight = True
            elif self._no_retreat_errors and isinstance(e, self._no_retreat_errors):
                self.log.error(f'{name} — 로봇 위치를 알 수 없다. 후퇴하지 않고 힘·순응만 끈다')
                self.message = f'{name}: 이동이 도중에 멈췄습니다 — 로봇 위치를 확인하세요'
                self._guard(self._force_off, what='force_off')
            else:
                self._retreat()                   # 후퇴가 또 터져도 _guard 가 삼킨다
            r = Result.fail(ROBOT_ERROR)
            code, ok = r.code, r.ok
        self.last_code = code
        if not ok:
            self.log.warn(f'{name} 실패 → {code}')
        return r

    def call_fn(self, mod_key, fn_name, *args):
        """기능 모듈에서 함수를 찾는 것까지 보호한다.

        주의: getattr 을 call() 밖에서 하면, 진짜 모듈에 함수 하나가 없을 때
           AttributeError 가 그대로 프로그램을 죽인다(진짜 패키지가 만들어지는 중이면 실제로 난다).
        """
        def resolve_and_call(*a):
            mod = self.f.get(mod_key)
            if mod is None:
                raise RuntimeError(f'{mod_key} 모듈이 없다 (use_mock 설정을 확인한다)')
            fn = getattr(mod, fn_name, None)
            if not callable(fn):
                raise AttributeError(f'{mod_key}.{fn_name} 이 없다')
            return fn(*a)
        resolve_and_call.__name__ = f'{mod_key}.{fn_name}'
        return self.call(resolve_and_call, *args)

    # ────────────────────────────────── 실패 정책
    def policy_for(self, code):
        """실패 코드에 대해 무엇을 할지 → (동작, 재시도 횟수).

        params.yaml 의 값 형식 (SDD §4.3 · IRD §8):
            next_zone · isolate · pause · "retry:N->isolate"
        모르는 코드·모르는 값은 안전하게 PAUSE 한다 — 조용히 넘어가면 안 된다.
        """
        action = self.policy.get(code)
        if action is None:
            self.log.warn(f'policy 에 없는 코드 {code} → pause 로 처리')
            return PAUSE, 0
        if action in (NEXT_ZONE, ISOLATE, PAUSE):
            return action, 0
        m = _RETRY_RE.match(str(action))
        if m:
            return RETRY, int(m.group(1))
        self.log.warn(f'policy 에 모르는 값 "{action}" (코드 {code}) → pause 로 처리')
        return PAUSE, 0

    # ────────────────────────────────── 일시 정지 / 재개
    def to_paused(self, why='', sig=None):
        """PAUSED 로 들어간다. sig 를 주면 그동안 남아 있던 resume 깃발을 함께 내린다.

        주의: 지우는 자리가 중요하다 — step 을 'PAUSED' 로 바꾸기 전이다.
           깃발은 take() 로 소비될 때까지 남아서, 운전 중(PAUSED 가 아닐 때) 눌렸거나
           한 번의 정지에서 두 번 눌린 resume 이 다음 PAUSED 를 사람이 아무것도 안 했는데
           0 초 만에 풀어 버린다(SDD §7 — ROBOT_ERROR·RACK_FULL 은 사람이 확인해야 한다.
           후퇴가 실패해 로봇 위치를 모르는 상태에서도 계속 움직이게 된다).

           왜 wait_resume 이 아니라 여기인가: flow_node 의 /flow/resume 은
           `step == 'PAUSED'` 일 때만 깃발을 세운다(두 번째 방어선). 그래서 지우는 자리가
           'PAUSED' 로 바꾼 뒤이면, 그 사이에 들어온 정당한 resume 을 지워 버린다 —
           HMI 는 '재개합니다' 를 받았는데 아무 일도 안 일어난다. 바꾸기 전에 지우면
           그 틈의 resume 은 노드가 'PAUSED 가 아닙니다' 로 분명히 거절한다.
           조용히 사라지는 것보다 거절이 낫다.
        """
        if sig is not None:
            sig.clear('resume')                       # 주의: 'PAUSED' 로 바꾸기 전에
        if self.step != 'PAUSED':
            self._prev_step = self.step
        self.step = 'PAUSED'
        self.log.warn(f'PAUSED — resume 을 기다린다{(" · " + why) if why else ""}')

    def wait_resume(self, sig, allow_nudge=False):
        """resume 을 기다린다. 기다리는 동안에도 /flow/state 는 계속 나간다.

        allow_nudge=True 면 HMI 재개 버튼 대신(또는 같이) **로봇팔을 가볍게 미는 것**도 재개 신호로
        본다(E37 · NEW-02a — cell.limits.nudge_force_n·nudge_hold_s). 사람이 현장에서 바로 손대는 멈춤에 쓴다 —
        툴 놓침·툴 집기 실패·로봇 오류(_NUDGE_CODES · 🔄 E52 9/25: 로봇 오류도 넛지로 — 쥔 것이 있으면 첫 넛지는 그리퍼만 연다).
        힘을 못 읽는 상태(보호정지 등)면 넛지를 포기하고 재개 버튼만 본다(handle_failure 가 고른다).

        Ctrl+C 로 끝내려면 여기서 KeyboardInterrupt 가 올라가 main() 의 finally 로 간다.

        🚨 재개 지점을 로그로 주장하지 않는다. `_prev_step` 은 **끝난** 단계라,
           "그 단계부터 다시" 라고 찍으면 거짓이 된다 — 부르는 자리마다 재개 지점이 다르다:
             · stop(단계 사이) → 멈춘 **다음** 단계부터   (멈출 때 "… 앞에서 정지" 로 이미 찍는다)
             · stop(용기 사이) → 다음 용기의 PICK 부터
             · 실패 PAUSE      → 이 용기를 접고 **다음 용기**부터 (handle_failure 가 GO_ON)
           self.step 복원은 HMI 가 PAUSED 에 머무르지 않게 하려는 것뿐이다.
        """
        # 🚨 여기서 resume 을 지우지 않는다 — 지우는 것은 to_paused 가 'PAUSED' 로
        #    바꾸기 **전**에 한다(이유는 to_paused 주석). 여기서 지우면 to_paused 와
        #    이 줄 사이에 들어온 **정당한** resume 이 조용히 사라진다.
        if allow_nudge:
            # 🚨 halt() 명령은 즉시 나가지만 팔이 실제로 완전히 멈추기까지는 물리적으로 시간이 든다.
            #    그 사이 기준값을 잡으면 흔들리는 값이 기준이 돼 오작동한다.
            #    완전히 멈춘 뒤에 기준을 잡도록 settle_s 만큼 기다린다.
            time.sleep(float(cc.cfg()['cell']['limits']['nudge_settle_s']))
            if not self._guard(cc.start_nudge_watch, what='start_nudge_watch'):
                # 🆕 E52: 힘을 못 읽으면(보호정지·ROS 없는 시험) 넛지는 포기하고 재개 버튼만 본다 — 여기서 터지면 셀이 선다
                self.log.warn('넛지 감시를 시작할 수 없다 — 재개 버튼만 기다린다')
                allow_nudge = False
            nudge_force_n = float(cc.cfg()['cell']['limits']['nudge_force_n'])
            nudge_hold_s = float(cc.cfg()['cell']['limits']['nudge_hold_s'])
            nudge_poll_s = float(cc.cfg()['cell']['limits']['nudge_poll_s'])
            lim_ = cc.cfg()['cell']['limits']
            nudge_taps = int(lim_.get('nudge_taps') or 1)                     # 🆕 9/24 E48: 2번 치기(없으면 예전대로 1번)
            nudge_window_s = float(lim_.get('nudge_tap_window_s') or 2.0)
            last_nudge_check = 0.0
        while True:
            if sig.take('abort'):                     # 🆕 사람이 "이 용기는 접자" 고 판단했다
                sig.clear('stop')
                self.log.warn('abort — 이 용기를 접고 다음 용기로 간다')
                return ABORTED
            if sig.take('resume'):
                sig.clear('stop')
                self.step = self._prev_step
                self.log.info('resume — 이어서 진행한다')
                return RESUMED
            # 🚨 9/23 실기: check_nudge 를 _POLL_S(0.05s)마다 부르면 힘 읽기 요청이 로봇 실시간
            #    제어 채널을 계속 붙잡아 하트비트가 5초 안에 못 나가 SAFE_STOP(1.3014)이 걸렸다
            #    (충돌 감지가 아니었다 — 통신 과부하였다). nudge_poll_s 간격으로만 부른다.
            now = time.monotonic()
            if allow_nudge and now - last_nudge_check >= nudge_poll_s:
                last_nudge_check = now
                try:
                    hit = cc.check_nudge(nudge_force_n, nudge_hold_s, nudge_taps, nudge_window_s)
                except Exception as e:                # noqa: BLE001 — 🆕 E52: 힘 읽기가 터지면 넛지만 포기(재개 버튼은 계속 본다)
                    self.log.warn(f'넛지 감지 불가({e!r}) — 재개 버튼만 기다린다')
                    allow_nudge, hit = False, False
                if hit:
                    sig.clear('stop')
                    self.step = self._prev_step
                    self.log.info(f'넛지 감지({nudge_taps}번 치기) — 이어서 진행한다')
                    return RESUMED_NUDGE
            time.sleep(_POLL_S)

    def abort_container(self, sig):
        """중단(/flow/abort) — 이 용기를 접고 다음 용기로 간다 (IRD §6 · 결정 E11).

        순서: 강제정지 풀기 → 곧게 위로(safe_retreat) → HOME → 툴 반납 → (홈 위 용기면 다시 집기) → 격리 구역에 → HOME
        실제 정리는 _cleanup_and_isolate 가 한다 — 정책 격리(isolate)와 같은 길(E52).
        주의: HOME 이 먼저인 이유: 결정 E7 로 이동에서 안전 높이 경유가 없어져 지금 자리에서
           다음 자리로 곧장 간다. 중단은 아무 때나 눌리므로 티칭 경로의 출발점에서 시작한다.
        주의: 한 단계가 실패해도 멈추지 않는다 — 치우는 중이라 더 나아가는 편이 낫다.
           다만 그 결과는 로그에 남긴다. 마지막에 이벤트는 ISOLATED 다.
        """
        # 주의: 깃발을 여기서 내린다 — 이동 도중 중단(halt_errors 경로)은 wait_resume() 을
        #    거치지 않아 지워 줄 사람이 없다. 안 지우면 정리가 끝나도 stop·abort 가 남아,
        #    마지막 용기였으면 다음 실행의 첫 PAUSE(GRIP_FAIL 등)를 사람이 아무것도 안 눌렀는데
        #    중단 정리로 풀어 버린다 — 로봇이 혼자 HOME → 격리 → HOME 으로 움직인다(리뷰에서 확인).
        sig.clear('abort')
        sig.clear('stop')
        self._clear_halt()                            # 중단 때 세운 강제정지를 푼다(안 풀면 새 이동도 거부된다)
        return self._cleanup_and_isolate(sig, '중단')

    def _cleanup_and_isolate(self, sig, why):
        """치우고 격리한다 — 중단(/flow/abort)과 정책 격리(isolate · 재시도 소진)가 **같은 길**을 쓴다 (🆕 E52 · 황인재 9/25).

        순서: 곧게 위로(safe_retreat) → HOME → 툴을 쥐었으면 반납 → 용기가 스펀지 홈에 있으면 **위에서 다시 집고 HOME** →
              격리 구역에 놓기 → HOME → ISOLATED(기록의 코드는 실패 원인 그대로).
        홈에서 다시 집기는 f1.regrip_top — 반납 구역에서 집어 홈에 놓을 때와 같은 파지(컵은 벽 집기)라 격리 자세와 맞는다
           (헹굼 앞 재파지 f1.pick 은 컵을 옆면으로 잡아 격리 구역에 옆으로 놓였다 · 실기).
        다시 집지 못하면 용기는 홈에 남기고 격리 구역에 놓기를 건너뛴다(빈손으로 격리 자세에 가지 않는다) — 사람이 치운다.
        🚨 HOME 이 먼저인 이유: 결정 E7 로 이동에서 안전 높이 경유가 없어져 **지금 자리에서 다음 자리로 곧장** 간다.
        🚨 HOME 으로 가기 **전에** 곧게 올라온다 (9/22 17:27 실기 충돌): 헹굼·담금 구간은 수조 안 자세(z −13.6)라
           거기서 HOME 으로 가면 관절 이동이 테이블을 가로질러 그리퍼가 상판을 쓴다. safe_retreat 은 XY 그대로 Z 만 올린다.
        🚨 홈에서 다시 집은 뒤 HOME 을 거친다 — 홈 → 격리 직행은 실기 0회, HOME → 격리 → HOME 은 #90·#103 으로 검증된 경로.
        🚨 한 단계가 실패해도 **멈추지 않는다** — 치우는 중이라 더 나아가는 편이 낫다. 다만 그 결과는 로그에 남긴다.
        🚨 9/23 E42 의 빈틈(정책 isolate 가 ISOLATED 만 기록 → 다음 PICK 의 release 가 든 용기를 그 자리에서 떨어뜨림)이 이걸로 닫힌다.
        """
        cause = self.last_code                        # 정리 이동이 성공하면 call() 이 last_code 를 OK 로 덮는다 — 기록엔 원인을 남긴다
        self.step = 'ISOLATE'
        self.message = f'{why} — 치우고 격리 구역으로 보냅니다'

        def step(what, mod, fname, *args):
            r = self.call_fn(mod, fname, *args)
            if not r.ok:
                self.log.error(f'{why} 정리 — {what} 실패({r.code}). 그래도 계속 치운다')
            return r

        self._retreat()
        step('HOME 복귀', 'f1', 'move_to', 'HOME', True)
        if self.holding_tool:
            step('툴 반납', 'f1', 'tool', self.holding_tool, 'RETURN')
            self.holding_tool = None
            self.holding = None
        left_on_bed = False
        if self.on_bed:                               # 세제·닦기 구간에서 왔다 — 용기는 스펀지 홈에 있다
            bed = 'SPONGE_BED_B' if self.kind == 'BOWL' else 'SPONGE_BED_C'
            if step('스펀지 홈에서 위로 다시 집기', 'f1', 'regrip_top', bed, self.kind).ok:
                step('HOME 복귀', 'f1', 'move_to', 'HOME', True)
            else:
                left_on_bed = True
            self.on_bed = False
        if left_on_bed:
            self.log.warn(f'{why} 정리 — 용기를 다시 집지 못해 스펀지 홈에 남겼다. 손이 비어 격리 구역에 놓기는 건너뛴다 · 사람이 치운다')
        else:
            step('격리 구역에 놓기', 'f1', 'place', 'ISOLATE', self.kind)
        step('HOME 복귀', 'f1', 'move_to', 'HOME', False)
        self.holding = None

        self.last_code = cause
        self.isolated += 1
        self.emit_event('ISOLATED')
        return GO_ON

    # ────────────────────────────────── 메인 루프 (메인 스레드에서만)
    def run(self, sig):
        """메인 스레드. Ctrl+C 면 KeyboardInterrupt 가 올라가 main() 의 finally 가 정리한다."""
        self.log.info('IDLE — /flow/start 를 기다린다')
        while True:
            if sig.take('start'):
                self.run_plan(sig)
            time.sleep(_POLL_S)

    def run_plan(self, sig):
        """plan 대로 구역을 돈다."""
        sig.clear('stop')
        # 주의: 지난 실행에서 남은 중단 깃발이 새 실행으로 넘어오지 않게 (to_paused 가 resume 을
        #    지우는 것과 같은 이유). abort_container 가 제 자리에서 지우지만, 두 번째 방어선을 둔다.
        sig.clear('abort')
        self.message = ''

        saw_container = False
        last_zone_empty = False

        for entry_i, entry in enumerate(self.plan):
            self.zone_id, self.kind = entry['zone'], entry['kind']
            zone_empty = False

            for _ in range(entry['count']):
                # 용기와 용기 사이. 단계 사이의 정지는 process_one 안에 따로 있다 (SDD §5.1)
                if sig.peek('stop') or self._is_paused():
                    self.log.info('stop 요청 — 용기 사이에서 정지')
                    self.to_paused('stop 버튼', sig)
                    if self.wait_resume(sig) == ABORTED:
                        # 주의: 용기 사이라 접을 용기가 없다 → 정리 없이 다음 용기로 간다.
                        #    전에는 반환값을 버려서 우연히 이렇게 됐다 — 코드로 분명히 한다.
                        self.log.info('abort — 아직 집지 않았으므로 치울 것이 없다. 다음 용기로')

                outcome = self.process_one(sig)

                if outcome == HALT:
                    return

                if outcome == SKIP_ZONE:
                    # pick()이 이 구역의 모든 슬롯을 확인한 뒤
                    # EMPTY_ZONE을 반환한 경우.
                    zone_empty = True
                    break

                # EMPTY_ZONE이 아니었다면 이번 실행에서 처리할 용기를
                # 하나 이상 발견한 것이다.
                saw_container = True

            if entry_i == len(self.plan) - 1:
                last_zone_empty = zone_empty

        # 마지막 구역(현재 RET_C)의 슬롯까지 모두 비었다면
        # 마지막 슬롯의 접근 높이에서 HOME으로 복귀한다.
        if last_zone_empty:
            self.message = '반납 구역 확인 완료 — HOME 복귀 중'

            while True:
                r = self.call_fn('f1', 'move_to', 'HOME', False)

                if r.ok:
                    break

                self.message = (
                    f'HOME 복귀 실패 ({r.code}) — 재개를 기다리는 중'
                )
                self.to_paused(
                    f'EMPTY_ZONE 후 HOME 복귀 실패 ({r.code})',
                    sig,
                )

                # 사람이 상태를 확인하고 resume한 뒤에만 HOME을 다시 시도한다.
                self.wait_resume(sig)

            if not saw_container:
                self.message = '처리 대상 없음 — HOME 복귀 완료'
            else:
                self.message = '남은 처리 대상 없음 — HOME 복귀 완료'

        self.step, self.kind, self.zone_id = 'DONE', '', ''

        self.log.info(f'plan 완료 — 그릇 {self.done_bowl} · 컵 {self.done_cup} · 격리 {self.isolated}')
        # 주의: 곧바로 IDLE 로 덮으면 2 Hz 타이머가 DONE 을 한 번도 못 보고 HMI 에 완료가 안 뜬다.
        #    발행 주기보다 길게 머무른다.
        time.sleep(self.done_hold_s)
        self.step = 'IDLE'

    def process_one(self, sig):
        """용기 1개를 처리한다. 돌려주는 값은 GO_ON · SKIP_ZONE · HALT(run_plan 이 다음에 할 일).

        흐름: ① 단계표(steps)를 만든다 — 순서는 IRD §8, 모듈은 use_mock 에 따라 진짜/가짜(load_features)
              ② 단계마다 먼저 stop 깃발(과 이동 도중 정지)을 본다 → PAUSED → 재개면 그 단계부터, 중단이면 abort_container
              ③ call_fn 으로 단계를 부르고, 실패면 정책(retry:N)만큼 후퇴 → 같은 단계를 다시 해 본다
              ④ 그래도 실패면 handle_failure — RETRY_STEP 이면 같은 단계를 다시, 아니면 그 결과를 run_plan 에 돌려준다
        끝까지 가면 카운터·소모품을 올리고 이벤트 DONE.
        """
        bowl = self.kind == 'BOWL'
        bed = 'SPONGE_BED_B' if bowl else 'SPONGE_BED_C'
        tool_id = 'SPONGE' if bowl else 'BRUSH'
        wipe_fn = 'wipe_bowl' if bowl else 'wipe_cup'
        rounds = self.rounds
        n = self.counts
        self.rack_slot = self._next_slot()
        self._tally = {}                         # FLOW-02 — 이번 용기의 값을 여기 모은다
        self._t0 = time.monotonic()
        self.holding, self.on_bed = None, False   # E52 — 용기마다 새로 센다

        # (단계, 모듈, 함수이름, 인자) — 주의: 함수 객체를 미리 꺼내지 않는다.
        #    꺼내는 것까지 call_fn 안에서 해야 "함수가 없다"가 크래시가 아니라 Result 가 된다.
        steps = [
            ('PICK', 'f1', 'pick', (self.zone_id, self.kind)),
            # 'f1.move_to WEIGH' 단계는 따로 없다 — sense.weigh 가 스스로 HOME → WEIGH 로 가므로(오는 길 통일)
            #    집은 자리에서 12.9 mm 살짝 내려가던 그 단계는 중복이었다. WEIGH 자세는 종류별(E8)이라 kind 는 leftover_loop 가 넘긴다.
            ('WEIGH', 'f2', 'leftover_loop', (self.kind, rounds)),
            ('SEAT', 'f1', 'place', (bed,)),
            ('SOAP', 'f1', 'tool', (tool_id, 'PICK')),
            ('SOAP', 'f3', 'soap', (n['soap_dips'], self.kind)),   # SOAP 자세도 종류별 (E8)
            ('WIPE', 'f3', wipe_fn, ()),
            ('WIPE', 'f1', 'tool', (tool_id, 'RETURN')),
            ('RINSE', 'f1', 'pick', (bed, self.kind)),
            ('RINSE', 'f2', 'dip', ('RINSE', n['rinse_dips'], self.kind)),
            ('RINSE', 'f2', 'shake', ('RINSE', n['rinse_shakes'], self.kind)),
            ('RACK', 'f1', 'rack_place', (self.rack_slot, self.kind)),
            ('RACK', 'f1', 'move_to', ('HOME', False)),
        ]
        if self.kind not in self.weigh_kinds:        # FLOW-05 · E25 — 컵은 PICK 에서 곧장 SEAT 로
            steps = [st for st in steps if st[0] != 'WEIGH']
            self.log.info(f'{self.kind} 은(는) 무게 단계를 건너뛴다 (flow.weigh_kinds={self.weigh_kinds} · E25)')
        # 주의: for 가 아니라 while 이다 — PAUSED 에서 재개하면 실패한 그 단계부터 다시 해야 해서
        #    같은 자리를 한 번 더 돌 수 있어야 한다(IRD §8). for 로는 못 돌아온다.
        i = 0
        while i < len(steps):
            step, mod, fname, args = steps[i]
            # 주의: stop 은 단계 사이마다 본다 (SDD §5.1 — V-20 에서 찾은 결함).
            #    여기가 없으면 정지 버튼을 눌러도 용기 하나(실기 수십 초)를 끝까지 하고서야 멈춘다.
            #    용기·툴을 든 채 멈출 수 있다 → 주의: 그리퍼에 아무 명령도 보내지 않는다.
            #    (기능 함수가 끝날 때 HOLD → NORMAL 로 되돌리므로 단계 사이는 이미 NORMAL 이다.
            #     여기서 힘을 바꾸면 드라이버가 다시 파지하면서 놓칠 수 있다 — 드라이버에 힘만 바꾸는 명령이 없다)
            #    resume 하면 이 단계부터 이어 간다.
            if sig.peek('stop') or self._is_paused():
                self.log.info(f'stop 요청 — {step} 앞에서 정지')
                self.to_paused('stop 버튼', sig)
                if self.wait_resume(sig) == ABORTED:  # 재개 대신 중단을 눌렀다
                    return self.abort_container(sig)
            self.step = step
            r = self.call_fn(mod, fname, *args)
            self._collect(step, fname, r)             # FLOW-02 — 기록에 쓸 값을 줍는다
            if self._halted:                          # 중단으로 끊긴 것 — 정책을 타지 않는다
                self._halted = False
                return self.abort_container(sig)
            if self._cable_tight:                     # 케이블 장력 이상 — 넛지 재개 대기
                self._cable_tight = False
                outcome = self.handle_cable_tight(sig)
                if outcome != RETRY_STEP:
                    return outcome
                continue                              # 실패한 그 단계를 다시
            if r.ok and fname == 'tool':               # 쥐고 있는 툴을 기억한다(중단 정리에서 반납)
                self.holding_tool = args[0] if args[1] == 'PICK' else None
            self._track(fname, args, r)               # E52 — 쥔 것 · 홈 위 용기
            if not r.ok:
                action, retries = self.policy_for(r.code)
                # retry:N->isolate — 후퇴한 뒤 같은 동작을 N 번까지 다시 해 본다
                # 주의: 세는 변수를 i 로 쓰지 않는다 — 바깥의 단계 인덱스 i 를 덮어써서,
                #    재시도가 성공하면 아래 `i += 1` 이 엉뚱한 자리로 뛴다(시험에서 발견).
                #    실기에서는 이미 팔레트에 넣은 용기로 공정을 통째로 한 번 더 돈다.
                for attempt in range(retries):
                    self.log.info(f'{step} 재시도 {attempt + 1}/{retries} (코드 {r.code})')
                    # 닦기 재시도 전에 툴을 아직 쥐고 있는지 본다 — 닦다가 사람이 툴을 당기면 폭보다 힘 상한이 먼저 걸릴 수 있다.
                    #    그대로 다시 부르면 빈손으로 그릇·컵에 다시 내려가고, 닦기 함수가 빈손 폭을 새 기준으로 잡아 놓침도 못 본다.
                    if step == 'WIPE' and self._tool_held(self.holding_tool) is False:
                        self.last_code = TOOL_LOST
                        self.message = f'툴 놓침 — 닦기를 다시 하기 전에 보니 {self.holding_tool} 이(가) 손에 없다'
                        r = Result.fail(TOOL_LOST)
                        action = PAUSE                # 툴 놓침과 같게: 멈춤 → 홀더에 꽂고 가볍게 밀기 → 툴 집기부터
                        break
                    if not self._retreat():   # 주의: 후퇴 실패 → 더 움직이지 않는다
                        action = PAUSE
                        break
                    # 주의: 그릇 닦기 재시도 전에 HOME 관절 자세(move_to 'HOME')로 가지 않는다 — 닦기는 툴 집기 자세의 손목 방향
                    #    (J6 ≈ 140°)을 그대로 두고 HOME 좌표로만 옮겨 와서 하므로, HOME 관절 자세(J6 0°)로 가면 수세미를 쥔 채
                    #    손목을 약 140° 돌리고(케이블 꼬임) 이어지는 툴 반납의 회전 방향이 정해지지 않는다. 재시도는 곧게 올라온 자리
                    #    (safe_z)에서 다시 부른다 — 바닥 찾기 여유가 얇아 못 찾으면 로봇 오류로 그 자리에 선다(움직이지 않는다).
                    r = self.call_fn(mod, fname, *args)
                    if self._halted:
                        self._halted = False
                        return self.abort_container(sig)
                    if r.ok:
                        break
                if not r.ok:
                    # 주의: 재시도 중에 실패 코드가 바뀌었을 수 있다 (예: 1차 FORCE_LIMIT →
                    #    재시도에서 기능 함수가 터져 ROBOT_ERROR). 첫 실패 코드로 정한 옛 정책으로
                    #    마무리하면 params.yaml 의 ROBOT_ERROR: pause 를 무시하고 격리해 버려,
                    #    로봇 위치를 모르는 채 격리함까지 이송하게 된다.
                    #    SDD §7 은 ROBOT_ERROR 를 "그 자리 정지 → PAUSED + 알림, 사람이 복구" 로 못 박는다.
                    #    → 마무리 직전에 최신 코드로 정책을 다시 읽는다.
                    #    단 action 이 이미 PAUSE 면 다시 읽지 않는다 — 후퇴 실패로 강제한 PAUSE 라
                    #    (위 `if not self._retreat()`) 덮어쓰면 다시 움직이게 된다.
                    #    다시 읽은 값이 (RETRY, n) 이어도 그대로 넘긴다 — handle_failure 가
                    #    "ISOLATE, 그리고 재시도를 다 쓴 RETRY" 를 같은 갈래로 처리한다.
                    if action != PAUSE:
                        action, _ = self.policy_for(r.code)
                    outcome = self.handle_failure(sig, action)
                    if outcome == RETRY_TOOL_PICK:     # 툴 놓침 — '툴 집기' 단계로 되돌아간다(세제가 닦는 자리로 옮겨 준다)
                        i = next(k for k, st in enumerate(steps) if st[2] == 'tool' and st[3][1] == PICK)
                        continue
                    if outcome != RETRY_STEP:
                        return outcome
                    continue                    # i 를 안 올린다 → 실패한 그 단계를 다시
            self.pause_between()
            i += 1

        if self.kind == 'BOWL':
            self.done_bowl += 1
        else:
            self.done_cup += 1
        self.sponge_uses += 1
        self.soap_dips += 1                      # 세제는 용기당 1회(세제 묻히는 행위 1번)로 센다 — 담금 횟수(3)가 아니다 · HMI 와 같은 기준
        self.rinse_dips += n['rinse_dips']
        # FLOW-02 — 임계에 닿으면 알리기만 한다(멈추지 않는다: 용기를 든 채 서게 된다)
        self._guard(self.consumables.check,
                    dict(sponge_uses=self.sponge_uses, soap_dips=self.soap_dips,
                         rinse_dips=self.rinse_dips),
                    what='consumables.check')
        self.emit_event('DONE')
        return GO_ON

    def _next_slot(self):
        """팔레트 칸 배정 — rack_order 순서대로. 다 차면 마지막 칸(실제 판정은 F1 이 RACK_FULL)."""
        order = self.rack_order.get(self.kind) or []
        done = self.done_bowl if self.kind == 'BOWL' else self.done_cup
        return order[done] if done < len(order) else (order[-1] if order else '')

    def handle_cable_tight(self, sig):
        """케이블 장력 이상 감지 시 정지(PAUSED) 후 사용자 개입(넛지 또는 resume) 및 상태 재검증.

        1. to_paused 로 상태를 PAUSED 로 변경하고 대시보드 안내 메시지 설정
        2. 현재 모션 즉시 PAUSE (후퇴 없이 그 자리에서 멈춤)
        3. 사용자 넛지(외력 변화량) 또는 HMI resume 대기
        4. 넛지 또는 resume 감지 시: 케이블 상태(jitter_g) 재측정
        5. 정상: 모션 resume 후 RETRY_STEP 돌려주어 그 단계부터 재개
        6. 이상 지속: PAUSED 유지 및 메시지 갱신 후 다시 대기
        7. abort 요청: abort_container(sig) 로 정리
        """
        self.to_paused('케이블 장력 이상 — 케이블 상태 확인 및 넛지 재개 대기', sig)
        self.message = '케이블 상태를 확인해주세요. 확인 후 로봇팔을 가볍게 밀어 주세요.'
        self.last_code = ROBOT_ERROR

        # 주의: 케이블 이상 시 후퇴 동작 없이 현재 모션 즉시 PAUSE
        self._guard(self._pause, what='pause')

        sense_mod = self.f.get('f2')
        wait_fn = getattr(sense_mod, 'wait_for_nudge', None)
        recheck_fn = getattr(sense_mod, 'recheck_cable', None)

        while True:
            ev = None
            if callable(wait_fn):
                ev = wait_fn(conf=None, sig=sig, timeout_s=0.2)
            else:
                if sig.take('abort'):
                    ev = 'abort'
                elif sig.take('resume'):
                    ev = 'resume'
                else:
                    time.sleep(_POLL_S)

            if ev == 'abort' or sig.take('abort'):
                sig.clear('stop')
                self._guard(self._resume, what='resume')
                self.log.warn('abort — 케이블 이상 중 용기 중단 요청')
                return self.abort_container(sig)

            if ev in ('nudge', 'resume') or sig.take('resume'):
                sig.clear('resume')                            # 이 신호는 여기서 쓴다 — 남기면 재검증이 실패해도 사람 신호 없이 다시 잰다
                sig.clear('stop')
                self.log.info(f'재개 요청 감지(유형: {ev}) — 케이블 상태 재확인 중...')
                self.message = '재개 요청 감지 — 케이블 상태를 재확인하고 있습니다...'

                # 주의: 넛지 때 강한 외력(예: >35 N)으로 제어기가 SAFE_STOP(5)에 걸릴 수 있다(실기).
                #    자동 복구(set_robot_control 2)를 시도하고 STANDBY 로 돌아올 때까지 대기.
                timeout_s = 2.0                                    # 설정을 못 읽을 때의 기본 2 s
                try:
                    timeout_s = float(cc.cfg().get('cell', {}).get('limits', {}).get('nudge_resume_settle_s', 2.0))
                except Exception:
                    pass
                if callable(getattr(cc, 'recover_robot_if_needed', None)):
                    cc.recover_robot_if_needed(timeout_s=timeout_s)

                is_ok = True                                       # recheck 함수가 없으면(가짜 모듈) 정상으로 보고 지나간다
                jitter = 0.0
                limit = 50.0                                       # 떨림 상한 기본 50 g(recheck_cable 이 실제 값을 돌려준다)
                if callable(recheck_fn):
                    try:
                        is_ok, jitter, limit = recheck_fn(conf=None)
                    except Exception as e:
                        self.log.warn(f'케이블 재검증 중 오류({e!r}) — 정지 유지')
                        is_ok = False

                if is_ok:
                    self.log.info(f'케이블 상태 정상 확인(떨림 {jitter:.1f} g <= {limit:.1f} g) — 작업 재개')
                    # 이동 재개 전 로봇 상태가 STANDBY(1)인지 최종 확인 및 복구
                    if callable(getattr(cc, 'recover_robot_if_needed', None)):
                        if not cc.recover_robot_if_needed(timeout_s=timeout_s):
                            if callable(getattr(cc, 'wait_robot_ready', None)) and not cc.wait_robot_ready(timeout_s):
                                self.log.warn(f'재개 전 로봇이 {timeout_s:g} s 안에 STANDBY 로 안 돌아왔다 — 그래도 이어간다')
                    self._guard(self._resume, what='resume')
                    self.step = self._prev_step
                    self.message = '케이블 정상 확인 — 작업을 재개합니다'
                    self.last_code = OK
                    return RETRY_STEP
                else:
                    self.log.warn(f'케이블 이상 지속(떨림 {jitter:.1f} g > {limit:.1f} g) — 정지 유지 · 새 신호를 기다린다')
                    self.to_paused('케이블 이상 지속', sig)       # 멈춤을 다시 건다 — 남은 재개 신호를 지우고, 사람이 다시 밀거나 재개할 때까지 기다린다
                    self.message = f'케이블 이상 지속(떨림 {jitter:.0f} g > 상한 {limit:.0f} g): 케이블 확인 후 다시 로봇팔을 가볍게 밀어 주세요'

    def handle_failure(self, sig, action=None):
        """실패를 정책대로 마무리한다 (재시도는 process_one 이 이미 끝냈다).

        돌려주는 값: RETRY_STEP(그 단계부터 다시) · GO_ON(다음 용기) · SKIP_ZONE(이 구역 그만) · HALT(중단)
        """
        if action is None:
            action, _ = self.policy_for(self.last_code)

        if action == PAUSE:
            code = self.last_code
            if code == ROBOT_ERROR:                    # 🆕 E52(황인재 9/25) — 그 자리 멈춤 · 쥔 것이 있으면 넛지 2번(첫 넛지는 그리퍼만 열기)
                return self._robot_error_pause(sig)
            if code == TOOL_FAIL:                      # 🆕 E52 — 홀더에서 못 집었다: 격리하지 않는다 · 사람이 홀더 확인 → 넛지 → 툴 집기부터 다시
                self.message = (f'{self.message or "툴 집기 실패"} — 홀더의 수세미·솔이 원래 방향으로 제대로 꽂혔는지 확인한 뒤 '
                                f'로봇팔 가볍게 밀기(또는 재개) → 툴 집기부터 다시 합니다')
            if code == TOOL_LOST:                      # 툴이 손에 없다 — 기다리는 동안 '중단'을 누르면 정리가 빈손으로 툴 반납을 가서
                self.holding, self.holding_tool = None, None   # 사람이 다시 꽂아 둔 손잡이 위로 닫힌 손가락을 내리지 않게 먼저 지운다
            self.to_paused(f'코드 {code}', sig)
            # 넛지 재개는 사람이 현장에서 바로 손대는 멈춤(_NUDGE_CODES)에만 — GRIP_FAIL·RACK_FULL 은 화면에서 확인하고 재개
            answer = self.wait_resume(sig, allow_nudge=(code in _NUDGE_CODES))
            if answer == ABORTED:                     # 🆕 사람이 이 용기를 접기로 했다
                return self.abort_container(sig)
            if answer == RESUMED_NUDGE:
                self._recover_robot()
            if code == TOOL_LOST:                      # 🆕 E37 — 닦는 도중 놓쳤다. 이어가기 전에 다시 집는다(못 집으면 다시 멈춤 · 격리 X)
                return self._repick_tool(sig)
            # 그 밖(GRIP_FAIL·RACK_FULL·TOOL_FAIL)은 **실패한 그 단계부터** 이어 간다.
            #    끝까지 가면 DONE 으로 기록되므로 여기서는 이벤트를 내지 않는다(9/20 PM 결정).
            #    다시 실패하면 또 PAUSED 가 된다 — 풀려면 사람이 재개해야 하므로 혼자 돌지 않는다.
            #    사람이 "이 용기는 접자" 고 판단하면 /flow/abort 다(IRD §6 — flow_node 가 PAUSED 에서만 받는다).
            self.log.info(f'재개 — {self.step} 단계부터 다시 (코드 {code})')
            return RETRY_STEP

        if action == NEXT_ZONE:                 # 구역이 비었다 — 남은 count 도 의미 없다
            self.emit_event('SKIPPED')
            return SKIP_ZONE

        # isolate · 재시도 소진(retry:N->isolate) — 🆕 E52(황인재 9/25): 기록만 하지 않고 **실제로 치운다**.
        #    잔반 남음(용기를 든 채) · 힘 상한/시간 초과(툴을 쥔 채 · 용기는 홈에) · 안착 실패 모두 중단과 같은 길:
        #    곧게 위로 → HOME → 툴 반납 → 홈 위 용기 다시 집기 → 격리 → HOME. (9/23 #103 의 LEFTOVER 전용 갈래를 여기에 합쳤다)
        return self._cleanup_and_isolate(sig, f'정책 격리 · 코드 {self.last_code}')

    def _robot_error_pause(self, sig):
        """🆕 E52(황인재 9/25) — 로봇 오류: **그 자리에서 멈춘다.** 로봇은 격리 구역으로 가지 않는다(자기 위치를 모를 수 있다).

        쥔 것이 있으면(툴·용기) → 사람이 확인 → 로봇팔 가볍게 밀기(또는 재개) → **그리퍼만 연다**(팔은 안 움직임) → 사람이 받아 치운다
          (툴은 홀더에 · 용기는 치움 · 스펀지 홈에 용기가 있으면 그것도) → **화면 재개 버튼**(신호 2 는 넛지를 받지 않는다 —
          황인재 9/27 · PM 지적: 넛지 감지 직후 팔이 위로 움직이기 시작하는데 사람 손이 로봇에 닿아 있을 수 있다) → 곧게 위로 → HOME → 다음 용기.
        빈손이면 → 로봇팔 가볍게 밀기(또는 재개) → 곧게 위로 → HOME → 다음 용기. 이 용기는 ERROR 로 기록한다(격리 X · 사람이 처리).
        🚨 그리퍼 열기·복구는 사람이 신호를 준 **뒤**에만 한다. 넛지가 안 잡히는 상태(보호정지에서 힘 읽기 불가)면 재개 버튼.
        """
        held = self.holding
        if not held and self._gripper_closed():        # 🆕 9/27 보강: 기록은 빈손인데 그리퍼가 닫혀 있다 — 집는 **도중**(예: 홈 C 옆면 재파지) 오류
            held = 'UNKNOWN'
        what = {'TOOL': '툴', 'CONTAINER': '용기'}.get(held, '무언가(집는 도중 오류 · 용기일 수 있음)')
        base = self.message or f'코드 {ROBOT_ERROR}'
        bed_note = ' 스펀지 홈에 용기가 있으면 그것도 꺼내 주세요.' if self.on_bed else ''
        if held:
            self.message = (f'{base} — 로봇 오류 · 그리퍼에 {what}이(가) 있습니다. 로봇과 주변을 확인한 뒤 '
                            f'로봇팔 가볍게 밀기(또는 재개) → 그리퍼만 열립니다 — 받을 준비를 하세요.{bed_note}')
        else:
            self.message = (f'{base} — 로봇 오류 · 빈손. 로봇과 주변을 확인한 뒤 로봇팔 가볍게 밀기(또는 재개) → '
                            f'곧게 위로 → HOME → 다음 용기로 갑니다.{bed_note}')
        self.to_paused(f'코드 {ROBOT_ERROR}', sig)
        if self.wait_resume(sig, allow_nudge=True) == ABORTED:     # flow_node 는 로봇 오류 중 중단을 거절한다 — 직접 호출·시험 대비
            return self.abort_container(sig)
        self._recover_robot()
        if held:
            self.log.warn(f'로봇 오류 — 사람 신호 1 · 그리퍼를 연다({what}) · 팔은 움직이지 않는다')
            self._guard(cc.release, what='release')
            self.holding, self.holding_tool = None, None
            self.message = (f'그리퍼를 열었습니다 — {what}을(를) 받아 '
                            + ('홀더에 원래 방향으로 꽂고 ' if held == 'TOOL' else '치우고 ')
                            + ('스펀지 홈의 용기도 꺼낸 뒤 ' if self.on_bed else '')
                            + '한 발 물러나 화면의 재개 버튼 → 곧게 위로 → HOME → 다음 용기 (이 신호는 넛지를 받지 않습니다)')
            self.to_paused('그리퍼 열림 — 받은 뒤 화면 재개', sig)
            # 🚨 신호 2 는 재개 버튼만(allow_nudge=False · 황인재 9/27): 감지 직후 팔이 움직이므로 손이 닿은 채 넛지로 출발시키지 않는다
            if self.wait_resume(sig, allow_nudge=False) == ABORTED:
                return self.abort_container(sig)
            self._recover_robot()
        self.on_bed = False                            # 사람이 치웠다고 본다(안내 문구에 넣었다)
        self._go_home_or_wait(sig)
        self.last_code = ROBOT_ERROR                   # HOME 이동이 성공하면 OK 로 덮인다 — 기록엔 원인
        self.emit_event('ERROR')
        return GO_ON

    def _gripper_closed(self):
        """🆕 E52 보강(9/27) — 그리퍼가 열려 있지 않으면(폭 ≤ 열림 기준 100 mm · gripper._OPEN_WIDTH_MM) '무언가 쥐었을 수 있다'로 본다.

        기록(holding)은 단계가 **끝난** 결과로만 갱신되므로, 집는 도중 오류(닫은 뒤 들다가 보호정지 등)면 빈손으로 남는다.
        그때 신호 1번으로 HOME 을 보내면 쥔 용기를 다음 PICK 의 release 가 떨어뜨린다 → 폭으로 한 번 더 본다.
        빈손인데 닫힌 경우(명령 폭에서 멈춤 · 옆면 70 은 빈손과 폭이 같다)도 True 가 되지만 그 값은 신호 한 번 더 · 그리퍼 열기 한 번이라 해가 없다.
        못 읽으면(보호정지 · 시험) False — 기록만 믿는다.
        """
        try:
            w = float(cc.grip_width())
        except Exception:                              # noqa: BLE001
            return False
        open_mm = float(getattr(getattr(cc, 'gripper', None), '_OPEN_WIDTH_MM', 100.0))
        return w <= open_mm

    def _repick_tool(self, sig):
        """툴 놓침(TOOL_LOST) 재개 뒤 — 곧게 위로 빠져나온 다음 '툴 집기' 단계로 되돌아간다(툴 집기 → 세제 → 닦기).

        놓친 자리는 그릇·컵 안이다. 거기서 그리퍼를 열거나 옆으로 가면 벽을 칠 수 있어 먼저 곧게 올라온다.
        툴만 다시 집고 곧장 닦기로 가면 안 된다: 닦기 함수는 세제 단계가 옮겨 준 자리(그릇·컵 바로 위)에서
        곧게 내려가므로, 홀더 자리에서 불리면 홀더 쪽으로 내려간다. 그래서 세제부터 다시 탄다.
        다시 집기가 실패하면 툴 집기 단계의 정책(TOOL_FAIL · 멈춤 → 홀더 확인 → 넛지·재개)을 그대로 탄다 — 격리하지 않는다.
        """
        self.holding, self.holding_tool = None, None       # 놓쳤다 — 쥔 것이 없다(중단 정리가 툴 반납을 하지 않게)
        if not self._retreat():                            # 곧게 못 올라왔다 → 위치를 모른다: 로봇 오류 절차
            return self._robot_error_pause(sig)
        self.log.info(f'재개 — 툴 놓침: 곧게 올라왔다 → 툴 집기부터 다시(툴 집기 → 세제 → 닦기)')
        return RETRY_TOOL_PICK

    def _recover_robot(self):
        """넛지·재개 뒤 컨트롤러가 STANDBY 로 돌아올 때까지 본다 — 보호정지(SAFE_STOP)면 자동 복구(set_robot_control).

        주의: 넛지(밀기)로 재개하면 컨트롤러 쪽 SOS(RS1 뒤 자세 유지 감시)가 아직 안 풀렸는데 바로 새 이동을
           보내 MoveIncomplete 로 끊겼다(실기) → 고정 시간이 아니라 로봇 상태를 본다. 상태를 못 읽는 환경(시험)은 그냥 지나간다.
        """
        try:
            timeout_s = float(cc.cfg()['cell']['limits']['nudge_resume_settle_s'])
        except Exception:                              # noqa: BLE001 — 설정이 없어도 셀은 선다
            timeout_s = 3.0                            # 기본 3 s
        if callable(getattr(cc, 'recover_robot_if_needed', None)):
            self._guard(cc.recover_robot_if_needed, timeout_s, what='recover_robot_if_needed')
        try:
            if callable(getattr(cc, 'wait_robot_ready', None)) and not cc.wait_robot_ready(timeout_s):
                self.log.warn(f'재개 뒤 로봇이 {timeout_s:g} s 안에 STANDBY 로 안 돌아왔다 — 그래도 이어간다')
        except Exception as e:                         # noqa: BLE001
            self.log.warn(f'로봇 상태를 읽을 수 없다({e!r}) — 그래도 이어간다')

    def _go_home_or_wait(self, sig, max_tries=3):
        """곧게 위로 → HOME. 실패하면 멈춰 사람이 펜던트로 팔을 옮긴 뒤 넛지(또는 재개)할 때까지 기다리고 HOME 만 다시 해 본다.

        🚨 로봇 오류 뒤 다음 용기 PICK 으로 곧장 가면 아무 자리에서 관절 이동을 한다(9/22 17:27 충돌의 길) — 중단 정리와 같이
           HOME 을 출발점으로 만든다.
        · 첫 시도: 후퇴(Z 위로) → HOME. 후퇴가 실패하면 로봇 위치를 모르는 것이라 HOME 을 보내지 않고 멈춘다.
        · 사람이 재개 버튼을 누른 뒤(넛지 X): 팔을 옮겼다고 보고 후퇴 없이 HOME 만. max_tries 번 다 실패하면 포기하고 로그에 남긴다
          (무한 반복 금지 — 사람이 매번 확인해도 안 되면 다음 용기 PICK 은 지금 자리에서 출발한다 · 눈으로 본다). 중단이면 False.
        """
        for attempt in range(1, max_tries + 1):
            ok = self._retreat() if attempt == 1 else True
            if ok and self.call_fn('f1', 'move_to', 'HOME', False).ok:
                return True
            if attempt == max_tries:
                self.log.error(f'HOME 복귀 {max_tries}번 실패 — 포기하고 다음 용기로 간다. 다음 PICK 은 지금 자리에서 출발한다 · 눈으로 확인')
                return False
            self.message = (f'HOME 복귀 실패({attempt}/{max_tries}) — 펜던트로 팔을 안전한 자리로 옮긴 뒤 '
                            f'화면의 재개 버튼을 누르면 후퇴 없이 HOME 으로 갑니다(넛지는 받지 않습니다)')
            self.to_paused('HOME 복귀 실패', sig)
            if self.wait_resume(sig, allow_nudge=False) == ABORTED:      # 버튼만 — 누르면 팔이 바로 움직인다(황인재 9/27 신호 2 와 같은 이유)
                return False
            self._recover_robot()
        return False

    def _track(self, fname, args, r):
        """단계 결과로 '그리퍼에 쥔 것'(holding)·'용기가 스펀지 홈에 있나'(on_bed)를 갱신한다(E52).

        pick 성공 → 용기를 쥠(홈에서 다시 집었으면 홈은 빈다) · place 성공 → 빈손, SPONGE_BED_* 면 홈 위 ·
        tool PICK/RETURN → 툴 쥠/빈손 · rack_place → 빈손. 실패한 단계는 바꾸지 않는다(그대로 쥔 것으로 본다).
        """
        if not r.ok:
            return
        if fname in ('pick', 'regrip_top'):
            self.holding, self.on_bed = 'CONTAINER', False
        elif fname == 'place':
            self.holding = None
            self.on_bed = str(args[0] if args else '').startswith('SPONGE_BED')
        elif fname == 'tool':
            self.holding = 'TOOL' if (len(args) > 1 and args[1] == PICK) else None
        elif fname == 'rack_place':
            self.holding = None

    def pause_between(self):
        """단계 사이에 flow.step_delay_s 만큼 쉰다(0 이면 안 쉼 · 시연·디버그에서 단계를 눈으로 가르기 위한 것)."""
        if self.step_delay_s:
            time.sleep(self.step_delay_s)

    # FLOW-02 — 어느 단계의 어떤 값을 기록 열로 옮길지 (SDD §4.2)
    #    (단계, 함수이름) → {Result 속성: 기록 열}
    #    주의: PICK 의 attempts 만 센다. RINSE 의 pick 은 스펀지 홈에서 다시 쥐는 것이라
    #       탐색 시도 횟수가 아니다(같은 함수라 단계로 갈라야 한다).
    _COLLECT = {
        ('PICK', 'pick'): {'attempts': 'attempts'},
        ('WEIGH', 'leftover_loop'): {'weight_before_g': 'weight_before_g',
                                     'weight_after_g': 'weight_after_g',
                                     'rounds': 'leftover_rounds'},
        ('SEAT', 'place'): {'offset_mm': 'seat_offset_mm'},
        ('WIPE', 'wipe_bowl'): {'duration_s': 'wipe_duration_s',
                                'force_log_path': 'force_log_path'},
        ('WIPE', 'wipe_cup'): {'duration_s': 'wipe_duration_s',
                               'force_log_path': 'force_log_path'},
    }

    def _collect(self, step, fname, r):
        """단계 하나의 Result 에서 기록에 쓸 값을 줍는다.

        주의: 실패한 Result 에서도 줍는다 — 격리된 용기의 기록에도 "어디까지 갔나" 가 남아야
           나중에 무엇이 문제였는지 본다(TC-12 의 "필드 누락 0" 은 성공 행만이 아니다).
        주의: 재시도로 같은 단계를 다시 불렀으면 나중 값이 이긴다(마지막 시도가 실제로 한 일).
        """
        for attr, col in (self._COLLECT.get((step, fname)) or {}).items():
            v = getattr(r, attr, None)
            if v is not None:
                self._tally[col] = v

    def emit_event(self, result):
        """용기 1개가 끝날 때마다 1건 (IRD §7 FlowEvent) + records.csv 한 줄 (SR-16)."""
        took = round(time.monotonic() - self._t0, 2) if self._t0 else 0.0
        ev = dict(kind=self.kind, zone_id=self.zone_id,
                  rack_slot=self.rack_slot if result == 'DONE' else '',
                  result=result, code=self.last_code,
                  attempts=int(self._tally.get('attempts') or 0),
                  weight_before_g=float(self._tally.get('weight_before_g') or 0.0),
                  weight_after_g=float(self._tally.get('weight_after_g') or 0.0),
                  duration_s=took,
                  force_log_path=str(self._tally.get('force_log_path') or ''))
        self._guard(self._publish_event, ev,
                    what='publish_event')      # 발행이 터져도 공정은 계속된다
        # 주의: 기록은 발행 뒤에 한다 — HMI 알림이 파일 쓰기를 기다리지 않게.
        #    둘 다 _guard 를 거치므로 하나가 터져도 다른 하나와 공정은 계속된다.
        row = dict(ev, ts=now_iso(),
                   leftover_rounds=self._tally.get('leftover_rounds', ''),
                   seat_offset_mm=self._tally.get('seat_offset_mm', ''),
                   wipe_duration_s=self._tally.get('wipe_duration_s', ''))
        self._guard(self.records.write, row, what='records.write')
