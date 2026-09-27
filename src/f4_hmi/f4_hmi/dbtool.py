# -*- coding: utf-8 -*-
"""hmi_db — SQLite 기록을 터미널에서 본다(F4-04). ROS 없이 돈다.

    ros2 run f4_hmi hmi_db tables                      표 5개의 줄 수
    ros2 run f4_hmi hmi_db dump events --limit 20      표 내용(최근 것부터)
    ros2 run f4_hmi hmi_db usage                       소모품·잔반통 사용량(마지막 교체 뒤)
    ros2 run f4_hmi hmi_db kpi --period today          KPI (run · today · all)
    ros2 run f4_hmi hmi_db replace sponge              교체 완료를 기록한다(화면 버튼과 같다)
    ros2 run f4_hmi hmi_db export --dir records        표 5개를 CSV 파일로(엑셀·LibreOffice 로 연다)
파일 위치는 params.yaml hmi.db_path(**워크스페이스 루트 기준** · 기본 <ws>/prewash.db) — --db 로 바꿀 수 있다.
"""
import argparse
import csv
import sys
from pathlib import Path

from .db import HmiDb, ITEMS, TABLES
from .paths import ws_path


def _cfg_db_path():
    try:
        from cobot_common import config
        return str((config.load().get('hmi') or {}).get('db_path') or 'prewash.db')
    except Exception:                                       # noqa: BLE001 — 설정을 못 읽어도 기본 파일로
        return 'prewash.db'


def _table(rows):
    if not rows:
        print('(없음)')
        return
    cols = list(dict.fromkeys(k for r in rows for k in r.keys()))          # 줄마다 열이 달라도(usage 의 used/used_g) 전부 보인다
    width = {c: max(len(c), *(len(str(r.get(c, ''))) for r in rows)) for c in cols}
    print(' | '.join(c.ljust(width[c]) for c in cols))
    print('-+-'.join('-' * width[c] for c in cols))
    for r in rows:
        print(' | '.join(str(r.get(c, '')).ljust(width[c]) for c in cols))


def main(argv=None):
    p = argparse.ArgumentParser(prog='hmi_db', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--db', default=None, help='SQLite 파일 (기본: params.yaml hmi.db_path)')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('tables')
    d = sub.add_parser('dump'); d.add_argument('table', choices=TABLES); d.add_argument('--limit', type=int, default=20)
    sub.add_parser('usage')
    k = sub.add_parser('kpi'); k.add_argument('--period', choices=('run', 'today', 'all'), default='all')
    r = sub.add_parser('replace'); r.add_argument('item', choices=ITEMS); r.add_argument('--note', default='터미널에서')
    e = sub.add_parser('export'); e.add_argument('--dir', default='records'); e.add_argument('--limit', type=int, default=100000)
    a = p.parse_args(argv)
    db = HmiDb(ws_path(a.db or _cfg_db_path()))            # 어디서 실행하든 워크스페이스의 파일
    print(f'# {db.path}')
    if a.cmd == 'tables':
        for t in TABLES:
            print(f'{t:13s} {len(db.dump(t, limit=100000))} 줄')
    elif a.cmd == 'dump':
        _table(db.dump(a.table, a.limit))
    elif a.cmd == 'usage':
        _table([{'item': k, **v} for k, v in db.usage().items()])
    elif a.cmd == 'kpi':
        _table([db.kpi(a.period)])
    elif a.cmd == 'replace':
        db.add_replacement(a.item, a.note)
        print(f'교체 기록: {a.item}')
    elif a.cmd == 'export':
        out = Path(a.dir); out.mkdir(parents=True, exist_ok=True)
        for t in TABLES:
            rows = list(reversed(db.dump(t, a.limit)))                    # 오래된 것부터
            f = out / f'{t}.csv'
            with f.open('w', newline='', encoding='utf-8-sig') as fh:      # BOM → 엑셀이 한글을 바로 읽는다
                w = csv.writer(fh)
                cols = list(rows[0].keys()) if rows else []
                w.writerow(cols)
                for r in rows:
                    w.writerow([r.get(c, '') for c in cols])
            print(f'{f}  {len(rows)} 줄')
    return 0


if __name__ == '__main__':
    sys.exit(main())
