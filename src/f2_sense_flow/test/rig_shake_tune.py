"""흔들기 튜닝 시험대 — 키로 진폭·주기·가속도·기울기·속도를 바꾸고 스페이스로 바로 흔들어 본다 (V-07 물 털기 "임팩트").

    soc && python3 src/f2_sense_flow/test/rig_shake_tune.py --mode RINSE --kind BOWL      # 물 털기 (BASE X 직선 왕복)
    soc && python3 src/f2_sense_flow/test/rig_shake_tune.py --mode WASTE --kind BOWL      # 잔반 버리기 (J5 기울여 흔들기)

시작: 문지기 → 힘제어 끄기 → HOME → (첫 스페이스에서 sense.shake 가 스스로 자리로 간다 · E15)
🚨 용기는 **미리 쥐고** 시작한다 (rig_f2.py grip) — 이 시험대는 그리퍼를 만지지 않는다.

키 (누르면 값만 바뀌고, 스페이스를 눌러야 움직인다):
    a / A     진폭 −/+   (직선 5 mm · 관절 5°)        p / P     주기 −/+ 0.05 s
    c / C     가속도 −/+ 100 mm/s² (직선만)            t / T     기울기 −/+ 10° (관절만)
    n / N     횟수 −/+ 1                                v         속도 30 % ↔ 100 % (vel_scale)
    space / s 지금 값으로 흔든다 (sense.shake · 진짜 함수)   w         지금 값을 params.yaml 줄로 찍는다
    h 도움말  q 끝 (안 움직임)

값은 이번 실행의 메모리 설정에만 쓴다 — 마음에 들면 w 로 찍힌 줄을 params.yaml 에 옮긴다.
상한은 sense.shake 가 그대로 검사한다(max_amp_mm · max_amp_deg · max_tilt_deg · 속도·가속도는 move_rel 이 자른다).
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys
import termios
import tty

import cobot_common as cc
from f2_sense_flow import sense
from f2_sense_flow.preflight import go_home_safely, require_controller


def _key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _show(log, mode, p, count):
    run = cc.cfg().get('run', {})
    vs = float(run.get('vel_scale', 1.0))
    if p.get('axis') is not None:
        body = f"axis {p['axis']} · amp {p.get('amp_mm')} mm · period {p.get('period_s')} s · acc {p.get('acc_mm_s2') or '기본'} mm/s²"
    else:
        body = (f"J{p.get('joint')} · amp {p.get('amp_deg')}° · period {p.get('period_s')} s · tilt {p.get('tilt_deg') or 0}°"
                + (f" · at {p.get('at')}" if p.get('at') else '') + (' · fast' if p.get('fast') else '') + (' · smooth' if p.get('smooth') else ''))
    log.info(f'[{mode}] {body} · 횟수 {count} · 속도 {vs * 100:.0f} %')


def _yaml(mode, p, kind=''):
    keys = [k for k in ('axis', 'joint', 'amp_mm', 'amp_deg', 'cycles', 'period_s', 'acc_mm_s2', 'tilt_deg', 'at', 'fast', 'smooth') if p.get(k) is not None]
    head = f'      {kind}:' if kind else f'    {mode}:'
    return f"{head} {{" + ', '.join(f'{k}: {p[k]}' for k in keys) + '}'


def main():
    ap = argparse.ArgumentParser(description='흔들기 튜닝 시험대')
    ap.add_argument('--mode', default='RINSE', choices=['RINSE', 'WASTE'])
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--count', type=int, default=3, help='처음 횟수')
    a = ap.parse_args()
    if not sys.stdin.isatty():
        sys.exit('터미널에서 직접 실행한다 (키 입력이 필요하다)')

    cc.init('rig_shake_tune')
    log = cc.io_node().get_logger()
    require_controller(cc.io_node(), cc.cfg(), log)          # TS-07
    cfg = cc.cfg()
    p = sense.shake_params(cfg['f2'], a.mode, a.kind)         # 메모리 설정(종류별 묶음이면 그 종류) — 바꾸면 sense.shake 가 그대로 읽는다
    linear = p.get('axis') is not None
    count = a.count
    cfg.setdefault('run', {}).setdefault('vel_scale', 1.0)
    try:
        log.info('E15 — 먼저 HOME 으로 간다 (낮으면 곧게 올라온 뒤에 · 테이블 충돌 이후)')
        go_home_safely(a.kind, log)
        log.info('준비됨 — 값을 바꾸고 스페이스로 흔든다. h 도움말 · q 끝')
        _show(log, a.mode, p, count)
        while True:
            k = _key()
            if k == 'q':
                log.info('끝 — 로봇은 그 자리. 마지막 값: ' + _yaml(a.mode, p, a.kind)); return
            if k == 'h':
                log.info(__doc__.split('키 (')[1].split('값은')[0]); continue
            if k in ('a', 'A'):
                key, step = ('amp_mm', 5.0) if linear else ('amp_deg', 5.0)
                p[key] = max(0.0, float(p.get(key) or 0.0) + (step if k == 'A' else -step))
            elif k in ('p', 'P'):
                p['period_s'] = round(max(0.05, float(p.get('period_s') or 0.5) + (0.05 if k == 'P' else -0.05)), 2)
            elif k in ('c', 'C') and linear:
                p['acc_mm_s2'] = max(0.0, float(p.get('acc_mm_s2') or 0.0) + (100.0 if k == 'C' else -100.0)) or None
            elif k in ('t', 'T') and not linear:
                p['tilt_deg'] = float(p.get('tilt_deg') or 0.0) + (10.0 if k == 'T' else -10.0)
            elif k in ('n', 'N'):
                count = max(1, count + (1 if k == 'N' else -1))
            elif k == 'v':
                run = cfg['run']
                run['vel_scale'] = 1.0 if float(run.get('vel_scale', 1.0)) < 1.0 else 0.3
            elif k == 'w':
                log.info('params.yaml f2.shake 에 넣을 줄:\n' + _yaml(a.mode, p, a.kind)); continue
            elif k in (' ', 's'):
                _show(log, a.mode, p, count)
                r = sense.shake(a.mode, count, a.kind)         # 🚨 진짜 함수 — 자리로 가서(_goto) 흔들고 되돌아온다
                log.info(f'→ {r}' + ('' if r.ok else '   🚨 실패 — 값을 줄이거나 멈춘다'))
                continue
            else:
                continue
            _show(log, a.mode, p, count)
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 로봇은 그 자리에 선다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
