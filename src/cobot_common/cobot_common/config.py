# -*- coding: utf-8 -*-
"""설정 로더 — config/cell.yaml(공용) + config/params.yaml(기능별 절)을 읽어 하나의 dict 로 합친다. (SDD §4.3, IRD §9)

    from cobot_common import config
    cfg = config.load()                     # 보통은 cc.cfg() 로 쓴다
    cfg['cell']['limits']['safe_z_mm']      # 공용 값 (cell.yaml — 주인만 고친다)
    cfg['f3']['wipe_bowl']                  # 기능별 절 (자기 절만 수정)
    cfg['run']['vel_scale']                 # 실행할 때 정하는 값 (YAML 에 없다 — 아래 "실행 인자")

설정 폴더를 찾는 순서
  1) 환경변수 PREWASH_CONFIG_DIR (시험·현장에서 다른 설정 묶음으로 바꿔 끼울 때)
  2) 설치된 패키지의 share/cobot_common/config  (cbc 는 --symlink-install 이라 YAML 을 고치면 재빌드 없이 반영된다)
  3) 빌드 전이면 소스 트리의 src/cobot_common/config (이 파일 기준 상대경로)

실행 인자 — 런치 인자가 환경변수로 넘어온다 (prewash_bringup 의 런치 2종이 넣어 준다. rig 는 손으로 줘도 된다)
  PREWASH_USE_MOCK="f1,f3"   → cfg['flow']['use_mock'] 을 덮어쓴다. 빈 문자열이면 [] (전부 실제). 변수가 없으면 YAML 값 그대로
  PREWASH_VEL_SCALE="0.3"    → cfg['run']['vel_scale'] (0 초과 1 이하, 없으면 1.0). 이동 함수가 cell.limits 의 속도 % 에 곱한다
  init() 보다 먼저 읽을 수 있어야 해서 ROS 파라미터가 아니라 환경변수다 (flow 는 use_mock 을 보고 init(robot=False) 를 정한다).
"""
import os
from pathlib import Path

import yaml

CELL_FILE = 'cell.yaml'
PARAMS_FILE = 'params.yaml'
CELL_KEYS = ('cell',)                               # cell.yaml 의 최상위 키
PARAM_SECTIONS = ('f1', 'f2', 'f3', 'flow', 'hmi')  # params.yaml 의 절 (IRD §9)
RUN_KEY = 'run'                                     # 실행 인자 (파일에 없다)
MOCKABLE = ('f1', 'f2', 'f3')                       # use_mock 에 쓸 수 있는 이름
ENV_CONFIG_DIR = 'PREWASH_CONFIG_DIR'
ENV_USE_MOCK = 'PREWASH_USE_MOCK'
ENV_VEL_SCALE = 'PREWASH_VEL_SCALE'


class ConfigError(RuntimeError):
    """설정 파일이 없거나 형식이 약속(SDD §4.3)과 다를 때."""


def config_dir() -> Path:
    """설정 폴더 경로를 돌려준다."""
    env = os.environ.get(ENV_CONFIG_DIR)
    if env:
        return Path(env)
    try:
        from ament_index_python.packages import get_package_share_directory
        return Path(get_package_share_directory('cobot_common')) / 'config'
    except Exception:       # 빌드 전(패키지 미설치) → 소스 트리
        return Path(__file__).resolve().parent.parent / 'config'


def _read(path: Path, allowed) -> dict:
    if not path.is_file():
        raise ConfigError(f'설정 파일이 없다: {path}')
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f'{path.name}: 최상위는 "키: 값" 형식이어야 한다')
    unknown = [k for k in data if k not in allowed]
    if unknown:
        raise ConfigError(f'{path.name}: 약속에 없는 최상위 키 {unknown} (허용: {list(allowed)})')
    return data


def parse_use_mock(text: str) -> list:
    """'f1, f3' → ['f1', 'f3'] · '' → []. 모르는 이름이면 ConfigError."""
    names = [n.strip() for n in text.split(',') if n.strip()]
    bad = [n for n in names if n not in MOCKABLE]
    if bad:
        raise ConfigError(f'use_mock 에 쓸 수 없는 이름 {bad} (허용: {list(MOCKABLE)})')
    return names


def parse_vel_scale(text: str) -> float:
    """'0.3' → 0.3. 0 초과 1 이하가 아니면 ConfigError (속도를 올리는 쪽으로는 못 쓴다)."""
    try:
        v = float(text)
    except ValueError:
        raise ConfigError(f'vel_scale 은 숫자여야 한다: {text!r}') from None
    if not 0.0 < v <= 1.0:
        raise ConfigError(f'vel_scale 은 0 초과 1 이하여야 한다: {v}')
    return v


def load(directory=None) -> dict:
    """두 파일을 읽어 하나의 설정으로 합치고, 실행 인자(환경변수)를 얹는다. 비어 있는 절은 빈 dict 로 채운다."""
    d = Path(directory) if directory else config_dir()
    merged = {}
    merged.update(_read(d / CELL_FILE, CELL_KEYS))
    merged.update(_read(d / PARAMS_FILE, PARAM_SECTIONS))
    for key in CELL_KEYS + PARAM_SECTIONS:
        if merged.get(key) is None:
            merged[key] = {}

    if ENV_USE_MOCK in os.environ:
        merged['flow']['use_mock'] = parse_use_mock(os.environ[ENV_USE_MOCK])
    merged[RUN_KEY] = {'vel_scale': parse_vel_scale(os.environ.get(ENV_VEL_SCALE, '1.0'))}
    return merged


def unfilled(cfg: dict, sections=CELL_KEYS + PARAM_SECTIONS) -> list:
    """값이 비어 있는(null) 키의 경로 목록. 예: ['cell.limits.safe_z_mm', 'cell.stations.HOME.posj', …]"""
    found = []

    def walk(node, path):
        if node is None:
            found.append(path)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f'{path}.{k}')
        elif isinstance(node, list) and any(isinstance(v, dict) for v in node):     # 슬롯 목록 (번호는 1 부터 — cc.move_to 의 point 와 같다)
            for i, v in enumerate(node, start=1):
                walk(v, f'{path}[{i}]')
    for s in sections:
        if isinstance(cfg.get(s), dict):
            for k, v in cfg[s].items():
                walk(v, f'{s}.{k}')
    return found
