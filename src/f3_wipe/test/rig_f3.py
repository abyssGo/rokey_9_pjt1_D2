"""F3 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    soc && python3 src/f3_wipe/test/rig_f3.py bowl            # wipe_bowl 연속 3회
    soc && python3 src/f3_wipe/test/rig_f3.py soap --soap-count 2
    soc && python3 src/f3_wipe/test/rig_f3.py cup -n 5
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_f3.py bowl -n 1 --limit-n 2
        → 누름 상한을 이 실행 동안만 2 N 으로 낮춰 나선 중 FORCE_LIMIT 을 일부러 낸다(E60 확인: 즉시 정지 → 힘 끄기 → 곧게 위로).
          params.yaml 은 그대로라 끝나면 원래 값(10 N)이다.

준비(손으로): 스펀지 홈에 그릇·컵을 놓고, 툴(그릇=수세미 툴, 컵=솔)을 그리퍼에 쥐여 준다.
같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys

import cobot_common as cc
from cobot_api import F3Api, check_api
from f3_wipe import wipe


def main():
    ap = argparse.ArgumentParser(description='F3 단독 시험')
    ap.add_argument('which', choices=['soap', 'bowl', 'cup'])
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--soap-count', type=int, default=3, help='soap(count) 인자 — flow 호출 예시(IRD §8)와 같게')
    ap.add_argument('--limit-n', type=float, default=None,
                    help='bowl·cup: 누름 상한(f3.*.limit_n)을 이 실행 동안만 바꾼다(메모리에서만 · 파일은 그대로) — FORCE_LIMIT 확인용')
    a = ap.parse_args()
    if a.limit_n is not None and (a.which == 'soap' or a.limit_n <= 0):
        sys.exit('--limit-n 은 bowl·cup 에만, 0 보다 큰 값으로')

    problems = check_api(wipe, F3Api)
    if problems:
        sys.exit(f'cobot_api.F3Api 약속과 다름: {problems}')

    fn = {'soap': lambda: wipe.soap(a.soap_count), 'bowl': wipe.wipe_bowl, 'cup': wipe.wipe_cup}[a.which]

    cc.init('rig_f3')                                       # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    if a.limit_n is not None:                               # cc.cfg() 는 프로세스 안에서 한 벌이다 — 이 실행에만 적용된다
        key = 'wipe_bowl' if a.which == 'bowl' else 'wipe_cup'
        old = cc.cfg()['f3'][key]['limit_n']
        cc.cfg()['f3'][key]['limit_n'] = float(a.limit_n)
        log.warn(f'시험용: f3.{key}.limit_n {old:g} → {a.limit_n:g} N (이 실행 동안만 · 파일은 그대로)')
    log.info(f'vel_scale {cc.cfg().get("run", {}).get("vel_scale", 1.0):g} · {a.which} {a.n} 회 '
             '· 🚨 실기면 E-Stop 에 손을 두고 본다')
    means = []
    try:
        for i in range(a.n):                                # ② 연속 3회 이상
            r = fn()
            log.info(f'{i + 1}/{a.n} {a.which} → {r}')
            if getattr(r, 'force_mean_n', None):
                means.append(r.force_mean_n)
            if not r.ok:
                log.error(f'{a.which} 실패({r.code}) — 원인을 고치기 전에는 반복하지 않는다')
                return 1
        if means:                                           # 마감 기준(TC-06): 3회의 누르는 힘 평균을 보고한다
            log.info(f'누르는 힘 평균 {sum(means) / len(means):.2f} N '
                     f'(회차별 {" · ".join(f"{m:.2f}" for m in means)}) — 이 값이 기준값이 된다')
    finally:
        cc.shutdown()                                       # ③ 끝낼 때 (Ctrl+C 포함)
    return 0


if __name__ == '__main__':
    sys.exit(main())
