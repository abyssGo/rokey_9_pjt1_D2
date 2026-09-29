#!/usr/bin/env python3
"""그릇 한 바퀴 실기 — F1 실제 제품 함수(f1_handling.pick·place·tool·rack_place) + F3 자리에 soap·wipe_bowl (박진용 9/22 5차).

    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_bowl_scenario_wipe.py
    cd ~/cobot1/rokey_9_pjt1_D2 && soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_bowl_scenario_wipe.py --step

🔧 9/22 5차: 예전엔 F1 파지·이송 로직을 이 파일에 손으로 베껴 뒀는데, F1 쪽(한석형·황인재·민범진) 좌표·방식이
   바뀔 때마다(9/22 하루에만 세 번) 여기도 매번 다시 맞춰야 했다. `f1_handling.pick()`·`place()`·`tool()`·
   `rack_place()`가 이미 **cell.yaml 만 보고 동작하는 진짜 제품 함수**(PR #74)라, 이제 그걸 그대로 부른다 —
   F1 쪽 설정이 바뀌어도 이 파일은 안 바꿔도 된다. 좌표·자리 이름은 전부 cell.yaml 에 있다(patch 없음).
"""
import argparse
import sys
import time

import cobot_common as cc
from cobot_common.bootstrap import ROBOT_ID, dsr
from cobot_common.motion import MoveIncomplete
from cobot_api import BOWL, PICK, RETURN, SPONGE, TOOL_LOST
from f1_handling import handling as f1
from f3_wipe import wipe

# 상태 번호 → set_robot_control 코드(dsr_msgs2/srv/SetRobotControl.srv 주석 그대로) — motion.py 의 상태 번호와 같다.
_RECOVER_CODE = {5: 2, 3: 3, 9: 4, 10: 5, 8: 7}   # SAFE_STOP·SAFE_OFF·SAFE_STOP2·SAFE_OFF2·RECOVERY → STANDBY


def _recover_if_needed(d, timeout_s=10.0):
    """STANDBY(1)가 아니면 set_robot_control 로 풀어준다 — 이 테스트 스크립트 전용(공용 파일은 안 건드린다).

    HOME 이동 전에 한 번 부른다. 이미 정상이면 아무것도 안 한다.
    """
    state = int(d.get_robot_state())
    if state == 1:
        return
    from dsr_msgs2.srv import SetRobotControl
    client = cc.io_node().create_client(SetRobotControl, f"/{ROBOT_ID}/dsr_controller2/system/set_robot_control")
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        state = int(d.get_robot_state())
        if state == 1:
            print("[복구 완료] 로봇이 STANDBY 로 돌아왔다")
            return
        code = _RECOVER_CODE.get(state)
        if code is None:
            raise RuntimeError(f"자동 복구: 상태 {state} 는 모르는 상태다 — 사람이 확인한다")
        print(f"[SAFE_STOP 감지] 상태 {state} — 자동 복구 시도 (set_robot_control {code})")
        if not client.wait_for_service(timeout_sec=2.0):
            raise RuntimeError("자동 복구: set_robot_control 서비스가 안 보인다 — 브링업을 확인한다")
        req = SetRobotControl.Request()
        req.robot_control = code
        res = client.call(req)
        if res is None or not res.success:
            raise RuntimeError(f"자동 복구: robot_control={code} 요청 실패")
        time.sleep(0.3)
    raise RuntimeError(f"자동 복구: {timeout_s:g} s 안에 STANDBY 로 못 돌아왔다(마지막 상태 {int(d.get_robot_state())})")


def _repick(d):
    """f1.tool(SPONGE, PICK) — MoveIncomplete 면 지금 관절각을 찍고 한 번 더 시도한다(RS1 뒤 애매한 자세 대응)."""
    try:
        return f1.tool(SPONGE, PICK)
    except MoveIncomplete as e:
        j = [round(float(v), 1) for v in d.get_current_posj()]
        print(f"[재PICK 이동 끊김] {e} · 지금 J = {j}")
        print("[재시도] 같은 이동을 한 번 더")
        return f1.tool(SPONGE, PICK)


def _with_nudge_retry(step_name, fn, *args):
    """TOOL_LOST 면 넛지로 재개한다 — flow.py(handle_failure/wait_resume)와 같은 절차를 이 rig 안에서도 그대로 쓴다(E37).

    정지 → nudge_settle_s(팔 완전히 멈추기) → 넛지 감시(nudge_poll_s 간격 — 너무 빠르면 하트비트 못 보내 SAFE_STOP) →
    감지되면 STANDBY 인지 보고 아니면 set_robot_control 로 직접 풀어준다(RS1 뒤에도 저절로 STANDBY 로
    안 돌아왔다 — 9/23 실기 확인. 그냥 기다리기만 하면 다음 이동이 SAFE_STOP 으로 또 막혔다) →
    f1.tool(SPONGE, PICK) 재호출 → 끊긴 함수(fn) 다시. 진짜 flow_node 통합은 황인재 몫이다.
    """
    d = dsr()
    r = fn(*args)
    while not r.ok and r.code == TOOL_LOST:
        print(f"\n[TOOL_LOST] {step_name} 도중 놓쳤다 — 수세미를 홀더에 다시 놓고 로봇팔을 가볍게 밀어 주세요")
        lim = cc.cfg()["cell"]["limits"]
        time.sleep(float(lim["nudge_settle_s"]))
        force_n = float(lim["nudge_force_n"])
        hold_s = float(lim["nudge_hold_s"])
        poll_s = float(lim["nudge_poll_s"])
        cc.start_nudge_watch()
        while not cc.check_nudge(force_n, hold_s):
            time.sleep(poll_s)
        print("[넛지 감지] STANDBY 확인/복구 중...")
        _recover_if_needed(d, timeout_s=float(lim["nudge_resume_settle_s"]))
        print("[재PICK] 다시 집으러 간다")
        rt = _repick(d)
        print(f"[F1] tool 재PICK: {rt.code} · 폭={rt.width_mm:.2f}mm")
        if not rt.ok:
            raise RuntimeError(f"재PICK 실패 {rt.code} — 여기서 멈춘다")
        print(f"[재개] {step_name} 다시 시작")
        r = fn(*args)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=("RACK_B1", "RACK_B2"), default="RACK_B1")
    ap.add_argument("--step", action="store_true", help="구간마다 Enter 로 확인 (기본: 한 번에)")
    args = ap.parse_args()
    slot = args.slot

    cc.init("rig_bowl_scenario_wipe")

    try:
        d = dsr()
        cfg = cc.cfg()
        tcp = d.get_tcp()
        tool_setting = d.get_tool()
        vel_scale = float(cfg["run"]["vel_scale"])

        print(f"BOWL 동선 · TCP={tcp!r} · TOOL={tool_setting!r} · vel_scale={vel_scale}")

        if tcp != "GripperDA_v1" or tool_setting != "Tool Weight":
            raise RuntimeError(
                "TCP/TOOL 설정 불일치 — DART에서 GripperDA_v1 / Tool Weight를 "
                "선택하고 브링업을 다시 시작한 뒤 재실행"
            )

        _recover_if_needed(d)

        step = 0

        def ask(label):
            nonlocal step
            step += 1
            print(f"\n[STEP {step}] {label}")
            if not args.step:
                return
            cmd = input("Enter = 실행 / q = 종료 > ").strip().lower()
            if cmd == "q":
                raise KeyboardInterrupt

        ask("시작 HOME")
        cc.move_to("HOME", False)

        ask("초기 빈손 RELEASE")
        cc.release()

        ask("F1: pick(RET_B, BOWL)")
        r = f1.pick("RET_B", BOWL)
        print(f"[F1] pick: {r.code} · 폭={r.width_mm:.2f}mm")
        if not r.ok:
            raise RuntimeError(f"pick {r.code} — 여기서 멈춘다")

        ask("F1: place(SPONGE_BED_B, BOWL)")
        rp = f1.place("SPONGE_BED_B", BOWL)
        print(f"[F1] place: {rp.code}")
        if not rp.ok:
            raise RuntimeError(f"place {rp.code} — 여기서 멈춘다")

        ask("F1: tool(SPONGE, PICK)")
        rt = f1.tool(SPONGE, PICK)
        print(f"[F1] tool PICK: {rt.code} · 폭={rt.width_mm:.2f}mm")
        if not rt.ok:
            raise RuntimeError(f"tool PICK {rt.code} — 여기서 멈춘다")

        ask("F3: soap (비틀기 3회 → Z 왕복 2회 → HOME)")
        r_soap = _with_nudge_retry("soap", wipe.soap, 3, "BOWL")
        print(f"[F3] soap: {r_soap.code}")
        if not r_soap.ok:
            raise RuntimeError(f"soap {r_soap.code} — 여기서 멈춘다")

        ask("F3: wipe_bowl (HOME → 그릇 닦기 → HOME)")
        r_wipe = _with_nudge_retry("wipe_bowl", wipe.wipe_bowl)
        print(f"[F3] wipe_bowl: {r_wipe.code} · {r_wipe.duration_s:.1f} s · 평균 힘 {r_wipe.force_mean_n:.1f} N")
        if not r_wipe.ok:
            raise RuntimeError(f"wipe_bowl {r_wipe.code} — 여기서 멈춘다")

        ask("F1: tool(SPONGE, RETURN)")
        rr = f1.tool(SPONGE, RETURN)
        print(f"[F1] tool RETURN: {rr.code}")
        if not rr.ok:
            raise RuntimeError(f"tool RETURN {rr.code} — 여기서 멈춘다")

        ask("F1: pick(SPONGE_BED_B, BOWL) — 그릇 재파지")
        r2 = f1.pick("SPONGE_BED_B", BOWL)
        print(f"[F1] regrip: {r2.code} · 폭={r2.width_mm:.2f}mm")
        if not r2.ok:
            raise RuntimeError(f"regrip {r2.code} — 여기서 멈춘다")

        ask(f"F1: rack_place({slot}, BOWL)")
        r3 = f1.rack_place(slot, BOWL)
        print(f"[F1] rack_place: {r3.code}")
        if not r3.ok:
            raise RuntimeError(f"rack_place {r3.code} — 여기서 멈춘다")

        ask("HOME 복귀")
        cc.move_to("HOME", False)

        print("\nREAL BOWL 동선 시험 완료")
        return 0

    except KeyboardInterrupt:
        print("\n사용자 중단 — 자동 HOME/RELEASE 하지 않음.")
        return 130

    finally:
        cc.shutdown()


if __name__ == "__main__":
    sys.exit(main())
