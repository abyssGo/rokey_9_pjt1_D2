# -*- coding: utf-8 -*-
"""hmi_db — SQLite 기록을 터미널에서 본다(F4-04). ROS 없이 돈다.

    ros2 run f4_hmi hmi_db tables                      표 5개의 줄 수
    ros2 run f4_hmi hmi_db dump events --limit 20      표 내용(최근 것부터)
    ros2 run f4_hmi hmi_db usage                       소모품·잔반통 사용량(마지막 교체 뒤)
    ros2 run f4_hmi hmi_db kpi --period today          KPI (run · today · all)
    ros2 run f4_hmi hmi_db replace sponge              교체 완료를 기록한다(화면 버튼과 같다)
파일 위치는 params.yaml hmi.db_path(실행 위치 기준 · 기본 prewash.db) — --db 로 바꿀 수 있다.
"""
import argparse
import sys

from .db import HmiDb, ITEMS, TABLES


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
    cols = list(rows[0].keys())
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
    a = p.parse_args(argv)
    db = HmiDb(a.db or _cfg_db_path())
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
    return 0


if __name__ == '__main__':
    sys.exit(main())
