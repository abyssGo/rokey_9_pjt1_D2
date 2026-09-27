# -*- coding: utf-8 -*-
"""가짜 기능 모듈 — 남의 코드·로봇 없이 flow 와 HMI 를 개발한다 (IRD §10, INF-03).

    params.yaml
      flow:
        use_mock: [f1, f3]                    # 이 기능만 가짜로. [f1,f2,f3] 면 드라이버 없이
        mock:
          fail_on: ["place:SEAT_FAIL"]        # place 가 항상 SEAT_FAIL 로 실패
          # "rack_place:RACK_JAM:1"           # 처음 1회만 실패 → 재시도 정책 시험용
          # "soap:BOOM"                       # 코드가 아니라 예외를 던진다 (TC-10)

실제 모듈과 같은 함수 이름·같은 인자다(`cobot_api.check_api` 로 검사).
돌려주는 숫자는 그럴듯한 값일 뿐 측정값이 아니다 — 임계값을 여기서 정하지 않는다.
"""
__all__ = ['configure', 'reset', 'code_for', 'parse_fail_on', 'BOOM']

_rules = None          # {함수이름: [코드, 남은횟수 or None]}


def parse_fail_on(specs):
    """["place:SEAT_FAIL", "rack_place:RACK_JAM:1"] → {'place': ['SEAT_FAIL', None], ...}

    형식: "함수명:코드" (항상 실패) 또는 "함수명:코드:횟수" (처음 N회만 실패).

    코드가 BOOM 이면 Result 를 돌려주는 대신 예외를 던진다(TC-10).
       왜 필요한가: 기능 함수가 터져도 flow_node 가 죽지 않고 ROBOT_ERROR → PAUSED 로
       가야 한다(SDD §9.3). 실패 코드만 주입해서는 그 길을 한 번도 안 지난다 —
       코드는 함수가 스스로 돌려준 것이라 이미 정상 경로다.
    """
    out = {}
    for spec in specs or []:
        parts = str(spec).split(':')
        if len(parts) not in (2, 3):
            raise ValueError(f'fail_on 형식이 틀렸다: {spec!r} — "함수명:코드" 또는 "함수명:코드:횟수"')
        name, code = parts[0].strip(), parts[1].strip()
        left = int(parts[2]) if len(parts) == 3 else None
        out[name] = [code, left]
    return out


def configure(fail_on):
    """실패 주입 규칙을 세운다. 시험에서 직접 부르거나, 첫 호출 때 설정에서 읽힌다."""
    global _rules
    _rules = parse_fail_on(fail_on)


def reset():
    global _rules
    _rules = None


def _load_from_cfg():
    """cobot_common 설정에서 flow.mock.fail_on 을 읽는다. 없으면 빈 규칙."""
    try:
        import cobot_common as cc
        specs = (cc.cfg().get('flow', {}).get('mock', {}) or {}).get('fail_on', [])
    except Exception:                      # init() 전이거나 설정이 없으면 주입 없음
        specs = []
    configure(specs)


BOOM = 'BOOM'                          # 이 코드는 "예외를 던져라" 는 뜻이다


def code_for(fn_name):
    """이 함수가 이번에 실패해야 하면 실패 코드를, 아니면 None 을 돌려준다.

    주의: 코드가 BOOM 이면 여기서 예외를 던진다 — 부르는 쪽(가짜 기능 함수)은
       그대로 두고 여기 한 곳만 보면 되게 했다. flow 의 call_fn 이 받아
       ROBOT_ERROR 로 바꾼다(SDD §7).
    """
    if _rules is None:
        _load_from_cfg()
    rule = _rules.get(fn_name)
    if rule is None:
        return None
    code, left = rule
    if left is not None:
        if left <= 0:
            return None
        rule[1] = left - 1
    if code == BOOM:
        raise RuntimeError(f'{fn_name} 이(가) 터졌다 (주입된 예외 — TC-10)')
    return code
