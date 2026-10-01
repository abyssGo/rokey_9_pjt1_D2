#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02d 사전 확인 — **아무것도 고치기 전에** 드라이버가 실제로 어떻게 동작하는지만 본다.

무엇을 확인하나 (전부 소스에서 읽어 낸 추정이다 — 실기에서 맞는지 보는 것이 이 파일의 전부)
    ① 값이 들어오는가 (폭)
    ② **지금 힘이 얼마인가** — `/onrobot_joint_states` 의 effort 로 읽는다
       🚨 힘은 **움직이거나 닫혀 있을 때만** 읽힌다(실기 확인) → 닫아서 움직임을 만든 뒤 읽는다
       🚨 드라이버가 힘을 **기억**해서 두 번째 실행부터는 40 N 이 아니다 → 읽은 값에서 이어 간다
    ③ `'d'`/`'i'` 한 번에 **2.5 N** 씩 실제로 움직이는가 (절대값이 아니라 **차이**를 본다)
    ④ **빈손 영점**(고무 핑거팁 두께 ×2) — 힘을 맞춘 뒤 닫아서 잰다.
       판정에 쓸 힘과 **같은 힘**으로 재야 한다(고무가 눌려 힘마다 다르다)
    ⑤ 닫힌 채 멈춰 있을 때도 힘이 읽히는가

🚨 이 파일이 지키는 것
    ① **로봇 팔을 움직이지 않는다** (`init(robot=False)`) — 그리퍼만 쓴다.
    ② **gripper.py 의 공개 함수를 부르지 않는다** — grip()/release() 는 힘 기준 맞추기('d' 17회)를
       먼저 해 버려서 "브링업 직후 40 N" 을 확인할 수 없다. 그래서 드라이버에 **직접** 명령한다.
    ③ **아무것도 고치지 않는다** — 읽고 재기만 한다. 결과를 보고 나서 gripper.py 를 고친다.
    ④ Ctrl+C 로 끊으면 그리퍼에 아무 명령도 보내지 않는다.

실행 (저장소 루트에서, 격리 상태 solo — docs/env/M0609_환경설정.md)
    rosinfo                                          # 🚨 RANGE=LOCALHOST 확인
    터미널 1:  sod && sodreal                         (이미 떠 있으면 그대로 쓴다)
    터미널 2:  soc && python3 src/cobot_common/test/rig_gripper_probe.py

    🚨 시작할 때 그리퍼는 **비어 있어야** 한다. 마지막에 열어 둔 채 끝난다.

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
종료 코드 0(전부 확인) / 1(하나라도 다름) / 130(Ctrl+C).
"""
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ['PREWASH_CONFIG_DIR'] = str(HERE / 'rig_gripper_config')   # cc.init 이 설정을 읽기 전에

import cobot_common as cc                          # noqa: E402
from cobot_common import gripper as G              # noqa: E402  cobot_common 자체 시험이라 내부를 본다

_STEP_N = 2.5                   # 'i'/'d' 한 계단 (드라이버 genCommand)
# 드라이버가 켜질 때 잡는 힘 (rg2 max_force 400).
# 🚨 **브링업 직후 첫 실행에서만** 이 값이다 — 드라이버가 목표 힘을 프로세스 종료 뒤에도 기억한다
#    (3회 연속 실행: 40 → 35 → 30 → 25 N). 그래서 '기대값' 이 아니라 '참고값' 이고 통과 조건이 아니다.
_EXPECT_INIT_N = 40.0
_SAMPLE_S = 0.02                # 값 읽는 주기 (드라이버 발행은 50 Hz)
_SETTLE_SPAN_MM = 0.05          # 이 폭 안에서 머물면 "멈췄다"
_SETTLE_HOLD_S = 0.2            # 그 상태가 이만큼 이어져야 한다
# 한 명령의 대기 상한. 🚨 3.0 s 는 짧았다 — 힘이 약하면 느리게 닫혀 상한에 걸리고
#    **닫는 중간**을 값으로 읽는다(실기 3회차: 10 N 으로 닫다가 36.10 mm 로 기록됐다).
_MOVE_TIMEOUT_S = 8.0


# ────────────────────────────────────────────────────────────── 읽는 도구
def _read():
    """지금 값 한 벌 — (폭 mm, 힘 N 또는 None). 콜백이 저장해 둔 것을 보기만 한다."""
    with G._lock:
        angle, effort = G._joint_angle, G._effort
    width = None if angle is None else G.grip_width()
    force = None if effort is None or effort <= 0.0 else float(effort)
    return width, force


def _wait_first(timeout_s=5.0):
    """첫 값이 올 때까지 기다린다. 브링업이 안 떠 있으면 여기서 걸린다."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        with G._lock:
            if G._joint_angle is not None:
                return True
        time.sleep(_SAMPLE_S)
    return False


def _settle():
    """폭이 멈출 때까지 기다린다 — 완료 판정을 **폭** 으로 했을 때의 실제 소요 시간을 잰다.

    돌려주는 것: (걸린 시간 s, 멈춘 폭 mm, 그동안 읽힌 힘 값 목록)
    """
    t0 = time.monotonic()
    window = []                                   # [(시각, 폭)] — 최근 _SETTLE_HOLD_S 구간만 남긴다
    forces = []
    while time.monotonic() - t0 < _MOVE_TIMEOUT_S:
        now = time.monotonic()
        width, force = _read()
        if force is not None:
            forces.append(force)
        if width is not None:
            window.append((now, width))
            window[:] = [(t, w) for t, w in window if now - t <= _SETTLE_HOLD_S]
            spread = max(w for _, w in window) - min(w for _, w in window)
            if now - t0 >= _SETTLE_HOLD_S and spread <= _SETTLE_SPAN_MM:
                return now - t0, width, forces
        time.sleep(_SAMPLE_S)
    width, _ = _read()
    return _MOVE_TIMEOUT_S, width, forces


def _cmd(command, what):
    """드라이버에 문자열 명령 하나를 보내고 멈출 때까지 기다린다. 결과를 한 줄로 남긴다."""
    G._send(command)                              # 🚨 _wait_done() 은 일부러 안 쓴다(그게 확인 대상이다)
    took, width, forces = _settle()
    shown = f'{width:.2f} mm' if width is not None else '폭 못 읽음'
    force_txt = f'{forces[-1]:.1f} N' if forces else '힘 안 나옴'
    _log().info(f'  {what:<22} {shown:>12}   {force_txt:>10}   ({took:.2f} s)')
    return took, width, forces


def _log():
    return cc.io_node().get_logger()


def _force_now(what='지금 힘'):
    """🚨 힘은 **움직이거나 닫혀 있을 때만** 읽힌다 — 활짝 열린 채 정지면 0 이 나온다(= 모름).

    그래서 닫아서 움직임을 만든 뒤 읽는다. 닫는 것은 빈손이라 안전하고,
    어차피 영점(빈손 닫힘 폭)을 재려면 닫아야 한다.
    돌려주는 것: (힘 N 또는 None, 닫힌 폭 mm)
    """
    _, width, forces = _cmd('c', what)
    return (max(forces) if forces else None), width


def _set_force_to(target_n, now_n):
    """현재 힘에서 target_n 까지 **계산해서** 맞춘다 (세지 않는다 — 읽은 값에서 출발한다).

    🚨 이전 판은 "브링업 직후니 40 N" 을 가정하고 계단을 셌는데, 드라이버가 힘을 기억해서
       두 번째 실행부터 어긋났다. 이제는 읽은 값을 기준으로 계단 수를 구한다.
    돌려주는 것: 맞춘 뒤 다시 읽은 힘 (못 읽으면 None)
    """
    steps = int(round((target_n - now_n) / _STEP_N))
    if steps == 0:
        _log().info(f'  힘 {now_n:.1f} N — 이미 목표 {target_n:.0f} N')
        return now_n
    cmd = 'i' if steps > 0 else 'd'
    got, _ = _n_times_then_read(cmd, abs(steps), f'{now_n:.1f} → {target_n:.0f} N ({cmd} ×{abs(steps)})')
    return got


def _n_times_then_read(command, n, what):
    """같은 명령을 n 번 보내고, **마지막 한 번의 움직임에서** 힘을 읽는다."""
    for _ in range(max(0, n - 1)):
        G._send(command)
    _, width, forces = _cmd(command, what)
    return (max(forces) if forces else None), width


# ────────────────────────────────────────────────────────────── 확인 절차
def probe():
    """①~⑤ 를 차례로 확인하고 {이름: (통과 여부, 설명)} 을 돌려준다."""
    results = {}                                  # 이름 → (통과 여부, 설명)

    _log().info('─' * 72)
    _log().info('① 값이 들어오는가 — 아직 아무 명령도 보내지 않는다')
    if not _wait_first():
        _log().error('  폭 값이 안 들어온다 — 브링업(sodreal)과 /onrobot_joint_states 를 확인한다')
        return {'수신': (False, '폭 값이 아예 안 들어옴')}
    width0, force0 = _read()
    _log().info(f'  폭 {width0:.2f} mm · 힘 '
                + (f'{force0:.1f} N' if force0 else '0 (멈춰 있어서 안 나온다 — 정상)'))
    results['수신'] = (True, f'폭 {width0:.2f} mm')

    _log().info('')
    _log().info('② 지금 힘이 얼마인가 — 🚨 읽으려면 움직여야 한다 (닫아서 읽는다)')
    now, w_close = _force_now('닫기 (힘을 읽으려고)')
    if now is None:
        results['힘 읽기'] = (False, '닫는 동안에도 힘이 안 나온다')
        results['2.5 N 계단'] = (False, '힘을 못 읽어 확인 불가')
        results['힘별 영점'] = (False, '힘을 못 맞춰 건너뜀')
    else:
        results['힘 읽기'] = (True, f'{now:.1f} N')
        if abs(now - _EXPECT_INIT_N) < 0.1:
            _log().info(f'  → {now:.1f} N — 드라이버 초기값. **브링업 직후 첫 실행**으로 보인다')
        else:
            _log().info(f'  → {now:.1f} N — 40 N 이 아니다. 드라이버가 앞선 실행의 힘을 '
                        f'기억하고 있다(정상). 이 값에서 이어서 맞춘다')

        _log().info('')
        _log().info("③ 'd' 한 번에 2.5 N 씩 내려가는가")
        after, _ = _n_times_then_read('d', 1, "'d' ×1")
        if after is None:
            results['2.5 N 계단'] = (False, '힘을 못 읽어 확인 불가')
        else:
            drop = now - after
            ok = abs(drop - _STEP_N) < 0.1
            results['2.5 N 계단'] = (ok, f'{now:.1f} → {after:.1f} N (−{drop:.1f})')
            now = after

        _log().info('')
        _log().info('④ 빈손 영점 — 힘을 맞춘 뒤 닫았을 때 폭 (판정에 쓸 힘과 같은 힘으로 재야 한다)')
        zeros = {}
        for label, target in (('NORMAL', 20.0), ('HOLD', 35.0)):
            got = _set_force_to(target, now)
            if got is None:
                _log().warn(f'  {label}: 힘을 못 읽어 건너뛴다')
                continue
            now = got
            _, w = _force_now(f'빈손 닫기 — {label} {now:.0f} N')
            if w is not None:
                zeros[label] = (w, now)

        if len(zeros) == 2:
            n_w, n_f = zeros['NORMAL']
            h_w, h_f = zeros['HOLD']
            delta = abs(h_w - n_w)
            _log().info(f'  → 힘이 {n_f:.0f} → {h_f:.0f} N 로 바뀌면 빈손 폭이 {delta:.2f} mm '
                        f'달라진다 (고무가 눌리는 양)')
            _log().info('     🚨 이 값을 모르면 NORMAL↔HOLD 전환의 폭 변화를 미끄러짐으로 오판한다')
            results['힘별 영점'] = (True, f'{n_w:.2f}({n_f:.0f}N) / {h_w:.2f}({h_f:.0f}N) · 차이 {delta:.2f}')
        else:
            results['힘별 영점'] = (False, f'두 힘에서 다 못 쟀다 ({len(zeros)}/2)')

    _log().info('')
    _log().info('⑤ 쥐지 않고 닫혀 있는 지금도 힘이 읽히는가')
    time.sleep(0.5)
    _, hold_force = _read()
    results['멈춘 뒤에도 읽힘'] = (
        hold_force is not None,
        f'{hold_force:.1f} N' if hold_force else '안 나옴 (용기를 쥐면 달라질 수 있다)')

    _log().info('')
    _log().info('마무리 — 열어 둔다')
    _cmd('o', '열기')
    return results


# ────────────────────────────────────────────────────────────── 보고
def report(results):
    """결과 표와 "그래서 무엇을 할 것인가" 를 남긴다. 전부 통과면 True."""
    log = _log()
    log.info('')
    log.info('═' * 72)
    log.info('  확인 결과')
    log.info('═' * 72)
    for name, (ok, detail) in results.items():
        log.info(f'  {"✅" if ok else "❌"}  {name:<16} {detail}')
    log.info('═' * 72)

    force_ok = results.get('힘 읽기', (False,))[0] and results.get('2.5 N 계단', (False,))[0]
    if force_ok:
        log.info('  → 힘을 **읽을 수 있다**. gripper.py 의 힘 세는 코드(_anchor_force)를 지우고')
        log.info('     읽기로 바꾼다. D1(0 N 쪽 vs 40 N 쪽) 질문은 철회한다(결정 E16 D-E).')
    else:
        log.warn('  → 힘을 못 읽는다. 지금처럼 **세는 방식**을 유지하고 D1 결정을 기다린다.')
    if results.get('힘별 영점', (False,))[0]:
        log.info('  → 빈손 영점을 측정했다. 이후 폭 판정은 **영점을 뺀 값**으로 한다.')
    log.info('═' * 72)
    return all(ok for ok, _ in results.values())


def main():
    """실행 진입점 — init → 확인 → 보고 → shutdown (SDD §3.2)."""
    cc.init('rig_gripper_probe', robot=False)     # ① 맨 앞에서 한 번 · 로봇 팔은 쓰지 않는다
    try:
        _log().info('🚨 그리퍼가 비어 있는지 확인하세요 — 아무것도 쥐지 않은 상태에서 시작합니다')
        results = probe()
        sys.exit(0 if report(results) else 1)
    except KeyboardInterrupt:
        _log().warn('Ctrl+C — 그리퍼에 아무 명령도 보내지 않고 끝낸다')
        sys.exit(130)
    finally:
        cc.shutdown()                             # ③ 끝낼 때 (Ctrl+C 포함)


if __name__ == '__main__':
    main()
