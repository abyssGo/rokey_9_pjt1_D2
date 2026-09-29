# -*- coding: utf-8 -*-
"""가짜 flow 의 대본 → 장면 목록 (ROS 불필요)."""
import pytest

from f4_hmi import scenario as sc

ALL = ['normal', 'isolate', 'error', 'paused', 'empty_zone', 'tool_lost', 'leftover_remain', 'cable', 'tool_fail']   # 🆕 9/25 예외 3종(E37·E42·#93) · 9/26 tool_fail(E52)


def _contract_steps():
    """함수 약속(cobot_api)의 단계 목록. 빌드 전이라 안 보이면 대본 모듈이 아는 이름으로 대신한다."""
    try:
        from cobot_api.contracts import STEPS
        return STEPS
    except ModuleNotFoundError:
        return sc.STEPS + ('IDLE', 'ISOLATE', 'DONE', 'ERROR', 'PAUSED')


def test_all_scenarios_exist_and_build():
    assert set(ALL) <= set(sc.names())
    for name in ALL:
        scenes = sc.build(sc.load(name))
        assert scenes[0].state['step'] == 'IDLE' and scenes[-1].state['step'] == 'IDLE'
        assert all(s.duration_s > 0 for s in scenes)
        assert {s.state['step'] for s in scenes} <= set(_contract_steps())  # 단계 이름은 IRD §2 그대로


def test_normal_runs_every_step_and_emits_one_event_per_item():
    scn = sc.load('normal')
    scenes = sc.build(scn)
    steps = [s.state['step'] for s in scenes]
    assert steps[1:9] == list(sc.STEPS)                                     # 용기 1개 = PICK … RACK
    events = [s.event for s in scenes if s.event]
    assert [(e['result'], e['rack_slot']) for e in events] == [('DONE', 'RACK_B1'), ('DONE', 'RACK_B2'), ('DONE', 'RACK_C1'), ('DONE', 'RACK_C2')]
    last = scenes[-1].state                                                 # 수량·소모품은 IDLE 로 돌아가도 남는다
    assert (last['done_bowl'], last['done_cup'], last['target_bowl'], last['target_cup']) == (2, 2, 2, 2)
    assert (last['sponge_uses'], last['soap_dips'], last['rinse_dips']) == (4, 12, 8)
    assert 'DONE' in steps and [s.wiping for s in scenes].count(True) == 4  # 닦는 장면에서만 힘을 낸다
    assert events[0]['duration_s'] == pytest.approx(sum(scn['step_s'][k] for k in sc.STEPS))


def test_event_fields_match_flow_event_message():
    msgs = pytest.importorskip('cobot_msgs.msg', reason='cobot_msgs 를 빌드한 뒤(soc)에 돈다 — 메시지 정의와 대본의 필드 이름을 대조한다')
    FlowEvent, FlowState = msgs.FlowEvent, msgs.FlowState
    scenes = sc.build(sc.load('isolate'))
    event = next(s.event for s in scenes if s.event)
    assert set(event) == set(FlowEvent.get_fields_and_field_types()) - {'stamp'}
    assert set(scenes[0].state) == set(FlowState.get_fields_and_field_types()) - {'stamp'}


def test_isolate_goes_through_isolate_step():
    scenes = sc.build(sc.load('isolate'))
    i = next(k for k, s in enumerate(scenes) if s.state['step'] == 'ISOLATE')
    assert scenes[i - 1].state['step'] == 'SHAKE'                           # 털기에서 실패 → 격리
    assert scenes[i].event['result'] == 'ISOLATED' and scenes[i].event['code'] == 'LEFTOVER_REMAIN' and scenes[i].event['rack_slot'] == ''
    assert scenes[i].state['isolated'] == 1 and scenes[-1].state['done_bowl'] == 1 and scenes[-1].state['done_cup'] == 2


def test_error_stops_in_paused_with_code():
    scenes = sc.build(sc.load('error'))
    paused = [s for s in scenes if s.state['step'] == 'PAUSED']
    assert len(paused) == 1 and paused[0].state['last_code'] == 'ROBOT_ERROR' and paused[0].state['message']
    assert paused[0].gripping is True                                       # 멈춰도 쥔 것은 쥐고 있다
    assert 'DONE' not in [s.state['step'] for s in scenes]                  # 멈췄으므로 완료가 아니다


def test_operator_pause_splits_the_step_and_resumes_it():
    scn = sc.load('paused')
    scenes = sc.build(scn)
    i = next(k for k, s in enumerate(scenes) if s.state['step'] == 'PAUSED')
    before, hold, after = scenes[i - 1], scenes[i], scenes[i + 1]
    assert before.state['step'] == after.state['step'] == 'WIPE'            # 하던 단계를 이어서
    assert before.duration_s + after.duration_s == pytest.approx(scn['step_s']['WIPE']) and hold.duration_s == 6.0
    assert hold.state['last_code'] == 'OK' and not hold.wiping and before.wiping and after.wiping


def test_empty_zone_is_skipped():
    scenes = sc.build(sc.load('empty_zone'))
    skipped = [s.event for s in scenes if s.event and s.event['result'] == 'SKIPPED']
    assert len(skipped) == 1 and skipped[0]['code'] == 'EMPTY_ZONE' and skipped[0]['attempts'] == 2
    assert (scenes[-1].state['done_bowl'], scenes[-1].state['target_bowl']) == (1, 2)


def test_scene_at_and_force():
    scn = sc.load('normal')
    scenes = sc.build(scn)
    assert sc.scene_at(scenes, 0.0)[0] == 0 and sc.scene_at(scenes, scn['idle_s'] + 0.01)[1].state['step'] == 'PICK'
    assert sc.scene_at(scenes, 1e9)[0] == len(scenes) - 1
    values = [sc.force_at(scn, t / 10) for t in range(20)]
    f = scn['force']
    assert min(values) >= f['target_n'] - f['ripple_n'] - 1e-9 and max(values) <= f['target_n'] + f['ripple_n'] + 1e-9


@pytest.mark.parametrize('text', ["items: []\n", "items: [{kind: PLATE}]\n",
                                  "items: [{kind: BOWL, fail: {at: NOWHERE, code: X, action: isolate}}]\n",
                                  "items: [{kind: BOWL, fail: {at: PICK, code: X, action: explode}}]\n"])
def test_bad_scenario_is_rejected(tmp_path, text):
    (tmp_path / '_defaults.yaml').write_text((sc.scenario_dir() / '_defaults.yaml').read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / 'bad.yaml').write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        sc.load('bad', tmp_path)


def test_unknown_scenario_name():
    with pytest.raises(FileNotFoundError):
        sc.load('no_such_scenario')


def test_scenes_know_their_item_so_abort_can_skip_to_the_next_one():
    scenes = sc.build(sc.load('normal'))
    assert scenes[0].item == -1 and scenes[-1].item == -1 and scenes[-2].state['step'] == 'DONE' and scenes[-2].item == -1
    assert [s.item for s in scenes[1:9]] == [0] * 8 and scenes[9].item == 1
    wipe = next(k for k, s in enumerate(scenes) if s.state['step'] == 'WIPE')
    nxt = sc.after_item(scenes, wipe)
    assert scenes[nxt].item == 1 and scenes[nxt].state['step'] == 'PICK'            # 첫 그릇을 접으면 둘째 그릇의 PICK 으로
    assert sc.start_of(scenes, nxt) == pytest.approx(sum(s.duration_s for s in scenes[:nxt]))
    last_wipe = max(k for k, s in enumerate(scenes) if s.state['step'] == 'WIPE')
    assert scenes[sc.after_item(scenes, last_wipe)].state['step'] == 'DONE'          # 마지막 용기를 접으면 DONE 으로


def test_rack_scene_has_not_counted_its_own_container_yet():
    """진짜 flow 는 적재까지 **다 끝난 뒤** done 을 올린다 → 적재(RACK) 중에는 이번 용기가 아직 안 세어져 있다.
    그래야 화면이 지금 넣는 칸(rack_order[done])을 가리킨다. 9/21 황인재: 가짜가 먼저 세어 다음 칸이 '적재 중' 으로 보였다."""
    scenes = sc.build(sc.load('normal'))
    racks = [s.state for s in scenes if s.state['step'] == 'RACK']
    assert [(r['kind'], r['done_bowl'], r['done_cup']) for r in racks] == [
        ('BOWL', 0, 0), ('BOWL', 1, 0), ('CUP', 2, 0), ('CUP', 2, 1)]


# ------------------------------------------------------------------ 🆕 9/25 pause_retry — 멈춘 뒤 그 단계부터 다시 이어 완료(TOOL_LOST · LEFTOVER_REMAIN · 케이블)
def test_pause_retry_pauses_with_the_code_then_finishes_the_item():
    scenes = sc.build(sc.load('tool_lost'))
    paused = [s for s in scenes if s.state['step'] == 'PAUSED']
    assert len(paused) == 1 and paused[0].state['last_code'] == 'TOOL_LOST' and paused[0].state['message'] == ''   # 실제 flow 처럼 문구는 비어 있다
    i = scenes.index(paused[0])
    assert scenes[i + 1].state['step'] == 'WIPE' and scenes[i + 1].state['last_code'] == 'OK'                   # 그 단계부터 다시
    assert paused[0].gripping is True                                                                            # 멈춰도 쥔 것은 그대로
    dones = [s.event for s in scenes if s.event and s.event['result'] == 'DONE']
    assert len(dones) == 4 and dones[0]['kind'] == 'BOWL' and dones[0]['rack_slot'] == 'RACK_B1'                  # 이 용기도 완료로 끝난다
    assert scenes[-2].state['step'] == 'DONE'


def test_cable_scenario_sends_the_resume_notice_before_continuing():
    scenes = sc.build(sc.load('cable'))
    paused = [s for s in scenes if s.state['step'] == 'PAUSED']
    assert paused[0].state['last_code'] == 'ROBOT_ERROR' and '케이블' in paused[0].state['message']
    i = scenes.index(paused[0])
    assert scenes[i + 1].state['step'] == 'WEIGH' and '재개 요청 감지' in scenes[i + 1].state['message']         # → HMI 비프
    assert scenes[i + 2].state['step'] == 'WEIGH' and scenes[i + 2].state['message'] == ''


def test_leftover_remain_scenario_pauses_at_shake_holding_the_bowl():
    scenes = sc.build(sc.load('leftover_remain'))
    paused = [s for s in scenes if s.state['step'] == 'PAUSED']
    assert len(paused) == 1 and paused[0].state['last_code'] == 'LEFTOVER_REMAIN' and paused[0].state['kind'] == 'BOWL' and paused[0].gripping
