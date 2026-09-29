# -*- coding: utf-8 -*-
"""무게 함수 (INF-02c). 함수 표는 docs/03_설계_SDD.md §3.1.

로봇 관절의 토크로 들고 있는 물건의 무게를 역산해 컨트롤러가 알려 준다.
우리는 계산하지 않고 받기만 한다. 다만 그냥 받으면 안 되는 이유가 있다:

① 값이 넓게 퍼진다 — V-02 실측에서 200 g 추가 40.8 g 폭으로 흔들렸다
   (기록은 docs/test_logs/ 색인의 V-02). → 여러 번 재서 중앙값을 쓴다.
      평균은 한 번 크게 튄 값에 끌려가지만 중앙값은 안 끌려간다.
② 움직이는 중에 재면 가속도가 섞인다 → 부르는 쪽(f2.weigh)이 먼저 멈춘다.
③ 주의: 실패를 음수로 알려 준다 — 설치된 DSR_ROBOT2.py 의 get_workpiece_weight 는
   서비스가 실패하면 예외 대신 -1 을 돌려준다(srv 주석: "Negative value if error").
   그대로 쓰면 "무게 -1 g" 으로 계산이 돈다 → 음수는 버린다.
④ 주의: 0점 재설정(reset)은 컨트롤러를 멈출 수 있다 — TS-03 에서 실제로 모든 서비스가
   응답하지 않았고 브링업을 다시 해야 했다. → 선택 동작, 응답 상한, 실패하면 다시 부르지 않는다.

⑤ 주의: 단위는 kg 이다 — 첫 실기(이 경로로 읽은 첫 값)에서 그릇을 쥔 채 0.0684,
   빈손 0.0239 가 읽혔다. g 로 보면 "0.1 g" 이라 말이 안 되고, kg 으로 보면 68.4 g · 23.9 g
   (그릇 ≈ 44.5 g)으로 딱 맞는다. V-02 는 펜던트 화면(N)을 손으로 읽은 것이라 이 경로의 단위를 몰랐다.

⑥ 주의: get_workpiece_weight 는 |Fz| 다 — 부호를 버린다. 그래서 안 쓴다 (실기).
   툴 힘센서 Fz(get_tool_force · BASE)와 나란히 읽어 보니 하중 추정치 = |Fz| / g 였다:
     빈손 Fz +0.87 N → 하중 89 g · 그릇 +0.05 → 10 g · 그릇+43 g −0.10 → 13 g · 그릇+107 g −0.79 → 80 g
   무게가 늘수록 Fz 는 마이너스로 가는데(중력 = −Z) 절댓값이라 0 근처에서 거울처럼 되튄다 —
   앞서 "0 에 잘린다" 고 본 것이 이것이었다. 등록된 툴 무게가 실제보다 무거워 빈손이 +0.87 N 인 것도
   (편향 — 기준값 빼기로 상쇄) 절댓값 때문에 "그릇을 쥐면 가벼워지는" 것처럼 보였다.
   → 이 함수는 −Fz × 101.97 (g/N) 을 돌려준다. 부호가 있어 편향이 음수여도 상쇄가 된다.
   같은 자세·같은 이동 속도에서 그릇+107 g 이 +86 g 으로 읽혔다(폭 29 g) — 잔반 대용품 ≥100 g(CELL-03)은 잡는다.
   43 g 은 +15~26 g 으로 반쯤 묻힌다(흔들림 ±25 g) — 임계 50 g 밑이라 어차피 잔반이 아니다.
   API 는 BR-SR §5.2 "사용 로봇 기능" 에 있는 get_tool_force (force.read_force 와 같은 호출).

주의: 옵셋에 대해: 값에 편향이 있다 — 빈손 −89 g(툴 무게 등록 뒤) 처럼 음수일 수도 있다.
   게다가 이동 속도·이력에 따라 수십 g 씩 달라진다(빈손 빠른 이동 −89 · 그릇 느린 이동 −5).
   잔반 판정은 `측정값 − 빈 용기 기준값` 이라 두 값을 같은 경로·같은 자세·같은 속도로 재면 상쇄된다.
   주의: 흔들림: 정지해 있어도 ±25 g 가 10~20 s 주기로 오르내린다(실기) → 표본을 10 개(≈ 7 s) 이상 잡아 중앙값.
      지금 설정은 15 개 × 0.5 s(≈ 7 s 창) — 창이 한 주기보다 짧아 중앙값이 그만큼 치우칠 수 있다(params.yaml f2.weigh_samples).
   주의: 읽기 사이에 간격(f2.weigh_sample_gap_s)을 둔다 — 실기: 간격 없이 50 회를 0.03 s 에 읽으니
      50 개가 전부 −48.7 이었다. get_tool_force 는 컨트롤러가 주기적으로 갱신하는 값을 돌려주므로 갱신 전에
      다시 읽으면 같은 값이다. 표본이 "10 개" 이려면 시간으로도 퍼져 있어야 한다.
   그래서 `params.yaml` 의 `f2.empty_weight_g` 는 저울 무게가 아니라 이 함수로 읽은 값이어야 한다.
   저울로 잰 진짜 무게를 넣으면 빈 용기가 잔반 24 g 으로 보인다.

표기 — E-nn: 팀 결정 번호(docs/meetings/20260919_결정기록_DSN-03.md) · V-nn/INT-nn: 검증 항목(docs/test_logs/) · TS-nn: 트러블슈팅(docs/troubleshooting/)
"""
import time

# 주의: 이 모듈은 이름이 함수 이름과 같다(weigh.py 안의 weigh()). __init__.py 의
#    `from .weigh import *` 가 함수를 패키지에 올려 모듈 이름을 가린다.
#    `from cobot_common import weigh` 는 함수를, 모듈이 필요하면
#    `importlib.import_module('cobot_common.weigh')` 를 쓴다(시험 코드 참고).
__all__ = ['weigh', 'weigh_last', 'set_weigh_listener']

_MIN_SAMPLES = 1                           # weigh(n) 의 n 하한 — 0 이하를 주어도 최소 1회는 읽는다
_last = {}                                 # 마지막 weigh() 의 {'median_g', 'spread_g', 'n'} — 케이블 장력 경고·기록용 (weigh_last)
_listener = None                           # 표본을 읽을 때마다 부르는 함수 (set_weigh_listener) — 화면에 재는 값을 보여 주는 데 쓴다


def set_weigh_listener(fn):
    """재는 동안 표본을 하나 읽을 때마다 fn(samples, n, done, median_g) 을 부르게 한다. None 이면 끈다.

    samples  : 지금까지 읽은 값(g) 의 사본 — 잰 순서대로
    n        : 잴 횟수
    done     : 다 쟀으면 True — 이때만 median_g 가 값이다(그 전에는 None)
    주의: fn 은 weigh() 를 부른 스레드(메인)에서 불린다 — 값을 넘기기만 하고 바로 돌아와야 한다(오래 걸리면 읽기 간격이 늘어난다).
       fn 이 예외를 내도 재기는 계속한다.
    """
    global _listener
    _listener = fn


def _tell(samples, n, done=False, median_g=None):
    """듣는 함수가 있으면 부른다. 거기서 무엇이 터져도 재기를 멈추지 않는다."""
    fn = _listener
    if fn is None:
        return
    try:
        fn(list(samples), n, done, median_g)
    except Exception as e:                 # noqa: BLE001 — 화면 표시 때문에 무게 재기가 죽으면 안 된다
        try:
            _log().warn(f'weigh 표본 알림 실패 — {e!r} (재기는 계속한다)')
        except Exception:                  # noqa: BLE001
            pass


def weigh_last():
    """마지막 weigh() 의 요약 {'median_g', 'spread_g'(10~90 % 폭), 'n'} — 부르는 쪽(rig · flow)이 기록에 쓴다. 없으면 {}."""
    return dict(_last)


def _spread(values):
    """튄 값을 뺀 폭 = 10 % ~ 90 % 분위 차이(g). 표본이 적으면 그냥 최대−최소."""
    s = sorted(values)
    n = len(s)
    if n < 5:
        return s[-1] - s[0]
    return s[int(0.9 * (n - 1))] - s[int(0.1 * (n - 1))]


def _drift_and_jitter(values):
    """표본을 흐름(drift) 과 떨림(jitter) 으로 나눈다 → (창 전체의 흐름 g, 추세를 뺀 퍼짐 g).

    왜 나누나 (실기): 30 표본이 −96 → −123 으로 한 방향으로 미끄러졌다(창 전체 −26 g).
       떨림이 아니라 영점이 움직이는 것인데, 그냥 퍼짐(23 g)으로 보면 둘이 섞여
       ① 케이블 장력 경고가 거짓으로 뜨고(추세를 빼면 떨림은 12 g 뿐이었다)
       ② 정작 중요한 "기준값이 낡았다" 는 신호를 놓친다.
    흐름은 잔반 판정의 기준값(empty_weight_g)이 지금도 맞는지를 말해 주고,
    떨림은 그리퍼 케이블 장력을 말해 준다 — 서로 다른 문제다.
    """
    n = len(values)
    if n < 5:
        return 0.0, _spread(values)
    xs = list(range(n))
    mx = (n - 1) / 2.0
    my = sum(values) / n
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, values)) / denom if denom else 0.0
    residual = [y - (my + slope * (x - mx)) for x, y in zip(xs, values)]
    return slope * (n - 1), _spread(residual)


KG_TO_G = 1000.0                           # ⑤ get_workpiece_weight 는 kg (지금은 안 쓴다 — ⑥)
N_TO_G = 101.97                            # ⑥ 1 N ≈ 101.97 g (g = 9.807)
_FZ = 2                                    # get_tool_force → [fx, fy, fz, mx, my, mz] 의 fz


def weigh(n, reset=False):
    """정지 상태에서 n 번 재서 중앙값을 g 로 돌려준다.

    n     : 잴 횟수 (params.yaml 의 f2.weigh_samples)
    reset : 0점 재설정을 먼저 할지 — 기본 끔. TS-03 참고
    반환  : 무게(g) = −Fz × 101.97 — 툴 힘센서 Z(BASE) 를 부호 그대로 (⑥). 편향이 있어 음수일 수 있다

    주의: 잴 수 없으면 예외를 던진다. 숫자 하나로는 "0 g" 과 "실패" 를 구분할 수 없기 때문이다.
       부르는 쪽(flow 의 Flow.call)이 잡아서 ROBOT_ERROR 로 바꾼다.
    주의: 멈춘 뒤에 불러야 한다. 움직이는 중에는 가속도가 섞인다.
    """
    from .bootstrap import cfg, dsr

    d = dsr()                              # init() 전이거나 메인 스레드가 아니면 여기서 막는다
    n = max(_MIN_SAMPLES, int(n))
    conf = cfg()
    gap = float(((conf.get('f2') or {}).get('weigh_sample_gap_s')) or 0.0)   # 읽기 사이 간격(s) — 위 머리말

    if reset:
        _try_reset(d, conf)

    samples = []
    for i in range(n):
        if i and gap > 0.0:
            time.sleep(gap)                            # 주의: 갱신 전에 다시 읽으면 같은 값
        try:
            f = d.get_tool_force(ref=d.DR_BASE)        # ⑥ 부호 있는 Fz — |Fz| 인 get_workpiece_weight 는 안 쓴다
        except Exception as e:             # noqa: BLE001 — 한 번 실패해도 나머지로 이어 간다
            _log().warn(f'get_tool_force 실패 — {e!r}')
            continue
        if not isinstance(f, (list, tuple)) or len(f) != 6:   # 주의: API 는 실패를 -1 하나로 알려 준다
            _log().warn(f'툴 힘 읽기 실패값 {f!r} — 버린다')
            continue
        samples.append(-float(f[_FZ]) * N_TO_G)       # ⑥ 중력은 −Z → 무게 = −Fz
        _tell(samples, n)

    if not samples:
        raise RuntimeError(f'하중을 {n}회 모두 읽지 못했다 — 브링업·제어권을 확인한다')
    if len(samples) < n:
        _log().warn(f'하중 {n}회 중 {len(samples)}회만 읽었다')

    g = _median(samples)
    spread = _spread(samples)
    drift, jitter = _drift_and_jitter(samples)
    _last.clear()
    _last.update(median_g=g, spread_g=spread, drift_g=drift, jitter_g=jitter, n=len(samples))
    _tell(samples, n, done=True, median_g=g)
    # 개별 값도 남긴다 — V-02 에서 회차 값을 안 남겨 평균·표준편차를 못 냈다(그 기록 §2)
    _log().info(f'weigh n={n} → {g:.1f} · 흐름 {drift:+.0f} g · 떨림 {jitter:.0f} g '
                f'(읽음: {", ".join(f"{s:.1f}" for s in samples)})')
    lim = (conf.get('f2') or {}).get('limits') or {}
    # 케이블 장력 = 떨림(추세를 뺀 퍼짐). 흐름을 섞어 보면 거짓 경보가 난다(실기: 퍼짐 52 → 떨림 12)
    limit = lim.get('max_weigh_spread_g')
    if limit is not None and jitter > float(limit):
        _log().warn(f'🔗 무게 떨림 {jitter:.0f} g > {float(limit):.0f} g — 그리퍼 **케이블 장력** 의심. '
                    '케이블 여유 길이를 확인한다(V-02 시험 기록). 이 값은 참고만')
    # 영점 흐름 = 기준값이 낡았다는 신호. 재는 몇 초 안에서도 움직이면 5 시간 전 기준값은 더더욱 안 맞는다
    dlimit = lim.get('max_weigh_drift_g')
    if dlimit is not None and abs(drift) > float(dlimit):
        _log().warn(f'📉 재는 동안 값이 {drift:+.0f} g 흘렀다 (상한 {float(dlimit):.0f} g) — **영점이 움직이고 있다.** '
                    '빈 용기 기준값(f2.empty_weight_g)을 방금 재지 않았다면 **잔반 판정을 믿지 않는다** '
                    '(rig_f2.py empty --kind BOWL 로 다시 잰다)')
    return g


# ------------------------------------------------------------------ 내부
def _median(values):
    """중앙값. 튄 값 하나에 끌려가지 않는다(V-02 에서 폭 40.8 g)."""
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def _try_reset(d, conf):
    """0점 재설정 — 주의: 선택 동작. 실패해도 다시 부르지 않고 그냥 진행한다.

    TS-03: reset_workpiece_weight 가 반환하지 않으면 컨트롤러의 서비스 처리가 그 한 건에
    물려 뒤따르는 요청이 전부 대기한다. 반복 호출하면 계속 막힌다.
    판정식이 차동(측정값 − 빈 용기 기준값)이라 0점이 없어도 옵셋은 상쇄된다.
    """
    limit = float((conf.get('f2') or {}).get('weigh_reset_timeout_s') or 3.0)
    t0 = time.monotonic()
    try:
        d.reset_workpiece_weight()
    except Exception as e:                 # noqa: BLE001 — reset 실패로 측정을 포기하지 않는다
        _log().warn(f'0점 재설정 실패 — {e!r} · 그대로 진행한다 (TS-03)')
        return False
    took = time.monotonic() - t0
    if took > limit:
        _log().warn(f'0점 재설정이 {took:.1f}s 걸렸다 (상한 {limit}s) — 다시 부르지 않는다 (TS-03)')
        return False
    return True


def _log():
    from .bootstrap import io_node
    return io_node().get_logger()
