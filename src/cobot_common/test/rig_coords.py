#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CELL-04 · V-22 · V-19 — **진짜 cell.yaml 의 좌표**를 cc.move_to 로 흐름 순서대로 돌아본다.

확인하는 것
    ① 찍은 자세마다: 이름(+ kind · point)으로 불러서 **그 자세에 도착하는가**(닿는가 · 도중에 멈추지 않는가) — V-19 도달 범위
    ② 접근점이 있는 자세: move_to 가 돌려준 높이만큼 곧게 내려가면 **끝점**에 닿는가 → 다시 올라온다 — V-22 재현 오차
    ③ 아직 안 찍은 자세(🔴): 로봇을 **움직이지 않고** KeyError 를 내는가
도는 순서는 공정 흐름 그대로 — 그릇 한 바퀴 → 컵 한 바퀴(E7 로 안전 높이 경유가 없어져 **구간마다** 보는 것이 중요하다).

실행 — 두 가지 모드 (rosinfo 로 RANGE=LOCALHOST 확인)
  ① Virtual 시험 (기본)                sod && sodvir  →  soc && python3 src/cobot_common/test/rig_coords.py
       cell.yaml 의 limits·motion 이 비어 있어도 돌게 **rig_coords.yaml 의 시험 값으로 채운 사본**을 임시 폴더에 만들어 쓴다
       (진짜 파일은 건드리지 않는다. 좌표는 진짜 값 그대로). 🚨 Virtual 이 아니면 거부한다.
  ② 실기 확인 (V-22·V-19)              sod && sodreal →  PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_coords.py --real
       진짜 cell.yaml 을 **그대로** 쓴다(limits·motion·presets 를 채운 뒤). **구간마다 Enter** 로 확인하며 넘어간다.
       막히는 구간이 나오면 q 로 멈추고 그 자리에서 접근점을 추가로 찍는다 → `--from N` 으로 그 구간부터 다시.
       🚨 E-Stop 을 손에 잡고, 로봇 반경 안에 사람이 없는지 확인한 뒤에 시작한다.
  · 실기 절차를 미리 익히려면 Virtual 에서 `--step`(채운 값 + 구간마다 Enter)으로 예행연습한다.

끝에 **오차 표**를 찍는다(V-22 산출물). 종료 코드 0(통과) / 1(실패) / 2(실행 거부).
"""
import argparse
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REAL_CONFIG = HERE.parent / 'config'

# (이름, 들고 있나, kind, point) — 티칭 스크립트(CELL-04)의 작업 순서
ROUTE = [
    ('HOME', False, None, None),
    ('RET_B', False, None, 1), ('WEIGH', True, 'BOWL', None), ('WASTE', True, 'BOWL', None),
    ('HOME', True, None, None),        # 잔반통이 로봇 뒤라 스펀지 홈(앞)까지 직선으로 가면 몸통을 가로지른다 → HOME 을 거친다
    ('SPONGE_BED_B', True, None, 'place'),
    ('TOOL_SPONGE', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_B', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_SPONGE', True, None, 'return'), ('SPONGE_BED_B', False, None, 'place'),
    ('RINSE', True, 'BOWL', None), ('HOME', True, None, None), ('RACK_B1', True, None, None),
    ('HOME', False, None, None), ('RACK_B2', True, None, None), ('HOME', False, None, None),
    ('RET_C', False, None, 1), ('WEIGH', True, 'CUP', None), ('WASTE', True, 'CUP', None), ('SPONGE_BED_C', True, None, 'place'),
    ('TOOL_BRUSH', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_C', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_BRUSH', True, None, 'return'), ('SPONGE_BED_C', False, None, 'regrip'),
    ('RINSE', True, 'CUP', None), ('HOME', True, None, None), ('RACK_C1', True, None, None),
    ('HOME', False, None, None), ('RACK_C2', True, None, None), ('HOME', False, None, None),
    # 35~42: 공정 한 바퀴에는 안 나오지만 **티칭한 뒤 확인해야 하는** 자세들. 앞 번호가 밀리지 않게 **맨 뒤에** 붙인다.
    #   SOAP 은 원래 툴을 쥔 채 가는 자리다 — 여기서는 자리·경로만 보므로 빈손으로 가도 된다(TCP 위치는 같다).
    ('SOAP', True, 'BOWL', None), ('HOME', True, None, None),
    ('SOAP', True, 'CUP', None), ('HOME', True, None, None),
    ('ISOLATE', True, 'BOWL', None), ('HOME', False, None, None),
    ('ISOLATE', True, 'CUP', None), ('HOME', False, None, None),
]
def _untaught(cfg):
    """지금 **비어 있는** 자세 → [(station, kind, None)]. ③ 은 이 자세로 move_to 를 불러 'KeyError · 안 움직임'을 본다.

    🚨 검토에서 발견: 전에는 고정 목록(SOAP·ISOLATE)이었는데 그 자세들이 채워지자
       ③ 이 **Enter 확인 없이** 실제로 로봇을 움직이게 됐다. 그래서 목록을 설정에서 그때그때 뽑는다 —
       채워진 자세는 절대 여기 들어오지 않는다.
    """
    from cobot_common import config
    out = []
    for path in config.unfilled(cfg):
        parts = path.split('.')                           # cell.stations.<STATION>.<KIND>.<posx|posj>
        if len(parts) == 5 and parts[:2] == ['cell', 'stations'] and parts[4] in ('posx', 'posj'):
            out.append((parts[2], parts[3], None))
    return out


def _filled_copy(fill):
    """진짜 설정 폴더의 사본을 만들고, cell.yaml 의 비어 있는 limits·motion 만 fill 로 채운다 → 사본 폴더 경로."""
    tmp = Path(tempfile.mkdtemp(prefix='rig_coords_'))
    shutil.copy(REAL_CONFIG / 'params.yaml', tmp / 'params.yaml')
    with open(REAL_CONFIG / 'cell.yaml', encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    for section, values in fill.items():
        target = doc['cell'].setdefault(section, {})
        for key, value in values.items():
            if target.get(key) is None:
                target[key] = value
    with open(tmp / 'cell.yaml', 'w', encoding='utf-8') as f:
        yaml.safe_dump(doc, f, allow_unicode=True)
    return tmp


def _rotation(rx, ry, rz):
    """두산 posx 의 방향(ZYZ 오일러각, deg) → 회전 행렬."""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc_, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[ca * cb * cc_ - sa * sc, -ca * cb * sc - sa * cc_, ca * sb],
            [sa * cb * cc_ + ca * sc, -sa * cb * sc + ca * cc_, sa * sb],
            [-sb * cc_, sb * sc, cb]]


def _rot_diff_deg(p, q):
    r1, r2 = _rotation(*p[3:]), _rotation(*q[3:])
    trace = sum(r1[i][k] * r2[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def main() -> int:
    ap = argparse.ArgumentParser(description='CELL-04·V-22·V-19 좌표 순회 (기본 Virtual · --real 로 실기)')
    ap.add_argument('--real', action='store_true', help='실기: 진짜 cell.yaml 을 그대로 쓰고 구간마다 Enter 로 확인한다')
    ap.add_argument('--step', action='store_true', help='구간마다 Enter (실기는 기본으로 켜진다)')
    ap.add_argument('--from', dest='start', type=int, default=1, help='몇 번째 이동부터 돌까 (1 부터 · 막힌 구간을 고친 뒤 이어서)')
    ap.add_argument('--skip', default='', help='건너뛸 번호 (쉼표로: 3,21,31) — 좌표가 틀렸다고 이미 아는 자세를 빼고 한 번에 돈다')
    ap.add_argument('--where', action='store_true', help='로봇을 **움직이지 않고** 지금 자세(관절·좌표)만 찍고 끝낸다')
    ap.add_argument('--home', action='store_true', help='HOME 으로만 가고 끝낸다 (Enter 한 번 확인 · 속도·상태 검사는 그대로)')
    ap.add_argument('--probe', nargs=2, type=float, metavar=('J1', 'DY'),
                    help='HOME 에서 J1 을 J1° 로 돌리고 BASE y 로 DY mm 간 뒤 그 자세를 찍는다 (새 자세 찾기 — 예: --probe -260 240)')
    opt = ap.parse_args([v for v in sys.argv[1:] if not v.startswith('--ros-args')])
    opt.step = opt.step or opt.real
    skip = {int(v) for v in opt.skip.replace(' ', '').split(',') if v}

    with open(HERE / 'rig_coords.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    tmp = None if opt.real else _filled_copy(p['fill'])        # 실기는 진짜 설정 그대로 — 시험 값으로 실기를 움직이지 않는다
    if tmp is not None:
        os.environ['PREWASH_CONFIG_DIR'] = str(tmp)

    import cobot_common as cc
    from cobot_common.bootstrap import dsr      # cobot_common 자체 시험이라 내부 함수를 쓴다
    from cobot_common.motion import _named_pose, _STATE

    cc.init('rig_coords')
    log = cc.io_node().get_logger()
    tol, fails, rows = p['tol'], [], []
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not opt.real and not virtual:
            log.error('Virtual 이 아니다 → 실행하지 않는다 (실기는 --real, 값이 채워진 cell.yaml 로)')
            return 2
        if opt.real and not opt.where:              # --where 는 로봇을 움직이지 않는다 → 속도·E-Stop 확인을 요구하지 않는다
            scale = cc.cfg()['run']['vel_scale']
            log.info(f"실기 절차{' (Virtual 에서 돈다)' if virtual else ''} · vel_scale {scale:g} · 구간마다 Enter")
            if not virtual and scale > 0.3:
                log.error(f'첫 실기는 vel_scale ≤ 0.3 이다 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
                return 2
            if not virtual and input('    🚨 E-Stop 을 손에 · 로봇 반경 안에 사람 없음 · 격리(rosinfo) 확인했으면 Enter > ').strip().lower() == 'q':
                return 2

        def posx():
            return [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]

        def posj():
            return [float(v) for v in d.get_current_posj()]

        def state_ok(why):
            """로봇이 명령을 받을 수 있는 상태(STANDBY)인가. 읽기만 한다.

            🚨 실기: 브링업은 떠 있는데 **컨트롤러와의 연결이 끊겨** 있었다.
               그때 get_robot_state 는 3(SAFE_OFF)을, get_current_posj 는 [0,0,0,0,0,0] 을 돌려준다.
               그 0 을 좌표로 받아 적으면 큰일 나므로, 움직이기 전에도 읽기 전에도 여기서 막는다.
            """
            if virtual:
                return True
            s = int(d.get_robot_state())
            if s == 1:
                return True
            log.error(f'🚨 로봇이 명령을 받을 수 없는 상태다 — {why} 전에 멈춘다.')
            log.error(f'   로봇 상태 {s} = {_STATE.get(s, "알 수 없음")}')
            log.error('   상태가 1(STANDBY) 이 아니면 이 도구의 숫자는 **믿을 수 없다**(자세가 0 으로 읽힌다).')
            log.error('   먼저 볼 것: ① 티치펜던트 E-Stop·오류 ② 서보 On ③ 그래도 3 이면 브링업 재시작(killdrcf → sod && sodreal)')
            return False

        if opt.where:                                          # 로봇을 움직이지 않는다 — 지금 자세를 읽어서 찍기만 한다
            if not state_ok('자세를 읽기'):
                return 2
            log.info('지금 자세 (로봇은 움직이지 않았다)')
            log.info('  관절 posj: [' + ', '.join(f'{v:.2f}' for v in posj()) + ']')
            log.info('  좌표 posx: [' + ', '.join(f'{v:.2f}' for v in posx()) + ']')
            return 0

        def off(now, want):
            """(위치 오차 mm, 방향 오차 deg)"""
            return math.dist(now[:3], want[:3]), _rot_diff_deg(now, want)

        last_j6 = [None]

        def jinfo():
            """도착한 뒤 J3(팔꿈치)·J6(손목) — 케이블 꼬임 뒤 추가. 팔이 쭉 펴진 특이점과 손목이 크게 도는 구간을 본다."""
            j = posj()
            d = '' if last_j6[0] is None else f' (앞에서 {j[5] - last_j6[0]:+.0f}°)'
            warn = []
            if abs(j[2]) < 15:
                warn.append('🚨 팔이 쭉 펴짐')
            if last_j6[0] is not None and abs(j[5] - last_j6[0]) >= 150:
                warn.append('🚨 손목 크게 돎')
            if abs(j[5]) > 180:
                warn.append('⚠ 손목 한 바퀴 넘게 감김')
            if abs(j[3]) > 90:
                warn.append('⚠ 팔뚝이 크게 비틀림 — 다음 자세로 갈 때 100° 넘게 풀린다')
            last_j6[0] = j[5]
            return f' │ J3 {j[2]:.1f}° · J4 {j[3]:+.1f}° · J6 {j[5]:+.1f}°{d}' + ('  ' + ' '.join(warn) if warn else '')

        def _rel(key):
            """이 팔레트 칸의 상대 이동 목록(BASE) — entry_rel_mm(밀어 넣기) · exit_rel_mm(빠져나오기)."""
            slots = ((cc.cfg().get('cell') or {}).get('rack') or {}).get('slots') or {}
            return (slots.get(station) or {}).get(key) or []

        def _walk(steps, what):
            """상대 이동 목록을 순서대로 실행한다. --step 이면 단계마다 Enter(s 로 건너뛰기)."""
            for k, step_mm in enumerate(steps, start=1):
                dx, dy, dz = (float(v) for v in step_mm)
                if opt.step and input(f'    {what} {k}: \u0394({dx:g}, {dy:g}, {dz:g}) mm — Enter = 이동 / s = 건너뛰기 > ').strip().lower() == 's':
                    return False
                cc.move_rel(dx, dy, dz, 'BASE')
                log.info(f'  \u21b3 {what} {k}: \u0394({dx:g}, {dy:g}, {dz:g}) mm')
            return True

        def record(label, ok, detail):
            rows.append((label, ok, detail))
            log.info(f"{'OK  ' if ok else 'FAIL'} {label:<34} {detail}")
            if not ok:
                fails.append(label)

        if opt.real and not state_ok('첫 이동'):
            return 2

        if opt.probe:                                           # 새 자세 찾기 — 격리 자리(J1 −260° 뒤 y +240)
            j1, dy = opt.probe
            now = posj()
            if max(abs(a - b) for a, b in zip(now, (0.0, 0.0, 90.0, 0.0, 90.0, 0.0))) > 1.0:
                log.error(f'HOME 에서 시작해야 한다 — 지금 관절 [{", ".join(f"{v:.1f}" for v in now)}]. 먼저 --home')
                return 2
            log.info(f'① J1 만 0° → {j1:g}° (관절 이동 · 팔 모양은 HOME 그대로 허리만 돈다)')
            if opt.step and input('    🚨 허리가 도는 동안 팔이 지나가는 자리를 보고 Enter / q = 그만 > ').strip().lower() == 'q':
                return 2
            cc.move_joint_rel(1, j1, carrying=False)
            log.info('   도착' + jinfo())
            log.info(f'② BASE y 로 {dy:+g} mm (직선)')
            if opt.step and input('    Enter = 이동 / q = 그만(여기서 멈추고 --where 로 읽어도 된다) > ').strip().lower() == 'q':
                return 2
            cc.move_rel(0.0, dy, 0.0, 'BASE')
            log.info('   도착' + jinfo())
            log.info('찾은 자세 — cell.yaml 에 넣을 값')
            log.info('  관절 posj: [' + ', '.join(f'{v:.2f}' for v in posj()) + ']')
            log.info('  좌표 posx: [' + ', '.join(f'{v:.2f}' for v in posx()) + ']')
            return 0

        if opt.home:                                            # HOME 으로만 — 실기에서 자주 필요했다(q 를 누를 틈 없이 다음 구간으로 넘어가던 문제)
            log.info(f'HOME 으로 간다 (관절 이동) · 지금 관절 [{", ".join(f"{v:.1f}" for v in posj())}]')
            if opt.step and input('    🚨 관절 이동이라 팔 전체가 휜다 — 갈 길에 걸릴 것이 없으면 Enter / q = 그만 > ').strip().lower() == 'q':
                return 2
            # 낮은 자세(수조 안 z −14 등)에서 곧장 관절 이동하면 테이블을 가로지른다(실기 충돌)
            #    → 먼저 힘을 끄고 **Z 만 안전 높이(cell.limits.safe_z_mm)까지** 올린 뒤 HOME. 이미 위면 안 움직인다.
            log.info('  먼저 곧게 위로 (safe_retreat · 이미 높으면 안 움직임)')
            cc.safe_retreat()
            # 실기: 팔레트 컵 칸(z 249)에서 --home 을 부르니 safe_z(235)보다 이미 높아 안 올라가고
            #    관절 이동으로 곧장 가다 **팔레트에 걸렸다**. 팔레트는 HOME 보다 +200 높은 구조물 → 칸 근처(xy 200 mm 안)면 칸 위 높이(350)까지 먼저 올린다.
            #    (공정 자체는 rack_place 가 놓은 뒤 위 100 → 옆으로 빠져나온 뒤 HOME 을 부르므로 해당 없음 — 이 도구만의 지름길 문제)
            now = posx()
            slots = ((cc.cfg().get('cell') or {}).get('rack') or {}).get('slots') or {}
            tops = [sl['approach_posx'] for sl in slots.values() if sl.get('approach_posx')]
            near = [t for t in tops if ((now[0] - t[0]) ** 2 + (now[1] - t[1]) ** 2) ** 0.5 < 200.0]
            if near:
                top_z = max(t[2] for t in near)
                if now[2] < top_z:
                    log.info(f'  팔레트 칸 근처(z {now[2]:.0f}) → 칸 위 높이 {top_z:.0f} 까지 곧게 올린 뒤 HOME')
                    cc.move_rel(0.0, 0.0, top_z - now[2], 'BASE')
            cc.move_to('HOME', False)
            log.info('OK   HOME' + jinfo())
            return 0

        stopped = False
        log.info(f'──── ① ② 찍은 자세 {len(ROUTE)}번 이동 — 자세에서 자세로 곧장(E7) ────')
        for n, (station, carrying, kind, point) in enumerate(ROUTE, start=1):
            label = station + (f' {kind}' if kind else '') + (f' point={point}' if point is not None else '')
            if n < opt.start:
                continue
            if n in skip:
                log.info(f'[{n}/{len(ROUTE)}] {label} — ⏭ 건너뛴다 (--skip)')
                continue
            _, spec = _named_pose(station, kind, point)
            if opt.step:
                log.info(f'[{n}/{len(ROUTE)}] 다음 이동: {label} · {"들고" if carrying else "빈손"}')
                if input('    Enter = 이동 / q = 그만(여기 번호를 --from 에 적어 이어서) > ').strip().lower() == 'q':
                    raise KeyboardInterrupt
            if station.startswith('RACK_C'):                             # 팔레트 컵 칸: HOME 에서 **먼저 곧게 올라간 뒤** 간다 (cell.rack.via · A안)
                via = (((cc.cfg().get('cell') or {}).get('rack') or {}).get('via') or {}).get('posx')
                here = posx()
                if via and math.hypot(here[0] - via[0], here[1] - via[1]) <= 5.0 and via[2] > here[2]:
                    rise = via[2] - here[2]
                    if opt.step and input(f'    경유 자세: HOME 에서 {rise:.1f} mm 곧게 올라간다(z {via[2]:g}) — Enter = 이동 / s = 건너뛰기 > ').strip().lower() != 's':
                        cc.move_rel(0.0, 0.0, rise, 'BASE')
                        log.info(f'  ↳ 경유 자세 z {via[2]:g} — 여기서부터 손목(J4)이 돌아도 아래가 허공이다')
                elif via:
                    log.warn(f'⚠  경유 자세를 못 쓴다 — 지금 자리가 HOME 위가 아니다(수평 {math.hypot(here[0] - via[0], here[1] - via[1]):.0f} mm). HOME 에서 출발해야 한다')
            try:
                up = cc.move_to(station, carrying, kind, point)
            except Exception as e:                                      # noqa: BLE001
                if opt.real:
                    # 🚨 실기 사고: 이동이 도중에 멈춘 뒤 이 도구가 **자동으로 HOME 으로 가려 했다**.
                    #    그때 로봇은 6번 관절이 돌아 케이블이 꼬인 채 멈춰 있었다 — 자동으로 움직이면 더 꼬이거나 부딪힌다.
                    #    MoveIncomplete 의 약속대로(motion.py) 로봇 위치를 모르면 **사람이 복구**한다. 실기에서는 여기서 끝낸다.
                    record(label, False, f'move_to 오류: {type(e).__name__}: {e}')
                    log.error('🚨 실기에서 이동이 실패했다 — 로봇을 **자동으로 움직이지 않고** 여기서 멈춘다.')
                    log.error(f'   티치펜던트로 상태를 확인·복구한 뒤 이어서 돌린다:  --real --from {n}')
                    stopped = True
                    break
                if not isinstance(e, cc.MoveIncomplete):
                    record(label, False, f'move_to 오류: {type(e).__name__}: {e}')
                    continue
                if station in p['known_path_stop']:                     # (Virtual 전용) 이미 아는 경로 문제 — HOME 으로 돌아가 계속
                    log.warn(f'⚠  {label}: {e}')
                    log.warn('⚠    └ 이미 아는 경로 문제(rig_coords.yaml known_path_stop) — 실패로 세지 않고 HOME 으로 돌아가 계속한다')
                else:
                    record(label, False, f'move_to 오류: MoveIncomplete: {e}')
                cc.move_to('HOME', carrying)
                continue
            time.sleep(p['settle_s'])
            if 'posj' in spec:
                worst = max(abs(a - b) for a, b in zip(posj(), spec['posj']))
                record(label, up == 0.0 and worst <= tol['joint_deg'], f'관절 자세 · 가장 큰 오차 {worst:.2f}°' + jinfo())
                continue
            end = spec.get('posx') or spec['approach_posx']
            stop = list(spec.get('approach_posx') or end)
            dpos, drot = off(posx(), stop)
            ok = dpos <= tol['pos_mm'] and drot <= tol['rot_deg'] and abs(up - (stop[2] - end[2])) < 1e-6
            record(label, ok, f"{'접근점' if 'approach_posx' in spec else '티칭 자세'} z {stop[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}° · 남은 높이 {up:.1f} mm" + jinfo())
            if up > 0.0:                                                # ② 곧게 내려가면 끝점인가 → 다시 올라온다
                if opt.step and input(f'    끝점까지 {up:.1f} mm 내려간다 — Enter = 하강 / s = 건너뛰기 > ').strip().lower() == 's':
                    continue
                cc.move_rel(0.0, 0.0, -up, 'BASE')
                time.sleep(p['settle_s'])
                dpos, drot = off(posx(), end)
                hit = dpos <= tol['pos_mm'] and drot <= tol['rot_deg']
                if not hit and station in p['known_tilted']:             # 이미 아는 어긋남 — 재서 보여 주기만 한다
                    log.warn(f"⚠    └ {station}: 곧게 내려간 자리가 찍은 끝점과 {dpos:.2f} mm · {drot:.2f}° 어긋난다 (접근점을 끝점 위로 다시 찍는다)")
                else:
                    record(f'  └ {up:.1f} mm 하강 → 끝점', hit, f'끝점 z {end[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}°')
                if not _rel('exit_rel_mm'):                              # 빠져나오는 길이 따로 있으면 그것으로 나간다(곧게 되올라가지 않는다)
                    cc.move_rel(0.0, 0.0, up, 'BASE')

            _walk(_rel('exit_rel_mm'), '빠져나오기')                      # ④ 팔레트 칸에서 빠져나오기 (cell.yaml 의 exit_rel_mm)

        log.info('──── ③ 아직 안 찍은 자세 — 움직이지 않고 KeyError ────')
        todo = [] if stopped else _untaught(cc.cfg())
        if opt.real:                                            # 🚨 실기에서는 돌리지 않는다 — 로봇에게 '거부하는지' 물어볼 이유가 없다
            log.info('   실기에서는 건너뛴다(빈 자세 확인은 Virtual·자동 시험이 한다)')
            todo = []
        elif not todo:
            log.info('   빈 자세 없음 — 건너뛴다')
        for station, kind, point in todo:
            try:                                                # 움직이기 전에 **설정만** 본다 — 값이 있으면 절대 move_to 를 부르지 않는다
                _named_pose(station, kind, point)
                log.warn(f'   {station} {kind}: 값이 있다 — 움직이지 않고 건너뛴다')
                continue
            except KeyError:
                pass
            before = posj()
            try:
                cc.move_to(station, False, kind, point)
                refused = False
            except KeyError:
                refused = True
            still = max(abs(a - b) for a, b in zip(posj(), before)) < 0.01
            record(f'{station} {kind or ""} {point or ""}'.strip() + ' (안 찍음)', refused and still, 'KeyError · 안 움직임' if refused and still else '움직였거나 오류가 안 났다')

        log.info('──── 오차 표 (V-22 산출물 — 기록 문서에 붙인다) ────')
        for label, ok, detail in rows:
            log.info(f"  {'OK  ' if ok else 'FAIL'} | {label:<34} | {detail}")
        n_ok = sum(1 for _, ok, _ in rows if ok)
        log.info(f"결과: {'통과' if not fails else '실패'} — OK {n_ok} · FAIL {len(fails)}" + (f' → {fails}' if fails else ''))
        return 0 if not fails else 1
    except KeyboardInterrupt:
        log.warn('사람이 멈췄다(q 또는 Ctrl+C)')
        return 130
    finally:
        cc.shutdown()
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
