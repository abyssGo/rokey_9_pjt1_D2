# -*- coding: utf-8 -*-
"""움직이기 전 문지기 — 컨트롤러의 툴·TCP 이름이 우리 좌표의 전제와 같은지 (TS-07).

왜: 실기에서 저울 자세로 가던 그릇이 바닥에 닿았다. 코드·좌표는 같은 날 아침에 6번 성공한 것과
    같았다. 원인은 다른 팀원이 펜던트에서 TCP 설정을 풀어 둔 것 — cell.yaml 의 posx 는 전부
    TCP `GripperDA_v1`(Z 208 mm) 기준이라, TCP 가 풀리면 같은 명령이 208 mm 아래를 향한다.
    여러 사람이 한 로봇을 쓰는 이상 남의 설정 실수가 내 실기를 깨뜨릴 수 있다 → 내 프로그램이
    움직이기 전에 확인하고 다르면 시작을 거부한다.

무엇: /dsr01/dsr_controller2/tool/get_current_tool · tcp/get_current_tcp 로 지금 이름을 읽어
      params.yaml flow.preflight 의 기대 이름과 비교한다. 로봇은 움직이지 않는다(조회만).
      기대 이름의 정본은 cell.yaml 머리말(ENV-05) — 여기는 그것을 확인하는 데만 쓴다.

쓰는 곳: flow_node.main (robot=True 일 때) · rig_f2 · rig_int12 · rig_weigh_probe — cc.init 직후, 첫 이동 전.
첫 이동 자체도 여기서 한다(go_home_safely) — 낮은 자세에서 HOME 으로 가다 테이블을 쓴 충돌 때문.
주의: 통신 노드의 실행기가 다른 스레드에서 돌고 있어야 동기 호출(call)이 돌아온다 — cc.init 뒤에만 부른다(gripper._send 와 같은 조건).

표기 — E-nn: 팀 결정 번호(docs/decisions/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test-reports/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
__all__ = ['PreflightError', 'check_controller', 'require_controller', 'warn_if_cable_tight', 'go_home_safely']

_SRV_PREFIX = '/dsr01/dsr_controller2/'          # 두산 드라이버 서비스 이름 (motion.py 와 같다)


class PreflightError(RuntimeError):
    """컨트롤러 설정이 기대와 다르다 — 움직이면 안 된다."""


def check_controller(node, expect, timeout_s=3.0):
    """지금 툴·TCP 이름을 읽어 기대값과 비교한다 → {'tool': (ok, 읽은 이름), 'tcp': (ok, 읽은 이름)}.

    expect : {'tool_name': 'Tool Weight', 'tcp_name': 'GripperDA_v1'} — 비어 있는 항목은 건너뛴다(검사 안 함).
    읽지 못하면(서비스 없음·응답 없음) ok=False, 이름 자리에 이유가 온다.
    """
    from dsr_msgs2.srv import GetCurrentTcp, GetCurrentTool
    plan = (('tool', 'tool_name', GetCurrentTool, 'tool/get_current_tool'),
            ('tcp', 'tcp_name', GetCurrentTcp, 'tcp/get_current_tcp'))
    out = {}
    for key, cfg_key, srv, name in plan:
        want = (expect or {}).get(cfg_key)
        if not want:
            continue
        client = node.create_client(srv, _SRV_PREFIX + name)
        try:
            if not client.wait_for_service(timeout_sec=float(timeout_s)):
                out[key] = (False, f'서비스 {_SRV_PREFIX + name} 가 안 보인다 — 브링업을 확인한다')
                continue
            res = client.call(srv.Request())
            if res is None or not getattr(res, 'success', False):
                out[key] = (False, '응답 없음 또는 success=False')
                continue
            got = str(getattr(res, 'info', ''))
            out[key] = (got == str(want), got)
        finally:
            try:
                node.destroy_client(client)
            except Exception:                        # noqa: BLE001 — 정리 실패는 결과에 영향 없다
                pass
    return out


def _is_virtual():
    """지금 붙어 있는 컨트롤러가 에뮬레이터인가. 두산 노드가 없으면(robot=False) False."""
    try:
        from cobot_common.bootstrap import dsr
        d = dsr()
        return d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
    except Exception:                                    # noqa: BLE001 — 모르면 "실기" 로 보고 확인한다(안전한 쪽)
        return False


def require_controller(node, cfg, log=None):
    """flow.preflight 설정대로 확인하고, 하나라도 다르면 PreflightError. 통과하면 읽은 이름을 돌려준다.

    설정이 없으면(flow.preflight 자체가 없음) 경고만 남기고 통과한다 — 옛 설정 파일로도 돌아가게.
    """
    pf = ((cfg or {}).get('flow') or {}).get('preflight') or {}
    if not pf:
        if log:
            log.warn('flow.preflight 가 없다 — 툴·TCP 이름을 확인하지 않고 움직인다 (TS-07)')
        return {}
    if _is_virtual():                                    # 에뮬레이터의 툴·TCP 이름은 실기 등록값과 다르다 → 가상에서는 건너뛴다
        if log:
            log.warn('Virtual 컨트롤러 — 툴·TCP 이름 확인을 건너뛴다 (실기 등록값과 다르다 · TS-07 은 실기용)')
        return {}
    got = check_controller(node, pf, pf.get('timeout_s', 3.0))
    bad = {k: v for k, (ok, v) in got.items() if not ok}
    if bad:
        want = {k: pf.get(f'{k}_name') for k in bad}
        raise PreflightError(
            '🚨 컨트롤러 설정이 우리 좌표의 전제와 다르다 — 움직이지 않는다 (TS-07).\n'
            + '\n'.join(f'   {k}: 기대 {want[k]!r} · 지금 {v!r}' for k, v in bad.items())
            + '\n   펜던트(Dart)에서 툴·TCP 를 다시 고르고, cell.yaml 머리말의 이름과 같은지 본 뒤 다시 띄운다')
    if log:
        log.info('문지기 통과 — ' + ' · '.join(f'{k} {v!r}' for k, (_, v) in got.items()))
    return {k: v for k, (_, v) in got.items()}


# ────────────────────────────────── 케이블 장력 (V-02 무게 편차의 원인)
def _read_fz():
    """툴 힘 Fz(BASE · N) 한 번 — 시험에서 바꿔 끼운다."""
    from cobot_common.bootstrap import dsr
    d = dsr()
    f = d.get_tool_force(ref=d.DR_BASE)
    if not isinstance(f, (list, tuple)) or len(f) != 6:
        raise RuntimeError(f'get_tool_force 실패값 {f!r}')
    return float(f[2])


def warn_if_cable_tight(cfg, log=None):
    """움직이기 전에 정지 상태에서 Fz 를 몇 번 읽어 흔들림(10~90 % 폭 · g)을 본다 → 넘으면 경고(멈추지 않는다).

    설정 flow.preflight.cable: {samples: 8, gap_s: 0.7, max_spread_g: 60}. 없거나 samples 0 이면 건너뛴다.
    왜: 그리퍼 케이블이 팽팽하면 팔이 서 있어도 힘센서가 ±25 g 넘게 오르내린다(실기). 문지기 뒤 HOME 에서 약 6 s —
        시작할 때 한 번이라 공정 시간은 안 든다. 무게를 잴 때마다의 검사는 cobot_common.weigh 가 같은 기준으로 한다.
    → (spread_g, samples) 또는 건너뛰면 (None, [])
    """
    import time
    cab = (((cfg or {}).get('flow') or {}).get('preflight') or {}).get('cable') or {}
    n = int(cab.get('samples') or 0)
    if n <= 0 or _is_virtual():
        return None, []
    gap = float(cab.get('gap_s') or 0.7)                 # 읽기 간격(없으면 0.7 s)
    limit = cab.get('max_spread_g')
    vals = []
    for i in range(n):
        if i:
            time.sleep(gap)
        try:
            vals.append(-_read_fz() * 101.97)            # 무게 g (−Fz · N → g 환산 101.97 · weigh.py 와 같은 부호)
        except Exception as e:                            # noqa: BLE001 — 못 읽으면 검사만 건너뛴다
            if log:
                log.warn(f'케이블 확인 — 힘을 못 읽었다({e!r}) · 건너뛴다')
            return None, vals
    s = sorted(vals)
    spread = (s[int(0.9 * (n - 1))] - s[int(0.1 * (n - 1))]) if n >= 5 else (s[-1] - s[0])
    if log:
        if limit is not None and spread > float(limit):
            log.warn(f'🔗 시작 전 힘센서 흔들림 {spread:.0f} g > {float(limit):.0f} g ({n}회 · {gap * (n - 1):.0f} s) — '
                     '그리퍼 **케이블 장력** 의심. 움직이기 전에 케이블 여유 길이를 확인한다(V-02 시험 기록)')
        else:
            log.info(f'케이블 확인 — 정지 흔들림 {spread:.0f} g ({n}회) ✅')
    return spread, vals


# ────────────────────────────────── 주의: 첫 이동 — 낮은 자세에서 HOME 으로 (테이블 충돌 뒤 추가)
def _cc():
    """cobot_common 모듈 — 시험에서 바꿔 끼운다(늦게 import 해서 드라이버 없이도 이 파일을 읽을 수 있게)."""
    import cobot_common
    return cobot_common


def go_home_safely(kind=None, log=None, carrying=True):
    """HOME 으로 간다 — 낮은 자세면 곧게 위로 빠져나온 뒤에 간다 (cc.safe_retreat → cc.move_to('HOME')).

    주의: 왜 (실기 충돌): f2.dip · f2.shake 는 수조 안 자세에서 끝난다
       (cell.stations.RINSE 끝점 z = −13.6 mm — 받침면보다 아래). 그 자리에서 cc.move_to('HOME') 을
       부르면 관절 이동이라 팔이 테이블 높이를 가로지르며 그리퍼가 상판을 쓸었다
       → 충돌 → 비상정지 → 툴 전원이 끊겨 그리퍼 드라이버(OnRobotRGControllerServer)까지 죽었다
       (`/onrobot/sendCommand 가 안 보인다` 로 드러난다).
       흐름(flow)에서는 헹굼 다음이 f1.rack_place 라 그 함수가 먼저 곧게 올라오지만,
       시험대는 직전에 어디 있었는지 모른다(dip 을 돌리고 이어서 다른 시험대를 띄운다) → 시작할 때마다 여기서 올라온다.

    어떻게: cc.safe_retreat() — 힘·순응을 끄고 XY 는 그대로 Z 만 cell.limits.safe_z_mm(235)까지 올린다.
            이미 그 위면 움직이지 않는다. 새 설정을 만들지 않고 팀이 정한 후퇴 높이를 그대로 쓴다.
    """
    cc = _cc()
    z0 = None
    try:
        z0 = float(cc.where()[2])
    except Exception:                                 # noqa: BLE001 — 못 읽어도 후퇴는 시도한다
        pass
    if log is not None and z0 is not None:
        log.info(f'지금 z {z0:.0f} mm → 안전 높이까지 곧게 올라온 뒤 HOME (테이블 충돌 이후)')
    cc.safe_retreat()                                 # 힘 끄기 + Z 만 위로 (이미 위면 안 움직인다)
    cc.move_to('HOME', carrying, kind)
