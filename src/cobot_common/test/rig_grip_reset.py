#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02d 단독 시험 — 그리퍼 **안전 스위치**를 읽고(grip_safety) 푸는(grip_reset) 시험대.

왜 필요한가
    그리퍼 손가락에 무리한 힘이 걸리면 안의 **안전 스위치(S1·S2)** 가 걸린다(RG2 매뉴얼 §6.2.3).
    멀티탭의 과부하 차단 버튼과 같아서, 걸리면 명령을 줘도 꿈쩍 안 하고 **툴 전원을 껐다 켜야만** 풀린다.
    지금까지는 사람이 전원을 뽑았다 꽂았다. 이 시험대는 그것을 **명령 한 줄**로 바꾼다.

실행 (저장소 루트에서, 격리 상태 solo — docs/env/M0609_환경설정.md)
    soc && python3 src/cobot_common/test/rig_grip_reset.py check     # 읽기만 — 🟢 아무것도 안 움직인다
    soc && python3 src/cobot_common/test/rig_grip_reset.py watch     # 계속 지켜본다 (Ctrl+C 로 끝)
    soc && python3 src/cobot_common/test/rig_grip_reset.py reset     # 🚨 툴 전원을 껐다 켠다

    🟢 check·watch 는 **브링업이 없어도 된다**. 그리퍼 상자(컴퓨트박스)와 직접 말하기 때문이다.
       reset 뒤에 드라이버가 살아남았는지까지 보려면 브링업(sod && sodreal)이 떠 있어야 한다.

🚨 이 시험대가 지키는 것
    ① **로봇 팔을 움직이지 않는다** (`init(robot=False)`) — 두산 드라이버도 cell.yaml 좌표도 필요 없다.
    ② check·watch 는 **읽기만** 한다 — 그리퍼에 아무 명령도 보내지 않는다.
    ③ reset 은 **사람이 `yes` 를 쳐야** 실행한다. 전원이 끊기면 쥐고 있던 용기가 떨어지기 때문이다.
       `--empty-hand` 를 주면 그 확인을 건너뛴다(손이 빈 것을 이미 아는 경우에만).
    ④ 상자 주소 같은 진짜 값은 **팀 params.yaml 의 f2.gripper_box** 를 그대로 쓴다
       (다른 rig 과 달리 PREWASH_CONFIG_DIR 을 바꾸지 않는다 — 여기서 확인해야 실기 값이 맞는지 알 수 있다).

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
종료 코드 0(통과) / 1(걸려 있음·못 풀었음) / 2(상자와 말이 안 통함·실행 거부) / 130(Ctrl+C).
"""
import argparse
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
COMMON_ROOT = HERE.parent
if str(COMMON_ROOT) not in sys.path:
    sys.path.insert(0, str(COMMON_ROOT))

import cobot_common as cc                          # noqa: E402
from cobot_common import gripper as G              # noqa: E402  cobot_common 자체 시험이라 내부를 본다


def _line(s):
    """읽은 상태를 한 줄로. 걸렸으면 앞에 표시를 단다."""
    return ('🚨 걸림 ' if s['tripped'] else '🟢 정상 ') + G._safety_text(s)


# ────────────────────────────────────────────────────────────── 명령
def cmd_check(a, p, log):
    """상자에 붙어 안전 스위치를 **읽기만** 한다. 그리퍼는 움직이지 않는다."""
    conf = G._box_cfg()
    log.info(f"그리퍼 상자 {conf['ip']}:{conf['port']} · 툴 번호 {conf['tool_unit']} — 읽기만 한다")
    try:
        s = cc.grip_safety()
    except cc.GripperBoxError as e:
        log.error(f'{e}')
        log.error('  → 실기 전원·랜선을 확인한다. Virtual 에는 이 상자가 없다(그때는 이 오류가 정상)')
        return 2
    log.info(f'  {_line(s)}')
    if s['tripped']:
        log.warning('  → 걸려 있다. 손가락에 걸린 것을 치운 뒤 reset 을 쓴다')
        return 1
    log.info('  → 안전 스위치는 정상이다')
    return 0


def cmd_watch(a, p, log):
    """계속 지켜본다 — 일부러 걸리게 해 보고 **언제 바뀌는지** 눈으로 확인할 때 쓴다."""
    interval = float(a.interval if a.interval is not None else p['watch_interval_s'])
    rounds = int(a.n if a.n is not None else p['watch_rounds'])
    log.info(f'{interval:g}s 마다 읽는다' + (f' ({rounds}회)' if rounds > 0 else ' (Ctrl+C 로 끝)'))
    seen, i, read_ok, tripped_once = None, 0, 0, False
    while rounds <= 0 or i < rounds:
        i += 1
        try:
            s = cc.grip_safety()
        except cc.GripperBoxError as e:
            if seen != 'ERR':                        # 같은 오류를 도배하지 않는다
                log.error(f'  [{i}] 못 읽었다: {e}')
                seen = 'ERR'
            time.sleep(interval)
            continue
        read_ok += 1
        key = tuple(sorted(s.items()))
        if key != seen:                              # 바뀔 때만 찍는다 — 화면이 조용해야 변화가 보인다
            log.info(f'  [{i}] {_line(s)}')
            seen = key
        tripped_once = tripped_once or s['tripped']
        time.sleep(interval)
    if read_ok == 0:                                 # 한 번도 못 읽었으면 "안 걸렸다" 가 아니다
        log.error(f'  끝 — {i}회 모두 못 읽었다. 상자와 말이 통하지 않는다')
        return 2
    log.info(f'  끝 — {read_ok}회 읽었다 · {"걸린 적 있다" if tripped_once else "한 번도 안 걸렸다"}')
    return 1 if tripped_once else 0


def cmd_reset(a, p, log):
    """🚨 툴 전원을 껐다 켠다. 사람이 `yes` 를 쳐야 실행한다."""
    try:
        before = cc.grip_safety()
        log.info(f'  지금: {_line(before)}')
        if not before['tripped']:
            log.warning('  걸려 있지 않다 — 그래도 전원을 껐다 켤 수 있다(확인을 거치면)')
    except cc.GripperBoxError as e:
        log.warning(f'  지금 상태를 못 읽었다({e}) — 그래도 재시작을 보낼 수는 있다')

    if not a.empty_hand and not _ask(log):
        log.info('  취소했다 — 아무것도 보내지 않았다')
        return 2
    try:
        after = cc.grip_reset(empty_hand=True)
    except cc.GripperBoxError as e:
        log.error(f'{e}')
        return 2
    log.info(f'  결과: {_line(after)}')
    if after['driver_alive'] is False:
        log.warning('  → 그리퍼 드라이버가 죽었다. 브링업을 다시 띄운다 (sod && sodreal)')
    elif after['driver_alive'] is None:
        log.info('  → 드라이버 생사는 확인하지 않았다(브링업 없이 돌렸다)')
    else:
        log.info('  → 드라이버는 살아남았다')
    return 1 if after['tripped'] else 0


def _ask(log):
    """🚨 사람 확인 — 전원이 끊기면 쥐고 있던 용기가 떨어진다."""
    width = None
    try:
        width = cc.grip_width()
    except RuntimeError:
        pass                                          # 브링업이 없으면 폭을 모른다 — 그래도 묻는다
    log.warning('🚨 툴 전원을 껐다 켭니다. 쥐고 있는 것은 **떨어집니다**.'
                + (f' (지금 폭 {width:.1f} mm)' if width is not None else ' (폭을 모른다 — 브링업 없음)'))
    try:
        return input('   그리퍼 손이 비었습니까? 비었으면 yes 를 그대로 입력 > ').strip().lower() == 'yes'
    except EOFError:                                  # 화면 없이 돌린 경우 — 확인을 못 받았으니 안 한다
        return False


# ────────────────────────────────────────────────────────────── 실행
_CMDS = {'check': cmd_check, 'watch': cmd_watch, 'reset': cmd_reset}


def main() -> int:
    ap = argparse.ArgumentParser(description='그리퍼 안전 스위치 읽기·풀기 시험 (실기)')
    ap.add_argument('which', choices=list(_CMDS),
                    help='check=읽기만 · watch=계속 지켜보기 · reset=툴 전원 껐다 켜기')
    ap.add_argument('-n', type=int, default=None, help='watch 반복 횟수 (0 이면 Ctrl+C 까지)')
    ap.add_argument('--interval', type=float, default=None, help='watch 간격(초)')
    ap.add_argument('--empty-hand', action='store_true',
                    help='🚨 reset 의 사람 확인을 건너뛴다 — 손이 빈 것을 이미 아는 경우에만')
    a = ap.parse_args()

    with open(HERE / 'rig_grip_reset.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)

    cc.init('rig_grip_reset', robot=False)            # ① 팔을 안 쓴다 — 상자와만 말한다
    log = cc.io_node().get_logger()
    try:
        return _CMDS[a.which](a, p, log)
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 그리퍼에 아무 명령도 보내지 않았다')
        return 130
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        log.error(f'{type(e).__name__}: {e}')
        return 1
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
