"""하중 센서 원값 탐침 — 기본은 읽기만(로봇·그리퍼 안 움직임). `--goto` 를 주면 그 자세로 **간 뒤** 읽는다 (V-02 · R2).

    soc && python3 src/cobot_common/test/rig_weigh_probe.py -n 10                           # 지금 자리에서 읽기만
    soc && python3 src/cobot_common/test/rig_weigh_probe.py -n 10 --goto WEIGH --kind BOWL  # 🚨 HOME → WEIGH(티칭 z) 로 가서 읽는다
    soc && python3 src/cobot_common/test/rig_weigh_probe.py -n 10 --goto WEIGH --kind BOWL --dz 77   # 거기서 z +77 (safe_z 235 자리)
    (용기를 쥔 채면 --carrying 을 붙인다 → 들고 가는 속도)

R2: 툴 무게 등록(ENV-05) 뒤 두 높이(z 158 · z 235) × 빈손·그릇 을 비교한다 — 자세별 차이가 등록 전(9 g vs 68 g)보다 줄었나.

--tool-force: 같은 자리에서 **툴 힘센서 Fz(BASE · N)** 도 같이 읽는다 — 하중 추정치(get_workpiece_weight)가 ±35 g 널뛰면
    (z 235 · 5 s 정지 뒤에도 74 → 4 → 36) 힘센서 쪽이 더 잔잔한지 본다. 1 N ≈ 102 g. 읽기 전용(force.read_force 와 같은 API).

왜: 첫 실기에서 그릇을 쥔 채 `get_workpiece_weight()` 가 "0.1, 0.0, 0.0" 으로 읽혔다.
    weigh.py 는 소수 첫째 자리까지만 찍어서 **단위(kg 인지 g 인지)** 를 알 수 없었다.
    여기서는 소수 4자리 원값과 시각을 그대로 보여 준다. 판정하지 않는다.
"""
import argparse
import statistics
import time

import cobot_common as cc
from cobot_common.bootstrap import dsr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=5)
    ap.add_argument('--gap', type=float, default=0.5, help='읽기 사이 대기(s)')
    ap.add_argument('--goto', metavar='STATION', help='🚨 팔이 움직인다 — HOME 을 거쳐 이 자세로 간 뒤 읽는다 (E15)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'], help='--goto 의 종류별 자세')
    ap.add_argument('--dz', type=float, default=0.0, help='--goto 뒤 BASE z 로 이만큼 더 (mm · +위)')
    ap.add_argument('--carrying', action='store_true', help='용기를 쥔 채 → 들고 가는 속도')
    ap.add_argument('--settle', type=float, default=1.0, help='도착 뒤 읽기 전 대기(s)')
    ap.add_argument('--tool-force', action='store_true', help='get_tool_force(BASE) 의 Fz 도 같이 읽는다 (N · 1 N ≈ 102 g)')
    a = ap.parse_args()
    cc.init('rig_weigh_probe')
    log = cc.io_node().get_logger()
    from f2_sense_flow.preflight import require_controller     # TS-07 — 움직이기 전 툴·TCP 확인 (f2 패키지의 문지기)
    require_controller(cc.io_node(), cc.cfg(), log)
    vals = []
    fzs = []
    try:
        d = dsr()
        if a.goto:
            log.info(f'E15 — HOME 을 거쳐 {a.goto}.{a.kind} 로 간다 (carrying={a.carrying})')
            cc.force_off()
            cc.move_to('HOME', a.carrying, a.kind)
            log.info('HOME 도착 — ' + _pose_txt(d))
            try:
                up = float(cc.move_to(a.goto, a.carrying, a.kind) or 0.0)
            except cc.MoveIncomplete:
                # 🚨 실기: WEIGH.BOWL 로 가다 그릇이 바닥에 닿아 46.6 mm 앞에서 섰다 — 어디서 섰는지
                #    숫자가 없어서 원인을 못 짚었다. 로봇은 움직이지 않고 **지금 자세만** 찍고 그대로 올린다.
                log.error('🚨 이동이 도중에 섰다 — 로봇을 움직이지 않는다. 멈춘 자세: ' + _pose_txt(d))
                raise
            if up > 0.0:
                cc.move_rel(0.0, 0.0, -up, 'BASE')        # 접근점이 있으면 끝점까지
            if a.dz:
                cc.move_rel(0.0, 0.0, a.dz, 'BASE')
            log.info(f'{a.goto} 도착 — ' + _pose_txt(d) + f' · {a.settle} s 정지 뒤 읽는다')
            time.sleep(a.settle)
        log.info(f'원값 {a.n}회 — 로봇은 움직이지 않는다')
        for i in range(a.n):
            t0 = time.monotonic()
            v = d.get_workpiece_weight()
            fz_txt = ''
            if a.tool_force:
                f = d.get_tool_force(ref=d.DR_BASE)
                if isinstance(f, (list, tuple)) and len(f) == 6:
                    fzs.append(float(f[2]))
                    fz_txt = f'   Fz {float(f[2]):+.3f} N (≈ {float(f[2]) * 101.97:+.0f} g)'
            log.info(f'  {i + 1:2d}  {v!r:>12}   ({time.monotonic() - t0:.2f} s){fz_txt}')
            if isinstance(v, (int, float)) and v >= 0:
                vals.append(float(v))
            time.sleep(a.gap)
        if vals:
            med = statistics.median(vals)
            log.info(f'중앙값 {med:.4f} · 최소 {min(vals):.4f} · 최대 {max(vals):.4f} · 폭 {max(vals) - min(vals):.4f}')
            log.info(f'→ kg 이라면 {med * 1000:.1f} g / g 이라면 {med:.1f} g')
        if fzs:
            m = statistics.median(fzs)
            log.info(f'Fz 중앙값 {m:+.3f} N (≈ {m * 101.97:+.0f} g) · 폭 {(max(fzs) - min(fzs)) * 101.97:.0f} g 상당')
    finally:
        cc.shutdown()


def _pose_txt(d):
    """지금 자세를 한 줄로 — posx(BASE) 와 관절값. 손목(J4·J6)이 어느 쪽으로 풀렸는지 보려고 관절값이 꼭 필요하다."""
    try:
        x = [round(float(v), 1) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
        j = [round(float(v), 1) for v in d.get_current_posj()]
        return f'posx {x} · posj {j}'
    except Exception as e:                      # noqa: BLE001 — 자세를 못 읽어도 탐침은 계속
        return f'(자세 읽기 실패 {e!r})'


if __name__ == '__main__':
    main()
