# -*- coding: utf-8 -*-
"""V-10 컵 안쪽 솔 삽입·문지르기 실기 시험 (F3-03 첫 단계).

    soc && python3 src/f3_wipe/test/rig_v10.py --real --stage find     # ① 바닥 찾기까지만 (맨 처음 이것부터)
    soc && python3 src/f3_wipe/test/rig_v10.py --real                  # ③ 전체 (기본 stage=scrub)
    soc && python3 src/f3_wipe/test/rig_v10.py --real --cycles 1 --stroke 5              # 값 바꿔 가며
    soc && python3 src/f3_wipe/test/rig_v10.py --real --speed 0.7                        # 세척 속도만 배수로(주기 ÷ 배수)
    soc && python3 src/f3_wipe/test/rig_v10.py --real --air                              # 컵 위 공중에서 세척 동작만(소리 확인)
    PREWASH_CONFIG_DIR=<임시 설정> python3 src/f3_wipe/test/rig_v10.py                 # Virtual(sodvir) — 흐름만

준비(손으로): 컵을 스펀지 홈에 넣고, **솔을 그리퍼에 쥐여 준다**(그리퍼 끝을 세척부 윗면에 닿게 — 세척부 95 mm).
🚨 E-Stop 에 손을 두고 본다. 값을 바꿨으면 먼저 `--air`(컵 위 공중)로 동작만 본다.

이 rig 가 확인하는 것 (V-10)
  · 초기자세 HOME → z +40 → y +140(도로 안 내려온다, 여기가 세척 시작점) 으로 컵 위에 간 뒤 fast_down_mm(120) 빠르게
    내려간 뒤 **힘으로 바닥을 찾는가** — 실측으로는 컵 위(HOME 높이 기준) ~ 바닥 90 mm(시작점이 40 높아져 120)
  · 솔이 얼마나 들어가는가 · 바닥에 닿을 때 힘이 어떻게 올라오는가
  · 세척(Move Periodic — 위아래 3 cm + 6번 조인트 좌우 ±90°, 주기 3.0 s × 5)이 컵 안에서 괜찮은가
    (제품 코드 wipe._scrub_cup 을 그대로 부른다 — 1·4번 조인트 감시 포함)
  · 컵이 홈 안에서 딸려 올라오거나 도는가 (옆 힘으로 본다)

🔸 바닥 위치는 미리 정하지 않는다 — 빠른 하강 길이만 정하고(실측 90 − 10), 나머지는 contact_down 이 찾는다.

제품 코드와 같은 공용 함수(cc.*)만 쓴다 — 여기서 정한 값이 그대로 params.yaml 의 f3.wipe_cup 으로 간다.
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import csv
import math
import os
import statistics
import sys
import time

import cobot_common as cc
from cobot_common.bootstrap import dsr
from f3_wipe.wipe import JointGuardStop, _fast_z, _scrub_cup, _Trip, cup_hops, cup_stroke

STAGES = ('find', 'scrub')
EXPECTED_TOOL, EXPECTED_TCP = 'Tool Weight', 'GripperDA_v1'
AIR_FORCE_MAX_N = 5.0           # 멈춰 있는데 이보다 크면 툴 무게 설정이 틀린 것 (V-03 과 같은 검사)


class Log:
    """힘 샘플 + 구간별 요약. 도는 중에는 힘만 읽는다(위치를 같이 읽으면 로봇이 선다)."""

    def __init__(self, p, node_log):
        self.p, self.log = p, node_log
        self.rows, self.results = [], []
        self.base = [0.0] * 6
        self.t0 = time.monotonic()

    def zero(self):
        self.base = [statistics.mean(v) for v in zip(*(cc.read_force() for _ in range(5)))]
        self.log.info(f'공중 기준값 Fz {self.base[2]:+.2f} N · 옆 {math.hypot(self.base[0], self.base[1]):.2f} N')
        return self.base

    def over_time(self):
        return time.monotonic() - self.t0 > float(self.p['duration_s'])

    def watch(self, phase):
        f = cc.read_force()
        press = abs(f[2] - self.base[2])
        lateral = math.hypot(f[0] - self.base[0], f[1] - self.base[1])
        self.rows.append([phase, round(time.monotonic() - self.t0, 3), f[0], f[1], f[2],
                          round(press, 3), round(lateral, 3)])
        if press > self.p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {self.p["limit_n"]} N')
        if lateral > self.p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {self.p["lateral_max_n"]} N '
                                     '(컵이 딸려 올라오거나 솔이 걸렸다)')
        return press, lateral

    def summarize(self, phase, since):
        vals = [(r[5], r[6]) for r in self.rows if r[0] == phase][since:]
        if not vals:
            return
        press, lat = [v[0] for v in vals], [v[1] for v in vals]
        self.results.append((phase, len(vals), statistics.mean(press), max(press), max(lat)))

    def save(self):
        os.makedirs(self.p['log_dir'], exist_ok=True)
        path = os.path.join(self.p['log_dir'], time.strftime('v10_%Y%m%d_%H%M%S.csv'))
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['phase', 't', 'fx', 'fy', 'fz', 'press_n', 'lateral_n'])
            w.writerows(self.rows)
        return path


def guards(a, log):
    """실기 안전 검사 — V-03 rig 와 같은 순서. 하나라도 걸리면 로봇을 움직이지 않는다."""
    d = dsr()
    virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
    if not virtual and not a.real:
        log.error('실기다 → --real 을 붙여야 실행한다 (E-Stop 담당·격리·저속 확인 뒤)')
        return None
    if virtual:
        log.warning('Virtual 이다 — 힘이 없어 바닥을 못 찾는다. 흐름만 본다')
    tool, tcp = d.get_tool(), d.get_tcp()
    if not virtual and (tool != EXPECTED_TOOL or tcp != EXPECTED_TCP):
        log.error(f'툴·TCP 가 {tool!r}·{tcp!r} — 기대 {EXPECTED_TOOL!r}·{EXPECTED_TCP!r}. '
                  '티치펜던트에서 맞추고 다시 (TCP 가 다르면 높이가 전부 어긋난다)')
        return None
    air = abs(statistics.mean(cc.read_force()[2] for _ in range(5)))
    if not virtual and air > AIR_FORCE_MAX_N:
        log.error(f'멈춰 있는데 |Fz| {air:.1f} N > {AIR_FORCE_MAX_N} N → 툴 무게 설정이 틀렸다. 실행 거부')
        return None
    scale = cc.cfg().get('run', {}).get('vel_scale', 1.0)
    if not virtual and scale > 0.3:
        log.error(f'vel_scale {scale:g} — 첫 실기는 0.3 이하로 (ros2 launch … vel_scale:=0.3)')
        return None
    return virtual


def main() -> int:
    ap = argparse.ArgumentParser(description='V-10 컵 솔 삽입·문지르기 (실기는 --real)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행한다')
    ap.add_argument('--stage', choices=STAGES, default='scrub', help='어디까지 할지 (기본 scrub = 전체)')
    ap.add_argument('--cycles', type=int, default=None, help='왕복 횟수 (기본 params.yaml)')
    ap.add_argument('--stroke', type=float, default=None, help='위아래 편진폭 mm')
    ap.add_argument('--lift', type=float, default=None, help='바닥을 찾은 뒤 띄우는 양 mm (세척의 가장 낮은 자리)')
    ap.add_argument('--period', type=float, default=None, help='한 번 오르내리는 시간 s')
    ap.add_argument('--air', action='store_true',
                    help='컵에 넣지 않고 컵 위 공중(+60 mm)에서 세척 동작만 — 6번 축 소리가 로봇인지 솔인지 가른다')
    ap.add_argument('--speed', type=float, default=None,
                    help='세척 속도 배수 — 주기 ÷ 배수')
    a = ap.parse_args()

    cc.init('rig_v10')                                                   # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    code, started, rec, can_move, trip = 1, False, None, True, None     # can_move=False → 정리할 때 로봇을 움직이지 않는다
    try:
        p = dict(cc.cfg()['f3']['wipe_cup'])                             # 값의 정본은 params.yaml — 인자는 덮어쓰기만
        for key, val in (('cycles', a.cycles), ('stroke_mm', a.stroke),
                         ('lift_mm', a.lift), ('period_s', a.period)):
            if val is not None:
                p[key] = val
                log.warning(f'덮어씀: {key} = {val}  (확정되면 params.yaml 에 넣는다)')
        if a.speed is not None:                                          # 세척 속도 배수 = 주기 ÷ 배수
            if not 0.2 <= a.speed <= 1.5:
                log.error(f'--speed {a.speed:g} — 0.2 ~ 1.5 사이로')
                return 2
            p['period_s'] = round(float(p['period_s']) / a.speed, 2)
            log.warning(f'덮어씀: 세척 주기 {p["period_s"]:g} s (확정되면 params.yaml 에 넣는다)')
        virtual = guards(a, log)
        if virtual is None:
            return 2
        rec = Log(p, log)
        scale = float(cc.cfg().get('run', {}).get('vel_scale', 1.0))
        log.info(f'V-10 · stage {a.stage} · vel_scale {scale:g} · 솔 세척부 {p["tool"]["clean_h_mm"]:g} mm')
        input('컵·솔 준비됐으면 엔터 → 이후 키보드에서 손을 떼고 E-Stop 에 손을 둔다 ')
        started = True

        # ── ① HOME → 컵 위 → 정한 길이만큼 빠르게 → 바닥 찾기 ───────────────────
        trip = _Trip(cup_hops(p), p)                                       # 제품 코드와 같은 길: HOME → z +40 → y +140 → z −40
        trip.go()
        if a.air:                                                        # 공중에서 돌리기 — 솔 끝이 컵 테두리보다 55 mm 위
            cc.move_rel(0.0, 0.0, 60.0, 'BASE')
            rec.zero()
            p['lift_mm'] = 0.5
            log.info('🔸 공중 시험: 컵 위 +60 mm 에서 세척 동작만 한다(컵에 닿지 않는다) — 소리가 나는지 들어 본다')
            t_air = time.monotonic()
            _scrub_cup(p, rec)
            dsr().mwait()
            log.info(f'공중 세척 끝 · 6번 축 {cc.joints()[5]:.1f}° · {time.monotonic() - t_air:.1f} s')
            code = 0
            return code
        z_top = cc.where()[2]
        rec.zero()
        fast = float(p['fast_down_mm'])
        log.info(f'컵 위 Z {z_top:.1f} → 빠르게 {fast:g} mm 내려간 뒤 힘으로 찾는다')
        _fast_z(p, -fast)                                                # 제품 코드와 같은 빠른 하강 속도
        n0 = len(rec.rows)
        found, f_n = cc.contact_down(float(p['find_max_mm']), float(p['find_limit_n']))
        z_bottom = cc.where()[2]
        rec.watch('bottom')
        rec.summarize('bottom', n0)
        log.info(f'🔸 바닥: TCP Z {z_bottom:.1f} · 빠르게 {fast:g} + 찾기 {found:.1f}/{p["find_max_mm"]:g} mm '
                 f'= 컵 위에서 {z_top - z_bottom:.1f} mm (실측 90) · 접촉 힘 {f_n:.1f} N')
        if found >= float(p['find_max_mm']) - 0.5 and not virtual:
            log.error('바닥을 못 찾았다 → 컵이 없거나 fast_down_mm 이 짧다. 확인 뒤 다시')
            return 1
        if a.stage == 'find':
            code = 0
            return code

        # ── ② ~ ⑥ 띄우기 → Periodic(위아래 + 6번 조인트 좌우) → 가장 낮은 곳 (제품 코드 wipe._scrub_cup 그대로) ──
        log.info(f'세척: 위아래 {2 * cup_stroke(p):.0f} mm · 6번 조인트 좌우 ±{float(p["spin_deg"]) / 2:g}° · '
                 f'{p["cycles"]} 회 (주기 {p["period_s"]:g} s — vel_scale 무관)')
        n0 = len(rec.rows)
        t_scrub = time.monotonic()
        _scrub_cup(p, rec)
        dsr().mwait()
        rec.summarize('cup-scrub', n0)
        log.info(f'끝: 아래쪽 끝 · 6번 축 {cc.joints()[5]:.1f}° · 문지르기 {time.monotonic() - t_scrub:.1f} s → 솔을 곧게 뽑는다')
        code = 0
    except cc.ForceLimitError as e:                                      # 로봇은 정상 — 설계된 후퇴를 한다
        log.error(f'🚨 힘 상한: {e} → 중단하고 후퇴한다')
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정리하고 끝낸다')
        code = 130
    except (cc.MoveIncomplete, cc.MotionHalted) as e:                    # 🚨 로봇이 어디 있는지 모른다
        log.error(f'중단: {type(e).__name__}: {e}')
        can_move = False
    except JointGuardStop as e:                                          # 🚨 1·4번 조인트가 움직여 멈췄다 — 손목이 꺾였을 수 있다
        log.error(f'🚨 {e}\n   → 힘만 끄고 **로봇을 움직이지 않는다**. 티치펜던트로 자세를 확인하고 사람이 컵에서 빼낸다')
        can_move = False
    except (RuntimeError, ValueError) as e:                              # 우리 코드의 검사(회전 방향·한계 등) — 위치는 안다 → 후퇴
        log.error(f'🚨 중단: {e} → 후퇴한다')                              #   🚨 MoveIncomplete·MotionHalted 도 RuntimeError 라 **반드시 그 뒤에** 둔다
    except Exception as e:                                               # 두산 DR_Error 포함 — 상태를 믿을 수 없다
        log.error(f'중단: {type(e).__name__}: {e}')
        can_move = False
    finally:
        import rclpy
        if started:
            if not rclpy.ok():                                           # DR_Error 가 rclpy.shutdown() 을 불렀다 (TS-05)
                log.error('🚨 두산 오류로 ROS 가 꺼졌다 → 힘·순응이 켜진 채일 수 있다. 새 터미널에서 바로:\n'
                          '    soc && python3 src/cobot_common/test/release_force.py --home   (E-Stop 에 손)')
            else:
                # 🚨 실기: 6번 관절이 163° 돌아 케이블이 꼬인 채 로봇이 멈췄는데 시험 도구가
                #    자동으로 HOME 으로 가려 했다(F4 가 rig_coords 8ae86d2 에서 발견·수정). 꼬인 채 움직이면 더 꼬인다.
                #    힘·순응 해제는 모션이 아니라 언제나 한다. **움직이는 것은 로봇 위치를 알 때만.**
                steps = [('힘·순응 끄기', cc.force_off)]
                if can_move or not a.real:
                    steps += [('동작 끝 대기', lambda: dsr().mwait()),
                              ('곧게 뽑아 HOME 으로', lambda: trip.back(True) if trip else cc.move_to('HOME', True))]
                for what, step in steps:
                    try:
                        step()
                    except Exception as e:
                        log.error(f'복귀 — {what} 실패: {e!r} → 눈으로 확인, 필요하면 release_force.py --home')
                if not can_move and a.real:
                    log.error('🚨 실기에서 이동이 실패했다 — 힘만 끄고 **로봇을 자동으로 움직이지 않았다.**\n'
                              '   티치펜던트로 상태(케이블 꼬임·오류)를 확인하고 사람이 복구한 뒤 다시 돌린다')
        if rec is not None and rec.rows:
            log.info(f'힘 로그: {rec.save()}')
            log.info('구간 | 샘플 | 평균 누름 N | 최대 누름 N | 최대 옆 N')
            for phase, n, mean, mx, lat in rec.results:
                log.info(f'{phase} | {n} | {mean:.2f} | {mx:.2f} | {lat:.2f}')
        cc.shutdown()                                                    # ③ 끝낼 때
    return code


if __name__ == '__main__':
    sys.exit(main())
