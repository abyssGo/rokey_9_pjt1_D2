#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-03 — 힘제어를 켠 채 X·Y 로 움직일 수 있는가 (솔로 그릇 안쪽 바닥을 누르며 문지르기). 실기 전용 · Virtual 은 흐름만.

실행 (저장소 루트, 격리 상태 solo — docs/env/M0609_환경설정.md)
    Virtual 흐름 확인 :  sod && sodvir  →  soc && python3 src/cobot_common/test/rig_v03.py
    Virtual + 가짜 벽 :  soc && python3 src/cobot_common/test/rig_v03.py --fake-wall   (나선 → 벽 → 2바퀴 흐름·시간)
                         그릇 크기를 바꿔 보려면  --fake-wall --fake-bowl-d 200   (안지름 mm)
    실기             :  sod && sodreal →  soc && python3 src/cobot_common/test/rig_v03.py --real
준비(로봇 정지 상태): 그릇 중심을 HOME 바로 아래에 테이프로 고정 · 솔을 그리퍼에 쥐여 둔다('o' → 넣고 → 'c')
        · rig_v03.yaml 의 approach_down_mm = (솔 끝 → 그릇 안쪽 바닥) − 30 mm
🚨 엔터를 누른 뒤에는 키보드에서 손을 떼고 한 손은 E-Stop, 눈은 로봇. 속도는 vel_scale 0.3(바꾸려면 PREWASH_VEL_SCALE).

흐름: HOME → 빠른 접근(approach_down_mm) → contact_down(바닥 찾기, 못 찾으면 힘제어 없이 중단)
      → 닿은 채 제자리 누르기 → 누른 채 손목을 ±scrub_deg 로 비틀며 중심에서 나선으로 넓혀 가기
      → 반지름 방향 힘이 (가운데에서 배운 마찰 + wall_margin_n) 을 넘으면 벽 → 그 자리에서 바로 벽에 붙어 2바퀴 → 후퇴 → HOME
걸음은 blend_radius_mm 로 이어 붙여 멈추지 않고 움직인다.
솔은 낮은 원통이라 손목(6축) 비틀림 각도는 닦기에 상관없다 — 따로 되돌리지 않고 HOME(관절 이동)이 0 으로 돌려 놓는다.
힘은 닿은 채 켠다(force.py 는 절대값 ABS: 목표 = 실제 누르는 힘). 1차 실기에서 3 mm 위(공중)에서 상대 모드로 켰더니
3 s 안에 바닥까지 못 내려가 공중에서 8자를 그렸다 → 방식 변경.
누르는 힘 = 공중에서 잰 기준값 대비 Fz 변화. 어느 순간이든 limit_n 을 넘으면 즉시 힘 해제 → 후퇴.
🚨 두산 API 의 DR_Error 는 생기는 순간 rclpy.shutdown() 을 부른다 → 이 프로세스로는 힘·순응을 못 끈다.
   그때는 화면 안내대로 release_force.py(--home) 를 새로 실행한다.
설정은 같은 폴더의 rig_v03_config/(시험 전용 cell.yaml) · rig_v03.yaml. 힘 로그는 log_dir 에 CSV.
종료 코드 0(통과) / 1(실패·중단) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import csv
import math
import os
import statistics
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ['PREWASH_CONFIG_DIR'] = str(HERE / 'rig_v03_config')      # cc.init 이 설정을 읽기 전에
os.environ.setdefault('PREWASH_VEL_SCALE', '0.3')                     # 첫 실기 저속

import cobot_common as cc                                               # noqa: E402
from cobot_common.bootstrap import dsr                                  # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다


class Run:
    """한 번의 V-03 실행: 힘 기록·구간 통계·CSV."""

    def __init__(self, d, p, log):
        self.d, self.p, self.log = d, p, log
        self.rows = []
        self.results = []
        self.baseline = 0.0
        self.t0 = time.monotonic()
        self.fake_wall_r = None                                          # Virtual 가짜 벽 반지름 mm (--fake-wall)
        self.climb = 0.0                                                 # 바닥에서 올라간 높이 mm (check 가 갱신)
        self.gap = 0.0                                                   # 반지름 방향으로 못 따라간 거리 mm (check 가 갱신)
        self.z_now = 0.0                                                 # 지금 실제 Z — 다음 걸음의 Z 명령으로 그대로 쓴다
        self.compliance_on = False                                       # 직접 켠 순응
        self.force_ctrl_on = False                                       # 직접 켠 힘제어
        self.z_contact = 0.0                                             # contact_down 으로 바닥을 찾은 높이

    def z(self):
        return self.d.get_current_posx(ref=self.d.DR_BASE)[0][2]

    def move_z(self, dz, vel, acc):
        s = cc.cfg()['run']['vel_scale']
        ret = self.d.movel([0.0, 0.0, float(dz), 0.0, 0.0, 0.0], vel=vel * s, acc=acc,
                           ref=self.d.DR_BASE, mod=self.d.DR_MV_MOD_REL)
        if ret != 0:
            raise RuntimeError(f'movel(Z {dz:+.1f} mm) 실패')

    def zero(self):
        """공중에서 Fz·Fx·Fy 기준값을 잡는다(툴 무게·옵셋 제거)."""
        fs = [cc.read_force() for _ in range(5)]
        self.baseline = statistics.mean(f[2] for f in fs)
        self.fx0 = statistics.mean(f[0] for f in fs)
        self.fy0 = statistics.mean(f[1] for f in fs)

    # ------------------------------------------------------------ 나선 문지르기 · 벽 찾기 · 벽 따라 돌기
    def scrub_to(self, x, y, phase='spiral'):
        """중심 기준 (x, y) 로 한 걸음 가면서 **동시에** 손목을 ±scrub_deg 로 비튼다 — movel 한 번(BASE 절대 좌표).

        목표 = [중심 X + x, 중심 Y + y, 바닥 Z, A, B, C + 비틀기]. 툴 Z 축 회전은 ZYZ 의 C 에 더하면 된다
        (Rz(A)·Ry(B)·Rz(C)·Rz(q) = Rz(A)·Ry(B)·Rz(C + q)).
        🚨 Z 는 **힘제어가 정한다** — 명령에는 '지금 실제 Z'를 넣는다. 처음 닿은 높이를 계속 명령하면
        힘제어(더 눌러 내려가려 함)와 위치 명령(그 높이로 끌어올림)이 싸워 작업대를 쿵쿵 친다(실기).
        🔸 blend_radius_mm(> 0) 이면 목표 앞 그 거리에서 다음 걸음으로 **이어서** 간다(멈췄다 가는 뚝뚝 끊김 없앰).
        🔸 손목은 twist_every 걸음마다 한 번만 방향을 바꾼다 — 걸음마다 바꾸면 이어 붙이기가 비틀기를 지워 버리고(Virtual 실측),
           매 걸음 회전을 세웠다 돌리느라 덜컹거린다(실기 소음).
        순응 중 관절 이동(movej) 금지라 직교 이동만. 한 걸음마다 힘을 읽어 기록하고 (누르는 힘, 옆 힘, 반지름 방향 힘) 을 돌려준다.
        """
        p, d, s = self.p, self.d, cc.cfg()['run']['vel_scale']
        vel = [p['scrub_lin_vel_mm_s'] * s, p['scrub_rot_vel_deg_s'] * s]
        acc = [p['scrub_lin_acc_mm_s2'], p['scrub_rot_acc_deg_s2']]
        self.step_i += 1
        if self.step_i % max(1, int(p['twist_every'])) == 0:
            self.twist = -self.twist
        rz = p['scrub_deg'] * self.twist
        x0, y0, _z0, a, b, c = self.p0
        target = [x0 + x, y0 + y, self.z_now, a, b, (c + rz + 180.0) % 360.0 - 180.0]
        if d.movel(target, vel=vel, acc=acc, radius=p['blend_radius_mm'], ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS) != 0:
            raise RuntimeError('movel(한 걸음 + 손목 비틀기) 실패')
        self.x, self.y = x, y
        self.rz = rz
        return self.check(phase)

    def set_frame(self):
        """지금 자세(바닥에 닿은 중심)를 나선·원의 기준으로 기억한다 — 손목 0° 기준."""
        self.p0 = [float(v) for v in self.d.get_current_posx(ref=self.d.DR_BASE)[0]]
        self.z_now = self.p0[2]

    def check(self, phase):
        """힘 한 번 읽기 → 기록 · 누르는 힘/옆 힘 상한 검사 → (press, lateral, radial).

        radial = 옆 힘을 지금 위치의 반지름 방향(중심 → 솔)으로 투영한 크기. 문지름 마찰은 주로 진행 방향(둘레)이라
        반지름 성분이 작고, 벽은 솔을 반지름 방향으로 되민다 → 벽 판정은 radial 로 한다(실기 3회차: 옆 힘 전체로는 못 찾음).
        """
        import math
        p = self.p
        f = cc.read_force()
        r = math.hypot(self.x, self.y)
        if self.fake_wall_r is not None:                                 # Virtual 가짜 벽(중심이 어긋난 그릇): 넘어간 만큼 되민다
            wx, wy = self.x - p['fake_bowl_offset_mm'][0], self.y - p['fake_bowl_offset_mm'][1]
            wr = math.hypot(wx, wy)
            if wr > self.fake_wall_r:
                push = p['fake_wall_k_n_per_mm'] * (wr - self.fake_wall_r)
                f = [f[0] - push * wx / wr, f[1] - push * wy / wr] + list(f[2:])
        press = abs(f[2] - self.baseline)
        lx, ly = f[0] - self.fx0, f[1] - self.fy0
        lateral = math.hypot(lx, ly)
        radial = abs(lx * self.x / r + ly * self.y / r) if r > 1e-6 else 0.0
        now = self.d.get_current_posx(ref=self.d.DR_BASE)[0]             # 실제 위치 — 명령을 못 따라간 만큼이 벽에 막힌 양이다
        ax, ay = float(now[0]) - self.p0[0], float(now[1]) - self.p0[1]
        if self.fake_wall_r is not None:                                 # Virtual 은 순응이 없어 늘 명령대로 간다 → 막히는 것도 흉내
            wx, wy = self.x - p['fake_bowl_offset_mm'][0], self.y - p['fake_bowl_offset_mm'][1]
            wr = math.hypot(wx, wy)
            if wr > self.fake_wall_r:
                k = (self.fake_wall_r + (wr - self.fake_wall_r) * 0.2) / wr     # 벽 너머는 20 %만 들어간다
                ax, ay = p['fake_bowl_offset_mm'][0] + wx * k, p['fake_bowl_offset_mm'][1] + wy * k
        self.gap = r - math.hypot(ax, ay) if r > 1e-6 else 0.0           # 반지름 방향으로 못 따라간 거리 mm (벽에 막힘)
        self.z_now = float(now[2])                                       # 다음 걸음은 이 높이를 명령한다(Z 는 힘제어 몫)
        self.climb = self.z_now - self.p0[2]                             # 바닥에서 올라간 높이 — 툴이 벽을 타고 오르면 커진다
        # 실제 손목 비틀림: B≈180°(툴이 아래를 봄)에서는 툴 Z 회전이 A − C 로 나타난다 → −Δ(A − C)
        arz = -((float(now[3]) - float(now[5])) - (self.p0[3] - self.p0[5]) + 180.0) % 360.0 + 180.0
        arz = (arz + 180.0) % 360.0 - 180.0
        self.rows.append([phase, round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], round(press, 3), p['wipe_target_n'],
                          round(self.x, 2), round(self.y, 2), round(radial, 3), round(ax, 2), round(ay, 2),
                          round(arz, 1), round(self.rz, 1), round(self.climb, 2), round(self.gap, 2)])
        if press > p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
        if lateral > p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N (벽을 세게 밀었다)')
        return press, lateral, radial

    def wall_r(self):
        """그릇 벽에 닿는 툴 중심 반지름 = (그릇 안지름 − 툴 지름) / 2 + 눌러 주는 양 (수세미가 물러서 힘으로 못 찾음 · E6)."""
        p = self.p
        return max(0.0, (p['bowl_inner_d_mm'] - p['brush_d_mm']) / 2 + p['wall_press_mm'])

    def r_max(self):
        """솔 중심이 갈 수 있는 최대 반지름 = 받을 수 있는 가장 큰 그릇 반지름 − 솔 반지름 + 여유. 그릇 크기를 가정하지 않는다."""
        p = self.p
        return p['bowl_r_max_mm'] - p['brush_d_mm'] / 2 + p['r_max_margin_mm']

    def wipe_bottom(self):
        """바닥 닦기 — 두산 **Move Spiral 한 번**. 중심에서 벽 반지름까지, 좌우 비틀기 없음.

        · 순응은 켜 두고 **힘제어는 끈 채**로 돈다 — 나선은 툴 Z 축 모션이라 Z 힘제어와 같은 방향이어서
          함께 쓸 수 없다(중급2 "힘 방향과 동일한 방향의 모션은 불가"). 켜 두면 명령만 받고 돌지 않는다(실기).
        · 나선 속도는 **시간으로 지정**한다(중급1 p.69). 속도로 주면 드라이버가 멈춘다(실기 확인).
        · 순응 중이므로 Task 모션만 쓴다(Move J 계열 금지, 2.1903).
        """
        p, d = self.p, self.d
        self.set_frame()
        self.x = self.y = self.rz = 0.0
        r_wall = min(self.wall_r(), self.r_max())
        rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
        self.log.info(f'  바닥: 나선 {rev}바퀴 · 반지름 {r_wall:.1f} mm · {p["spiral_time_s"]:g} s (비틀기·힘제어 없음)')
        d.mwait()
        ret = d.amove_spiral(rev=rev, rmax=r_wall, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0],
                             time=float(p['spiral_time_s']), axis=d.DR_AXIS_Z, ref=d.DR_TOOL)
        if ret != 0:
            raise RuntimeError(f'amove_spiral 실패 (반환 {ret!r})')
        started = self.wait_start()
        rmax_seen = self.sample_spiral()
        self.log.info(f'  나선: 실제 최대 반지름 {rmax_seen:.1f} mm (목표 {r_wall:.1f}) · 시작됨={started}')
        if rmax_seen < r_wall * 0.5:
            raise RuntimeError('나선이 돌지 않았다 — 힘제어가 켜져 있는지 확인(중급2: 같은 축 모션 불가)')
        now = d.get_current_posx(ref=d.DR_BASE)[0]
        self.x, self.y = float(now[0]) - self.p0[0], float(now[1]) - self.p0[1]
        return r_wall

    def wipe_wall(self, r_wall):
        """벽면 닦기 — 원호(Move C)를 이어 붙여 **반대 방향** circle_turns 바퀴, 도는 동안 좌우 비틀기.

        Move C 는 중첩(블렌딩) 가능한 모션이라 radius 를 주면 멈추지 않고 다음 원호로 이어진다(중급교육1 p.79).
        원호 끝 자세의 C 를 ±scrub_deg 로 번갈아 주면 도는 동안 손목이 좌우로 비틀린다.
        """
        p, d, s = self.p, self.d, cc.cfg()['run']['vel_scale']
        x0, y0, _z, a, b, c = self.p0
        vel = [p['scrub_lin_vel_mm_s'] * s, p['scrub_rot_vel_deg_s'] * s]
        acc = [p['scrub_lin_acc_mm_s2'], p['scrub_rot_acc_deg_s2']]
        th0 = math.atan2(self.y, self.x) if math.hypot(self.x, self.y) > 1e-6 else 0.0
        per = max(2, int(round(360.0 / p['wall_arc_deg'])))
        n = int(p['circle_turns'] * per)
        dth = -2 * math.pi / per                                         # 나선과 반대 방향
        chord = 2 * r_wall * abs(math.sin(dth / 2))
        radius = min(p['blend_radius_mm'], chord * 0.45)
        self.log.info(f'  벽면: {p["circle_turns"]}바퀴 · 반지름 {r_wall:.1f} mm · 원호 {n}개 '
                      f'· 이어 붙이기 {radius:.1f} mm · 비틀기 ±{p["scrub_deg"]:g}°')

        def pose(th, rz):
            return [x0 + r_wall * math.cos(th), y0 + r_wall * math.sin(th), self.z_now,
                    a, b, (c + rz + 180.0) % 360.0 - 180.0]

        twist = 1
        d.mwait()
        # 벽까지는 **천천히 밀어 붙이며** 나간다 — 나선이 어디서 끝났든 한 번에 튀어나가면 벽을 세게 박는다(실기: 25 N 초과)
        approach_vel = [p['wall_approach_vel_mm_s'] * s, p['scrub_rot_vel_deg_s'] * s]
        if d.movel(pose(th0, p['scrub_deg']), vel=approach_vel, acc=acc,
                   radius=0.0, ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS) != 0:
            raise RuntimeError('벽으로 이동 실패')
        self.x, self.y = r_wall * math.cos(th0), r_wall * math.sin(th0)
        self.force_only('wall_touch')
        self.log.info(f'  벽에 붙임: 반지름 {r_wall:.1f} mm · {p["wall_approach_vel_mm_s"] * s:.0f} mm/s 로 접근')
        for k in range(n):
            th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
            rz_mid = p['scrub_deg'] * twist
            twist = -twist
            r = 0.0 if k == n - 1 else radius                            # 마지막 원호만 이어 붙이지 않는다
            if d.movec(pose(th_mid, rz_mid), pose(th_end, p['scrub_deg'] * twist), vel=vel, acc=acc,
                       radius=r, ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS) != 0:
                raise RuntimeError('movec(벽면 원호) 실패')
            self.x = r_wall * math.cos(th_end)
            self.y = r_wall * math.sin(th_end)
            if k % max(1, int(p['force_every'])) == 0:
                self.force_only('wall')
        d.mwait()
        self.rz = p['scrub_deg'] * twist

    def force_only(self, phase):
        """도는 중에는 힘만 읽어 기록·상한 확인 — 위치는 읽지 않는다(서비스 왕복이 끼면 움직임이 끊긴다)."""
        p = self.p
        f = cc.read_force()
        press = abs(f[2] - self.baseline)
        self.rows.append([phase, round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], round(press, 3),
                          p['wipe_target_n'], round(self.x, 2), round(self.y, 2), '', '', '', '', '', '', ''])
        if press > p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
        if math.hypot(f[0] - self.fx0, f[1] - self.fy0) > p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 상한 {p["lateral_max_n"]} N 초과')

    def sample_spiral(self):
        """나선이 도는 동안 힘과 실제 위치를 기록 → 도달한 최대 반지름."""
        p = self.p
        rmax = 0.0
        t0 = time.monotonic()
        while True:
            f = cc.read_force()
            now = self.d.get_current_posx(ref=self.d.DR_BASE)[0]
            x, y = float(now[0]) - self.p0[0], float(now[1]) - self.p0[1]
            rmax = max(rmax, math.hypot(x, y))
            press = abs(f[2] - self.baseline)
            lateral = math.hypot(f[0] - self.fx0, f[1] - self.fy0)
            self.rows.append(['spiral', round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], round(press, 3),
                              p['wipe_target_n'], '', '', '', round(x, 2), round(y, 2), '', '', '', ''])
            if press > p['limit_n']:
                raise cc.ForceLimitError(f'나선: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
            if lateral > p['lateral_max_n']:                              # 나선 끝은 벽을 누른다 → 옆 힘도 본다
                raise cc.ForceLimitError(f'나선: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N')
            if self.d.check_motion() == 0:
                return rmax
            if time.monotonic() - t0 > p['spiral_time_s'] + 5.0:
                raise cc.MotionTimeout('나선이 끝나지 않는다')
            time.sleep(p['sample_s'])

    def wait_start(self, seconds=2.0):
        """비동기 동작이 실제로 시작될 때까지 기다린다 (check_motion 이 0 이 아니게 될 때까지)."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            if self.d.check_motion() != 0:
                return True
            time.sleep(0.02)
        return False

    def back_to_center(self):
        """세척 끝 — 올리지 않고 **그 높이에서 중심(HOME X·Y)으로** 돌아온다. 손목도 0 으로."""
        p, d, s = self.p, self.d, cc.cfg()['run']['vel_scale']
        x0, y0, _z, a, b, c = self.p0
        d.mwait()
        ret = d.movel([x0, y0, self.z_now, a, b, c], vel=[p['scrub_lin_vel_mm_s'] * s, p['scrub_rot_vel_deg_s'] * s],
                      acc=[p['scrub_lin_acc_mm_s2'], p['scrub_rot_acc_deg_s2']],
                      ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS)
        if ret != 0:
            raise RuntimeError('중심 복귀 실패')
        self.rz = 0.0
        self.log.info('  중심으로 복귀 (그 높이에서)')

    def sample(self, phase, target, seconds=None, until_motion=False):
        """seconds 동안 또는 비동기 동작이 끝날 때까지 힘을 기록. limit_n 넘으면 ForceLimitError."""
        p = self.p
        start = time.monotonic()
        vals = []
        while True:
            f = cc.read_force()
            press = abs(f[2] - self.baseline)
            now = time.monotonic()
            self.rows.append([phase, round(now - self.t0, 3), f[0], f[1], f[2], round(press, 3), target,
                              '', '', '', '', '', '', '', '', ''])
            if now - start >= p['settle_s']:
                vals.append(press)
            if press > p['limit_n']:
                raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > limit {p["limit_n"]} N')
            if until_motion:
                if self.d.check_motion() == 0:
                    break
            elif now - start >= seconds:
                break
            if now - start > cc.cfg()['cell']['limits']['timeout_s']:
                raise cc.MotionTimeout(f'{phase}: 시간 초과')
            time.sleep(p['sample_s'])
        self.result(phase, target, vals)

    def result(self, phase, target, vals):
        p = self.p
        if not vals:
            self.results.append((phase, target, None, None, None, 0, False))
            return
        mean, mx = statistics.mean(vals), max(vals)
        sd = statistics.pstdev(vals)
        ok = abs(mean - target) <= p['tol_n'] and mx <= p['limit_n']
        self.results.append((phase, target, mean, sd, mx, len(vals), ok))
        self.log.info(f'  {phase}: 목표 {target:.1f} N · 평균 {mean:.2f} · 흔들림 {sd:.2f} · 최대 {mx:.2f} N · {"OK" if ok else "FAIL"}')

    def compliance_on_here(self):
        """순응제어 ON — **바닥을 찾은 그 자리에서** 켠다(중급2: 목표 TCP 근처에서 ON 권장).

        · 켜기 전에 mwait — 비동기·블렌딩 모션이 도는 중에 켜면 2.1903 오류(중급2 특징3).
        · 켠 뒤에는 Task 모션만 쓴다(Move J 계열 금지, 2.1903). TCP 도 바꾸지 않는다.
        """
        p, d = self.p, self.d
        d.mwait()
        stx = cc.cfg()['cell']['force']['compliance_stx']
        if d.task_compliance_ctrl(stx) != 0:
            raise RuntimeError('task_compliance_ctrl 실패')
        self.compliance_on = True
        if self.z_contact <= 0:
            raise RuntimeError('바닥 높이를 모른다(contact_down 먼저)')
        want = self.z_contact - p['after_contact_mm']                    # + 면 더 누름, − 면 들어 올림
        dz = want - self.z()
        if abs(dz) > 0.05:
            self.move_z(dz, p['press_vel_mm_s'], p['press_acc_mm_s2'])
        self.log.info(f'  순응 ON · Z {self.z_contact:.1f} → {self.z():.1f} mm '
                      f'(바닥 대비 {self.z() - self.z_contact:+.1f} · 순응 Z {stx[2]:g} N/m)')

    def force_on_z(self, target):
        """힘제어 ON (Z 로 target N 유지) — 벽면 구간에서만 쓴다.

        🚨 중급2 "Force 명령어 – 모션 특성": **힘 방향과 같은 방향의 모션은 불가**.
           나선(move_spiral)은 툴 Z 축 회전 모션이라 Z 힘제어와 같은 축이다 → 나선 중에는 힘제어를 켜지 않는다
           (실기: 켜 두면 나선이 반환 0 인데 시작조차 하지 않았다).
           벽면 원호는 이동이 X·Y 라 Z 힘제어와 함께 쓸 수 있다(폴리싱 예시와 같다).
        🚨 힘제어는 순응 ON 이 먼저여야 한다(없으면 2.1903).
        """
        p = self.p
        fd = target + abs(self.baseline)                                 # 공중 기준값(센서 치우침·툴 무게) 보정
        self.d.mwait()
        cc.force_on('z', fd, p['limit_n'])
        self.force_ctrl_on = True
        self.log.info(f'  힘제어 ON: 목표 {target:g} N (기준값 {self.baseline:+.2f} 보정 → 명령 {fd:.2f} N)')

    def force_off_z(self):
        """힘제어만 끈다(순응은 유지)."""
        if self.force_ctrl_on:
            self.d.mwait()
            self.d.release_force()
            self.force_ctrl_on = False
            self.log.info('  힘제어 OFF')

    def press_off(self):
        """끝내기 — 힘제어 → 순응 순서로 끈다(중급2: 순응 OFF 하면 힘제어도 자동 종료된다)."""
        cc.force_off()                                                   # cc.force_on 으로 켠 것 정리
        if self.force_ctrl_on:
            self.d.release_force()
            self.force_ctrl_on = False
        if self.compliance_on:
            self.d.release_compliance_ctrl()
            self.compliance_on = False

    def save(self):
        os.makedirs(self.p['log_dir'], exist_ok=True)
        path = os.path.join(self.p['log_dir'], time.strftime('v03_%Y%m%d_%H%M%S.csv'))
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['phase', 't', 'fx', 'fy', 'fz', 'press_n', 'target', 'x_mm', 'y_mm', 'radial_n',
                        'actual_x_mm', 'actual_y_mm', 'actual_rz_deg', 'cmd_rz_deg', 'climb_mm', 'gap_mm'])
            w.writerows(self.rows)
        return path


def main() -> int:
    ap = argparse.ArgumentParser(description='V-03 힘제어 중 X·Y 이동 (실기는 --real)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행한다 (🚨 E-Stop 담당·격리·저속 확인 뒤)')
    ap.add_argument('--fake-wall', action='store_true',
                    help='Virtual 전용: 그릇 안지름·솔 지름으로 가짜 벽 힘을 넣는다 (실기에서는 거부)')
    ap.add_argument('--fake-bowl-d', type=float, default=None,
                    help='Virtual 가짜 그릇 안지름 mm (기본 rig_v03.yaml)')
    args = ap.parse_args()
    with open(HERE / 'rig_v03.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)

    cc.init('rig_v03')                                                   # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    code = 1
    run = None
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not virtual and not args.real:
            log.error('실기다 → --real 을 붙여야 실행한다 (E-Stop 담당·격리·저속 확인 뒤)')
            return 2
        if args.fake_wall and not virtual:
            log.error('--fake-wall 은 Virtual 전용이다 (실기에는 진짜 벽이 있다) → 실행 거부')
            return 2
        approach = p['virtual_approach_down_mm'] if virtual else p['approach_down_mm']
        if approach is None:
            log.error('rig_v03.yaml 의 approach_down_mm 이 비어 있다 → (솔 끝 → 그릇 바닥 실측) − 30 mm 를 넣는다')
            return 2
        tool, tcp = d.get_tool(), d.get_tcp()
        if not virtual and (tool != p['expected_tool'] or tcp != p['expected_tcp']):
            # 브링업을 새로 켜면 툴·TCP 가 비어 있다. 자동 모드에서는 설정이 거부돼 수동 모드로 바꿔 설정하고 되돌린다
            log.warning(f'툴·TCP 가 {tool!r}·{tcp!r} → {p["expected_tool"]!r}·{p["expected_tcp"]!r} 로 설정한다 (로봇 안 움직임)')
            d.set_robot_mode(d.ROBOT_MODE_MANUAL)
            d.set_tool(str(p['expected_tool']))
            d.set_tcp(str(p['expected_tcp']))
            d.set_robot_mode(d.ROBOT_MODE_AUTONOMOUS)
            tool, tcp = d.get_tool(), d.get_tcp()
        log.info(f"{'Virtual(흐름만 — 힘 판정은 의미 없음)' if virtual else '실기'} · vel_scale {cc.cfg()['run']['vel_scale']:g} "
                 f'· 툴 {tool!r} · TCP {tcp!r} · 접근 {approach:.0f} mm')
        if not virtual and (tool != p['expected_tool'] or tcp != p['expected_tcp']):
            log.error(f"툴·TCP 설정이 다르다(기대 {p['expected_tool']!r} · {p['expected_tcp']!r}) → 실행 거부. 설정:\n"
                      f"    ros2 service call /dsr01/dsr_controller2/tool/set_current_tool dsr_msgs2/srv/SetCurrentTool "
                      f"\"{{name: '{p['expected_tool']}'}}\"\n"
                      f"    ros2 service call /dsr01/dsr_controller2/tcp/set_current_tcp dsr_msgs2/srv/SetCurrentTcp "
                      f"\"{{name: '{p['expected_tcp']}'}}\"")
            return 2
        air = abs(statistics.mean(cc.read_force()[2] for _ in range(5)))
        if not virtual and air > p['air_force_max_n']:
            log.error(f"로봇이 멈춰 있는데 |Fz| {air:.1f} N > {p['air_force_max_n']} N → 툴 무게 설정이 틀렸다(무게가 외력으로 잡힘). 실행 거부")
            return 2
        input('준비되면 엔터 → 이후 키보드에서 손을 떼고 E-Stop 에 손을 둔다 ')

        run = Run(d, p, log)
        if args.fake_wall:
            if args.fake_bowl_d is not None:                             # Virtual 전용 — 실기는 위에서 이미 거부
                p['fake_bowl_inner_d_mm'] = args.fake_bowl_d
            run.fake_wall_r = max(0.0, (p['fake_bowl_inner_d_mm'] - p['brush_d_mm']) / 2)
            log.info(f"가짜 벽: 그릇 안지름 {p['fake_bowl_inner_d_mm']:g} − 솔 지름 {p['brush_d_mm']:g} → "
                     f"솔 중심 반지름 {run.fake_wall_r:.1f} mm 에서 벽 · 나선 최대 {run.r_max():.1f} mm")
        d.movej(p['home_posj'], vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'], acc=p['home_acc_deg_s2'])
        z_home = run.z()
        cc.cfg()['cell']['limits']['safe_z_mm'] = z_home                 # 시험 전용: 안전 높이 = HOME
        log.info(f'HOME Z {z_home:.1f} → 빠른 접근 {approach:.0f} mm')
        run.move_z(-approach, p['approach_vel_mm_s'], p['approach_acc_mm_s2'])

        run.zero()                                                       # 공중 기준값 (닿기 전)
        log.info(f'공중 Fz 기준값 {run.baseline:.2f} N')
        if not virtual and abs(run.baseline) > p['air_force_max_n']:
            log.error(f'접근 뒤 공중 |Fz| {abs(run.baseline):.1f} N 가 크다 → 툴 무게·접촉 확인. 힘제어 없이 중단')
            return 1
        depth, f = cc.contact_down(p['contact_max_depth_mm'], p['contact_limit_n'])
        run.z_contact = run.z()                                          # 🚨 바닥 높이를 기억한다 — 띄우기·누르기는 이 값 기준
        contacted = depth < p['contact_max_depth_mm'] - 0.5
        log.info(f'contact_down: 깊이 {depth:.1f} mm · |Fz| {f:.1f} N · {"바닥 찾음" if contacted else "못 찾음"} · 바닥 Z {run.z():.1f}')
        if not contacted and not virtual:
            log.error('바닥을 못 찾았다 → 힘제어를 켜지 않고 중단 (approach_down_mm·그릇 위치 확인)')
            return 1

        log.info('① 순응 ON (바닥 찾은 자리에서) — 힘제어는 아직 켜지 않는다')
        run.compliance_on_here()

        log.info('② 바닥 — move_spiral 한 번 (비틀기 없음 · 힘제어 OFF: 나선은 Z 축 모션이라 Z 힘제어와 같은 방향)')
        r_wall = run.wipe_bottom()

        log.info('③ 벽면 — 힘제어 ON 뒤 원호로 반대 방향 %d바퀴 + 좌우 비틀기 (이동은 X·Y 라 Z 힘제어와 함께 가능)'
                 % p['circle_turns'])
        run.force_on_z(p['wipe_target_n'])
        run.wipe_wall(r_wall)
        run.force_off_z()

        log.info('③ 그 높이에서 중심으로 복귀 → 순응 끄고 위로')
        run.back_to_center()
        run.press_off()
        code = 0
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정지 명령을 보내고 끝낸다')
        code = 130
    except Exception as e:                                               # 두산 DR_Error 포함 — 무엇이든 멈추고 정리
        log.error(f'중단: {type(e).__name__}: {e}')
        code = 1
    finally:
        import rclpy
        if code != 130 and run is not None:                              # 로봇을 움직이기 시작한 경우에만 복귀 (거부·Ctrl+C 는 제외)
            if not rclpy.ok():                                           # DR_Error 가 rclpy.shutdown() 을 불렀다 → 이 프로세스로는 못 끈다
                log.error('🚨 두산 오류로 ROS 가 꺼졌다 → 힘·순응이 켜진 채일 수 있다. 새 터미널에서 바로:\n'
                          '    soc && python3 src/cobot_common/test/release_force.py --home   (E-Stop 에 손)')
            else:
                for what, step in (('힘·순응 끄기', run.press_off), ('동작 끝 대기', lambda: dsr().mwait()),
                                   ('안전 높이로', cc.safe_retreat),
                                   ('HOME', lambda: dsr().movej(p['home_posj'],
                                                                vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'],
                                                                acc=p['home_acc_deg_s2']))):
                    try:                                                 # 하나가 실패해도 다음을 시도
                        step()
                    except Exception as e:
                        log.error(f'복귀 — {what} 실패: {e!r} → 눈으로 확인, 필요하면 release_force.py --home')
        if run is not None and run.rows:
            path = run.save()
            log.info(f'힘 로그: {path}')
            log.info('구간 | 목표 N | 평균 | 흔들림 | 최대 | 샘플 | 판정')
            for phase, target, mean, sd, mx, n, ok in run.results:
                vals = '—' if mean is None else f'{mean:.2f} | {sd:.2f} | {mx:.2f}'
                log.info(f'{phase} | {target:g} | {vals} | {n} | {"OK" if ok else "FAIL"}')
            wipe = [r for r in run.results if r[0].startswith('wipe_') and r[0] != 'wipe_settle']
            verdict = '가능' if wipe and all(r[6] for r in wipe) else '불가 또는 미확인'
            log.info(f'V-03 판정: 힘제어 중 X·Y 이동 {verdict} (문지르는 동안 평균이 목표 ±{p["tol_n"]} N · 최대 ≤ {p["limit_n"]} N)')
        cc.shutdown()                                                    # ③ 끝낼 때 (Ctrl+C 포함)
    return code


if __name__ == '__main__':
    sys.exit(main())
