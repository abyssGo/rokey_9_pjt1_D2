# -*- coding: utf-8 -*-
"""그리퍼 함수(RG2) — 담당 민범진 (INF-02d). 함수 표는 docs/03_설계_SDD.md §3.1.

강사 배포 드라이버(`onrobot_rg_control`)를 통해 쓴다. 드라이버 소스에서 확인한 사실:

명령 — srv `/onrobot/sendCommand` 는 문자열 하나만 받는다 (OnRobotRGControllerServer.genCommand):
    '600'  폭 60.0 mm (0.1 mm 단위) · 힘은 직전 값 유지
    'o'    열기(최대 폭)          · 힘은 직전 값 유지
    'c'    닫기(폭 0)             · 힘은 직전 값 유지
    'i'    힘 +2.5 N · 직전 폭으로 다시 파지
    'd'    힘 −2.5 N · 직전 폭으로 다시 파지
  주의: 힘을 절대값으로 줄 수 없다. 2.5 N 계단으로만 오르내린다.
  'i'/'d' 가 "같은 폭으로 힘만 바꿔 다시 파지" 라서 grip_level 에 그대로 맞는다.

현재 힘 — 읽을 수 있다(실기 확인). `/onrobot_joint_states` 의 effort 가
  드라이버의 현재 목표 힘(N)이다(getStatus: `effort = rgfr/10`, 상태 비트가 켜져 있을 때).
  주의: 움직이거나 닫혀 있을 때만 읽힌다 — 활짝 열린 채 정지하면 0 이 온다(= 모름).
  주의: 드라이버가 힘을 프로세스 종료 뒤에도 기억한다(3회 연속 실행: 40 → 35 → 30 → 25 N)
     → "브링업 직후 40 N" 은 첫 실행에서만 참이다. 세지 않고 매번 읽어서 맞춘다.

완료 — 서비스 응답은 "보냈다" 일 뿐이다(`res.success = True` 를 무조건 돌려준다 — 실패를 알 수 없다).
  주의: 끝났는지는 폭이 멈추는 것으로 본다. effort 로 보면 파지에 성공했을 때 "잡았다" 비트 때문에
     0 이 되지 않아 잡을 때마다 상한까지 기다린다(실기에서 확인).

현재 폭 — 드라이버는 폭(mm)을 발행하지 않는다. `/onrobot_joint_states` 의 관절각을
  드라이버와 같은 식으로 환산한다(jointValueToWidth). `finger_joint` 의 mimic 비율이 1 이라
  position[finger_joint] 가 곧 관절각이다. 왕복 검증 오차 0.000 mm,
  그릇 벽 구간(0~5 mm)에서 1 mm 당 관절각 차이 0.0091 rad — 분해능 충분.

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import threading
import time
from contextlib import contextmanager

import numpy as np

__all__ = ['grip', 'grip_level', 'release', 'grip_width', 'set_grip_preset',
           'grip_safety', 'grip_reset', 'GripperBoxError']


class GripperBoxError(RuntimeError):
    """그리퍼 상자(컴퓨트박스)와 말이 안 통할 때. 그리퍼 명령 실패(RuntimeError)와 구분하려고 따로 둔다."""


# ── 드라이버 상수 (OnRobotRGControllerServer.py 의 RG2 분기에서 그대로) ──
_L1, _L3 = 0.108505, 0.055
_THETA1, _THETA3, _DY = 1.41371, 0.76794, -0.0144
_MAX_FORCE_N = 40.0                  # max_force 400 (0.1 N 단위)
_OPEN_WIDTH_MM = 100.0               # 이 폭보다 넓으면 '열려 있다(빈손)' — grip_level 이 힘 전환·탐색을 거부한다(RG2 최대 110)
_MAX_WIDTH_MM = 110.0                # max_width 1100 (0.1 mm 단위)
_FORCE_STEP_N = 2.5                  # 'i'/'d' 한 계단
_FINGER_JOINT = 'finger_joint'       # mimic 비율 1 → position 이 곧 관절각
_POLL_S = 0.02                       # 폭을 들여다보는 간격 (드라이버 발행 50 Hz)
_SETTLE_SPAN_MM = 0.05               # 이 폭 안에서 머물면 "멈췄다"
_SETTLE_HOLD_S = 0.2                 # 그 상태가 이만큼 이어져야 한다

# ── 안전 스위치 (상자에서 직접 읽는다) ──
# OnRobot RG2 공식 Modbus 규격 (OnRobotRGInput.msg 참조):
# status_addr(258) + 10 = 268번 레지스터(regs[10])가 `gsta`(상태 비트필드)다.
#   Bit 0: Busy (동작 중)
#   Bit 1: Grip detected (파지 감지)
#   Bit 2: S1 pushed (스위치 1 눌림)
#   Bit 3: S1 triggered (안전회로 1 걸림 — 전원 재시작 필요)
#   Bit 4: S2 pushed (스위치 2 눌림)
#   Bit 5: S2 triggered (안전회로 2 걸림 — 전원 재시작 필요)
#   Bit 6: Safety error (전원 켤 때 스위치 눌림 오류)
_GSTA_INDEX = 10
_SAFETY_BITS = {
    's1_pushed': 2,
    's1_triggered': 3,
    's2_pushed': 4,
    's2_triggered': 5,
    'safety': 6,
}
_TRIPPED_FIELDS = ('s1_triggered', 's2_triggered')       # 이 중 하나라도 0 이 아니면 걸린 것
_BOX_KEYS = ('ip', 'port', 'tool_unit', 'box_unit', 'status_addr', 'status_count',
             'restart_addr', 'restart_value', 'connect_timeout_s', 'restart_wait_s', 'driver_alive_s')
_RESET_POLL_S = 0.5                  # 전원이 다시 들어왔나 다시 읽어 보는 간격

_lock = threading.Lock()
_client = None                       # /onrobot/sendCommand
_joint_angle = None                  # 최신 관절각(rad)
_effort = None                       # 최신 effort — 0.0 이면 멈춘 것
# 주의: 마지막으로 읽은 힘(N). 셈으로 만들지 않는다 — 콜백이 effort 에서 갱신한다.
#    드라이버가 목표 힘을 프로세스 종료 뒤에도 기억해서(실기: 3회 연속 40 → 35 → 30 → 25 N)
#    "브링업 직후 40 N" 같은 가정은 첫 실행에서만 맞는다. 그래서 세지 않고 읽는다.
#    주의: 힘은 움직이거나 닫혀 있을 때만 읽힌다 — 활짝 열린 채 정지하면 0 이 온다(= 모름).
#       그래서 마지막으로 읽은 값을 들고 있는다. 어떤 움직임이든 일어나면 콜백이 갱신한다.
_force_n = None
# 지금 쥔 용기를 어느 프리셋으로 잡았는지(None = 종류 프리셋). 컵은 반납 자리에서 벽(테두리 · presets.CUP · HOLD 35 N)으로 집고,
# 홈 C 에서 옆면 몸통(presets.CUP_SIDE · 고정 폭 70 · 10 N)으로 다시 잡는다. grip_level(kind, HOLD) 이 kind 프리셋의 35 N 을
# 몸통에 걸면 컵이 눌린다(E19: 20 N 에서 안전 스위치) → 재파지한 쪽(f1)이 set_grip_preset 으로 알려 주고 release() 가 지운다.
_held_preset = None
_stamp = None                        # /onrobot_joint_states 를 마지막으로 받은 시각(monotonic). 드라이버 생사 판정용


def setup_io(node):
    """init() 이 실행기를 돌리기 전에 한 번 불러 준다 (SDD §3.1). 콜백은 값 저장만."""
    global _client
    from onrobot_rg_msgs.srv import SetCommand
    from sensor_msgs.msg import JointState

    _client = node.create_client(SetCommand, '/onrobot/sendCommand')
    node.create_subscription(JointState, '/onrobot_joint_states', _on_joint_states, 10)


def _on_joint_states(msg):
    """주의: 값 저장만 한다 — 로봇 함수를 부르지 않는다 (SDD §3.2 규칙 ③)."""
    global _joint_angle, _effort, _force_n, _stamp
    try:
        i = list(msg.name).index(_FINGER_JOINT)
    except ValueError:
        i = 0
    with _lock:
        _stamp = time.monotonic()
        if i < len(msg.position):
            _joint_angle = float(msg.position[i])
        if i < len(msg.effort):
            _effort = float(msg.effort[i])
            # 주의: 값 저장만 한다. effort > 0 이면 그게 드라이버의 현재 목표 힘(N) 이다
            #    (드라이버 getStatus: effort = rgfr/10, 상태 비트가 켜져 있을 때만).
            if _effort > 0.0:
                _force_n = float(_effort)


# ------------------------------------------------------------------ 공개 함수
def grip(width, force):
    """목표 폭(mm)·힘(N)으로 잡고 완료를 기다린 뒤 실제 폭(mm) 을 돌려준다.

    주의: 부르는 쪽은 목표 폭을 기대보다 작게 준다(SDD §5.2).
       같은 값을 주면 빈손으로 닫아도 그 폭에서 멈춘 것처럼 보인다 —
       그릇은 벽 파지라 기대 폭이 ≈ 2 mm 밖에 안 된다.
    """
    _set_force(float(force))                               # 잡기 전에 맞춘다 (아직 빈손)
    before = _width_or_none()
    _send(str(int(round(_clamp_width(width) * 10))))       # 0.1 mm 단위
    after = _wait_done()
    _warn_if_stuck(before, after, f'폭 {float(width):.1f} mm 로 잡기')
    with _lock:
        held_force = _force_n
    # 힘 계단('i'/'d')은 그리퍼가 열려 있을 때 보내면 읽는 값(effort)이 갱신되지 않아 "못 맞춘다 → 20 N" 경고가 나온다.
    #    실제로 어떤 힘으로 쥐었는지는 닫힌 뒤 읽어야 안다 → 여기서 남긴다(컵 옆면 5 N 이 약해 이송 중 돌아간 실기의 근거).
    _log().info(f'grip 완료 — 폭 {after:.2f} mm · 쥔 뒤 읽은 힘 ' + (f'{held_force:.1f} N' if held_force is not None else '없음')
                + f' (명령 {float(force):.1f} N)')
    return grip_width()


def grip_level(kind, level):
    """파지 힘 2단계 전환 NORMAL ↔ HOLD. 같은 폭 목표로 힘만 바꿔 다시 파지 (SDD §3.1).

    털기·담금·물 털기는 시작할 때 HOLD, 끝날 때 NORMAL 로 되돌린다(IRD §4).
    드라이버의 'i'/'d' 가 직전 폭으로 다시 파지하므로 폭을 다시 명령하지 않는다.
    """
    from .bootstrap import cfg
    level = str(level).upper()
    if level not in ('NORMAL', 'HOLD'):
        raise ValueError(f"grip_level: level={level!r} — 'NORMAL' 또는 'HOLD'")
    with _lock:
        name = _held_preset or kind                      # 다시 잡은 프리셋(컵 옆면 CUP_SIDE)이 있으면 그 힘을 쓴다
    preset = _preset(cfg(), name)
    key = 'grip_force_n' if level == 'NORMAL' else 'hold_force_n'
    if key not in preset:
        raise KeyError(f'cell.presets.{name}.{key} 가 없다 — 프리셋을 확인한다')
    w_now = _width_or_none()
    if w_now is not None and w_now > _OPEN_WIDTH_MM:
        # 주의: 실기에서 명령이 섞여 그리퍼가 열린 채(110.6) 담금이 시작됐고, 아래 탐색 'i' 가 빈손을 꽉 닫아 버렸다
        #    → 쥐고 있지 않으면 힘 전환도 탐색도 하지 않는다(부르는 쪽이 GRIP_FAIL 로 처리)
        raise RuntimeError(f'grip_level: 그리퍼가 열려 있다(폭 {w_now:.1f} mm > {_OPEN_WIDTH_MM:g}) — 쥐고 있을 때만 힘을 바꾼다')
    with _lock:
        known = _force_n is not None
    if not known:
        # 주의: 여기는 이미 쥐고 있는 자리다. 힘을 모르는 채 계단을 보내면 어디로 갈지 모른다.
        #    E36 실기: 새 프로세스가 쥔 용기로 시작하면 드라이버가 effort 를 안 보내 여기서 멈추는 일이
        #    났다(상태 비트가 꺼져 있으면 effort 0). 놓지 않고 읽는 방법 = 한 계단 올려(+2.5 N) 같은 폭으로 다시 잡기
        #    ('i' 는 직전 폭으로 재파지 → 움직이는 동안 effort 가 온다). 그 다음 _set_force 가 읽은 값에서 목표까지 맞춘다.
        _log().warn('grip_level: 그리퍼 힘을 아직 못 읽었다 — 쥔 채로 한 계단(+2.5 N) 다시 잡아 읽는다')
        _send('i')
        _wait_done()
        with _lock:
            known = _force_n is not None
        if not known:
            raise RuntimeError(
                'grip_level: 그리퍼 힘을 다시 잡아도 못 읽었다 — 모르는 채로 힘을 바꾸면 용기를 놓칠 수 있다. '
                '드라이버(/onrobot_joint_states effort)를 확인하고, 이 프로그램에서 cc.release() 나 cc.grip() 을 먼저 부른다')
    before = grip_width()
    _set_force(float(preset[key]))                       # 'i'/'d' 안에서 _wait_done 까지 한다
    after = grip_width()
    _log().info(f'grip_level({kind}, {level}) — 폭 {before:.1f} → {after:.1f} mm' + (f' · 프리셋 {name}' if name != kind else ''))
    return after


def release():
    """그리퍼 열기. 힘 설정은 그대로 둔다(드라이버의 'o' 가 힘을 안 바꾼다).

    주의: 힘은 움직이거나 닫혀 있을 때만 읽힌다. 이미 활짝 열려 있으면 'o' 가 아무 움직임도
       안 만들어 못 읽는다 → 아직 한 번도 못 읽었으면 빈손으로 한 번 닫았다 연다.
       여기가 손이 빈 게 확실한 유일한 자리다 — 그래서 그리퍼를 쓰는 프로그램은
       아무것도 쥐지 않은 상태의 release() 로 시작한다(그 약속은 그대로다).
    """
    global _held_preset
    with _lock:
        _held_preset = None                          # 놓으면 "무엇으로 잡고 있는지" 기억도 지운다
    before = _width_or_none()
    _send('o')
    after = _wait_done()
    _warn_if_stuck(before, after, '열기')
    with _lock:
        known = _force_n is not None
    if not known:
        _log().info('그리퍼 힘을 아직 못 읽었다 — 빈손으로 한 번 닫았다 열어서 읽는다')
        _send('c')
        _wait_done()
        _send('o')
        _wait_done()


def set_grip_preset(name):
    """지금 쥐고 있는 용기를 어느 프리셋으로 잡았는지 기억한다 (None = 종류(kind) 프리셋으로 되돌림).

    컵은 반납 자리에서 벽(presets.CUP)으로 집고 홈 C 에서 옆면 몸통(presets.CUP_SIDE · 고정 폭 70 · 10 N)으로
       다시 잡는다. 그 뒤 f2 의 grip_level('CUP', 'HOLD') 가 CUP 의 35 N 을 몸통에 걸면 컵이 눌린다(E19) →
       다시 잡은 쪽(f1._regrip)이 여기로 알려 주면 grip_level 이 그 프리셋의 힘을 쓴다. release() 가 지운다.
    """
    global _held_preset
    with _lock:
        _held_preset = None if name is None else str(name)


def grip_width():
    """현재 그리퍼 폭(mm). `/onrobot_joint_states` 의 관절각을 드라이버와 같은 식으로 환산한다."""
    with _lock:
        th = _joint_angle
    if th is None:
        raise RuntimeError('그리퍼 관절각을 아직 못 받았다 — /onrobot_joint_states 와 브링업을 확인한다')
    return float((np.cos(th + _THETA3) * _L3 + _DY + _L1 * np.cos(_THETA1)) * 2 * 1000.0)


def grip_safety():
    """그리퍼 안전 스위치 상태를 상자에서 직접 읽는다 — 주의: 그리퍼를 움직이지 않는다(읽기만 한다).

    돌려주는 것 (숫자는 상자가 준 값 그대로):
        {'tripped': True/False,      ← 걸렸나 (s1_triggered · s2_triggered 중 하나라도 0 이 아니면 True)
         's1_pushed': 0, 's1_triggered': 0, 's2_pushed': 0, 's2_triggered': 0, 'safety': 0}

    말이 안 통하면 `GripperBoxError` 를 낸다 — "정상이다" 와 "판정을 못 했다" 를 부르는 쪽이 가릴 수 있게.
    주의: Virtual 에는 상자가 없어 늘 GripperBoxError 다(그게 정상이다).
    """
    conf = _box_cfg()
    with _box_open(conf) as client:
        return _read_safety(client, conf)


def grip_reset(empty_hand=False, wait_s=None):
    """안전 스위치를 푼다 — 툴 전원을 잠깐 껐다 켠다. 푼 뒤의 상태(dict)를 돌려준다.

    주의: 쥐고 있던 것을 떨어뜨린다. 전원이 끊기면 손가락을 잡아 주는 힘이 사라진다.
       그래서 손이 빈 것을 눈으로 확인하고 `empty_hand=True` 로 불러야 실행한다(AGENTS 규칙 1).
    주의: 메인 스레드에서만 부른다 — 콜백·타이머에서 용기를 떨어뜨리면 안 된다(SDD §3.2).

    하는 일  ① 지금 상태를 읽어 기록한다  ② 상자에 "툴 전원 재시작"(레지스터 0 ← 2, 상자 번호 63)을 쓴다
            ③ restart_wait_s 안에 풀렸는지 다시 읽어 확인한다  ④ 드라이버가 살아남았는지 본다

    돌려주는 것: grip_safety() 의 dict + {'driver_alive': True/False/None}
        driver_alive=False → 그리퍼 드라이버가 죽었다. 브링업을 다시 띄운다.
        driver_alive=None  → 판단 불가(`/onrobot_joint_states` 를 한 번도 못 받았다)
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('grip_reset() 은 메인 스레드에서만 부른다 — '
                           '콜백·타이머에서 용기를 떨어뜨리면 안 된다 (SDD §3.2)')
    conf = _box_cfg()
    width = _width_or_none()
    if not empty_hand:
        raise RuntimeError(
            'grip_reset(): 툴 전원을 껐다 켜면 **쥐고 있던 것을 떨어뜨린다**'
            + (f' (지금 폭 {width:.1f} mm)' if width is not None else '')
            + '. 손이 빈 것을 눈으로 확인하고 grip_reset(empty_hand=True) 로 다시 부른다')

    try:
        before = grip_safety()
    except GripperBoxError as e:
        _log().warn(f'전원 재시작 **전** 상태를 못 읽었다({e}) — 재시작 명령은 그대로 보낸다')
    else:
        _log().info(f"전원 재시작 전 — {'걸림' if before['tripped'] else '정상'} · {_safety_text(before)}")

    _log().warn('그리퍼 툴 전원을 껐다 켠다 (안전 스위치 풀기) — 🚨 쥐고 있던 것은 떨어진다')
    t_mark = time.monotonic()
    with _box_open(conf) as client:
        try:
            rr = client.write_register(address=int(conf['restart_addr']),
                                       value=int(conf['restart_value']),
                                       slave=int(conf['box_unit']))
            if rr is not None and hasattr(rr, 'isError') and rr.isError():
                _log().warn(f'상자가 전원 재시작 명령에 오류로 답했다({rr!r}) — 그래도 먹혔을 수 있어 아래에서 확인한다')
        except Exception as e:                           # noqa: BLE001 pymodbus 예외 종류가 판마다 다르다
            _log().warn(f'전원 재시작 명령의 응답을 못 받았다({e!r}) — 실제로는 먹혔을 수 있어 아래에서 확인한다')

    wait = float(conf['restart_wait_s']) if wait_s is None else float(wait_s)
    after, last = None, None
    t0 = time.monotonic()
    while time.monotonic() - t0 < wait:
        time.sleep(_RESET_POLL_S)
        try:
            after = grip_safety()
        except GripperBoxError as e:                     # 아직 꺼져 있다 — 다시 붙을 때까지 기다린다
            after, last = None, e
            continue
        if not after['tripped']:
            break
    took = time.monotonic() - t0
    if after is None:
        raise GripperBoxError(
            f'전원 재시작 뒤 {wait:.0f}s 동안 그리퍼 상태를 못 읽었다 (마지막 오류: {last}). '
            '툴 전원이 돌아오지 않았거나 상자와의 연결이 끊겼다 — 브링업부터 다시 띄운다')

    after['driver_alive'] = alive = _driver_alive_since(t_mark, conf['driver_alive_s'])
    if after['tripped']:
        _log().error(f'🚨 전원을 다시 넣었는데도 안전 스위치가 걸려 있다 ({_safety_text(after)}) — '
                     '손가락에 걸린 것을 치우고 다시 부른다')
    else:
        _log().info(f'그리퍼 안전 스위치가 풀렸다 ({took:.1f}s) — {_safety_text(after)}')
    if alive is False:
        _log().warn('🚨 그리퍼 드라이버가 멈췄다(/onrobot_joint_states 가 다시 오지 않는다) — '
                    '전원이 끊긴 순간 드라이버가 죽은 것이다. 브링업을 다시 띄운다(sod && sodreal)')
    return after


# ------------------------------------------------------------------ 내부
def _send(command):
    """드라이버에 문자열 명령 하나를 보낸다. 통신 노드가 다른 스레드에서 돌고 있어 동기 호출이 된다."""
    from onrobot_rg_msgs.srv import SetCommand
    if _client is None:
        raise RuntimeError('cobot_common.init(name) 을 먼저 부른다 (그리퍼 클라이언트가 없다)')
    if not _client.wait_for_service(timeout_sec=_timeout()):
        raise RuntimeError('/onrobot/sendCommand 가 안 보인다 — 브링업을 확인한다')
    req = SetCommand.Request()
    req.command = str(command)
    res = _client.call(req)
    if res is None or not res.success:
        raise RuntimeError(f'그리퍼 명령 {command!r} 실패 — {getattr(res, "message", "응답 없음")}')


def _set_force(target_n):
    """목표 힘에 맞춘다 — 주의: 세지 않고 읽어서 맞춘다.

    드라이버는 힘을 절대값으로 못 받고 2.5 N 계단('i'/'d')으로만 오르내린다. 그런데 현재 힘은
    effort 로 읽을 수 있으므로(머리말) 마지막으로 읽은 값에서 계단 수를 구하면 된다.
    예전처럼 0 N 까지 내려 기준을 잡던 방식(_anchor_force)은 없앴다 —
      · 0 N 은 데이터시트 유효 범위(3~40 N) 밖이고
      · 쥔 채로 하면 힘이 0 을 지나는 동안 용기를 놓치며
      · 매번 17회 통신이 들었는데, 무엇보다 드라이버가 힘을 기억해서 셈이 어긋났다(실기).

    주의: 한 번도 못 읽었으면(_force_n is None) 맞출 수 없다 — 부르는 쪽이 먼저 움직여 준다(release).
    """
    target_n = max(0.0, min(_MAX_FORCE_N, float(target_n)))
    with _lock:
        now = _force_n
    if now is None:
        raise RuntimeError(
            '그리퍼 힘을 아직 한 번도 못 읽었다 — 힘은 움직이거나 닫혀 있을 때만 읽힌다. '
            'cc.release() 를 먼저 불러 한 번 움직인 뒤에 쓴다')
    steps = int(round((target_n - now) / _FORCE_STEP_N))
    if steps == 0:
        return now
    cmd = 'i' if steps > 0 else 'd'
    for _ in range(abs(steps)):
        _send(cmd)
    _wait_done()                                         # 'i'/'d' 는 직전 폭으로 다시 파지한다
    with _lock:
        got = _force_n
    if got is None or abs(got - target_n) > 0.01:
        _log().warn(f'그리퍼 힘 {target_n:.1f} N 을 정확히 못 맞춘다 (2.5 N 계단) → 읽은 값 '
                    + (f'{got:.1f} N' if got is not None else '없음'))
    return got


def _width_or_none():
    try:
        return grip_width()
    except RuntimeError:
        return None


def _warn_if_stuck(before, after, what):
    """주의: 폭을 명령했는데 전혀 안 움직이면 안전 스위치를 읽어서 확인한다.

    RG2 매뉴얼 §6.2.3 — 안전 스위치(S1·S2)가 걸리면 그리퍼가 움직이지 않고
    전원을 다시 넣어야만 풀린다. 시연 중에 걸리면 그 자리에서 멈춘다.
    예전에는 "걸렸을 수도 있다" 고 짐작만 했다. 지금은 상자에서 직접 읽어
       걸렸다 / 아니다 를 말한다. 못 읽으면(Virtual·랜선 없음) 예전처럼 짐작으로 되돌아간다.
    주의: 스스로 풀지는 않는다 — 전원을 껐다 켜면 쥔 것을 떨어뜨리기 때문이다(AGENTS 규칙 1).
       사람이 `cc.grip_reset(empty_hand=True)` 를 부른다.
    """
    if before is None or after is None or abs(after - before) >= _SETTLE_SPAN_MM:
        return
    stayed = f'폭 {before:.2f} mm 그대로'
    try:
        s = grip_safety()
    except Exception as e:                               # noqa: BLE001 진단이 본 동작을 막으면 안 된다
        _log().warn(f'그리퍼가 "{what}" 에 **전혀 움직이지 않았다** ({stayed}). '
                    f'안전 스위치는 확인하지 못했다({e}) — 이미 그 자리였을 수도, 걸렸을 수도 있다. '
                    'cc.grip_safety() 로 직접 확인한다')
        return
    if s['tripped']:
        _log().error(f'🚨 그리퍼 **안전 스위치가 걸렸다** — "{what}" 명령이 무시됐다 ({stayed}). '
                     f'{_safety_text(s)}. 손가락에 걸린 것을 치운 뒤 '
                     'cc.grip_reset(empty_hand=True) 로 툴 전원을 껐다 켠다 (쥔 것은 떨어진다)')
    else:
        _log().warn(f'그리퍼가 "{what}" 에 전혀 움직이지 않았다 ({stayed}). '
                    f'안전 스위치는 정상이다({_safety_text(s)}) — 이미 그 자리였을 가능성이 크다')


def _wait_done():
    """움직임이 끝날 때까지 기다린다 — 폭이 멈추는 것으로 본다. 멈춘 폭(mm)을 돌려준다.

    주의: 예전에는 effort 가 0 이 되는 것으로 봤다. 그런데 드라이버의 `busy` 는 상태 레지스터를
       통째로 읽은 값이라(비트 묶음), 파지에 성공하면 "잡았다" 비트 때문에 0 이 되지 않는다
       → 잡을 때마다 상한까지 기다렸다. 실기에서 확인했고, 폭 기준으로 바꾸니 0.20~0.34 s 다.
    주의: 폭은 0.1 mm 단위로 계속 오므로 "더 안 변하면 끝" 이 더 정확하다.
    """
    limit = _timeout()
    t0 = time.monotonic()
    window = []                                          # [(시각, 폭)] — 최근 _SETTLE_HOLD_S 구간만 남긴다
    while time.monotonic() - t0 < limit:
        now = time.monotonic()
        try:
            w = grip_width()
        except RuntimeError:                             # 아직 관절각이 안 왔다
            time.sleep(_POLL_S)
            continue
        window.append((now, w))
        window[:] = [(t, x) for t, x in window if now - t <= _SETTLE_HOLD_S]
        spread = max(x for _, x in window) - min(x for _, x in window)
        if now - t0 >= _SETTLE_HOLD_S and spread <= _SETTLE_SPAN_MM:
            return w
        time.sleep(_POLL_S)
    _log().warn(f'그리퍼 동작이 {limit:.1f}s 안에 안 끝났다 — 그대로 진행한다')
    try:
        return grip_width()
    except RuntimeError:
        return None


def _clamp_width(mm):
    w = float(mm)
    if not 0.0 <= w <= _MAX_WIDTH_MM:
        _log().warn(f'그리퍼 폭 {w:.1f} mm 는 범위(0~{_MAX_WIDTH_MM:.0f}) 밖 — 잘라서 보낸다')
    return max(0.0, min(_MAX_WIDTH_MM, w))


def _preset(conf, kind):
    presets = ((conf.get('cell') or {}).get('presets') or {})
    if kind not in presets:
        raise KeyError(f'cell.presets.{kind} 가 없다 — 티칭·프리셋을 확인한다')
    return presets[kind] or {}


def _timeout():
    from .bootstrap import cfg
    try:
        return float((cfg().get('cell') or {}).get('limits', {}).get('timeout_s') or 10.0)
    except Exception:                                    # noqa: BLE001 — 설정이 없어도 기본값으로 돈다
        return 10.0


def _log():
    from .bootstrap import io_node
    return io_node().get_logger()


# ------------------------------------------------------------------ 내부: 그리퍼 상자(컴퓨트박스) 직접 통신
def _box_cfg():
    """params.yaml 의 `f2.gripper_box`. 값이 비어 있으면 GripperBoxError — 모르는 주소로 쏘지 않는다."""
    from .bootstrap import cfg
    conf = ((cfg().get('f2') or {}).get('gripper_box') or {})
    missing = [k for k in _BOX_KEYS if conf.get(k) is None]
    if missing:
        raise GripperBoxError(f'params.yaml 의 f2.gripper_box 에 {missing} 가 없거나 비어 있다 — '
                              '그리퍼 상자 주소를 채운다 (AGENTS.md 규칙 6: 코드에 박지 않는다)')
    return conf


@contextmanager
def _box_open(conf):
    """그리퍼 상자에 잠깐 붙었다 뗀다.

    주의: 부를 때마다 새로 붙는다. ① 전원을 껐다 켜면 쓰던 연결이 끊기고
       ② 드라이버가 이미 50 Hz 로 붙어 있어서 우리 연결은 짧을수록 서로 방해가 없다.
    """
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError as e:
        raise GripperBoxError('pymodbus 가 없다 — sudo apt install python3-pymodbus '
                              '(🚨 pip 로 깔면 최신판이 와서 드라이버가 죽는다 — AGENTS.md §5)') from e
    client = ModbusTcpClient(host=str(conf['ip']), port=int(conf['port']),
                             timeout=float(conf['connect_timeout_s']))
    try:
        if not client.connect():
            raise GripperBoxError(f"그리퍼 상자 {conf['ip']}:{conf['port']} 에 붙지 못했다 — "
                                  '실기 전원·랜선을 확인한다 (Virtual 에는 이 상자가 없다)')
        yield client
    finally:
        try:
            client.close()
        except Exception:                                # noqa: BLE001 닫기 실패가 원래 오류를 덮지 않게
            pass


def _read_safety(client, conf):
    """상태 레지스터를 한 번에 읽어 안전 스위치 부분만 뽑는다 (regs[10] gsta 비트필드)."""
    try:
        rr = client.read_holding_registers(address=int(conf['status_addr']),
                                           count=int(conf['status_count']),
                                           slave=int(conf['tool_unit']))
    except Exception as e:                               # noqa: BLE001 pymodbus 예외 종류가 판마다 다르다
        raise GripperBoxError(f'그리퍼 상태를 못 읽었다: {e!r}') from e
    regs = getattr(rr, 'registers', None)
    if rr is None or not regs or (hasattr(rr, 'isError') and rr.isError()):
        raise GripperBoxError(f'그리퍼 상태를 못 읽었다(상자 응답 {rr!r}) — 툴 전원이 꺼져 있을 수 있다')
    if len(regs) <= _GSTA_INDEX:
        raise GripperBoxError(f'상태 칸이 {len(regs)}개뿐이다 — {_GSTA_INDEX + 1}개가 필요하다. '
                              'f2.gripper_box.status_count 를 확인한다')
    gsta = int(regs[_GSTA_INDEX])
    out = {name: (1 if (gsta & (1 << bit)) else 0) for name, bit in _SAFETY_BITS.items()}
    out['tripped'] = any(out[k] != 0 for k in _TRIPPED_FIELDS)
    return out


def _safety_text(s):
    """사람이 읽는 한 줄. 예: 'S1 눌림 0/걸림 1 · S2 눌림 0/걸림 0 · safety 0'"""
    return (f"S1 눌림 {s['s1_pushed']}/걸림 {s['s1_triggered']} · "
            f"S2 눌림 {s['s2_pushed']}/걸림 {s['s2_triggered']} · safety {s['safety']}")


def _driver_alive_since(t_mark, limit_s):
    """전원 재시작 뒤에 `/onrobot_joint_states` 가 한 번이라도 왔나.

    True  왔다(드라이버가 살아남았다) · False  limit_s 안에 안 왔다(드라이버가 죽었다)
    None  구독 자체가 없다(한 번도 못 받았다) — 판단하지 않는다
    """
    with _lock:
        seen = _stamp
    if seen is None:
        return None
    deadline = time.monotonic() + float(limit_s)
    while time.monotonic() < deadline:
        with _lock:
            seen = _stamp
        if seen is not None and seen > t_mark:
            return True
        time.sleep(_POLL_S)
    return False
