# UT-FLOW — `flow_node` 를 실제로 띄워서 (TC-10 · TC-12)

| 항목 | 내용 |
|---|---|
| 담당 | 민범진 |
| 일시 | 2026-09-21 18시대 (로봇 슬롯 대기 중) |
| 모드 | **로봇 없음** — 기능 3개를 전부 가짜(mock)로 (`PREWASH_USE_MOCK=f1,f2,f3`) |
| 무엇을 봤나 | 정지 → 재개 · 정지 → 중단 · **기능 함수가 터졌을 때** · **Ctrl+C 뒤 재실행** |
| **판정** | ✅ **4가지 전부 통과** · 🔧 시험 방법 함정 2건을 찾아 고침 |

지금까지 F2 는 **부품 단위 시험**(pytest 355건)만 있었다. 이 기록은 **진짜 프로그램을
띄워서** 사람이 버튼을 누르는 것처럼 서비스를 부른 것이다.

---

## 0. 어떻게 돌렸나

단계마다 0.5 초 쉬게 한 시험용 설정을 따로 만들었다 — 기본값 `step_delay_s: 0.0` 으로는
4개가 **2초 만에** 끝나 정지 버튼을 누를 틈이 없다.

```bash
# 시험용 설정 (params.yaml 의 flow.step_delay_s 만 0.5 로)
export PREWASH_USE_MOCK=f1,f2,f3 PREWASH_CONFIG_DIR=<시험용 폴더>
ros2 run f2_sense_flow flow_node
ros2 service call /flow/start  std_srvs/srv/Trigger
ros2 service call /flow/stop   std_srvs/srv/Trigger
ros2 service call /flow/resume std_srvs/srv/Trigger
ros2 service call /flow/abort  std_srvs/srv/Trigger
```

---

## 1. ① 정지 → 재개 — ✅

```
stop   → success=True
    stop 요청 — RINSE 앞에서 정지
    PAUSED — resume 을 기다린다 · stop 버튼
resume → success=True
    resume — 이어서 진행한다
    plan 완료 — 그릇 2 · 컵 2 · 격리 0
records.csv 4행
```

🔑 **단계 사이에서 멈춘다**(`RINSE 앞에서`) — 용기를 든 채 한가운데서 서지 않는다(SDD §5.1).
🔑 멈춘 동안 `/flow/state` 의 `step` 이 `PAUSED` 로 나간다(HMI 가 이걸 본다).

---

## 2. ② 정지 → 중단(abort) — ✅

```
stop   → success=True   → PAUSED
abort  → success=True
    abort — 이 용기를 접고 다음 용기로 간다
    plan 완료 — 그릇 1 · 컵 2 · 격리 1
records.csv 4행
```

🔑 **그릇 1 · 격리 1** — 접은 용기는 완료로 세지 않고 격리로 간다(IRD §6).
🔑 기록은 **4행 그대로** — 접힌 용기도 한 줄 남는다(`result=ISOLATED`).

---

## 3. ③ 기능 함수가 **터졌을 때** — ✅ (가장 중요)

`f3.soap` 이 `Result` 를 돌려주는 대신 **예외를 던지게** 주입했다.

```
    f3.soap 에서 예외 — RuntimeError('soap 이(가) 터졌다')
    f3.soap 실패 → ROBOT_ERROR
    PAUSED — resume 을 기다린다 · 코드 ROBOT_ERROR
노드 살아있나: 예 ✅
상태: step: PAUSED
Traceback 개수: 0
```

🔑 **프로그램이 죽지 않는다.** 예외가 `ROBOT_ERROR` 로 바뀌고 `PAUSED` 가 된다(SDD §7).
🔑 트레이스백이 콘솔로 새지 않는다 — 로그 한 줄로 정리된다.

🔧 **여기를 시험하려고 mock 에 예외 주입을 새로 넣었다.** 전에는 실패 **코드**만 주입할 수
있었는데, 코드는 함수가 스스로 돌려준 것이라 **이미 정상 경로**다. "터지는 길" 은 한 번도
지나간 적이 없었다 → `fail_on: ["soap:BOOM"]` 형식 추가.

---

## 4. ④ Ctrl+C 로 끄고 다시 띄우기 — ✅

```
공정 도중 SIGINT  →  종료 코드 0 · Traceback 0
다시 띄움         →  start success=True  →  plan 완료 — 그릇 2 · 컵 2 · 격리 0
records.csv 4행 (새로)
```

🔑 **지난 실행의 깃발이 넘어오지 않는다** — 다시 띄우면 처음부터 정상이다.

---

## 5. 🔧 시험 방법에서 찾은 함정 2건 (결과가 아니라 **방법**의 문제)

### ① `flow_node` 가 두 개 떠 있었다 → 응답이 섞였다

첫 시도에서 `/flow/state` 가 `step: IDLE · done_bowl: 4` 를 돌려줬다. 계획이 그릇 2개인데
**4** 가 나올 수 없다 → 앞 시도에서 안 죽은 노드가 하나 더 떠 있었다.

```
ros2 node list  →  /flow_node · /flow_node
```

🚨 결정기록 S1(격리 규칙)이 **다른 PC** 를 두고 경고하는 것과 같은 일이 **내 PC 안에서도** 난다.
→ 띄우기 전에 `ps` 로 확인하고 죽인다. 시험 스크립트에도 넣었다.

### ② "Ctrl+C 가 안 먹는다" 는 **틀린 결론**이었다

bash 에서 `명령 &` 로 띄우면 **대화형이 아닌 셸은 그 프로세스의 SIGINT 를 무시로 걸어 준다**
(POSIX). 그래서 신호를 보내도 아무 일이 없었고, 처음에 "Ctrl+C 로 안 꺼진다 ← 문제" 로 적었다.

파이썬에서 `start_new_session=True` 로 띄워 다시 보니 **종료 코드 0 으로 정상 종료**했다.
→ 코드는 멀쩡했다. **시험 방법이 틀렸다.**

🔔 남겨 두는 이유: 나중에 누가 같은 방법으로 "Ctrl+C 가 안 된다" 고 볼 수 있다.

---

## 6. 이 시험이 확인하지 **못한** 것

| | |
|---|---|
| 로봇이 **실제로 움직이는 중** 의 정지 | mock 은 즉시 돌아온다 — 이동 도중 `move_pause` 는 9/22 실기 |
| HMI 화면과 이어 보기 | 화면 PC 와 같이 띄우는 INT-4 (9/22) |
| 힘이 걸린 채 멈추는 동작 | F3 닦기 도중 정지 — 9/22 실기 확인 대상(IRD §6) |
| `/flow/abort` 의 **실기** 정리 순서 | ISOLATE 좌표로 실제로 가는 것은 실기에서 |

---

## 부록 — 재현

```bash
cd $PREWASH_WS && cbc
# 1) 시험용 설정 폴더를 만든다 (config 를 복사해 flow.step_delay_s 만 0.5 로)
# 2) 전부 가짜로 띄운다
PREWASH_USE_MOCK=f1,f2,f3 PREWASH_CONFIG_DIR=<폴더> ros2 run f2_sense_flow flow_node
# 3) 다른 터미널에서 서비스를 부른다 (위 §0)
```

🚨 띄우기 전에 **이미 떠 있는 `flow_node` 가 없는지** 확인한다 — 둘이면 응답이 섞인다.
```bash
ros2 node list | grep flow_node
```
