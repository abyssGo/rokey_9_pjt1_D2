"""F1 파지·이송·적재 (IRD v3.0 §3, SDD §5.2).

flow_node(메인 프로그램)나 test/rig_f1.py 가 cobot_common.init() 뒤 메인 스레드에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F1Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 좌표·숫자는 전부 cell.yaml · params.yaml 의 f1 절에서 읽는다(SDD §3.2).

물리 인계: F1 이 놓은 자리에서 F3 가 시작한다 → 단독 시험은 용기·툴을 손으로 놓아 주면 된다.
어떤 실패에서도 로봇은 안전 높이로(cc.safe_retreat), 툴 반납은 flow 가 tool(RETURN) 을 부른다.

공개 함수 다섯 개 — move_to(F1-01) · place(F1-01) · pick(F1-02) · tool(F1-03) · rack_place(F1-04) — 는 모두 구현되어
실기로 검증됐다(기록은 docs/test_logs/). 스펀지 홈 놓기는 티칭 높이의 일반 놓기로 돌며, 힘 탐색 안착(F1-05)은 넣지 않았다(place 참고).
  본문은 cobot_common 의 motion · gripper · force 함수로만 채운다:
      import cobot_common as cc
      p = cc.cfg()['cell']['zones'][zone_id]          # 숫자는 YAML 에서
      cc.move_to(...) · cc.move_rel(...) · cc.contact_down(...) · cc.grip(...) · cc.release() · cc.safe_retreat()
  주의: DSR_ROBOT2 를 직접 import 하지 않는다. 접촉 동작에는 힘 상한 + 후퇴 + 타임아웃.

실패를 돌려주는 방식 (flow.call() 의 실제 동작에 맞춘 것)
  · 공정에서 있을 수 있는 실패 = 코드로: SEAT_FAIL · TOOL_FAIL · EMPTY_ZONE · RACK_JAM · FORCE_LIMIT · TIMEOUT (Result.fail)
  · 로봇·설정이 잘못된 경우 = 예외를 그대로 위로: cc.MoveIncomplete(이동이 도중에 멈춤) · cc.MotionHalted(강제정지) ·
    cc.MoveTimeout · KeyError(cell.yaml 값이 비어 있음) · ValueError(이름·kind 가 틀림).
    flow.call() 이 받아 ROBOT_ERROR → 후퇴 → PAUSED 로 바꾸고 오류 문구를 상태 메시지(HMI 화면)에 싣는다
    — 여기서 삼켜 코드만 돌려주면 "왜 멈췄는지"가 사라진다. 주의: 그래서 이동이 실패한 뒤에는 release 하지 않는다(공중에서 놓지 않는다).

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import cobot_common as cc
from cobot_api import (BRUSH, CUP, EMPTY_ZONE, FORCE_LIMIT, GRIP_FAIL, PICK, RACK_JAM, RETURN, SPONGE, TIMEOUT, TOOL_FAIL,
                       PickResult, PlaceResult, Result, ToolResult)
from cobot_common.force import ForceLimitError, MotionTimeout      # 접촉 동작의 힘 상한·시간 초과 (코드로 바꿔 돌려준다)

_PLACE_POINT = 'place'          # 스펀지 홈(cell.beds.*)에서 '용기를 놓는 자리'의 point 이름 (cell.yaml 의 자세 적는 법)
_REGRIP_POINT = 'regrip'        # 컵은 놓을 때와 다른 방향에서 다시 잡는다(cell.beds.SPONGE_BED_C.regrip)
_TOOL_STATION = {SPONGE: 'TOOL_SPONGE', BRUSH: 'TOOL_BRUSH'}    # 툴 이름 → 홀더 자리 이름 (IRD §2 · F1-03)
# 툴 이름 → 집은 자리 posx(BASE). RETURN 은 집었던 자리로 역순으로 돌아가 놓는다(별도 반납 자세·바닥 찾기 없이).
# 같은 프로그램 안에서 PICK 한 툴만 기억한다 — 없으면(다른 프로그램이 집었음) 옛 방식(return 자세 + contact_down).
_LAST_PICK = {}


def _log():
    return cc.io_node().get_logger()


def _cell():
    return (cc.cfg() or {}).get('cell') or {}


def _need(node, key, where):
    """설정값 하나를 반드시 읽는다 — 비어 있으면 KeyError(로봇을 움직이기 전에)."""
    v = (node or {}).get(key) if isinstance(node, dict) else None
    if v is None:
        raise KeyError(f'{where}.{key} 가 비어 있다 — cell.yaml/params.yaml 을 채운 뒤에 쓴다')
    return v


def _grip_close(kind):
    """종류별 닫는 목표 폭·힘 → (목표 폭 mm · 힘 N · 판정 함수 · 영점 · 고정 폭 여부).

    BOWL(SDD §5.2 · E16): 목표 = 영점 + max(0, 기대 − 2 × 허용오차) — 기대 폭을 그대로 주면 빈손으로도 그 폭에서 멈춘다.
        판정 = |(실제 폭 − 영점) − 기대| ≤ 허용오차.
    고정 폭(E19 · 프리셋에 `grip_target_mm` 이 있을 때): 그 폭까지만 닫고 판정하지 않는다 — 컵 옆면 파지는 빈손과 구분이 안 되고 눌린다.
        컵도 그릇처럼 테두리 벽을 위에서 집는 것으로 바뀌어(CELL-05) presets.CUP 에서 grip_target_mm 을 빼고 폭 판정으로 돈다.
        종류가 아니라 프리셋 키로 방식을 고른다 — 나중에 다시 옆면 파지로 돌리려면 grip_target_mm 만 넣으면 된다.
    돌려주는 마지막 값 fixed: 고정 폭이면 True(보고 폭 = 드라이버 값) · 아니면 False(보고 폭 = 영점 뺀 값).
    """
    preset = _need(_cell().get('presets'), kind, 'cell.presets')
    where = f'cell.presets.{kind}'
    force = float(_need(preset, 'grip_force_n', where))
    zero = float(_need(preset, 'grip_zero_mm', where))
    fixed = preset.get('grip_target_mm')
    if fixed is not None:
        return float(fixed), force, (lambda got: True), zero, True
    expect = float(_need(preset, 'grip_width_mm', where))
    tol = float(_need(preset, 'width_tol_mm', where))
    target = zero + max(0.0, expect - 2.0 * tol)
    return target, force, (lambda got: abs((got - zero) - expect) <= tol), zero, False


def _grip_here(kind):
    """지금 자리에서 쥔다 → (성공 여부, 보고할 폭). 폭 판정이면 영점 뺀 폭, 고정 폭(E19)이면 드라이버 폭."""
    target, force, judge, zero, fixed = _grip_close(kind)
    got = float(cc.grip(target, force))
    ok = judge(got)
    width = got if fixed else got - zero
    _log().info(f'grip({kind}) 목표 {target:.2f} mm · {force:.0f} N → 실제 {got:.2f} mm'
                + ('' if fixed else f' · 영점 뺀 폭 {width:.2f} mm') + (' ✅' if ok else ' ✗ (빈손·헛잡음)'))
    return ok, width


def _retreat():
    """실패를 돌려주기 전에 안전 높이로 물러난다. 후퇴가 실패해도 원래 실패 코드를 잃지 않게 로그만 남긴다.

    (f2 sense.py 와 같은 방식 — flow.call() 의 후퇴는 예외가 올라올 때만 걸리는데, 우리는 코드로 돌려주기 때문에 여기서 해야 한다.)
    """
    try:
        cc.safe_retreat()
    except Exception as e:                                          # noqa: BLE001 — 후퇴 실패가 실패 코드를 덮으면 안 된다
        try:
            cc.io_node().get_logger().error(f'safe_retreat 실패 — {type(e).__name__}: {e}')
        except Exception:                                           # noqa: BLE001 — 로그가 죽어도 결과는 돌려준다
            pass


def pick(zone_id: str, kind: str) -> PickResult:
    """고정 슬롯 파지(DSN-04). 코드 OK / EMPTY_ZONE / GRIP_FAIL(재파지) / 예외(로봇 이상). — F1-02

    경로는 rig_bowl_scenario_real.py 로 실기 검증한 것 그대로, 좌표는 cell.yaml 에서 읽는다.
    절차(반납 구역 RET_*): 그리퍼 열기 → 슬롯 1번부터 —
      cc.move_to(zone_id, False, point=i) (접근점) → 남은 높이만큼 곧게 하강 → grip(프리셋)
      → 그릇·컵: 영점 뺀 폭이 기대 ± 허용오차면 성공(CUP_SIDE 고정폭 재파지는 별도) → 접근 높이로 되올라와 PickResult(width_mm, attempts=i)
      → 실패(빈손·헛잡음)면 release → 되올라와 → 다음 슬롯. 다 돌면 PickResult.fail(EMPTY_ZONE, attempts=슬롯 수).
    재파지(SPONGE_BED_*): 그릇 = point='place' 접근점 → 하강 → grip → 되올라옴 / 컵 = point='regrip'(posj) → grip
      → rack.cup_entry_z_mm 까지 올린다(낮은 자세에서 곧장 다음 자리로 가지 않게).
      재파지가 빈손이면 GRIP_FAIL(flow 정책 pause — 사람이 확인 · E12). EMPTY_ZONE 으로 하면 구역을 건너뛰어 홈에 있는 용기를 잃는다.
    주의: 이동이 실패하면(예외) release 하지 않고 그대로 올린다(머리말). 쥔 뒤의 이동 실패도 마찬가지(용기를 든 채 멈춘다).
    """
    cell = _cell()
    _grip_close(kind)                                               # 주의: 프리셋이 비었으면 움직이기 전에 KeyError
    if zone_id in (cell.get('beds') or {}):
        return _regrip(zone_id, kind)
    zone = _need(cell.get('zones'), zone_id, 'cell.zones')
    slots = zone.get('slots') or []
    if not slots:
        raise KeyError(f'cell.zones.{zone_id}.slots 가 비어 있다')
    cc.release()                                                    # 주의: 빈손으로 시작
    for i in range(1, len(slots) + 1):
        up = float(cc.move_to(zone_id, False, kind, i) or 0.0)      # 접근점 (없으면 끝점 · 0)
        if up > 0.0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')                      # 끝점(집는 자세)까지 곧게
        ok, width = _grip_here(kind)
        if ok:
            if up > 0.0:
                cc.move_rel(0.0, 0.0, up, 'BASE')                   # 쥔 채 접근 높이로 (다음 이동은 여기서 출발)
            return PickResult(width_mm=width, attempts=i)
        cc.release()                                                # 헛잡음 — 놓고 다음 슬롯
        if up > 0.0:
            cc.move_rel(0.0, 0.0, up, 'BASE')
    _log().warn(f'pick({zone_id}, {kind}) — 슬롯 {len(slots)}개 모두 빈손 → EMPTY_ZONE')
    return PickResult.fail(EMPTY_ZONE, attempts=len(slots))


def _regrip(bed: str, kind: str) -> PickResult:
    """스펀지 홈에서 다시 잡기 — pick() 의 재파지 갈래.

    종류가 아니라 홈에 `regrip` 자세가 있는지로 고른다(E29) —
      · regrip(posj) 이 있으면 그 자세에서 잡는다(옆면 파지 · 잡은 뒤 rack.cup_entry_z_mm 까지 올림)
      · 없으면 그릇처럼 놓은 자리(place 접근점 → 하강)에서 그대로 다시 잡는다 — 컵도 벽 집기로 바뀌어 이 갈래
    """
    bed_spec = ((_cell().get('beds') or {}).get(bed) or {})
    if bed_spec.get(_REGRIP_POINT):
        # 옆면 재파지는 다른 프리셋(beds.<bed>.regrip_preset · 컵은 CUP_SIDE 고정 폭 70 mm · 10 N)으로 잡는다 —
        #    반납 자리 집기(벽 · CUP 1.7 mm · 20 N)와 같은 프리셋을 쓰면 몸통(≈78 mm)에서 "헛잡음" 판정이 난다.
        #    76 mm · 5 N 은 폭에 닿자마자 위치로 멈춰 힘이 안 쓰여 이송 중 돌아갔다(실기).
        #    잡은 뒤 cc.set_grip_preset 으로 알려 주어 f2 의 HOLD/NORMAL 전환이 이 프리셋의 힘(5 N)을 쓰게 한다(35 N 이면 눌림 · E19).
        preset = bed_spec.get('regrip_preset') or kind
        cc.release()
        # 재파지 자세에 접근점(approach_posx + posx · rig_fkin 으로 posj → posx)을 두면
        #    위에서 자세를 맞추고 Z 만 내려 손가락이 컵 양옆으로 내려온다. posj 만 있으면(옛 방식) 관절 이동으로 곧장 가는데,
        #    실기에서 HOME 에서 곧장 가다 열린 그리퍼가 홈 C 의 컵에 걸려 SAFE_STOP 이 났다.
        up = float(cc.move_to(bed, False, kind, _REGRIP_POINT) or 0.0)
        free = depth = 0.0
        raw_watch = (cc.cfg().get('f1') or {}).get('regrip_watch_mm')
        watch_mm = float(raw_watch) if raw_watch is not None else 60.0        # 0 = 감시 없음(걸음 하강 자체를 없앤다) · 없으면 60 mm
        if up > 0.0 and watch_mm <= 0.0:
            # 순응 걸음 하강(3 mm ≈ 3 s × 15 = 40 s) 없이 곧게 내려가 바로 잡는다(마지막 land_slow_mm 완충).
            #    컵 XY 는 로봇이 스스로 놓은 자리(SPONGE_BED_C.place)라 어긋남이 작고 손가락 여유(110 − 70 = 양쪽 20 mm)가 있다.
            #    테두리에 얹힘 판정(GRIP_FAIL)은 없어진다 — 걸리면 로봇 충돌 감지가 마지막 보호. 실기 확인(E50).
            _descend(up)
            free = up
        elif up > 0.0:
            # 내려오는 마지막 f1.regrip_watch_mm(60)은 힘 감시(cell.limits.insert_limit_n) — 손가락이 컵 테두리에 얹히면
            #    컨트롤러 SAFE_STOP 대신 상한에서 멈춰 되올라오고 GRIP_FAIL(정책 pause · 사람이 자세 XY 확인). 컵 윗단은 잡는 높이 +45 쯤.
            cell = _cell()
            watch = min(up, watch_mm)
            free = up - watch
            if free > 0.0:
                cc.move_rel(0.0, 0.0, -free, 'BASE')
            limit_n = float(_need(cell.get('limits'), 'insert_limit_n', 'cell.limits'))
            try:
                depth, force = cc.contact_down(watch, limit_n, timeout_s=_contact_timeout(watch))   # 감시 거리에 비례한 시간 상한
            except ForceLimitError as e:
                _log().error(f'재파지({bed}) 하강 — 힘 상한: {e}')
                _after_contact_failure(free, watch)
                return PickResult.fail(FORCE_LIMIT, attempts=1)
            except MotionTimeout as e:
                _log().error(f'재파지({bed}) 하강 — 시간 초과: {e}')
                _after_contact_failure(free, watch)
                return PickResult.fail(TIMEOUT, attempts=1)
            cc.force_off()
            tol = float((cell.get('rack') or {}).get('seat_tol_mm') or 3.0)   # 닿은 깊이 허용 오차(없으면 3 mm)
            if depth < watch - tol:
                _log().warn(f'재파지({bed}) — {depth:.1f}/{watch:.1f} mm 에서 {force:.1f} N 닿음 → 손가락이 컵에 얹힌 것 · 재파지 자세 XY 확인 → GRIP_FAIL')
                cc.move_rel(0.0, 0.0, free + depth, 'BASE')
                return PickResult.fail(GRIP_FAIL, attempts=1)
        ok, width = _grip_here(preset)
        if not ok:
            cc.release()                                            # 헛잡음 — 놓고 접근점으로 올라가 GRIP_FAIL(사람이 확인)
            if up > 0.0:
                cc.move_rel(0.0, 0.0, free + depth, 'BASE')
            return PickResult.fail(GRIP_FAIL, attempts=1)
        if preset != kind:
            cc.set_grip_preset(preset)
        entry_z = float(_need(_cell().get('rack'), 'cup_entry_z_mm', 'cell.rack'))
        dz = entry_z - float(cc.where()[2])
        if dz > 0.0:
            cc.move_rel(0.0, 0.0, dz, 'BASE')                       # 재파지 뒤 cup_entry_z_mm 까지 올린 뒤 다음 자리로(낮은 자세에서 곧장 가지 않게)
        return PickResult(width_mm=width, attempts=1)
    return _regrip_at_place(bed, kind)


def _regrip_at_place(bed: str, kind: str) -> PickResult:
    """놓았던 자세(point='place')에서 위로 다시 잡는다 — 접근점 → 곧게 하강 → 종류 프리셋으로 grip → 접근점으로 되올라옴.

    반납 구역에서 집어 홈에 놓을 때와 같은 파지다(컵은 벽 집기). 빈손이면 release → 되올라와 GRIP_FAIL.
    """
    cc.release()
    up = float(cc.move_to(bed, False, kind, _PLACE_POINT) or 0.0)
    if up > 0.0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    ok, width = _grip_here(kind)
    if not ok:
        cc.release()
        if up > 0.0:
            cc.move_rel(0.0, 0.0, up, 'BASE')
        _log().warn(f'pick({bed}, {kind}) — 재파지가 빈손 → GRIP_FAIL (사람이 확인 · E12)')
        return PickResult.fail(GRIP_FAIL, attempts=1)
    if up > 0.0:
        cc.move_rel(0.0, 0.0, up, 'BASE')
    return PickResult(width_mm=width, attempts=1)


def regrip_top(bed: str, kind: str) -> PickResult:
    """스펀지 홈의 용기를 **놓았던 자세에서 위로** 다시 잡는다 — 격리 정리(flow._cleanup_and_isolate)용. 코드 OK / GRIP_FAIL.

    반납 구역에서 집어 홈에 놓을 때와 같은 파지(종류 프리셋 · 컵은 벽 집기)라 격리 구역 자세(cell.stations.ISOLATE)와 맞는다.
    헹굼 앞 재파지(pick → _regrip)는 컵을 옆면(CUP_SIDE)으로 잡는다 — 뒤집어 팔레트 기둥에 꽂기 위한 파지라 격리에는 맞지 않는다.
    그릇은 홈에 옆면 자세가 없어 pick(bed) 과 같은 길이다.
    """
    if bed not in (_cell().get('beds') or {}):
        raise KeyError(f'cell.beds.{bed} 가 없다 — regrip_top 은 스펀지 홈(SPONGE_BED_*)만 받는다')
    _grip_close(kind)                                               # 주의: 프리셋이 비었으면 움직이기 전에 KeyError
    return _regrip_at_place(bed, kind)


def place(station: str, kind: str = None) -> PlaceResult:
    """놓기 — 성공하면 항상 release 까지 한다. 코드 OK(실패는 예외로 올라간다 · 안착 놓기를 넣으면 SEAT_FAIL · FORCE_LIMIT · TIMEOUT). — F1-01(일반) · F1-05(안착)

    일반 놓기(F1-01): ① 자리의 접근점으로(cc.move_to — 접근점이 없으면 끝점까지 곧장) ② 끝점까지 곧게 하강
      ③ release ④ 내려간 만큼 되올라온다(접근점이 없던 자리는 f1.place_clear_mm 만큼 위로 — 놓은 용기를 끌지 않게). offset_mm = 0.
      kind(BOWL/CUP) = 종류별 자리(ISOLATE …)에 놓을 때. 스펀지 홈(SPONGE_BED_*)은 point='place' 자세를 쓴다.
      끝점은 티칭한 '놓는 높이'다 — 힘으로 바닥을 찾는 접촉 하강이 아니다(그건 아래 안착 놓기).
      주의: ①·② 가 실패하면(예외) release 하지 않고 그대로 위로 올린다 — 머리말의 '실패를 돌려주는 방식'.
    ISOLATE 는 그릇·컵 모두 같은 격리 자세(cell.stations.ISOLATE · 관절값)로 곧장 가서 놓는다.
    안착 놓기(F1-05 · 힘 탐색)는 넣지 않았다 — 설계는 SPONGE_BED_B/C 에서 ② 를 force_on(z) 순응 하강 + contact_down 으로 바꾸고,
      깊이 미달이면 periodic_search(cell.beds.*.seat) → 들어가면 release(offset_mm = 보정 거리) / 한도 초과면 들고 후퇴 + SEAT_FAIL.
      지금은 스펀지 홈에서도 위 일반 놓기로 돈다(범위 방어: "단순 놓기부터") — SEAT_FAIL 은 나지 않는다.
    """
    point = _PLACE_POINT if station in (cc.cfg().get('cell') or {}).get('beds', {}) else None
    clear = float(_need(cc.cfg().get('f1'), 'place_clear_mm', 'params.yaml 의 f1'))   # 값이 없으면 움직이기 전에 KeyError
    up = float(cc.move_to(station, True, kind, point) or 0.0)       # ① 접근점(없으면 끝점)
    _descend(up)                                                    # ② 끝점까지 곧게(마지막 land_slow_mm 만 살짝 느리게)
    cc.release()                                                    # ③
    cc.move_rel(0.0, 0.0, up if up > 0.0 else clear, 'BASE')        # ④ 되올라오기
    return PlaceResult(offset_mm=0.0)


def move_to(station: str, carrying: bool, kind: str = None) -> Result:
    """station 의 티칭 자세로 곧장 이동(E7 — 안전 높이를 거치지 않는다). 들고 있으면(carrying) 저속. 복귀는 move_to('HOME', False). — F1-01

    cobot_common.move_to(station, carrying, kind) 를 감싼 것(좌표는 cell.yaml 에서, 읽기만).
    kind(BOWL/CUP): 종류별 자리(WEIGH·WASTE·SOAP·RINSE·ISOLATE)로 갈 때 flow 가 넘겨 준다. HOME 처럼 종류와 무관한 자리는 생략.
    접근점이 있는 자리(스펀지 홈·팔레트 칸)는 이 함수의 대상이 아니다 — point 를 고르는 place · tool · rack_place · pick 이 맡는다
      (여기로 부르면 cc.move_to 가 "point 를 고르라"는 ValueError 를 내고 로봇은 움직이지 않는다).
    실패는 전부 예외로 올라간다(머리말) — 이동에는 '있을 수 있는 실패' 가 없다. 도착하지 못했으면 cc.MoveIncomplete.
    """
    cc.move_to(station, carrying, kind)
    return Result()


def tool(tool: str, action: str) -> ToolResult:
    """툴 픽업/반납. tool = SPONGE/BRUSH, action = PICK/RETURN. 코드 OK / TOOL_FAIL / FORCE_LIMIT / TIMEOUT. — F1-03

    PICK  : 홀더의 집는 자세(cell.stations.TOOL_*.pick)로 → 접근점이 있으면 끝점까지 하강 → grip(프리셋 힘)
            → 폭 판정이 맞으면 OK — 잡은 자리에서 끝난다(홀더에서 빼내지 않는다 · _tool_pick). 어긋나면 release(툴을 홀더에 두고) → 후퇴 → TOOL_FAIL.
            폭은 결정 E16 D-A 대로 영점(grip_zero_mm)을 빼고 본다: 명령 = 영점 + (기대 폭 − 2 × 허용오차)(SDD §5.2 "기대보다 작게"),
            판정 = |읽은 폭 − 영점 − 기대 폭| ≤ 허용오차.
            프리셋에 `grip_target_mm` 이 있으면 컵(결정 E19)처럼 그 폭까지만 닫고 폭 판정을 하지 않는다 —
            툴이 물러서 끝까지 닫으면 눌리는 경우. 어느 쪽으로 할지는 V-08 결과로 정한다(E23).
    RETURN: 이 프로그램이 집은 툴이면 집었던 자리(_LAST_PICK)로 역순으로 돌아가 놓는다(_tool_return). 아니면
            홀더의 반납 자세(cell.stations.TOOL_*.return)로 툴을 들고 → cc.contact_down 으로 홀더 바닥을 찾는다
            (접촉 힘 f1.tool_return_contact_n · 최대 깊이 = 접근점까지의 높이 또는 f1.tool_return_depth_mm ·
             힘 상한과 타임아웃은 contact_down 이 본다) → release → 되올라오기.
            주의: 바닥을 못 찾으면 release 하지 않는다(공중에서 툴을 떨어뜨리지 않는다) → 후퇴 + TOOL_FAIL.
    참고: 툴을 쥐면 툴 무게가 바뀐다 — 툴 무게 설정이 틀리면 힘 값이 틀어진다(CELL-02a §3-5).
       contact_down 은 시작할 때 대비 힘 변화량으로 본다(절대값 아님)라 이 함정은 이미 피해 간다.
    제한: 폭 판정 — grip() 머리말의 "목표 폭을 기대보다 작게" 함정: 명령한 폭과 기대 폭이 같으면 빈손으로 닫아도 통과할 수 있다.
       툴(수세미 손잡이·솔)은 그릇(벽 파지 ≈ 2 mm)과 달리 두께가 커서 빈손(≈ 0 mm)과 간격이 충분할 것으로 보고
       프리셋 값을 그렇게 정했다. V-08(집기·반납 10회)에서 빈손을 실제로 넣어 확인한다.
    """
    station = _TOOL_STATION.get(tool)
    if station is None:
        raise ValueError(f'tool: tool={tool!r} — {tuple(_TOOL_STATION)} 중 하나')
    if action not in (PICK, RETURN):
        raise ValueError(f'tool: action={action!r} — {PICK!r} 또는 {RETURN!r}')
    conf = cc.cfg()
    f1 = conf.get('f1')
    clear = float(_need(f1, 'tool_clear_mm', 'params.yaml 의 f1'))   # 필요한 값을 전부 읽은 뒤에 로봇에 손댄다
    if action == PICK:
        preset = ((conf.get('cell') or {}).get('presets') or {}).get(tool)
        if not preset:
            raise KeyError(f'cell.presets.{tool} 가 없다 — 툴 파지 폭·힘을 cell.yaml 에 채운다')
        return _tool_pick(station, tool, preset, clear)
    return _tool_return(station, f1, clear, tool)


def _tool_pick(station, tool, preset, clear) -> ToolResult:
    """툴 PICK 의 본체 — 홀더(놓친 뒤에는 처음 집었던 자리)로 가서 쥐고, 폭이 맞으면 잡은 자리에서 끝난다.

    _LAST_PICK 에 이 프로그램이 집었던 자리가 있으면(놓친 뒤 재PICK · E37) 그 위로 갔다가 곧게 내려가 잡는다.
    없으면 홀더의 pick 자세로 간다. 폭이 어긋나면 release → 후퇴 → TOOL_FAIL. 성공하면 자리를 _LAST_PICK 에 기억한다.
    """
    where = f'cell.presets.{tool}'
    force = float(_need(preset, 'grip_force_n', where))
    fixed = preset.get('grip_target_mm')
    if fixed is not None:                                           # 고정 폭(E19 방식) — 폭으로 판정하지 않는다
        target, check = float(fixed), None
    else:                                                           # 폭 판정(E16 D-A) — 값을 전부 읽은 뒤에 로봇에 손댄다
        want = float(_need(preset, 'grip_width_mm', where))
        tol = float(_need(preset, 'width_tol_mm', where))
        zero = float(_need(preset, 'grip_zero_mm', where))
        target, check = zero + max(0.0, want - 2 * tol), (want, tol, zero)
    pick = _LAST_PICK.get(tool)
    if pick:
        # 놓친 뒤(TOOL_LOST) 재PICK(E37). 놓친 자리에서 홀더 자세로 곧장
        #    관절이동하면 경로가 예측 안 된다(실기: 목표까지 16~32° 남고 MoveIncomplete 반복).
        #    맨 처음 실제로 잡았던 정확한 자리를 이미 아니까(_LAST_PICK), 힘으로 더듬을 필요 없다
        #    (실기: contact_down 이 아무 저항도 못 찾고 TIMEOUT) — 위로 갔다가 그 자리로 직선
        #    하강해 바로 잡는다.
        motion, limits = _cell().get('motion') or {}, _cell().get('limits') or {}
        vel = float(_need(motion, 'vel_tcp_max_mm_s', 'cell.motion')) * float(_need(limits, 'vel_free_pct', 'cell.limits')) / 100.0
        acc = float(_need(motion, 'acc_tcp_max_mm_s2', 'cell.motion')) * float(_need(limits, 'vel_free_pct', 'cell.limits')) / 100.0
        cc.release()                                                 # 놓친 폭에서 바로 grip 하면 거의 안 움직여 헛잡음(실기)
        above = list(pick)
        above[2] = pick[2] + clear
        cc.move_pose(above, vel, 60.0, acc, 60.0)                    # 잡았던 자리 위로(직선 · 자세 포함 · 회전 60 °/s · 60 °/s²)
        cc.move_pose(pick, vel, 60.0, acc, 60.0)                     # 그 정확한 자리로 곧장 내려간다(더듬지 않는다)
    else:
        # 두 손가락 그리퍼는 J6 를 180° 돌려도 같은 파지다(수세미 J6 −220.37° · −40.37° 둘 다 실기 통과) →
        #    cell.presets.<툴>.j6_symmetric 이 참이면 티칭 J6 ± 180·k 중 지금 손목에서 가장 가까운 것으로 간다(홈 B 에서 220° → 43°).
        j6 = {'j6_period': 180.0} if preset.get('j6_symmetric') else {}
        up = float(cc.move_to(station, False, point='pick', **j6) or 0.0)   # 빈손으로 간다
        if up > 0.0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')
    width = float(cc.grip(target, force))
    if check and abs(width - check[2] - check[0]) > check[1]:       # 헛잡음 — 툴을 홀더에 두고 물러난다
        cc.release()
        _retreat()
        return ToolResult.fail(TOOL_FAIL, width_mm=width)
    # 잡은 자리에서 끝난다 — 홀더에서 빼내지 않는다.
    #    F3 soap 이 이 자리(세제 컵 안)에서 비틀기·왕복을 하고 스스로 올라간다. 빼내던 tool_clear_mm 는 RETURN 에서만 쓴다.
    _LAST_PICK[tool] = [float(v) for v in cc.where()]               # RETURN 이 역순으로 돌아갈 자리
    return ToolResult(width_mm=width)


def _tool_return(station, f1, clear, tool=None) -> ToolResult:
    """툴 RETURN 의 본체 — 이 프로그램이 집은 툴이면 집었던 자리로 역순, 아니면 반납 자세에서 바닥을 찾아 놓는다.

    집었던 자리(_LAST_PICK)가 있으면 그 위 clear 만큼에서 곧게 내려 놓는다(f1.tool_return_depth_mm 가 양수면 마지막 그만큼은 힘 감시).
    없으면 return 자세로 툴을 들고 가서 contact_down 으로 홀더 바닥을 찾고, 못 찾으면 놓지 않고 TOOL_FAIL.
    """
    pick = _LAST_PICK.get(tool)
    if pick:                                                        # 집은 자리로 역순 — 위 clear 만큼에서 곧게 내려 놓는다
        motion, limits = _cell().get('motion') or {}, _cell().get('limits') or {}
        vel = float(_need(motion, 'vel_tcp_max_mm_s', 'cell.motion')) * float(_need(limits, 'vel_carry_pct', 'cell.limits')) / 100.0
        acc = float(_need(motion, 'acc_tcp_max_mm_s2', 'cell.motion')) * float(_need(limits, 'vel_carry_pct', 'cell.limits')) / 100.0
        above = list(pick)
        above[2] = pick[2] + clear
        cc.move_pose(above, vel, 60.0, acc, 60.0)                   # 툴을 들고 집은 자리 위로(직선 · 자세 포함)
        watch = min(clear, float(_need(f1, 'tool_return_depth_mm', 'params.yaml 의 f1')))   # 마지막 구간은 힘 감시
        limit = float(_need(f1, 'tool_return_contact_n', 'params.yaml 의 f1'))
        if watch <= 0.0:
            # 반납 자리 = 이 프로그램이 집은 바로 그 자리(posx 기억)라 바닥을 찾을 필요가 없다 →
            #    힘 감시 없이 곧게 내려가 놓는다(순응 걸음 ≈3 s × 7 = 20 s 절약 · 리허설의 반납 TIMEOUT 도 이 구간이었다).
            #    tool_return_depth_mm 을 0 으로 두면 이 갈래, 양수면 예전처럼 마지막 그만큼을 힘 감시.
            _descend(clear)                                         # 감시 없이 곧게 · 마지막 land_slow_mm 완충
            cc.release()
            cc.move_rel(0.0, 0.0, clear, 'BASE')
            _LAST_PICK.pop(tool, None)
            return ToolResult()
        cc.move_rel(0.0, 0.0, -(clear - watch), 'BASE')             # 자유 하강
        try:
            depth, _force = cc.contact_down(watch, limit, timeout_s=_contact_timeout(), step_mm=_watch_step(watch))   # 집은 z 까지 감시 하강 — 툴이 미끄러졌거나 홀더가 밀렸으면 여기서 멈춘다
        except cc.ForceLimitError as e:
            _log().error(f'툴 반납({tool}) 감시 하강 — 힘 상한: {e}')          # 사유 없이 TIMEOUT 만 보이면 원인을 못 가른다(실기) → 깊이·시간을 남긴다
            _after_contact_failure(clear - watch, watch)
            return ToolResult.fail(FORCE_LIMIT)
        except cc.MotionTimeout as e:
            _log().error(f'툴 반납({tool}) 감시 하강 — 시간 초과: {e}')
            _after_contact_failure(clear - watch, watch)
            return ToolResult.fail(TIMEOUT)
        cc.release()                                                # 집은 자리(또는 닿은 자리)에서 놓는다
        cc.move_rel(0.0, 0.0, (clear - watch) + depth, 'BASE')
        _LAST_PICK.pop(tool, None)
        return ToolResult()
    limit = float(_need(f1, 'tool_return_contact_n', 'params.yaml 의 f1'))
    depth_budget = float(_need(f1, 'tool_return_depth_mm', 'params.yaml 의 f1'))   # 주의: 값을 전부 읽은 뒤에 로봇에 손댄다
    up = float(cc.move_to(station, True, point='return') or 0.0)    # 툴을 들고 간다
    budget = up if up > 0.0 else depth_budget
    try:
        depth, _force = cc.contact_down(budget, limit)               # 힘 상한·타임아웃은 contact_down 안에서 본다
    except cc.ForceLimitError:
        _retreat()
        return ToolResult.fail(FORCE_LIMIT)
    except cc.MotionTimeout:
        _retreat()
        return ToolResult.fail(TIMEOUT)
    if depth >= budget:                                             # 주의: 바닥을 못 찾았다 → 놓지 않는다
        _retreat()
        return ToolResult.fail(TOOL_FAIL)
    cc.release()
    cc.move_rel(0.0, 0.0, depth + (0.0 if up > 0.0 else clear), 'BASE')   # 접근점이 있으면 접근점까지, 없으면 그 위로
    return ToolResult()


def _descend(dist_mm):
    """곧게 dist_mm 내려간다(순응·힘 감시 없음 · 한 번에).

    "지정된 위치에 가면 바로 놓는다 · 단계별로 내려가는 것처럼 보이지 않게" — 마지막 f1.land_slow_mm(기본 0 = 없음)만
    f1.land_vel_mm_s(배속 무관)로 살짝 느리게: 1.0 배속에서 툴·용기가 바닥에 닿는 충격(솔 반납 SAFE_STOP 의심)을 줄이는 완충.
    두 구간이지만 멈춤 없이 이어져 한 번의 하강으로 보인다. 0 으로 두면 한 구간."""
    dist = float(dist_mm)
    if dist <= 0.0:
        return
    f1 = cc.cfg().get('f1') or {}
    slow = min(float(f1.get('land_slow_mm') or 0.0), dist)
    fast = dist - slow
    if fast > 0.0:
        cc.move_rel(0.0, 0.0, -fast, 'BASE')
    if slow > 0.0:
        cc.move_rel(0.0, 0.0, -slow, 'BASE', vel_mm_s=float(f1.get('land_vel_mm_s') or 30.0))   # 완충 속도(없으면 30 mm/s)


def _watch_step(watch_mm):
    """마지막 감시 구간(툴 반납 · 팔레트 삽입)의 순응 하강 걸음(mm). → contact_down(step_mm=…) · None 이면 cell.force.contact_step_mm(3) 그대로.

    순응 하강은 한 걸음(3 mm)에 ≈3 s 걸린다(배속 무관 · 컨트롤러가 순응 상태의 '이동 끝'을 늦게 잡음).
    감시 5 mm 를 3 + 2 두 걸음으로 가면 ≈6 s 가만히 선 것처럼 보인다 → f1.watch_step_mm(5) 로 한 걸음에(≈3 s).
    걸음이 감시 거리보다 크지는 않게(min). 재파지(45 mm)·닦기 바닥 찾기는 그대로 3 mm.
    """
    s = (cc.cfg().get('f1') or {}).get('watch_step_mm')
    if not s:
        return None
    return min(float(watch_mm), float(s))


def _contact_timeout(watch_mm=None):
    """접촉 동작 타임아웃(cell.limits.timeout_s)을 배속과 감시 거리에 맞춰 늘린다.

    · 배속: 0.3 이면 contact_down 3 mm 걸음이 느려 10 s 로는 20 mm 도 못 내려간다(실기: 19.9/20 mm 시간 초과) → ÷ vel_scale(최소 1배).
    · 거리: 걸음당 ≈0.8 s(가속 제한 · 배속과 거의 무관)라 60 mm 감시(재파지)는 배속 1 에서 ≈16 s 가 필요한데
      10 s 로 잘렸다(실기: 36.9/60 mm TIMEOUT). timeout_s 는 기준 거리(params f1.contact_timeout_ref_mm · 20)에 맞춘 값이므로 감시 거리에 비례해 늘린다.
    """
    f1 = cc.cfg().get('f1') or {}
    base = float(_need(_cell().get('limits'), 'timeout_s', 'cell.limits'))
    scale = float(((cc.cfg() or {}).get('run') or {}).get('vel_scale') or 1.0)
    factor = 1.0
    if watch_mm is not None:                                        # 기준 거리(f1.contact_timeout_ref_mm · 20)보다 긴 감시만 늘린다
        ref = float(_need(f1, 'contact_timeout_ref_mm', 'f1'))
        factor = max(1.0, float(watch_mm) / ref)
    # 리허설(배속 0.5): 툴 반납 contact_down 이 20 mm 를 다 내려갔는데도 20 s 를 넘겨 TIMEOUT(사유 로그로 확인).
    #    순응 하강 한 걸음(3 mm)이 컨트롤러에서 ≈3 s 걸려 20 mm ≈ 21 s — 배속과 무관한 시간이라 "÷ vel_scale" 로는 0.5 이상에서 늘 짧다
    #    (0.3 → 33 s 통과 · 0.5 → 20 s 실패). 접촉 없이 끝까지 내려가는 경우를 덮는 최소 시간(f1.contact_timeout_min_s)을 둔다.
    floor = float(f1.get('contact_timeout_min_s') or 0.0)
    return max(base / max(min(scale, 1.0), 0.1) * factor, floor)    # 배속은 0.1~1.0 으로 자른다(÷0 방지 · 1 배 넘게는 안 줄임)


def _after_contact_failure(free, watch):
    """contact_down 이 예외로 끝난 뒤 — 순응을 끄고(켜진 채 두면 다음 task_compliance_ctrl 이 −1 로 실패했다 · 실기) 접근점 위로 되올라온다.
    내려간 깊이를 모르므로 감시 구간 전체만큼 올린다(접근점보다 최대 watch 만큼 위 — 안전)."""
    try:
        cc.force_off()
    except Exception as e:                                          # noqa: BLE001 — 끄기 실패가 실패 코드를 덮으면 안 된다
        _log().error(f'force_off 실패 — {type(e).__name__}: {e}')
    cc.move_rel(0.0, 0.0, free + watch, 'BASE')


def _near_slot(slot, within_mm=150.0):
    """지금 TCP 가 칸 접근점의 x·y 반경 안이면 True — 재시도 때 수조·경유점을 다시 거치지 않기 위해."""
    target = slot.get('approach_posx') or slot.get('posx')
    if not target:
        return False
    try:
        now = cc.where()
    except Exception:                                               # noqa: BLE001 — 못 읽으면 정상 경로
        return False
    return ((float(now[0]) - float(target[0])) ** 2 + (float(now[1]) - float(target[1])) ** 2) ** 0.5 <= within_mm


def rack_place(rack_slot: str, kind: str) -> Result:
    """팔레트 칸 삽입. 걸리면 RACK_JAM · 힘 상한 FORCE_LIMIT · 시간 초과 TIMEOUT. — F1-04

    경로는 rig_bowl_scenario_real.py 로 실기 검증한 것 그대로, 좌표는 cell.yaml 에서 읽는다.
    전제: IRD §8 순서대로 헹굼(RINSE) 뒤에 불린다 — 수조 안(낮은 자세)에서 시작하므로 먼저 수조 위로 빠져나온다.
    절차:
      ① cc.move_to('RINSE', True, kind) — 접근점(수조 바로 위)으로 곧게 올라온다 · 컵은 rack.cup_entry_z_mm 까지 더 올린다
      ② 경유점 cell.rack.slots[slot].via (관절 자세 · 손목이 도는 동안 아래가 허공이게 — J4 충돌 · B1 손목 반전은 경유점에서 · 실기)
      ③ up = cc.move_to(rack_slot, True) — 칸 바로 위(접근점) · 그릇은 그 앞에 HOME 을 거친다(수조 → 팔레트 · E15)
      ④ 하강 = (up − f1.insert_approach_mm) 자유 하강 → 마지막 insert_approach_mm 는 cc.contact_down(insert_limit_n) 으로 삽입력 감시
         · 깊이가 남았는데 힘이 먼저 닿음 = 걸림 → 내려간 만큼 되올라와 RACK_JAM
         · ForceLimitError → FORCE_LIMIT · MotionTimeout → TIMEOUT (둘 다 되올라온 뒤)
      ⑤ release → cell.rack.slots[slot].exit_rel_mm 순서대로 빠져나온다(그릇 y −25 → z +100 · 컵 z → y)
    재시도(flow retry)로 이미 칸 근처(_near_slot)에 있으면 ①~② 를 건너뛴다.
    RACK_FULL 은 여기서 판정하지 않는다(칸이 차 있으면 삽입이 걸려 RACK_JAM → 정책 retry:1 → isolate).
    """
    cell = _cell()
    slot = _need(cell.get('rack', {}).get('slots'), rack_slot, 'cell.rack.slots')
    where = f'cell.rack.slots.{rack_slot}'
    via = _need(slot, 'via', where)
    exits = slot.get('exit_rel_mm') or []
    f1 = (cc.cfg() or {}).get('f1') or {}
    approach_mm = float(_need(f1, 'insert_approach_mm', 'f1'))
    limit_n = float(_need(cell.get('limits'), 'insert_limit_n', 'cell.limits'))

    cc.force_off()
    if not _near_slot(slot):                                        # 재시도(flow retry)는 이미 칸 위에 있다 → 수조·경유점 생략(실기: 헹굼 자리로 되돌아갔다)
        cc.safe_retreat()                                           # 먼저 Z 만 safe_z(235) 로 — 낮은 채 수조 쪽으로 가면 툴 홀더(솔)에 걸린다(실기)
        cc.move_to('RINSE', True, kind)                             # ① 수조 위로 (접근점 z 235 — 같은 높이로 평행 이동)
        if kind == CUP:
            entry_z = float(_need(cell.get('rack'), 'cup_entry_z_mm', 'cell.rack'))
            dz = entry_z - float(cc.where()[2])
            if dz > 0.0:
                cc.move_rel(0.0, 0.0, dz, 'BASE')
        else:
            cc.move_to('HOME', True)                                # 그릇: 수조(오른쪽) → 팔레트(왼쪽) 사이 HOME 경유 (E15)
        cc.move_to(via, True)                                       # ② 경유점 (관절 자세)
    up = float(cc.move_to(rack_slot, True) or 0.0)                  # ③ 칸 바로 위
    free = max(0.0, up - approach_mm)
    watch = min(up, approach_mm) if up > 0.0 else 0.0
    if free > 0.0:
        if watch > 0.0:
            cc.move_rel(0.0, 0.0, -free, 'BASE')                    # ④-1 자유 하강(그 뒤 감시 구간)
        else:
            _descend(free)                                          # 감시 0 이면 곧게 끝까지 · 마지막 land_slow_mm 완충
    depth = 0.0
    try:
        if watch > 0.0:
            depth, force = cc.contact_down(watch, limit_n, timeout_s=_contact_timeout(), step_mm=_watch_step(watch))   # ④-2 삽입력 감시 (순응 ON · 마지막 구간은 한 걸음 · 시간은 배속에 맞춰 늘림)
            seated = depth >= watch - float(_need(cell.get('rack'), 'seat_tol_mm', 'cell.rack'))
            if not seated:
                _log().warn(f'rack_place({rack_slot}) — {depth:.1f}/{watch:.1f} mm 에서 {force:.1f} N 걸림 → RACK_JAM')
                cc.move_rel(0.0, 0.0, free + depth, 'BASE')         # 들고 접근점으로
                return Result.fail(RACK_JAM)
    except ForceLimitError as e:
        _log().error(f'rack_place({rack_slot}) — 힘 상한: {e}')
        _after_contact_failure(free, watch)
        return Result.fail(FORCE_LIMIT)
    except MotionTimeout as e:
        _log().error(f'rack_place({rack_slot}) — 시간 초과: {e}')
        _after_contact_failure(free, watch)
        return Result.fail(TIMEOUT)
    cc.release()                                                    # ⑤ 놓고
    for dx, dy, dz in exits:
        cc.move_rel(float(dx), float(dy), float(dz), 'BASE')        #    칸에서 빠져나온다 (순서 그대로)
    return Result()
