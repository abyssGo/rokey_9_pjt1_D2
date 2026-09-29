"""INT-12 통합 시험대 (F1 + F2) — flow_node 없이 INT-12a·12b 구간만 골라 반복한다 (L2).

    python3 src/f2_sense_flow/test/rig_int12.py check                    # 🟢 로봇 없이 — F1 이 빈 껍데기인지 · 좌표가 있는지 먼저
    soc && python3 src/f2_sense_flow/test/rig_int12.py a --kind BOWL     # INT-12a  집기 → 저울 → 잔반 처리        × 5
    soc && python3 src/f2_sense_flow/test/rig_int12.py b --kind BOWL     # INT-12b  재파지 → 헹굼 → 물 털기 → 적재  × 5
    python3 src/f2_sense_flow/test/rig_int12.py a --mock f1,f2 --no-robot   # 대본이 도는지만 (전부 가짜 · 로봇 없이)

왜 flow_node 가 아니라 이 파일인가: flow_node 는 용기 한 개를 **끝까지**(닦기·툴까지) 돌린다. L2 는 두 기능만
이어 붙여 5회 반복하는 시험이라(SDD §9 INT-12a·12b) 그 구간만 같은 순서·같은 인자로 부르는 시험대가 따로 필요하다.
호출 순서·인자는 flow.py 의 steps 와 같다 — 어긋나면 test_f2_int12_rig.py 가 잡는다.

🚨 F1 의 pick·rack_place 가 아직 빈 껍데기면 **"성공"을 돌려준다** — Result 의
   기본값이 ok=True 라서. 그러면 로봇이 한 번도 안 움직였는데 저울로 가서 빈손 무게를 잰다.
   → `check` 가 로봇 없이 먼저 가려낸다(진짜 구현은 로봇 없이 부르면 예외가 나고, 빈 껍데기는 조용히 성공한다).
   → 실기 중에도 pick 이 폭 0.0·시도 0 을 돌려주면 그 자리에서 멈춘다.

🟢 rviz(Virtual) 로 경로만 볼 때(--virtual): Virtual 에는 무게·힘·그리퍼 드라이버가 없다(rig_f2_virtual.py) →
   그 셋만 가짜로 바꿔 끼우고 **이동은 진짜 가상 로봇**이 한다. 팀 cell.yaml 좌표 그대로. 실기 컨트롤러면 거부한다.
   --leftover-round 회차(기본 3)에만 가짜 하중을 '잔반 100 g' 으로 넣어 털기 경로(HOME 경유 · E15)까지 돈다.
    터미널 1: sod && sodvir            터미널 2: soc && python3 src/f2_sense_flow/test/rig_int12.py a --virtual -n 3

🟡 집기·적재가 아직 없을 때(--allow-stub): 용기를 **손으로 쥐여 주고**(rig_f2.py grip) F1 이동 + F2 만 잇는다.
   그리퍼는 끝까지 쥔 채다(가짜 pick 이 안 집으니까). 결과는 대본·경로 확인용이지 INT-12 합격에는 못 쓴다.
    soc && python3 src/f2_sense_flow/test/rig_f2.py grip --kind BOWL          # 먼저 손으로 쥐여 준다
    soc && python3 src/f2_sense_flow/test/rig_int12.py b --kind BOWL --allow-stub   # 헹굼·물 털기·HOME 경로가 실제로 돈다

회차 사이 되돌리기는 사람이 한다: a = HOME 에서 용기를 받아 반납 구역에 다시 놓는다 / b = 팔레트 칸에서 꺼내 스펀지 홈에 다시 놓는다.
"무개입 5회" 는 회차 **안**의 이야기다 — 용기가 2개뿐이라 회차 사이 되돌리기는 어차피 사람이 한다.

🚨 실패했을 때 로봇을 스스로 움직이지 않는다 — 힘·순응만 끄고 멈춘다. 사람이 복구한다.
🚨 로봇을 움직이기 전에 `rosinfo` 로 RANGE=LOCALHOST 인지 확인한다.

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import cobot_common as cc
from cobot_api import F1Api, F2Api, check_api

STUB_MSG = ('🚨 f1.pick 이 빈 껍데기다 — ok 인데 폭 0.0 · 시도 0 (로봇이 움직이지 않았다).\n'
            '   f1.pick 이 구현된 뒤에 다시 돌린다. 가짜로 대본만 볼 때는 --mock f1')


# ────────────────────────────────── 로봇 없이 되는 부분 (pytest 가 본다)
def steps_for(which, kind, cfg, zone=None, slot=None):
    """(단계, 모듈, 함수, 인자) — flow.py process_one 의 steps 에서 INT-12a·12b 구간만 그대로 잘라 온 것.

    which : 'a' = INT-12a  pick → move_to(WEIGH) → leftover_loop
            'b' = INT-12b  pick(BED) → dip → shake → rack_place → move_to(HOME)
    zone·slot : 비우면 params.yaml 의 flow.plan · flow.rack_order 첫 값.
    """
    flow = cfg['flow']
    bowl = kind == 'BOWL'
    if which == 'a':
        if zone is None:
            zone = next(p['zone'] for p in flow['plan'] if p['kind'] == kind)
        return [('PICK', 'f1', 'pick', (zone, kind)),
                ('WEIGH', 'f2', 'leftover_loop', (kind, int(flow['leftover_max_rounds'])))]
    if which == 'b':
        bed = 'SPONGE_BED_B' if bowl else 'SPONGE_BED_C'
        n = flow['counts']
        if slot is None:
            slot = flow['rack_order'][kind][0]
        return [('RINSE', 'f1', 'pick', (bed, kind)),
                ('RINSE', 'f2', 'dip', ('RINSE', int(n['rinse_dips']), kind)),
                ('RINSE', 'f2', 'shake', ('RINSE', int(n['rinse_shakes']), kind)),
                ('RACK', 'f1', 'rack_place', (slot, kind)),
                ('RACK', 'f1', 'move_to', ('HOME', False))]
    raise ValueError(f'which 는 a 또는 b: {which!r}')


def looks_like_stub(r):
    """pick 의 반환이 '빈 껍데기 그대로' 인가 — ok 인데 폭 0.0 · 시도 0.

    진짜 pick 은 쥔 폭(그릇 ≈ 2 mm 대 · 컵 ≈ 78 mm)과 시도한 슬롯 수(1 이상)를 채운다.
    실패(EMPTY_ZONE 등)는 빈 껍데기가 아니다 — 무엇인가 해 보고 돌아온 것이다.
    """
    return (bool(getattr(r, 'ok', False))
            and float(getattr(r, 'width_mm', 0.0)) == 0.0
            and int(getattr(r, 'attempts', 0)) == 0)


def probe(fn, args):
    """로봇 없이 한 번 불러 본다 → ('impl' | 'stub', 설명).

    진짜 구현은 첫 로봇 명령에서 예외가 난다(드라이버가 없으니까) → 'impl'.
    실패 코드를 돌려줘도 무엇인가 한 것이다 → 'impl'.
    빈 껍데기는 아무것도 안 하고 ok 를 돌려준다 → 'stub'.
    """
    try:
        r = fn(*args)
    except Exception as e:                      # noqa: BLE001 — 어떤 예외든 "로봇을 건드렸다" 는 뜻
        return 'impl', f'{type(e).__name__}: {e}'
    if getattr(r, 'ok', False):
        return 'stub', repr(r)
    return 'impl', repr(r)


def missing_coords(cfg, kind):
    """이 구간이 쓰는 자세·칸이 cell.yaml 에 있는지 — 없는 것의 설정 키 목록 (없으면 [])."""
    cell = cfg.get('cell') or {}
    st = cell.get('stations') or {}
    flow = cfg['flow']
    out = []

    def has(node):
        return bool(node) and isinstance(node, dict) and any(k in node for k in ('posj', 'posx', 'approach_posx'))

    for name in ('WEIGH', 'WASTE', 'RINSE'):        # 종류별 자리
        node = st.get(name) or {}
        if not (has(node) or has(node.get(kind))):
            out.append(f'stations.{name}.{kind}')
    if not has(st.get('HOME')):
        out.append('stations.HOME')
    zone = next((p['zone'] for p in flow['plan'] if p['kind'] == kind), None)
    if zone is None or zone not in (cell.get('zones') or {}):
        out.append(f'zones.{zone}')
    bed = 'SPONGE_BED_B' if kind == 'BOWL' else 'SPONGE_BED_C'
    if bed not in (cell.get('beds') or {}):
        out.append(f'beds.{bed}')
    slots = (cell.get('rack') or {}).get('slots') or {}
    for s in flow['rack_order'].get(kind) or []:
        if s not in slots:
            out.append(f'rack.slots.{s}')
    return out


# ────────────────────────────────── 실행
def main():
    ap = argparse.ArgumentParser(description='INT-12 통합 시험대 (F1 + F2)')
    ap.add_argument('which', choices=['check', 'a', 'b'],
                    help='check = 로봇 없이 사전 점검 · a = INT-12a · b = INT-12b')
    ap.add_argument('-n', type=int, default=5, help='회차 (SDD §9: 5회)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--mock', default='', help='가짜로 바꿀 기능, 쉼표로. 예: f1 · f1,f2 (flow_node 의 use_mock 과 같다)')
    ap.add_argument('--no-robot', action='store_true', help='두산 드라이버 없이 (전부 가짜일 때)')
    ap.add_argument('--no-home', action='store_true', help='🚨 시작할 때 HOME 으로 가지 않는다 (이미 HOME 일 때만)')
    ap.add_argument('--zone', help='a: 반납 구역 (기본 flow.plan)')
    ap.add_argument('--slot', help='b: 팔레트 칸 (기본 flow.rack_order 첫 칸)')
    ap.add_argument('--out', default='logs/int12', help='회차 기록 CSV 폴더 (실행 위치 기준)')
    ap.add_argument('--virtual', action='store_true',
                    help='🟢 rviz(Virtual) — 무게·그리퍼만 가짜, 이동은 진짜 가상 로봇. --allow-stub 을 포함한다. 실기면 거부')
    ap.add_argument('--leftover-round', type=int, default=3,
                    help='--virtual 에서 가짜 잔반(100 g)을 넣는 회차 (털기·HOME 경유 경로 확인용)')
    ap.add_argument('--allow-stub', action='store_true',
                    help='🟡 f1.pick 이 빈 껍데기여도 계속 — 용기를 손으로 쥐여 준 상태에서 F1 이동 + F2 만 잇는다. 합격 판정에 못 쓴다')
    a = ap.parse_args()

    from f2_sense_flow.flow import load_features          # flow_node 와 **같은** 진짜/가짜 선택
    from cobot_common.config import parse_use_mock
    use_mock = parse_use_mock(a.mock) if a.mock else []

    if a.which == 'check':
        return _check(a, use_mock)

    if a.virtual and a.no_robot:
        sys.exit('--virtual 은 가상 로봇(브링업)이 있어야 한다 — --no-robot 과 같이 못 쓴다')
    cfg = cc.cfg()
    steps = steps_for(a.which, a.kind, cfg, a.zone, a.slot)
    cc.init('rig_int12', robot=not a.no_robot)               # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    virt = None
    if a.virtual:
        _require_virtual()                                   # 🚨 실기 컨트롤러에 가짜 무게를 끼우지 않는다
        virt = _stub_what_virtual_lacks(a, cfg, log)
        a.allow_stub = True
        log.warn('--virtual → --allow-stub 도 켠다 (Virtual 엔 그리퍼가 없어 pick 이 있어도 못 쥔다 — 이동만 본다)')
    feats = load_features(use_mock, log)
    for key, api in (('f1', F1Api), ('f2', F2Api)):
        problems = check_api(feats[key], api)
        if problems:
            sys.exit(f'{key} 가 cobot_api 약속과 다름: {problems}')
    if a.no_robot:
        log.warn('--no-robot — 두산 드라이버 없이 함수 반환만 본다')
    else:
        from f2_sense_flow.preflight import go_home_safely, require_controller, warn_if_cable_tight
        require_controller(cc.io_node(), cfg, log)             # TS-07 — 툴·TCP 가 다르면 여기서 끝
        warn_if_cable_tight(cfg, log)                          # 🔗 케이블 장력(경고만)

    rows = []
    try:
        if not a.no_home and not a.no_robot:
            log.info('E15 — 먼저 HOME 으로 간다 (앞뒤를 가로지르지 않으려고 · 낮으면 곧게 올라온 뒤에)')
            go_home_safely(None, log, a.allow_stub)      # --allow-stub = 용기를 쥔 채 시작 → 저속
        for i in range(1, a.n + 1):
            if virt is not None and a.which == 'a' and i == a.leftover_round:
                virt['queue'][:] = [virt['empty'] + 100.0, virt['empty']]      # 잔반 100 g → 털면 0
                log.warn(f'[{i}/{a.n}] 가짜 잔반 100 g — 털기 · HOME 경유 경로가 돈다')
            row, go_on = _round(i, a, steps, feats, log)
            rows.append(row)
            if not go_on:
                log.error(f'{i} 회차에서 멈춘다 — 로봇을 움직이지 않는다. 사람이 복구한 뒤 다시')
                break
            if i < a.n:
                _reset(a, feats, log)
    finally:
        _summary(a, rows, log)
        cc.shutdown()                                        # ③ 끝낼 때 (Ctrl+C 포함)


def _round(i, a, steps, feats, log):
    """한 회차. → (기록 행, 계속해도 되는가)"""
    row = {'round': i, 'kind': a.kind, 'code': 'OK', 'width_mm': '', 'attempts': '',
           'before_g': '', 'after_g': '', 'rounds': '', 's': ''}
    t0 = time.monotonic()
    go_on = True
    try:
        for label, mod_key, fname, args in steps:
            fn = getattr(feats[mod_key], fname)
            log.info(f'[{i}/{a.n}] {label:5} {mod_key}.{fname}{args}')
            r = fn(*args)
            log.info(f'        → {r}')
            if fname == 'pick':
                if looks_like_stub(r):
                    if not a.allow_stub:
                        sys.exit(STUB_MSG)
                    log.warn('🟡 f1.pick 빈 껍데기 — 쥔 용기로 계속 (--allow-stub)')
                    row.update(width_mm='stub', attempts='stub')
                else:
                    row.update(width_mm=r.width_mm, attempts=r.attempts)
            elif fname == 'leftover_loop':
                row.update(before_g=r.weight_before_g, after_g=r.weight_after_g, rounds=r.rounds)
            if not r.ok:
                row['code'] = r.code
                # LEFTOVER_REMAIN 은 '잔반이 남았다' 는 **정상 판정**이다 — 용기는 손에 있으니 되돌리고 계속.
                # 그 밖(EMPTY_ZONE · GRIP_FAIL · RACK_JAM · ROBOT_ERROR …)은 용기가 어디 있는지 모른다 → 멈춘다(E12).
                go_on = (fname == 'leftover_loop' and r.code == 'LEFTOVER_REMAIN')
                break
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except Exception as e:                      # noqa: BLE001 — 로봇 이상. 위치를 모르니 움직이지 않는다
        row['code'] = f'EXC:{type(e).__name__}'
        log.error(f'예외 — {type(e).__name__}: {e}')
        if not a.no_robot:
            cc.force_off()                      # 힘·순응만 끈다
        go_on = False
    row['s'] = round(time.monotonic() - t0, 2)
    return row, go_on


def _reset(a, feats, log):
    """회차 사이 — 사람이 용기를 제자리로. a 는 로봇이 용기를 쥔 채 HOME 으로 가서 열어 준다."""
    if a.allow_stub:                                        # 가짜 pick 은 안 집는다 → 쥔 채로 다음 회차
        if a.which == 'a':
            feats['f1'].move_to('HOME', True, a.kind)
        _ask(log, '용기는 쥔 채 그대로 — 다음 회차 Enter')
        return
    if a.which == 'a':
        feats['f1'].move_to('HOME', True, a.kind)           # 저울(앞) → HOME: E15 에 어긋나지 않는다
        _ask(log, '용기를 손으로 받쳐 주세요 — Enter 하면 그리퍼를 엽니다')
        if not a.no_robot:
            cc.release()
        _ask(log, f'용기를 반납 구역 자리에 다시 놓았으면 Enter')
    else:
        _ask(log, '팔레트 칸에서 용기를 꺼내 스펀지 홈에 다시 놓았으면 Enter (로봇은 HOME 에 있다)')


_FAKE_WIDTH_MM = 2.15           # 가짜 그리퍼가 늘 돌려주는 폭 (그릇 프리셋값) — 판정은 실기에서만 뜻이 있다


def _require_virtual():
    """🚨 --virtual 은 가상 컨트롤러에서만 — 실기에 가짜 무게·그리퍼를 끼우면 판정이 전부 거짓이 된다."""
    from cobot_common.bootstrap import dsr
    d = dsr()
    if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
        sys.exit('--virtual 인데 실기 컨트롤러다 — 거부한다 (sod && sodvir 로 Virtual 브링업을 띄운다)')


def _stub_what_virtual_lacks(a, cfg, log):
    """Virtual 에 없는 것(무게·그리퍼)만 가짜로 — rig_f2_virtual.py 와 같은 방식. 이동은 진짜 가상 로봇."""
    empty = float(cfg['f2']['empty_weight_g'][a.kind])
    state = {'empty': empty, 'queue': []}

    def fake_weigh(n, reset=False):                 # queue 에 값이 있으면 그 순서대로, 비면 빈 용기값(잔반 0)
        q = state['queue']
        return q.pop(0) if q else empty

    presets = (cfg.get('cell') or {}).get('presets') or {}
    b = presets.get('BOWL') or {}
    bowl_held = float(b.get('grip_zero_mm') or 0.0) + float(b.get('grip_width_mm') or 0.0)   # 그릇을 쥐었을 때 드라이버 폭(12.73)

    def fake_grip(width, force):                    # 진짜 f1.pick 이 판정하므로 "쥐었다" 로 보이는 폭을 돌려준다
        return max(float(width), bowl_held)         #   그릇: 목표 11.53 → 12.73(판정 OK) · 컵: 목표 76 → 76(판정 없음)

    def fake_contact_down(max_depth, limit):        # Virtual 엔 힘·순응이 없다 → 그냥 곧게 내려가고 "끝까지 닿았다"
        cc.move_rel(0.0, 0.0, -float(max_depth), 'BASE')
        return float(max_depth), 0.0

    cc.weigh = fake_weigh
    cc.grip = fake_grip
    cc.grip_level = lambda kind, level: _FAKE_WIDTH_MM
    cc.grip_width = lambda: _FAKE_WIDTH_MM
    cc.release = lambda: None
    cc.contact_down = fake_contact_down
    log.warn('🚨 Virtual 에 없는 것을 가짜로 바꿔 끼웠다 — cc.weigh · grip · grip_level · grip_width · release · contact_down')
    log.warn('   이 실행은 **이동·순서만** 본다. 무게·파지·낙하는 실기(INT-12a·12b)에서 본다')
    return state


def _ask(log, msg):
    """사람이 준비될 때까지 기다린다. 파이프로 돌리면(입력 없음) 그냥 진행한다."""
    log.info(f'▶ {msg}')
    try:
        input()
    except EOFError:
        log.warning('입력이 없다 — 기다리지 않고 진행한다')


def _summary(a, rows, log):
    if not rows:
        return
    cols = ['round', 'kind', 'code', 'width_mm', 'attempts', 'before_g', 'after_g', 'rounds', 's']
    log.info(f'── INT-12{a.which} {a.kind} 요약 ({len(rows)}/{a.n} 회차)')
    log.info('  ' + '  '.join(f'{c:>9}' for c in cols))
    for r in rows:
        log.info('  ' + '  '.join(f'{str(r.get(c, "")):>9}' for c in cols))
    ok = sum(1 for r in rows if r['code'] in ('OK', 'LEFTOVER_REMAIN'))
    log.info(f'  회차 안 무개입 완료 {ok}/{a.n}  (합격: 5/5 — SDD §9)')
    if a.virtual:
        log.warn('  🟢 --virtual 결과 — 이동·순서만 본 것. INT-12 합격 판정에 쓰지 않는다')
    elif a.allow_stub:
        log.warn('  🟡 --allow-stub 결과 — 집기·적재가 가짜라 INT-12 합격 판정에 쓰지 않는다')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'int12{a.which}_{a.kind}_{time.strftime("%Y%m%d_%H%M")}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    log.info(f'  기록 → {path}')


def _check(a, use_mock):
    """로봇 없이 — ① 약속 ② 빈 껍데기 ③ 좌표. 하나라도 걸리면 종료 코드 1."""
    from f2_sense_flow.flow import load_features
    cfg = cc.cfg()
    feats = load_features(use_mock)
    bad = []
    print('① cobot_api 약속')
    for key, api in (('f1', F1Api), ('f2', F2Api)):
        problems = check_api(feats[key], api)
        print(f'  {key}  {"OK" if not problems else problems}')
        bad += [f'{key}: {p}' for p in problems]

    print('② F1 이 빈 껍데기인가 (로봇 없이 불러 본다 — 진짜면 예외, 빈 껍데기면 조용히 성공)')
    kinds = ('BOWL', 'CUP')                                  # check 는 --kind 와 무관하게 둘 다 본다
    for fname, args in (('pick', ('RET_B', 'BOWL')), ('rack_place', ('RACK_B1', 'BOWL')), ('tool', ('SPONGE', 'PICK'))):
        kind_, why = probe(getattr(feats['f1'], fname), args)
        mark = 'OK 구현돼 있다' if kind_ == 'impl' else '🚨 빈 껍데기'
        print(f'  f1.{fname:10} {mark}   ({why[:70]})')
        if kind_ == 'stub' and fname in ('pick', 'rack_place'):
            bad.append(f'f1.{fname} 빈 껍데기 — INT-12{"a" if fname == "pick" else "b"} 못 돈다')

    print('③ 좌표 (cell.yaml)')
    for kind in kinds:
        miss = missing_coords(cfg, kind)
        print(f'  {kind:5} {"OK" if not miss else "없다 " + str(miss)}')
        bad += [f'{kind} {m}' for m in miss]

    print('④ 호출 순서 (flow.py 와 같아야 한다)')
    for which in ('a', 'b'):
        for kind in kinds:
            print(f'  12{which} {kind}: ' + ' → '.join(f'{m}.{f}' for _, m, f, _ in steps_for(which, kind, cfg)))

    print('\n' + ('점검 통과 — 로봇만 있으면 된다' if not bad else '>>> 막힌 것:\n    ' + '\n    '.join(bad)))
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
