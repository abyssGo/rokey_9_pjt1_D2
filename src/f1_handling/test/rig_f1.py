"""F1 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    rosinfo                                                        # 🚨 먼저 RANGE=LOCALHOST(격리) 확인
    soc && python3 src/f1_handling/test/rig_f1.py pick --zone RET_B --kind BOWL      # pick 연속 3회
    soc && python3 src/f1_handling/test/rig_f1.py place --station SPONGE_BED_B
    soc && python3 src/f1_handling/test/rig_f1.py move_to --station WEIGH --carrying
    soc && python3 src/f1_handling/test/rig_f1.py tool --tool SPONGE --action PICK -n 5
    soc && python3 src/f1_handling/test/rig_f1.py tool --tool SPONGE --action CYCLE -n 10  # V-08: 집기 → 반납 한 쌍 × 10 (1회차만 Enter)
    soc && python3 src/f1_handling/test/rig_f1.py rack_place --slot RACK_B1 --kind BOWL
    soc && python3 src/f1_handling/test/rig_f1.py pick --no-robot                     # 브링업 없이 함수 반환만 확인(🚧 골격 함수만)
  Virtual 에서 (cell.yaml 의 limits·motion 이 아직 비어 있는 동안):
    soc && python3 src/f1_handling/test/rig_f1.py move_to --station WEIGH --carrying --kind CUP --fill-virtual
    soc && python3 src/f1_handling/test/rig_f1.py place --station SPONGE_BED_B --fill-virtual --no-gripper
      --fill-virtual : 비어 있는 limits·motion 만 Virtual 시험 값(cobot_common/test/rig_coords.yaml)으로 채운 임시 사본으로 돈다. 🚨 Virtual 이 아니면 거부한다
      --no-gripper   : cc.release() 를 로그만 남기는 가짜로 바꾼다(그리퍼 드라이버가 없는 환경에서 이동·순서만 볼 때)

준비(손으로): 시험할 함수의 시작 조건을 만들어 준다 — pick 은 반납 구역에 용기, place·rack_place 는 용기를 그리퍼에 쥐여 줌,
tool PICK 은 홀더에 툴. 같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).
실기에서는 속도를 낮춘다:  PREWASH_VEL_SCALE=0.3 python3 …/rig_f1.py …   (첫 실기 20~30 %)
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys

import cobot_common as cc
from cobot_api import BOWL, BRUSH, CUP, PICK, RACK_SLOTS, RET_B, RET_C, RETURN, SPONGE, STATIONS, F1Api, check_api
from f1_handling import handling

BEDS = ('SPONGE_BED_B', 'SPONGE_BED_C')
CYCLE = 'CYCLE'            # V-08 — 집기 → 반납 을 한 쌍으로 n 회. 이 시험 스크립트만의 이름(cobot_api 의 action 이 아니다)


def passed(ok, n):
    """V-08 완료 기준 "10회 ≥ 9" 를 n 회로 — 열 번에 한 번까지 실패를 허용한다(n < 10 이면 전부 성공)."""
    return ok >= n - n // 10


def _ask(log, msg):
    """Enter = 진행 · q = 그만. 입력이 없으면(파이프) 로봇을 움직이지 않고 그만둔다 — 실기에서 처음 가는 길이다."""
    log.info(f'▶ {msg} — Enter = 진행 / q = 그만')
    try:
        answer = input('    > ').strip().lower()
    except EOFError:
        answer = 'q'
    if answer == 'q':
        raise KeyboardInterrupt


def tool_cycle(tool, n, log, call=None, ask=None):
    """V-08 — 홀더에서 집기 → 홀더에 반납 을 한 쌍으로 n 회. (성공 회차 수, 회차별 기록 [(회차, 단계, 코드, 폭)]) 을 돌려준다.

    · 1회차만 집기·반납 전에 Enter 를 기다린다 — 툴 홀더 자세는 실기에서 처음 간다(cell.yaml TOOL_SPONGE.pick 의 J6 −220° 경고).
    · 집기 실패(폭이 안 맞음) → tool() 이 툴을 홀더에 두고 물러났다 → 실패로 세고 다음 회차.
    · 반납 실패 → 🚨 tool() 이 툴을 **놓지 않고** 물러났다(바닥을 못 찾음 · 힘 상한 · 시간 초과) → 툴을 든 채 더 돌지 않는다 → 중단.
    """
    call = call or handling.tool
    ask = ask or _ask
    ok, rounds = 0, []
    for i in range(1, n + 1):
        if i == 1:
            ask(log, f'1회차 집기 — {tool} 홀더로 가는 길(처음)을 볼 준비가 됐으면')
        got = call(tool, PICK)
        log.info(f'{i}/{n} 집기 → {got}')
        if not got.ok:
            rounds.append((i, PICK, got.code, got.width_mm))
            log.warn(f'{i}회차 집기 실패({got.code}) — 툴은 홀더에 두고 물러났다 → 다음 회차')
            continue
        if i == 1:
            ask(log, '1회차 반납 — 홀더로 돌아가는 길을 볼 준비가 됐으면')
        back = call(tool, RETURN)
        log.info(f'{i}/{n} 반납 → {back}')
        if not back.ok:
            rounds.append((i, RETURN, back.code, got.width_mm))
            log.error(f'{i}회차 반납 실패({back.code}) — 🚨 툴을 든 채다. 여기서 멈춘다(남은 {n - i}회는 돌지 않는다)')
            return ok, rounds
        ok += 1
        rounds.append((i, 'OK', 'OK', got.width_mm))
    return ok, rounds


def _summary(log, tool, n, ok, rounds, zero=None):
    """끝에 한 번 — 판정 · 실패 회차 · 읽은 폭(허용 오차를 정할 때 쓴다)."""
    log.info(f"결과: 성공 {ok}/{n} → {'통과' if passed(ok, n) else '실패'}(기준 {n - n // 10} 이상)")
    for i, step, code, width in rounds:
        if code != 'OK':
            log.info(f'  실패: {i}회차 {step} {code} (폭 {width:.2f} mm)')
    widths = [w for _, step, _, w in rounds if step != PICK]      # 집기에 성공한 회차의 폭
    if widths:
        lo, hi, avg = min(widths), max(widths), sum(widths) / len(widths)
        line = f'  읽은 폭(드라이버 값) 최소 {lo:.2f} · 최대 {hi:.2f} · 평균 {avg:.2f} mm · 흔들림 {hi - lo:.2f}'
        if zero is not None:
            line += f' → 영점 {zero:.2f} 뺀 폭 {lo - zero:.2f}~{hi - zero:.2f}'
        log.info(line)


def main():
    ap = argparse.ArgumentParser(description='F1 단독 시험')
    ap.add_argument('which', choices=['pick', 'place', 'move_to', 'tool', 'rack_place'])
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--zone', default=RET_B, choices=(RET_B, RET_C) + BEDS, help='pick: 반납 구역 또는 스펀지 홈(재파지)')
    ap.add_argument('--kind', default=BOWL, choices=(BOWL, CUP), help='pick · rack_place')
    ap.add_argument('--station', default='HOME', choices=STATIONS, help='place · move_to')
    ap.add_argument('--carrying', action='store_true', help='move_to: 들고 이동(저속)')
    ap.add_argument('--tool', default=SPONGE, choices=(SPONGE, BRUSH))
    ap.add_argument('--action', default=PICK, choices=(PICK, RETURN, CYCLE), help='tool: CYCLE = 집기 → 반납 한 쌍 × n (V-08)')
    ap.add_argument('--slot', default=RACK_SLOTS[0], choices=RACK_SLOTS, help='rack_place')
    ap.add_argument('--to-slot', action='store_true',
                    help='rack_place: 놓는 자세 **위에서 멈춘다**(놓지 않음 · 되돌아오지 않음) — 펜던트로 칸 자세를 새로 찍을 때')
    ap.add_argument('--hold-mm', type=float, default=20.0, help='--to-slot 에서 놓는 자세 몇 mm 위에 멈출지 (기본 20)')
    ap.add_argument('--no-robot', action='store_true', help='두산 드라이버 없이 시작(init(robot=False)) — 골격·반환값 확인용')
    ap.add_argument('--fill-virtual', action='store_true', help='비어 있는 limits·motion 을 Virtual 시험 값으로 채운 임시 설정으로 돈다(Virtual 전용)')
    ap.add_argument('--no-gripper', action='store_true', help='cc.release() 를 가짜로 — 그리퍼 드라이버 없이 이동·순서만 확인')
    a = ap.parse_args()
    if a.fill_virtual:
        _use_filled_config()

    problems = check_api(handling, F1Api)
    if problems:
        sys.exit(f'cobot_api.F1Api 약속과 다름: {problems}')

    fn = {'pick': lambda: handling.pick(a.zone, a.kind),
          'place': lambda: handling.place(a.station, a.kind),              # kind 는 종류별 자리(ISOLATE …)에서만 쓰인다
          'move_to': lambda: handling.move_to(a.station, a.carrying, a.kind),
          'tool': lambda: handling.tool(a.tool, a.action),
          'rack_place': lambda: handling.rack_place(a.slot, a.kind)}[a.which]

    cc.init('rig_f1', robot=not a.no_robot)                 # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    try:
        if not a.no_robot:                                  # 🚨 E26 문지기 — 움직이기 전에 컨트롤러의 툴·TCP 이름 확인(실기에서 두 번 풀렸다)
            from cobot_common.bootstrap import dsr          # rig 의 안전 확인용 — 기능 코드에서는 쓰지 않는다
            want = ((cc.cfg().get('flow') or {}).get('preflight') or {})          # 기대 이름은 params flow.preflight (정본은 cell.yaml 머리말)
            got_tool, got_tcp = str(dsr().get_tool()), str(dsr().get_tcp())
            bad = [f'{k} {g!r} ≠ {w!r}' for k, g, w in (('tool', got_tool, want.get('tool_name')), ('tcp', got_tcp, want.get('tcp_name'))) if w and g != w]
            if bad:
                log.error('🚨 컨트롤러 툴·TCP 이름이 다르다 — ' + ' · '.join(bad)
                          + ' → 움직이지 않는다. 펜던트에서 다시 선택(ROS set 금지 · E26): 브링업 끄고 → 선택 → Dart 닫고 → 브링업')
                return
            log.info(f'문지기 통과 — tool {got_tool!r} · tcp {got_tcp!r}')
        if a.fill_virtual:
            from cobot_common.bootstrap import dsr          # rig 의 안전 확인용 — 기능 코드에서는 쓰지 않는다
            if dsr().get_robot_system() != dsr().ROBOT_SYSTEM_VIRTUAL:
                log.error('--fill-virtual 은 Virtual 전용이다(시험 값으로 실기를 움직이지 않는다) → 실행하지 않는다')
                return
        if a.no_gripper:
            def fake_release():
                from cobot_common.bootstrap import dsr
                z = float(dsr().get_current_posx(ref=dsr().DR_BASE)[0][2]) if not a.no_robot else float('nan')
                log.info(f'  (가짜) release — 그리퍼 명령은 보내지 않았다 · 이 순간 TCP 높이 z = {z:.1f} mm')
            cc.release = fake_release                       # handling.cc 는 같은 모듈이라 같이 바뀐다
        cycle = a.which == 'tool' and a.action == CYCLE
        if not a.no_robot and (a.which in ('place', 'move_to') or cycle):
            log.info('시작 자세 HOME 으로 — 공정은 HOME 에서 시작한다(켠 직후의 곧게 편 자세는 특이점이라 직선 이동이 안 먹는다)')
            cc.move_to('HOME', False)
        if cycle:                                           # V-08 — 같은 함수 n 번이 아니라 집기 → 반납 한 쌍 n 번
            # 🚨 그리퍼 힘은 **움직이거나 닫혀 있을 때만** 읽힌다(gripper.py) → 새 프로그램에서 첫 grip 전에 release 로 한 번 움직여야 한다.
            #    실기: 이게 없어서 tool(PICK) 이 홀더 위까지 간 뒤 grip 첫 줄에서 RuntimeError 로 죽었다.
            #    실제 공정(flow_node)에서는 앞 단계(pick·place)가 이미 그리퍼를 움직였으므로 tool() 안에는 넣지 않는다 — 빈손 HOME 에서 한 번.
            log.info('빈손 HOME 에서 release 한 번 — 그리퍼 힘 읽기 준비(새 프로그램)')
            cc.release()
            ok, rounds = tool_cycle(a.tool, a.n, log)
            preset = ((cc.cfg().get('cell') or {}).get('presets') or {}).get(a.tool) or {}
            _summary(log, a.tool, a.n, ok, rounds, preset.get('grip_zero_mm'))
            return
        if a.which == 'rack_place' and a.to_slot:
            _to_slot(a.slot, a.kind, a.hold_mm, log)
            return
        for i in range(a.n):                                # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    except KeyboardInterrupt:
        log.warn('Ctrl+C 또는 q — 정지 명령을 보내고 끝낸다')
    finally:
        cc.shutdown()                                       # ③ 끝낼 때 (Ctrl+C 포함)


def _to_slot(slot_name, kind, hold_mm, log):
    """rack_place 와 **같은 길**로 칸까지 가서 놓는 자세 hold_mm 위에서 멈춘다 — 놓지 않고, 빠져나오지도 않는다.

    컵 칸(RACK_C1/C2) 놓는 자세를 펜던트로 다시 찍기 위해. 컵을 옆으로 쥔 채(pick SPONGE_BED_C 뒤)
    이 명령으로 칸 위까지 오면, 펜던트 수동으로 전환해 컵을 기둥에 앉히고 X·Y·Z·A·B·C 를 읽는다.
    길: 수조 위(RINSE 접근 235) → 컵은 rack.cup_entry_z_mm 까지 상승(그릇은 HOME 경유) → 경유점(via) → 칸 위 → (up − hold) 하강.
    """
    cell = cc.cfg()['cell']
    slot = cell['rack']['slots'][slot_name]
    cc.force_off()
    cc.safe_retreat()
    cc.move_to('RINSE', True, kind)                             # ① 수조 위 접근점 (E15 경로 그대로)
    if kind == CUP:
        entry_z = float(cell['rack']['cup_entry_z_mm'])
        dz = entry_z - float(cc.where()[2])
        if dz > 0.0:
            cc.move_rel(0.0, 0.0, dz, 'BASE')
    else:
        cc.move_to('HOME', True)
    cc.move_to(slot['via'], True)                               # ② 경유점 (관절 자세)
    up = float(cc.move_to(slot_name, True) or 0.0)              # ③ 칸 바로 위
    down = max(0.0, up - float(hold_mm))
    if down > 0.0:
        cc.move_rel(0.0, 0.0, -down, 'BASE')
    now = cc.where()
    log.info(f'{slot_name} 놓는 자세 {hold_mm:g} mm 위에서 멈췄다(놓지 않음) — 지금 posx [' + ', '.join(f'{float(v):.2f}' for v in now) + ']')
    log.info('→ 펜던트 수동으로 전환해 컵을 기둥에 앉히고 X·Y·Z·A·B·C(BASE)·J1~J6 를 기록한다. 끝나면 자동으로 되돌리고 다음 명령의 문지기가 이름을 확인한다')


def _use_filled_config():
    """진짜 설정의 사본을 만들고 비어 있는 limits·motion 만 Virtual 시험 값으로 채운다(cobot_common/test/rig_coords.py 의 방식 그대로)."""
    import os
    from pathlib import Path

    import yaml
    common_test = Path(__file__).resolve().parents[2] / 'cobot_common' / 'test'
    sys.path.insert(0, str(common_test))
    import rig_coords
    with open(common_test / 'rig_coords.yaml', encoding='utf-8') as f:
        os.environ['PREWASH_CONFIG_DIR'] = str(rig_coords._filled_copy(yaml.safe_load(f)['fill']))


if __name__ == '__main__':
    main()
