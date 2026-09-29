#!/usr/bin/env python3
"""HMI 그림 만들기 — 코드로 그린 등각 일러스트.

    cd src/f4_hmi/web && npm run illust        (= python3 illust/build.py)

  만드는 것(손으로 고치지 않는다 — 그림을 바꾸려면 illust/*.py 를 고치고 다시 돌린다)
    public/illust/steps/<단계>-<BOWL|CUP>.svg   단계 그림 18장 (320 × 240)
    public/illust/icons/<이름>.svg               숫자 패널 아이콘 9개 (96 × 96) — brush · cable · robot 3개는 손으로 넣은 SVG(여기서 만들지 않는다)
    app/lib/palletArt.js                          팔레트 조각 — 칸마다 적재됨/넣는 중/비어 있음
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scenes import STEPS, step_svg   # noqa: E402
import icons                          # noqa: E402
import pallet                         # noqa: E402

WEB = os.path.dirname(HERE)


def write(rel, text):
    path = os.path.join(WEB, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return rel


def main():
    made = []
    for step in STEPS:
        for kind in ('BOWL', 'CUP'):
            made.append(write(f'public/illust/steps/{step}-{kind}.svg', step_svg(step, kind) + '\n'))
    for name, fn in icons.ALL.items():
        made.append(write(f'public/illust/icons/{name}.svg', fn(f'ic-{name}') + '\n'))
    p = pallet.parts()
    js = ['// 자동 생성 — web/illust/build.py (npm run illust). 손으로 고치지 않는다.',
          '// 팔레트 입체 그림 조각. Pallet 이 칸 상태에 맞는 조각을 ORDER 순서(뒤 → 앞)로 겹치고 번호표를 맨 위에 얹는다.',
          f'export const VIEW = {{ x: {pallet.CROP[0]}, y: {pallet.CROP[1]}, w: {pallet.CROP[2]}, h: {pallet.CROP[3]} }};',
          f'export const ORDER = {json.dumps(pallet.ORDER)};',
          f'export const BASE = {json.dumps(p["base"], ensure_ascii=False)};',
          f'export const FRONT = {json.dumps(p["front"], ensure_ascii=False)};',
          f'export const DIV = {json.dumps(p["div"], ensure_ascii=False)};',
          f'export const SLOT = {json.dumps(p["slot"], ensure_ascii=False)};',
          f'export const BADGE = {json.dumps(p["badge"], ensure_ascii=False)};',
          '']
    made.append(write('app/lib/palletArt.js', '\n'.join(js)))
    total = sum(os.path.getsize(os.path.join(WEB, m)) for m in made)
    print(f'그림 {len(made)}개 · {total / 1024:.0f} KB')


if __name__ == '__main__':
    main()
