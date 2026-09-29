# -*- coding: utf-8 -*-
"""F1 그릇 가져오기 + F3 그릇 닦기 — Virtual 통합 시험.

    sod && sodvir                                              # 터미널 1 (이미 떠 있으면 그대로)
    soc && python3 src/f3_wipe/test/sim_bowl_flow.py           # 터미널 2 — 처음부터 끝까지 한 번에

F1 티칭 스크립트(CELL-04 rig_f1.py v6 의 bowl_cycle)의 픽앤플레이스 순서 그대로,
그 안의 '세척 자리 갔다 오기(BOWL_WASH_WAIT → CONTACT → WAIT)' 만 **우리 wipe_bowl()** 로 바꿨다.
좌표는 티칭으로 확정해 main cell.yaml 에 들어간 값(CELL-04 · 잔반통은 로봇 뒤로 옮긴 값):
  ① HOME → ② 반납 구역 RET_B 집기 → ③ 저울 WEIGH → ④ 잔반통 WASTE(로봇 뒤) → ⑤ HOME
  → ⑥ 스펀지 홈에 놓기 = **F1 place('SPONGE_BED_B') 제품 코드** → ⑦ 수세미 잡기 → ⑧ HOME
  → ⑨ **F3 wipe_bowl() 제품 코드** (HOME 에서 시작·끝) → ⑩ 수세미 반납
  → ⑪ 그릇 다시 잡기 → ⑫ 헹굼 RINSE → ⑬ HOME → ⑭ 팔레트 RACK_B1 → ⑮ HOME
속도는 sim_f3_seq.py 의 SPEED 칸을 같이 쓰고, 픽앤플레이스 이동은 실기 시험(rig_bowl_flow.py)과 같게 **빠른 하강 속도**로 맞춘다.

Virtual 이라 실기와 다르게 하는 것 (전부 이 파일·sim_f3_seq.py 안에서만):
  · TCP — Virtual 에는 그리퍼 TCP 가 없어 툴 끝이 210 mm 어긋난다 → 시작할 때 **GripperDA_v1 (0, 0, 210)** 을 만들어 켠다.
    cell.yaml 좌표가 전부 그리퍼 TCP 기준이라 이게 없으면 좌표가 210 mm 아래로 간다.
  · 힘 — 실기를 흉내 낸 가짜 힘(sim_f3_seq.py) · 나선 — 같은 길을 그린다(Virtual 드라이버가 amove_spiral 에 대답을 안 한다)
  · 그리퍼 — F1 티칭 rig 와 같이 Virtual 그리퍼에 **폭·열기 명령만** 보낸다(Virtual 드라이버는 힘 'i'/'d' 를 모른다).
    수세미 파지 프리셋(cell.presets.SPONGE)이 비어 있어 F1 티칭 rig 값(30 mm)을 쓴다
  · 헹굼 담금·팔레트 삽입 힘 감시는 하지 않는다(F2·F1 몫) — 자리에 가서 내려갔다 올라온다
  · 무게 재기·털기는 하지 않는다(F2 몫) — 그 자리에 가서 1 s 머문다
🚨 실기에서는 실행을 거부한다. 파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_f3_seq as sim                                                   # noqa: E402  (VEL_SCALE · SPEED · 가짜 힘 · 나선 그리기)
import rig_bowl_flow as rig                                                # noqa: E402  (실기 시험과 같은 이동 속도·파지 힘)

import cobot_common as cc                                                  # noqa: E402
from cobot_common.bootstrap import dsr                                     # noqa: E402
from f1_handling import handling                                           # noqa: E402
from f3_wipe import wipe                                                   # noqa: E402

VIRTUAL_TCP = ('GripperDA_v1', [0.0, 0.0, 210.0, 0.0, 0.0, 0.0])           # 실기 TCP 이름 · 값(티칭 좌표에서 역산 ≈ 210)
BOWL_GRIP_MM = 2.0                                                         # Virtual 그리퍼 폭 — F1 티칭 rig v6 값 그대로
SPONGE_GRIP_MM = 30.0                                                      # 🟡 cell.presets.SPONGE 가 비어 있다 — F1 티칭 rig v6 값
DWELL_S = 1.0                                                              # 저울·잔반통에서 머무는 시간 (F2 대신)

_steps = []


def _set_tcp(log):
    d = dsr()
    name, pos = VIRTUAL_TCP
    if d.get_tcp() == name:
        log.info(f'TCP {name} 이미 켜져 있다')
        return
    d.set_robot_mode(0)                                                    # TCP 등록은 수동 모드에서만 된다
    try:
        d.add_tcp(name, pos)                                               # 이미 있으면 실패해도 된다 — 바로 켠다
        d.set_tcp(name)
    finally:
        d.set_robot_mode(1)
    tcp = d.get_tcp()
    if tcp != name:
        raise RuntimeError(f'Virtual TCP 설정 실패 (지금 {tcp!r}) — 좌표가 210 mm 어긋나므로 멈춘다')
    log.info(f'Virtual TCP = {name} {pos}')


class _Grip:
    """F1 티칭 rig v6 방식 — Virtual 그리퍼 /onrobot/sendCommand 에 폭(0.1 mm 단위) 또는 'o' 만 보낸다."""

    def __init__(self, log):
        from onrobot_rg_msgs.srv import SetCommand
        self.log, self.Req = log, SetCommand.Request
        self.cli = cc.io_node().create_client(SetCommand, '/onrobot/sendCommand')
        if not self.cli.wait_for_service(timeout_sec=3.0):
            raise RuntimeError('/onrobot/sendCommand 가 안 보인다 — Virtual 그리퍼 노드 확인')

    def _send(self, cmd, what):
        req = self.Req()
        req.command = str(cmd)
        res = self.cli.call(req)
        if res is None or not res.success:
            raise RuntimeError(f'{what}: 그리퍼 명령 {cmd!r} 실패')
        time.sleep(0.4)

    def grip(self, what, width):
        self._send(int(round(float(width) * 10)), what)
        self.log.info(f'   {what} 잡기 — 폭 {width:g} mm')

    def release(self, what):
        self._send('o', what)
        self.log.info(f'   {what} 놓기')


def _step(log, label, fn):
    log.info(f'▶ {label}')
    t0 = time.monotonic()
    fn()
    _steps.append((label, time.monotonic() - t0))


def _down_up(up):
    """접근점에서 끝점까지 곧게 내려간 높이 up 을 돌려준다(0 이면 끝점에 이미 있다)."""
    if up > 0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    return up


def main() -> int:
    os.environ['PREWASH_VEL_SCALE'] = str(sim.VEL_SCALE)
    cc.init('sim_bowl_flow')
    log = cc.io_node().get_logger()
    code = 1
    try:
        d = dsr()
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
            log.error('🚨 실기다 — 이 시험은 Virtual(sodvir) 전용')
            return 2
        sim._apply_speed(log)
        rig._apply_test_values(log)                                        # 실기 시험과 같게: 이동 속도 = 빠른 하강 속도 · 파지 힘 +5 N
        sim._patch()
        _set_tcp(log)
        g = _Grip(log)
        g.release('처음 — 빈손')
        t_all = time.monotonic()

        _step(log, '① HOME', lambda: cc.move_to('HOME', False))
        x, y, z = cc.where()[:3]
        sim._home.update(x=x, y=y, z=z)
        log.info(f'   HOME 툴 끝 ({x:.1f}, {y:.1f}, {z:.1f}) · 가짜 그릇 바닥 z {z - sim.SIM_BOWL_DEPTH:.1f}')

        def pick():
            up = _down_up(float(cc.move_to('RET_B', False, point=1) or 0.0))
            g.grip('그릇', BOWL_GRIP_MM)
            if up > 0:
                cc.move_rel(0.0, 0.0, up, 'BASE')
        _step(log, '② 반납 구역 RET_B 집기', pick)
        _step(log, '③ 저울 WEIGH', lambda: (cc.move_to('WEIGH', True, 'BOWL'), time.sleep(DWELL_S)))
        _step(log, '④ 잔반통 WASTE (로봇 뒤)', lambda: (cc.move_to('WASTE', True, 'BOWL'), time.sleep(DWELL_S)))
        _step(log, '⑤ HOME', lambda: cc.move_to('HOME', True))

        def place():
            orig = cc.release
            cc.release = lambda: g.release('그릇')                          # F1 place 안의 놓기 — Virtual 그리퍼 상태에 맞춘다
            try:
                handling.place('SPONGE_BED_B')                             # ⑥ F1 제품 코드 그대로
            finally:
                cc.release = orig
        _step(log, '⑥ 스펀지 홈에 놓기 (F1 place)', place)

        def tool_pick():
            cc.move_to('TOOL_SPONGE', False, point='pick')
            g.grip('수세미', SPONGE_GRIP_MM)
        _step(log, '⑦ 수세미 잡기', tool_pick)
        _step(log, '⑧ HOME', lambda: cc.move_to('HOME', True))

        res = {}

        def wash():
            sim._sim.update(mode='bowl', z=None)
            res['r'] = wipe.wipe_bowl()                                     # ⑨ F3 제품 코드 그대로
        _step(log, '⑨ 그릇 닦기 (F3 wipe_bowl)', wash)
        r = res['r']
        log.info(f'   wipe_bowl: {r.code} · {r.duration_s:.1f} s · 평균 힘 {r.force_mean_n:.1f} N')
        if not r.ok:
            log.error(f'그릇 닦기 {r.code} — 여기서 멈춘다')
            return 1

        def tool_return():
            cc.move_to('TOOL_SPONGE', True, point='return')
            g.release('수세미')
            cc.move_rel(0.0, 0.0, float(cc.cfg()['f1']['place_clear_mm']), 'BASE')
        _step(log, '⑩ 수세미 반납', tool_return)

        def regrip():
            up = _down_up(float(cc.move_to('SPONGE_BED_B', False, point='place') or 0.0))
            g.grip('그릇 다시', BOWL_GRIP_MM)
            cc.move_rel(0.0, 0.0, up if up > 0 else float(cc.cfg()['f1']['place_clear_mm']), 'BASE')
        _step(log, '⑪ 그릇 다시 잡기', regrip)

        def rinse():
            up = _down_up(float(cc.move_to('RINSE', True, 'BOWL') or 0.0))
            time.sleep(DWELL_S)
            if up > 0:
                cc.move_rel(0.0, 0.0, up, 'BASE')
        _step(log, '⑫ 헹굼 RINSE', rinse)
        _step(log, '⑬ HOME', lambda: cc.move_to('HOME', True))

        def rack():
            _down_up(float(cc.move_to('RACK_B1', True) or 0.0))
            g.release('그릇 (팔레트)')
            for dx, dy, dz in cc.cfg()['cell']['rack']['slots']['RACK_B1'].get('exit_rel_mm') or [[0, 0, 100]]:
                cc.move_rel(float(dx), float(dy), float(dz), 'BASE')
        _step(log, '⑭ 팔레트 RACK_B1', rack)
        _step(log, '⑮ HOME', lambda: cc.move_to('HOME', False))

        log.info('구간별 시간 ─────────────')
        for label, sec in _steps:
            log.info(f'   {label:<28} {sec:6.1f} s')
        log.info('   ⑨ 안쪽 ─')
        for label, sec, note in sim._times:
            log.info(f'      {label:<24} {sec:6.1f} s   {note}')
        log.info(f'합계 {time.monotonic() - t_all:.1f} s')
        code = 0
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 힘 끄고 끝낸다')
        code = 130
    except Exception as e:                                                 # noqa: BLE001
        log.error(f'중단: {type(e).__name__}: {e}')
        import traceback
        log.error(traceback.format_exc())
    finally:
        try:
            cc.force_off()
        except Exception:                                                  # noqa: BLE001
            pass
        cc.shutdown()
    return code


if __name__ == '__main__':
    sys.exit(main())
