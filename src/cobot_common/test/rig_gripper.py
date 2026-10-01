#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02d 단독 시험 — 그리퍼 함수(gripper.py)로 V-05 · V-23 · V-01 을 실기에서 잰다.

실행 (저장소 루트에서, 격리 상태 solo — docs/env/M0609_환경설정.md)
    rosinfo                                                           # 🚨 RANGE=LOCALHOST 확인
    터미널 1:  sod && sodreal                                          (이미 떠 있으면 그대로 쓴다)
    터미널 2:  soc && python3 src/cobot_common/test/rig_gripper.py check
               soc && python3 src/cobot_common/test/rig_gripper.py v05 -n 10
               soc && python3 src/cobot_common/test/rig_gripper.py v23 --kind BOWL -n 10
               soc && python3 src/cobot_common/test/rig_gripper.py v01 -n 10

무엇을 재나 (완료 기준은 일정표 · docs/03_설계_SDD.md §9)
    check  연결만 확인 — 그리퍼를 **움직이지 않는다**
    V-05   폭 경로 확인 — 빈손으로 목표 폭을 반복 명령해 읽은 폭의 **흔들림**. 사람 개입 없음
           🔑 닫힌 쪽(0~5 mm)이 핵심이다 — 그릇 벽 파지가 ≈ 2 mm 라 거기서 흔들리면 못 가린다
    V-23   파지 힘 전환 — 쥔 채 NORMAL ↔ HOLD 를 n 회. 완료 기준 "전환 10회 낙하 0"
    V-01   폭 3상태 구분 — 빈손 · 그릇 · 컵을 n 회씩.
           닫는 힘은 **종류별**이다: 빈손·그릇 = BOWL 힘 / 컵 = CUP 힘.
              컵이 15 N 에서 변형돼 낮췄고, 빈손·그릇은 간격이 2.7 mm 뿐이라 같은 조건으로 재야 한다.
              --force-n 을 주면 그 값이 전부를 덮는다.
           완료 기준 "세 범위가 겹치지 않고,
           그릇 ↔ 빈손 간격이 흔들림(최대 − 최소)의 2배 이상" → 결과가 cell.yaml 의 width_tol_mm 가 된다

🚨 이 시험대가 지키는 것
    ① 모든 명령을 **release() 로 시작** 한다 — 힘 기준 맞추기(0 N 까지 내리기)가 **빈손** 에서 일어나야
       한다. 지금 gripper.py 는 힘을 **읽어서** 맞추므로(기준 잡기 삭제) 쥔 채 놓칠 일은 없어졌다.
       다만 release() 로 시작하는 약속은 그대로다 — 힘은 움직이거나 닫혀 있을 때만 읽히기 때문이다.
    ② **로봇 팔을 움직이지 않는다** (`init(robot=False)`) — 그리퍼만 쓴다. 두산 드라이버도,
       아직 비어 있는 팀 cell.yaml 의 limits·motion 도 필요 없다.
    ③ Ctrl+C 로 끊으면 **그리퍼에 아무 명령도 보내지 않는다** — 쥔 채면 놓는 쪽이 더 위험하다.
    ④ 설정은 같은 폴더의 rig_gripper_config/ 와 rig_gripper.yaml. 팀 cell.yaml 은 읽지 않는다.

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
종료 코드 0(통과) / 1(실패) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ['PREWASH_CONFIG_DIR'] = str(HERE / 'rig_gripper_config')    # cc.init 이 설정을 읽기 전에

import cobot_common as cc                          # noqa: E402
from cobot_common import gripper as G              # noqa: E402  cobot_common 자체 시험이라 내부를 본다

_STATE_NAME = {'EMPTY': '빈손', 'BOWL': '그릇', 'CUP': '컵'}


# ────────────────────────────────────────────────────────────── 재는 도구
def _zero(preset, kind, log):
    """빈손 영점(mm) — 결정 E16 D-A. 없으면 None (그때는 옛 방식으로 로그만 남긴다).

    🚨 드라이버가 재는 폭은 **알루미늄 손가락 사이**라 고무 핑거팁 두께가 안 빠진다
       → 빈손으로 꽉 닫아도 0 이 아니라 10.5 mm 쯤이 읽힌다(실측).
       그래서 판정은 `읽은 폭 − 영점`, 명령은 `영점 + 목표` 다(방향이 반대다).
    """
    z = preset.get('grip_zero_mm')
    if z is None:
        log.warn(f'presets.{kind}.grip_zero_mm 이 비어 있다 — 영점 없이 판정한다(V-01 에서 잰다)')
        return None
    return float(z)


def _stats(vals):
    """평균·최소·최대·흔들림(최대 − 최소). 흔들림이 V-01·V-05 판정의 기준이다."""
    lo, hi = min(vals), max(vals)
    return {'n': len(vals), 'avg': sum(vals) / len(vals), 'min': lo, 'max': hi, 'spread': hi - lo}


def _row(label, s):
    return (f'  {label:<6} {s["avg"]:7.2f} {s["min"]:7.2f} {s["max"]:7.2f} {s["spread"]:7.2f}')


def _head(first):
    return f'  {first:<6} {"평균":>6} {"최소":>6} {"최대":>6} {"흔들림":>5}'


def _wait_width(log, limit_s):
    """첫 폭 값을 기다린다 — /onrobot_joint_states 구독이 붙어야 읽힌다."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s:
        try:
            return cc.grip_width()
        except RuntimeError:
            time.sleep(0.1)
    log.error(f'{limit_s:.0f} s 안에 그리퍼 폭을 못 받았다 — /onrobot_joint_states 와 브링업을 확인한다')
    return None


def _ask(log, msg):
    """사람이 용기를 대 줄 때까지 기다린다. 파이프로 돌리면(입력 없음) 그냥 진행한다."""
    log.info(f'▶ {msg} — 준비되면 Enter')
    try:
        input()
    except EOFError:
        log.warning('입력이 없다 — 기다리지 않고 진행한다')


def _close_once(target_mm, force_n):
    """열었다가 목표 폭으로 닫고 실제 폭을 읽는다. 반복성을 재려면 매번 열어야 한다."""
    cc.release()
    return cc.grip(target_mm, force_n)


# ────────────────────────────────────────────────────────────── check
def cmd_check(a, p, log):
    """연결만 확인한다 — 그리퍼를 움직이지 않는다."""
    ok = True
    if G._client is None or not G._client.wait_for_service(timeout_sec=3.0):
        log.error('/onrobot/sendCommand 가 안 보인다 — 그리퍼 드라이버·브링업을 확인한다')
        ok = False
    else:
        log.info('OK   /onrobot/sendCommand 보인다')

    w = _wait_width(log, p['width_wait_s'])
    if w is None:
        ok = False
    else:
        log.info(f'OK   현재 폭 {w:.2f} mm 를 읽었다')
    log.info(f'결과: {"통과" if ok else "실패"} (그리퍼를 움직이지 않았다)')
    return 0 if ok else 1


# ────────────────────────────────────────────────────────────── V-05
def cmd_v05(a, p, log):
    """폭 경로 확인 — 빈손으로 목표 폭을 n 회씩 반복 명령하고 읽은 폭의 흔들림을 본다."""
    conf = p['v05']
    force = a.force_n if a.force_n is not None else float(p['force_n'])   # 빈손이라 종류가 없다
    log.info(f'V-05  폭 경로 확인 — 빈손, 목표 {conf["targets_mm"]} mm 를 {a.n} 회씩 · {force:.1f} N')
    log.info('🚨 그리퍼에 **아무것도 없어야** 한다')
    cc.release()                                    # ① 열기 + (첫 호출이면) 힘 기준 맞추기
    if _wait_width(log, p['width_wait_s']) is None:
        return 1

    rows, worst, bad = [], 0.0, []
    for target in conf['targets_mm']:
        vals = [_close_once(float(target), force) for _ in range(a.n)]
        s = _stats(vals)
        rows.append((f'{target:.1f}', s))
        worst = max(worst, s['spread'])
        if abs(s['avg'] - float(target)) > conf['tol_mm']:
            bad.append(f'목표 {target:.1f} → 평균 {s["avg"]:.2f} mm')
        log.info(f'  목표 {target:>5.1f} mm : ' + ' '.join(f'{v:.2f}' for v in vals))
    cc.release()                                    # 끝내고 열어 둔다 (빈손이라 안전)

    log.info('')
    log.info(f'V-05  결과 ({a.n} 회씩)')
    log.info(_head('목표'))
    for label, s in rows:
        log.info(_row(label, s))
    log.info('')
    log.info(f'  흔들림 최대 {worst:.2f} mm  ← 🔑 V-01 의 판정 여유가 이보다 커야 한다')
    for m in bad:
        log.warning(f'  명령값과 벌어짐: {m}')
    log.info(f'  판정: {"OK   명령 → 동작 → 폭 읽기 경로 확인" if not bad else "확인 필요"}')
    return 0 if not bad else 1


# ────────────────────────────────────────────────────────────── V-23
def cmd_v23(a, p, log):
    """파지 힘 전환 — 쥔 채 NORMAL ↔ HOLD 를 n 회. 폭이 줄면 놓친 것이다."""
    conf = p['v23']
    preset = cc.cfg()['cell']['presets'][a.kind]
    for k in ('grip_width_mm', 'width_tol_mm', 'grip_force_n', 'hold_force_n'):
        if preset.get(k) is None:                   # 키는 있는데 값이 비어 있는 경우까지 잡는다
            log.error(f'presets.{a.kind}.{k} 가 비어 있다 — rig_gripper_config/cell.yaml 을 채운다')
            return 2
    log.info(f'V-23  파지 힘 전환 {_STATE_NAME[a.kind]} — NORMAL {preset["grip_force_n"]} N '
             f'↔ HOLD {preset["hold_force_n"]} N 를 {a.n} 회')

    cc.release()                                    # ① 🚨 빈손에서 힘 기준을 맞춘다
    if _wait_width(log, p['width_wait_s']) is None:
        return 1
    _ask(log, f'{_STATE_NAME[a.kind]} 을(를) 그리퍼 사이에 대 주세요')

    # 🚨 닫는 목표는 **기대 폭보다 작게** 준다 — SDD §5.2 의 식 그대로.
    #    기대 폭을 그대로 주면 그리퍼가 **빈손으로도 그 폭에서 멈춰**,
    #    용기를 안 대 줬는데 "파지 성공 · 낙하 0 회" 로 통과한다.
    #    그 결과가 cell.yaml 파지 힘이 되므로 실기에서 용기를 놓치게 된다.
    #    (같은 파일 cmd_v01 은 close_mm: 0.0 으로 이 규칙을 지키는데 여기만 빠져 있었다)
    expect = float(preset['grip_width_mm'])
    tol = float(preset['width_tol_mm'])
    zero = _zero(preset, a.kind, log)
    # 결정 E16 D-A — 명령에는 영점을 **더하고**(드라이버 값이라서), 판정에서는 **뺀다**.
    #    영점이 없으면 옛 방식 그대로(드라이버 값끼리 비교).
    base = zero if zero is not None else 0.0
    target = base + max(0.0, expect - 2 * tol)
    if a.target_mm is not None:
        # 🔻 끝까지 닫지 않고 정해진 폭에서 멈춘다 — 무른 용기(컵)가 눌리는 것을 줄이려는 것.
        #    🚨 대가가 있다: **빈손도 그 폭에서 멈춘다.** 아래에서 "목표에 그대로 도달" 을 경고한다.
        log.warn(f'  🔻 닫는 목표를 {a.target_mm:.1f} mm 로 직접 준다(기본 계산값 {target:.2f} 대신) '
                 f'— 끝까지 닫지 않는다')
        target = float(a.target_mm)
    w0 = cc.grip(target, float(preset['grip_force_n']))
    net0 = w0 - base
    log.info(f'  최초 파지(NORMAL) — 목표 {target:.2f} mm(영점 {base:.2f} + 기대 {expect:.1f} '
             f'− 2 × 허용오차 {tol:.1f}) → 실제 {w0:.2f} mm · **영점 뺀 폭 {net0:.2f} mm**')
    if abs(w0 - target) < 0.3:
        # 🚨 결함 수정 — 전에는 경고만 하고 **통과**시켰다. 빈손으로 돌려 보니 그대로 OK 가 났다
        #    (컵 77.90 vs 빈손 77.80 — 차이 0.10 mm, 흔들림 0.20 보다 작다).
        #    앞서 고친 "빈손으로 통과하면 안 된다" 보호가 --target-mm 을 넣으며 다시 뚫린 것이다.
        #    힘 전환 시험은 **쥐고 있어야** 뜻이 있으므로 여기서 멈춘다.
        log.error(f'  🚨 목표 {target:.1f} mm 에 **그대로 도달**했다 (실제 {w0:.2f}) — '
                  f'막는 것이 없었다는 뜻이다. **빈손도 이렇게 보인다.**')
        log.error('  → 이 조건에서는 "잡았는지" 를 폭으로 가를 수 없다. 힘 전환 시험을 하지 않는다')
        log.error('  → 끝까지 닫는 방식(--target-mm 없이)으로 돌리거나, 파지 확인을 다른 방법으로 한다')
        return 1
    if abs(net0 - expect) > tol:
        # 용기가 없으면 목표(≈ 0)까지 닫힌다 → 여기서 걸린다. 이 시험은 빈손으로 통과하면 안 된다.
        log.error(f'  {_STATE_NAME[a.kind]} 이(가) 안 잡혔다 — '
                  f'영점 뺀 폭 {net0:.2f} mm 가 기대 {expect:.1f} ± {tol:.1f} mm 밖이다 '
                  f'(읽은 값 {w0:.2f} − 영점 {base:.2f})')
        log.error('  용기를 제대로 대 주고 다시 실행한다 (힘 전환 시험은 쥐고 있어야 뜻이 있다)')
        return 1
    # 놓치면 그리퍼가 닫혀 버려 폭이 0 근처로 간다. 절대값(drop_mm)만 쓰면 컵(≈ 70 mm)에서
    # 1 mm 미끄러진 것까지 낙하로 읽는다 → "최초의 절반" 과 함께 보고 더 낮은 쪽을 기준으로 삼는다.
    floor = min(w0 * 0.5, w0 - conf['drop_mm'])
    log.info(f'  낙하로 보는 폭: {floor:.2f} mm 아래')

    drops, widths = [], [w0]
    for i in range(1, a.n + 1):
        w_hold = cc.grip_level(a.kind, 'HOLD')
        w_norm = cc.grip_level(a.kind, 'NORMAL')
        widths += [w_hold, w_norm]
        mark = ''
        if w_hold < floor or w_norm < floor:
            drops.append(i)
            mark = '  🚨 놓친 것으로 보인다'
        log.info(f'  {i:>3} 회 : HOLD {w_hold:6.2f} → NORMAL {w_norm:6.2f} mm'
                 f'  (최초 대비 {w_norm - w0:+.2f}){mark}')

    change = max(abs(w - w0) for w in widths)
    log.info('')
    log.info(f'V-23  결과 — 전환 {a.n} 회')
    log.info(f'  낙하 {len(drops)} 회' + (f' (회차 {drops})' if drops else '') + '   완료 기준: 0')
    log.info(f'  최초 대비 폭 변화 최대 {change:.2f} mm   (V-16 기준 {conf["change_limit_mm"]:.1f} mm 이하)')
    ok = not drops and change <= conf['change_limit_mm']
    log.info(f'  판정: {"OK" if ok else "확인 필요"}')
    if ok:
        log.info(f'  → cell.yaml: presets.{a.kind}.hold_force_n = {preset["hold_force_n"]} 로 된다'
                 '  (V-16 에서 더 낮춰 "낙하 없는 최소" 를 찾는다)')
    else:
        log.info('  → 힘을 올리거나 핑거 패드를 손본 뒤 다시 — 실패한 값은 cell.yaml 에 넣지 않는다')
    log.info('🚨 용기를 쥔 채 끝난다 — 받은 뒤에 손으로 release 한다')
    return 0 if ok else 1


# ────────────────────────────────────────────────────────────── V-01
def cmd_v01(a, p, log):
    """폭 3상태 구분 — 빈손 · 그릇 · 컵을 **같은 명령** 으로 닫고 폭을 비교한다."""
    conf = p['v01']
    # 🚨 판정(아래)이 EMPTY·BOWL·CUP 셋을 모두 쓴다. 하나라도 빼고 적으면 사람이 용기를 대 주는
    #    측정을 **다 끝낸 뒤에** KeyError 가 나서 실기 시간만 버린다 → 로봇을 만지기 전에 거부한다.
    #    (순서는 바꿔도 된다 — 사람에게 물어보는 차례만 달라진다)
    need = {'EMPTY', 'BOWL', 'CUP'}
    if set(conf['states']) != need:
        log.error(f"v01.states 는 {sorted(need)} 셋이 다 있어야 한다 — 지금 {list(conf['states'])}")
        log.error('  판정이 셋을 모두 쓴다. 순서는 바꿔도 되지만 빼면 안 된다 (rig_gripper.yaml)')
        return 2
    close = float(conf['close_mm'])
    log.info(f'V-01  폭 3상태 구분 — 세 상태를 모두 "목표 {close:.1f} mm 로 닫기" 로 {a.n} 회씩')
    log.info('      목표를 기대 폭보다 작게 줘야 빈손과 갈린다(SDD §5.2) → 막는 것이 있으면 거기서 멈춘다')

    cc.release()                                    # ① 🚨 빈손에서 힘 기준을 맞춘다
    if _wait_width(log, p['width_wait_s']) is None:
        return 1

    # 종류마다 **다른 힘**으로 닫는다. 컵은 15 N 에서 눈으로 보이게 변형됐다(실기 관찰).
    #    · 빈손·그릇 : 그릇 힘 (둘을 **같은 조건**으로 재야 비교가 된다 — 간격이 2.7 mm 뿐이라 촘촘하다)
    #    · 컵        : 컵 힘   (빈손과 60 mm 넘게 떨어져 있어 조건이 달라도 구분에 지장이 없다)
    #    --force-n 을 주면 그 값이 **전부**를 덮는다(예전 방식).
    presets = cc.cfg()['cell']['presets']
    # 🔎 컵을 5 N 으로 낮췄는데 실행에서 20 N 이 찍힌 적이 있어(원인 미상) 근거를 남긴다.
    log.info('  닫는 힘(설정에서 읽음): '
             + ' · '.join(f'{k} {(presets.get(k) or {}).get("grip_force_n")} N' for k in ('BOWL', 'CUP'))
             + (f" · --force-n {a.force_n} 로 **전부 덮음**" if a.force_n is not None else ''))
    log.info(f'  설정 폴더: {os.environ.get("PREWASH_CONFIG_DIR")}')

    def _force_for(st):
        if a.force_n is not None:
            return a.force_n
        kind = 'BOWL' if st in ('EMPTY', 'BOWL') else st
        f = (presets.get(kind) or {}).get('grip_force_n')
        if f is None:
            raise KeyError(f'presets.{kind}.grip_force_n 이 비어 있다 — rig_gripper_config 를 채운다')
        return float(f)

    out = {}
    for st in conf['states']:
        if st == 'EMPTY':
            _ask(log, '그리퍼를 **비워** 주세요')
        else:
            _ask(log, f'{_STATE_NAME[st]} 을(를) 그리퍼 사이에 대 주세요')
        force = _force_for(st)
        log.info(f'  {_STATE_NAME[st]:<4} — {force:.1f} N 으로 {a.n} 회 닫는다')
        vals = [_close_once(close, force) for _ in range(a.n)]
        out[st] = _stats(vals)
        log.info(f'  {_STATE_NAME[st]:<4} : ' + ' '.join(f'{v:.2f}' for v in vals))
    cc.release()

    log.info('')
    log.info(f'V-01  결과 ({a.n} 회씩)')
    log.info(_head('상태'))
    for st in conf['states']:
        log.info(_row(_STATE_NAME[st], out[st]))

    # ── 판정 ① 세 범위가 겹치지 않는가
    order = sorted(conf['states'], key=lambda s: out[s]['min'])
    overlap = [f'{_STATE_NAME[x]}↔{_STATE_NAME[y]}'
               for x, y in zip(order, order[1:]) if out[y]['min'] <= out[x]['max']]

    # ── 판정 ② 그릇 ↔ 빈손 간격이 흔들림의 2배 이상인가 (완료 기준)
    gap = out['BOWL']['min'] - out['EMPTY']['max']
    wob = max(out['BOWL']['spread'], out['EMPTY']['spread'])
    gap_ok = gap >= 2 * wob

    log.info('')
    log.info('  판정')
    log.info(f'    세 범위 겹침 {"없음" if not overlap else str(overlap)}'
             f'{"":>10}{"OK" if not overlap else "FAIL"}')
    log.info(f'    그릇 ↔ 빈손 간격 {gap:.2f} ≥ 2 × 흔들림 {wob:.2f} ({2 * wob:.2f})'
             f'{"":>3}{"OK" if gap_ok else "FAIL"}')

    # ── 산출물: cell.yaml 에 넣을 값 (결정 E16 D-A — 영점을 빼서 실측 치수와 같은 뜻으로)
    log.info('')
    log.info('  → cell.yaml presets 에 넣을 값')
    zero = out['EMPTY']['avg']                       # 빈손 평균 = grip_zero_mm
    log.info(f'       presets.<kind>.grip_zero_mm : {zero:.2f}'
             f'   (빈손 평균 — 판정은 `읽은 폭 − 영점`, 명령은 `영점 + 목표`)')
    for kind in ('BOWL', 'CUP'):
        net = out[kind]['avg'] - zero
        log.info(f'       presets.{kind}.grip_width_mm : {net:.2f}'
                 f'   (읽은 {out[kind]["avg"]:.2f} − 영점 {zero:.2f} · 실측 치수와 맞는지 보세요)')
    for kind, nb in (('BOWL', 'EMPTY'), ('CUP', 'BOWL')):
        g = out[kind]['min'] - out[nb]['max']
        w = max(out[kind]['spread'], out[nb]['spread'])
        tol = round(max(0.1, min(g / 2, w * 2)), 1)          # 흔들림보다 크고 간격의 절반보다 작게
        if g <= 0 or tol <= w:
            # 흔들림보다 큰 tol 을 잡으면 옆 상태까지 먹는다 → 값을 지어내지 않는다
            log.warning(f'       presets.{kind}.width_tol_mm : 제안 불가'
                        f'   (흔들림 {w:.2f} mm 가 {_STATE_NAME[nb]}과의 간격 {g:.2f} mm 을 먹는다)')
            log.warning('           → 핑거 패드를 두껍게 하거나 파지 위치를 바꾼 뒤 다시 잰다')
        else:
            log.info(f'       presets.{kind}.width_tol_mm : {tol}'
                     f'   (흔들림 {w:.2f} < tol < 간격/2 {g / 2:.2f})')

    ok = not overlap and gap_ok
    log.info(f'  판정: {"OK" if ok else "확인 필요"}')
    return 0 if ok else 1


# ────────────────────────────────────────────────────────────── 실행
_CMDS = {'check': cmd_check, 'v05': cmd_v05, 'v23': cmd_v23, 'v01': cmd_v01}


def main() -> int:
    ap = argparse.ArgumentParser(description='cobot_common 그리퍼 함수 시험 (실기)')
    ap.add_argument('which', choices=list(_CMDS), help='check=연결만 · v05=폭 경로 · v23=힘 전환 · v01=3상태')
    ap.add_argument('-n', type=int, default=10, help='반복 횟수 (완료 기준은 10)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'], help='v23 의 용기 종류 (IRD §2)')
    ap.add_argument('--force-n', type=float, default=None, help='v05·v01 에서 닫을 때 쓰는 힘 (N)')
    ap.add_argument('--target-mm', type=float, default=None,
                    help='v23 에서 닫는 목표 폭을 직접 준다 (드라이버 값 · 영점 포함). '
                         '끝까지 닫지 않아 용기가 눌리는 것을 줄인다 — 🚨 아래 경고를 함께 본다')
    a = ap.parse_args()

    with open(HERE / 'rig_gripper.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    # 🚨 여기서 yaml 기본값(20 N)으로 **채우면 안 된다**. 채우면 v01 의
    #    "--force-n 을 줬을 때만 덮는다" 검사가 항상 참이 되어 **컵도 20 N 으로** 닫힌다
    #    (V-01 에서 실제로 그렇게 났고, 컵이 눌리며 안전 스위치가 걸렸다).
    #    a.force_n 은 **사람이 준 값일 때만** 값이 있다. 기본값은 쓰는 쪽(v05)에서 고른다.
    if a.n < 1:
        return 2

    cc.init('rig_gripper', robot=False)              # ② 팔을 안 쓴다 — 그리퍼만
    log = cc.io_node().get_logger()
    try:
        return _CMDS[a.which](a, p, log)
    except KeyboardInterrupt:
        # ③ 🚨 그리퍼에 아무 명령도 보내지 않는다 — 쥔 채면 놓는 쪽이 더 위험하다
        log.warning('Ctrl+C — 그리퍼는 그대로 둔다(명령 없음). 용기를 받은 뒤 손으로 연다')
        return 130
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        log.error(f'{type(e).__name__}: {e}')
        return 1
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
