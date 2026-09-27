# -*- coding: utf-8 -*-
"""가짜 flow 의 대본(scenario yaml) → 시간 순서의 '장면' 목록. ROS 를 쓰지 않는다(그래서 로봇·ROS 없이 시험할 수 있다).

대본 = scenarios/_defaults.yaml(공통 값) 위에 scenarios/<이름>.yaml 을 덮어쓴 것. 시간·횟수·힘 같은 숫자는 전부 yaml 에 있다.
장면(Scene) 1개 = "이 상태를 몇 초 동안 방송한다" + 끝날 때 낼 이벤트(있으면).
    state    : FlowState 메시지의 필드(stamp 제외) — 실제 flow 의 snapshot() 과 같은 키
    gripping : /cell/gripping 값
    wiping   : True 면 그동안 /cell/force 를 낸다(닦는 동안만 — IRD §6)
    event    : 장면이 끝날 때 내는 FlowEvent 필드 (용기 1개 완료·격리·건너뜀마다 1건 — IRD §7)
    item     : 몇 번째 용기의 장면인가(0 부터). 용기와 무관한 장면(IDLE·DONE)은 -1 — 중단(abort) 때 '다음 용기'를 찾는 데 쓴다

실제 flow(f2_sense_flow/flow.py)를 흉내 낸 규칙
    단계 순서 PICK → WEIGH → SHAKE → SEAT → SOAP → WIPE → RINSE → RACK, 용기마다 이벤트 1건, 전부 끝나면 DONE 을 잠깐 유지한 뒤 IDLE.
    실패는 정책대로: isolate(격리) → ISOLATE 단계 + ISOLATED 이벤트 / next_zone(빈 구역) → SKIPPED 이벤트 / pause → PAUSED(last_code 에 실패 코드).
    수량·소모품 값은 IDLE 로 돌아가도 남는다(다음 시작 때 0 으로).
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

STEPS = ('PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK')
ACTIONS = ('isolate', 'next_zone', 'pause', 'pause_retry')   # 🆕 9/25 pause_retry = 멈춘 뒤 **그 단계부터 다시** 이어 완료(TOOL_LOST·LEFTOVER_REMAIN·케이블 이상 · 실제 flow 의 RETRY_STEP)
DEFAULTS_FILE = '_defaults.yaml'
OK = 'OK'


@dataclass
class Scene:
    duration_s: float
    state: dict
    gripping: bool = False
    wiping: bool = False
    event: dict = field(default=None)
    item: int = -1


def scenario_dir() -> Path:
    """대본 폴더: 설치본(share/f4_hmi/scenarios)이 있으면 그것, 없으면 소스 폴더."""
    try:
        from ament_index_python.packages import get_package_share_directory
        found = Path(get_package_share_directory('f4_hmi')) / 'scenarios'
        if found.is_dir():
            return found
    except Exception:                                # noqa: BLE001 — 빌드 전이거나 ROS 환경이 아니다 → 소스 폴더
        pass
    return Path(__file__).resolve().parents[1] / 'scenarios'


def names(directory=None) -> list:
    d = Path(directory) if directory else scenario_dir()
    return sorted(p.stem for p in d.glob('*.yaml') if not p.name.startswith('_'))


def load(name_or_path, directory=None) -> dict:
    """대본을 읽어 공통 값과 합친다. 이름('normal') 또는 yaml 파일 경로."""
    d = Path(directory) if directory else scenario_dir()
    path = Path(name_or_path)
    if path.suffix != '.yaml':
        path = d / f'{name_or_path}.yaml'
    if not path.is_file():
        raise FileNotFoundError(f'대본이 없다: {path} — 쓸 수 있는 이름: {names(d)}')
    with open(path.parent / DEFAULTS_FILE, encoding='utf-8') as f:
        merged = yaml.safe_load(f) or {}
    with open(path, encoding='utf-8') as f:
        own = yaml.safe_load(f) or {}
    for key, value in own.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}                  # step_s 처럼 일부만 바꿀 수 있게
        else:
            merged[key] = value
    merged.setdefault('name', path.stem)
    _validate(merged, path)
    return merged


def _validate(scn, path):
    if not scn.get('items'):
        raise ValueError(f'{path}: items 가 비어 있다')
    for i, item in enumerate(scn['items'], start=1):
        if item.get('kind') not in ('BOWL', 'CUP'):
            raise ValueError(f"{path}: items[{i}].kind={item.get('kind')!r} — BOWL 또는 CUP")
        fail = item.get('fail')
        if fail and (fail.get('at') not in STEPS or fail.get('action') not in ACTIONS or not fail.get('code')):
            raise ValueError(f'{path}: items[{i}].fail 은 at(단계 {STEPS}) · code · action({ACTIONS}) 가 필요하다')
        pause = item.get('pause')
        if pause and pause.get('at') not in STEPS:
            raise ValueError(f"{path}: items[{i}].pause.at={pause.get('at')!r} — 단계 이름")


def build(scn: dict) -> list:
    """대본 → 장면 목록(한 바퀴). 맨 앞은 IDLE, 맨 뒤는 DONE 유지 → IDLE."""
    step_s, grip, counts, weights = scn['step_s'], scn['gripping'], scn['counts'], scn['weight_g']
    targets = scn.get('targets') or {}
    st = dict(step='IDLE', kind='', zone_id='', done_bowl=0, done_cup=0, isolated=0,
              target_bowl=int(targets.get('bowl', sum(1 for it in scn['items'] if it['kind'] == 'BOWL'))),
              target_cup=int(targets.get('cup', sum(1 for it in scn['items'] if it['kind'] == 'CUP'))),
              sponge_uses=0, soap_dips=0, rinse_dips=0, last_code=OK, message='')
    scenes = []
    current = [-1]                                                  # 지금 만드는 장면이 속한 용기 번호

    def add(duration_s, *, event=None, wiping=False, gripping=None):
        scenes.append(Scene(float(duration_s), dict(st), grip.get(st['step'], False) if gripping is None else gripping,
                            wiping, event, current[0]))

    add(scn['idle_s'])                                              # 시작 전 IDLE
    halted = False
    for number, item in enumerate(scn['items']):
        current[0] = number
        kind, fail, pause = item['kind'], item.get('fail'), item.get('pause')
        st.update(kind=kind, zone_id=item.get('zone', ''), last_code=OK, message='')
        spent = 0.0

        def event(result, code=OK, rack_slot=''):
            before, after = weights.get(kind, [0.0, 0.0])
            return dict(kind=kind, zone_id=st['zone_id'], rack_slot=rack_slot, attempts=int(item.get('attempts', 1)),
                        weight_before_g=float(before), weight_after_g=float(after if result == 'DONE' else before),
                        result=result, code=code, duration_s=round(spent, 2), force_log_path='')

        for step in STEPS:
            st.update(step=step, last_code=OK, message='')
            full = float(step_s[step])
            wiping = step == 'WIPE'
            if pause and pause['at'] == step:                       # 운영자가 도중에 일시정지 → 재개 (IRD §6: 그 자리에서 멈췄다 이어서)
                first = min(float(pause.get('after_s', full / 2)), full)
                add(first, wiping=wiping)
                was_gripping = scenes[-1].gripping
                st.update(step='PAUSED', message=pause.get('message', '일시 정지'))
                add(pause['hold_s'], gripping=was_gripping)         # 멈춰도 쥔 것은 그대로 쥐고 있다
                st.update(step=step, message='')
                add(full - first, wiping=wiping)
                spent += full + float(pause['hold_s'])
            else:
                add(full, wiping=wiping)
                spent += full
            if fail and fail['at'] == step:
                st.update(last_code=fail['code'], message=fail.get('message', ''))
                if fail['action'] == 'next_zone':                   # 구역이 비었다 → 건너뜀
                    scenes[-1].event = event('SKIPPED', fail['code'])
                elif fail['action'] == 'isolate':                   # 격리 구역에 내려놓고 다음 용기
                    st.update(step='ISOLATE', isolated=st['isolated'] + 1)
                    spent += float(step_s['ISOLATE'])
                    add(step_s['ISOLATE'], event=event('ISOLATED', fail['code']))
                elif fail['action'] == 'pause_retry':               # 🆕 9/25 멈춤 → (사람이 손을 쓴 뒤) 그 단계부터 다시 → 완료(E42·E37·케이블)
                    was_gripping = scenes[-1].gripping
                    st.update(step='PAUSED')
                    add(fail.get('hold_s', scn['pause_hold_s']), gripping=was_gripping)
                    spent += float(fail.get('hold_s', scn['pause_hold_s']))
                    if fail.get('resume_message'):                  # 재개 직후 flow 가 잠깐 보내는 문구(케이블: '재개 요청 감지 …' → HMI 비프)
                        st.update(step=step, last_code=OK, message=fail['resume_message'])
                        add(float(fail.get('resume_s', 1.5)), wiping=wiping)
                        spent += float(fail.get('resume_s', 1.5))
                    st.update(step=step, last_code=OK, message='')
                    add(full, wiping=wiping)                        # 그 단계부터 다시
                    spent += full
                    fail = None                                     # 이 용기는 정상 완료로 이어 간다(다시 실패하지 않음)
                else:                                               # pause — 사람이 볼 때까지 멈춘다(ROBOT_ERROR · RACK_FULL)
                    was_gripping = scenes[-1].gripping
                    st.update(step='PAUSED')
                    add(fail.get('hold_s', scn['pause_hold_s']), gripping=was_gripping)
                    halted = True
                if fail is not None:
                    break
            if step == 'SOAP':
                st['soap_dips'] += int(counts['soap_dips'])
            elif step == 'WIPE':
                st['sponge_uses'] += 1
            elif step == 'RINSE':
                st['rinse_dips'] += int(counts['rinse_dips'])
        else:                                                       # 끝까지 갔다 → 완료
            # 진짜 flow(flow.py process_one)처럼 적재(RACK)까지 **다 끝난 뒤에** 센다 — 늘어난 수는 다음 장면부터 보인다.
            # 9/21 황인재: 적재 장면에서 먼저 세었더니 화면이 '다음 칸'을 적재 중으로 보였다가 비워 버렸다.
            st['done_bowl' if kind == 'BOWL' else 'done_cup'] += 1
            scenes[-1].event = event('DONE', OK, item.get('rack_slot', ''))
        if halted:
            break
    current[0] = -1
    if not halted:
        st.update(step='DONE', kind='', zone_id='', last_code=OK, message='')
        add(scn['done_hold_s'])
    st.update(step='IDLE', kind='', zone_id='', message='')
    add(scn['idle_s'])
    return scenes


def total_s(scenes) -> float:
    return sum(s.duration_s for s in scenes)


def start_of(scenes, index) -> float:
    """index 번 장면이 시작하는 시각."""
    return sum(s.duration_s for s in scenes[:index])


def after_item(scenes, index) -> int:
    """index 번 장면의 용기가 끝난 **다음** 장면 번호(다음 용기의 첫 장면, 없으면 DONE·IDLE). 중단(abort)이 건너뛸 곳."""
    item = scenes[index].item
    for k in range(index + 1, len(scenes)):
        if scenes[k].item != item:
            return k
    return len(scenes) - 1


def scene_at(scenes, t_s):
    """한 바퀴 안의 시각 t_s 에 방송할 장면과 그 번호."""
    acc = 0.0
    for i, s in enumerate(scenes):
        acc += s.duration_s
        if t_s < acc:
            return i, s
    return len(scenes) - 1, scenes[-1]


def force_at(scn, t_s) -> float:
    """닦는 힘 흉내: 목표 힘 주위로 출렁이는 값(N). 음수는 내지 않는다."""
    import math
    f = scn['force']
    return max(0.0, float(f['target_n']) + float(f['ripple_n']) * math.sin(2.0 * math.pi * t_s / float(f['period_s'])))
