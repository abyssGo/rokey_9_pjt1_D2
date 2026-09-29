# -*- coding: utf-8 -*-
"""설정 로더 시험 — 로봇·ROS 실행 없이 돈다.  실행: python3 -m pytest src/cobot_common/test/test_config.py"""
from pathlib import Path

import pytest

from cobot_api import CODES, RACK_SLOTS, RET_B, RET_C, STATIONS
from cobot_common import config

SRC_CONFIG = Path(__file__).resolve().parent.parent / 'config'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (config.ENV_CONFIG_DIR, config.ENV_USE_MOCK, config.ENV_VEL_SCALE):
        monkeypatch.delenv(name, raising=False)


def _write(d, cell='cell: {}\n', params='hmi: {port: 8000}\nflow: {use_mock: [f1]}\n'):
    (d / config.CELL_FILE).write_text(cell, encoding='utf-8')
    (d / config.PARAMS_FILE).write_text(params, encoding='utf-8')


# ------------------------------------------------------------------ 저장소의 실제 설정 파일
def test_repo_config_loads_all_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg) == set(config.CELL_KEYS + config.PARAM_SECTIONS) | {config.RUN_KEY}
    assert all(isinstance(cfg[k], dict) for k in cfg)
    assert {'port', 'state_rate_hz', 'disconnect_after_s', 'db_path'} <= set(cfg['hmi'])
    assert cfg['run'] == {'vel_scale': 1.0}


def test_repo_cell_skeleton_uses_ird_ids():
    """cell.yaml 키 골격이 IRD §2 의 ID 와 어긋나지 않는다(오타·누락 방지)."""
    cell = config.load(SRC_CONFIG)['cell']
    assert set(cell) == {'limits', 'motion', 'force', 'presets', 'stations', 'zones', 'beds', 'rack'}
    assert set(cell['motion']) == {'vel_tcp_max_mm_s', 'acc_tcp_max_mm_s2', 'vel_joint_max_deg_s', 'acc_joint_max_deg_s2',
                                   'vel_joint_fast_max_deg_s', 'acc_joint_fast_max_deg_s2',   # E36 물 털기 전용 상한
                                   'move_timeout_s'}
    assert set(cell['force']) == {'compliance_stx', 'contact_step_mm', 'contact_vel_mm_s', 'contact_acc_mm_s2',
                                  'retreat_vel_mm_s', 'retreat_acc_mm_s2', 'force_max_n', 'search_y_period_ratio'}   # 힘 함수 공용 값(V-03)
    beds = {'SPONGE_BED_B', 'SPONGE_BED_C'}
    vias = {'RACK_B_VIA', 'RACK_B1_VIA', 'RACK_C_VIA'}           # 팔레트 경유점(f1.rack_place · stations 아래) — IRD 자리는 아니다
    extra = vias | {'RINSE_SHAKE'}                                # E36 물 털기 자세(f2.shake at:) — IRD 스테이션이 아니라 f2 내부 자세(경유점과 같은 취급)
    assert set(cell['stations']) == (set(STATIONS) - beds) | extra   # 스펀지 홈은 beds 에 있다
    assert set(cell['beds']) == beds
    assert set(cell['zones']) == {RET_B, RET_C}
    assert set(cell['rack']['slots']) == set(RACK_SLOTS)
    assert set(cell['presets']) == {'BOWL', 'CUP', 'CUP_SIDE', 'SPONGE', 'BRUSH'}   # CUP_SIDE = 홈 C 옆면 재파지 전용(결정 ㉡)
    # CELL-04: 양식을 티칭 데이터에 맞췄다 — 종류별 · 용도별(point) · 슬롯별
    for name in ('WEIGH', 'WASTE', 'SOAP', 'RINSE', 'ISOLATE'):
        assert set(cell['stations'][name]) == {'BOWL', 'CUP'}, name
    for name in ('TOOL_SPONGE', 'TOOL_BRUSH'):
        assert set(cell['stations'][name]) == {'pick', 'return'}, name
    assert set(cell['beds']['SPONGE_BED_B']) == {'place', 'wash', 'seat'}
    assert set(cell['beds']['SPONGE_BED_C']) == {'place', 'wash', 'seat', 'regrip', 'regrip_preset'}   # 결정 ㉡: 옆면 재파지(접근점 posx + 전용 프리셋)
    assert all(len(cell['zones'][z]['slots']) == 2 for z in (RET_B, RET_C))       # E41(강사 피드백): 그릇 2·컵 2 처음부터 배치 → 구역마다 자리 2개(E9 대체)


def _rotation(rx, ry, rz):
    """두산 posx 의 방향(ZYZ 오일러각, deg) → 회전 행렬."""
    import math
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc_, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[ca * cb * cc_ - sa * sc, -ca * cb * sc - sa * cc_, ca * sb],
            [sa * cb * cc_ + ca * sc, -sa * cb * sc + ca * cc_, sa * sb],
            [-sb * cc_, sb * sc, cb]]


def _angle_between(p, q):
    import math
    r1, r2 = _rotation(*p[3:]), _rotation(*q[3:])
    trace = sum(r1[i][k] * r2[i][k] for i in range(3) for k in range(3))          # tr(R1ᵀ·R2)
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


# ⚠ 접근점 → 끝점이 수직이 아닌 채로 옮겨 온 자세. 다시 찍으면 여기서 지운다.
#   · RET_B 슬롯 1 은 접근(잡기1) → 그립(잡기2)이 수평 2.8 mm 였다
#   · RACK_C2 는 실기 좌표로 수직 정렬해 목록에서 제거했다.
KNOWN_TILTED = set()                                            # RET_B 접근점을 끝점 바로 위로 고쳐(E14) 알려진 예외가 없어졌다


def test_repo_approach_points_are_straight_above_end_points():
    """cc.move_to 는 접근점까지만 가고 부르는 쪽이 곧게 내려간다 → 접근점은 끝점의 **바로 위 · 같은 방향**이어야 끝점에 닿는다."""
    import math
    cell = config.load(SRC_CONFIG)['cell']
    pairs = {}

    def walk(node, path):
        if isinstance(node, dict):
            if node.get('approach_posx') and node.get('posx'):
                pairs[path] = (node['approach_posx'], node['posx'])
            for k, v in node.items():
                walk(v, f'{path}.{k}')
        elif isinstance(node, list):                                               # 구역의 슬롯 목록 (번호는 1 부터)
            for i, v in enumerate(node, start=1):
                walk(v, f'{path}[{i}]')
    walk(cell, 'cell')
    assert len(pairs) >= 7                                                         # 스펀지 홈 place·wash × 2 + 팔레트 컵 2칸 + 그릇 집기
    tilted = set()
    for path, (up, end) in pairs.items():
        assert up[2] > end[2], f'{path}: 접근점이 끝점보다 낮다'
        if math.hypot(up[0] - end[0], up[1] - end[1]) > 1.0 or _angle_between(up, end) > 1.0:   # 1 mm · 1° — 손 티칭의 읽기 오차보다 크면 어긋난 것
            tilted.add(path)
    assert tilted == KNOWN_TILTED


def test_repo_params_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg['flow']['policy']) <= set(CODES)               # 정책의 키는 IRD §2 실패 코드
    assert {'soap', 'wipe_bowl', 'wipe_cup'} == set(cfg['f3'])
    assert config.unfilled(cfg, config.PARAM_SECTIONS) == []      # params.yaml 은 빈 값 없이 초안 값이 있다


def test_unfilled_lists_empty_cell_values():
    empty = config.unfilled(config.load(SRC_CONFIG))
    # V-01·V-05·V-23 실기로 **그릇·컵 프리셋을 채웠다** → 이제 비어 있으면 안 된다
    for kind in ('BOWL', 'CUP'):
        for key in ('grip_width_mm', 'grip_zero_mm', 'grip_force_n', 'hold_force_n', 'width_tol_mm'):
            assert f'cell.presets.{kind}.{key}' not in empty, f'{kind}.{key} 가 다시 비었다'
    assert 'cell.presets.CUP.grip_target_mm' not in empty         # 결정 E19 — 컵의 고정 폭
    assert 'cell.limits.safe_z_mm' not in empty                   # limits·motion·seat 는 설계 문서 값으로 채웠다
    poses = [e for e in empty if not e.startswith('cell.presets.')]
    assert poses == [], f'빈 자세가 남아 있다: {poses}'           # 자세는 전부 찼다(E14 · 격리까지)
    # V-08 실기로 **툴 프리셋(SPONGE·BRUSH)도 채웠다**(rig_tool_width --at-holder) → 남은 빈 값은 approach_z_mm 뿐
    for tool_ in ('SPONGE', 'BRUSH'):
        for key in ('grip_width_mm', 'grip_zero_mm', 'grip_force_n', 'width_tol_mm'):
            assert f'cell.presets.{tool_}.{key}' not in empty, f'{tool_}.{key} 가 다시 비었다'
    assert {e.split('.')[2] for e in empty} == {'BOWL', 'CUP'}, empty
    assert {e.split('.')[3] for e in empty} == {'approach_z_mm'}
    assert 'cell.stations.HOME.posj' not in empty and 'cell.zones.RET_B.slots[1].posj' not in empty   # 슬롯 목록도 센다(번호는 1 부터)
    assert not [p for p in empty if not p.startswith('cell.')]


# ------------------------------------------------------------------ 형식 검사
def test_env_dir_overrides(tmp_path, monkeypatch):
    _write(tmp_path, params='hmi: {port: 9000}\n')
    monkeypatch.setenv(config.ENV_CONFIG_DIR, str(tmp_path))
    assert config.load()['hmi']['port'] == 9000
    assert config.load()['f3'] == {}                              # 없는 절은 빈 dict


def test_unknown_top_level_key_is_rejected(tmp_path):
    _write(tmp_path, params='f9: {}\n')
    with pytest.raises(config.ConfigError, match='f9'):
        config.load(tmp_path)


def test_section_in_wrong_file_is_rejected(tmp_path):
    _write(tmp_path, cell='cell: {}\nf1: {}\n')                   # 기능 절을 cell.yaml 에 넣으면 안 된다
    with pytest.raises(config.ConfigError, match='f1'):
        config.load(tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(config.ConfigError, match=config.CELL_FILE):
        config.load(tmp_path)


# ------------------------------------------------------------------ 실행 인자(환경변수)
def test_use_mock_env_overrides_yaml(tmp_path, monkeypatch):
    _write(tmp_path)
    assert config.load(tmp_path)['flow']['use_mock'] == ['f1']    # 변수가 없으면 YAML 그대로
    monkeypatch.setenv(config.ENV_USE_MOCK, 'f1, f3')
    assert config.load(tmp_path)['flow']['use_mock'] == ['f1', 'f3']
    monkeypatch.setenv(config.ENV_USE_MOCK, '')
    assert config.load(tmp_path)['flow']['use_mock'] == []        # 빈 값 = 전부 실제


def test_use_mock_unknown_name(tmp_path, monkeypatch):
    _write(tmp_path)
    monkeypatch.setenv(config.ENV_USE_MOCK, 'f1,f4')
    with pytest.raises(config.ConfigError, match='f4'):
        config.load(tmp_path)


@pytest.mark.parametrize('text,ok', [('0.3', True), ('1', True), ('0', False), ('1.5', False), ('-0.2', False), ('빠르게', False)])
def test_vel_scale_range(tmp_path, monkeypatch, text, ok):
    _write(tmp_path)
    monkeypatch.setenv(config.ENV_VEL_SCALE, text)
    if ok:
        assert config.load(tmp_path)['run']['vel_scale'] == float(text)
    else:
        with pytest.raises(config.ConfigError, match='vel_scale'):
            config.load(tmp_path)


def test_repo_rack_exit_paths_are_relative_vectors():
    """팔레트 칸의 exit_rel_mm = 꽂고 놓은 뒤 빠져나오는 상대 이동 목록(BASE).

    실기: 그릇 칸은 꽂은 자리에서 HOME 으로 곧장 가면 **그리퍼가 팔레트에 걸린다** → 먼저 칸 밖으로 빼야 한다.
    컵 칸은 접근점이 있어 수직으로 되올라가므로 필요 없다.
    """
    slots = config.load(SRC_CONFIG)['cell']['rack']['slots']
    have = {name for name, s in slots.items() if s.get('exit_rel_mm')}
    assert have == set(slots)                                           # 컵 칸도 그릇 칸과 같은 방식으로 빠져나온다
    # 🚨 들어가는 길에는 상대 이동이 **없다** — 내려온 뒤 y 로 밀어 넣으면 팔레트 **칸막이 벽에 걸린다**(실기).
    #    적재는 '칸 바로 위 → z 만 하강 → 놓기'. 빼는 것만 exit_rel_mm 이다.
    assert not any(s.get('entry_rel_mm') for s in slots.values())
    for name in have:
        for step in slots[name]['exit_rel_mm']:
            assert len(step) == 3 and all(isinstance(v, (int, float)) for v in step), (name, step)


def test_rig_coords_never_targets_a_filled_pose(tmp_path):
    """rig_coords ③(빈 자세는 KeyError · 안 움직임)의 목록은 **지금 비어 있는 자세**에서만 나와야 한다.

    검토에서 발견: 고정 목록(SOAP·ISOLATE)이 전부 채워지자, ③ 이 **Enter 확인 없이**
    실기 로봇을 SOAP → ISOLATE(실기 미확인 경로)로 움직이게 되어 있었다. 목록을 설정에서 뽑도록 고쳤고,
    채워진 자세가 들어오면 이 시험이 실패한다.
    """
    import importlib.util
    import shutil
    import yaml
    spec = importlib.util.spec_from_file_location('rig_coords', Path(__file__).resolve().parent / 'rig_coords.py')
    rig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rig)                                    # 모듈 맨 위는 ROS 를 부르지 않는다(cobot_common 은 main 안에서)

    real = config.load(SRC_CONFIG)
    assert rig._untaught(real) == []                                # 빈 자세 0개 → ③ 은 아무 데도 가지 않는다

    shutil.copy(SRC_CONFIG / 'params.yaml', tmp_path / 'params.yaml')
    doc = yaml.safe_load((SRC_CONFIG / 'cell.yaml').read_text(encoding='utf-8'))
    doc['cell']['stations']['SOAP']['BOWL']['posx'] = None          # 하나만 비운다
    (tmp_path / 'cell.yaml').write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
    assert rig._untaught(config.load(tmp_path)) == [('SOAP', 'BOWL', None)]   # 비운 것만 — 채워진 SOAP.CUP·ISOLATE 는 안 들어온다
