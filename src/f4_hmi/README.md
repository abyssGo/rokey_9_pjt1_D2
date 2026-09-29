# f4_hmi — 시스템 모니터(웹 HMI)

설계: SDD §6(휴먼 인터페이스) · 인터페이스: IRD §6

| 프로그램 | 역할 | 실행 |
|---|---|---|
| `hmi_bridge` | ROS 방송(`/flow/state` 등)을 듣고 브라우저에 전달하고(REST · WebSocket), 버튼을 flow 의 서비스로 전하는 서버 | `ros2 run f4_hmi hmi_bridge` → http://localhost:8000 |
| `fake_state_pub` | **가짜 flow** — 대본대로 실제 flow 와 같은 토픽을 방송하고 버튼(`/flow/start·stop·resume·abort`)에 반응(로봇·브링업 불필요) | `ros2 run f4_hmi fake_state_pub [대본] [--speed N] [--once] [--wait-start]` |

대본(`scenarios/*.yaml`): `normal` 정상 · `isolate` 격리 · `error` 로봇 오류로 멈춤 · `paused` 일시정지→재개 · `empty_zone` 빈 구역
· `tool_lost` 툴 놓침 → 멈춤 → 다시 집고 이어감(E37) · `leftover_remain` 잔반 남음 → 용기 든 채 멈춤 → 덜어내고 재개(E42) · `cable` 케이블 이상 → 멈춤 → 넛지 재개 → 무게부터 다시(E64) · `tool_fail` 툴 집기 실패 → 멈춤(홀더 확인 → 넛지 → 다시 집기 · E52)
  — 네 대본은 `fail.action: pause_retry`(멈춘 뒤 **그 단계부터 다시** 이어 완료 · 실제 flow 의 RETRY_STEP — 툴 놓침은 실제로는 툴 집기부터(E62) · `leftover_remain` 은 정책 pause 일 때의 화면 — 지금 설정은 격리). 멈춤은 `hold_s` 뒤 저절로 풀리고, 화면의 **재개** 를 누르면 바로 풀린다. 예외 멈춤 화면을 로봇 없이 연습할 때 쓴다.
🚨 `fake_state_pub` 와 실제 `flow_node` 를 **동시에 띄우지 않는다**(같은 토픽에 두 곳이 방송한다).

## 한 번만: 웹 서버 부품 설치 (HMI 를 돌리는 PC 에서만)
```bash
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
```
상자(venv)를 열지 않아도 된다 — `hmi_bridge` 가 `params.yaml` 의 `hmi.venv_dir` 에서 부품을 찾아 붙인다. HMI 를 돌리지 않는 PC 는 설치할 필요 없다(빌드·시험은 그대로 통과).

## 화면이 보여 주는 것 (UT-F4 TC-11)
| 구역 | 내용 | 값의 출처 |
|---|---|---|
| 맨 위 | 연결 점(`flow 연결됨` / `flow 연결 끊김 — 마지막 값` / `HMI 서버에 닿지 않는다`) · **일시 정지**(항상 표시 · 운전 중에만 활성) | `/api/state`.connected · step |
| 알람 상자 | 멈춤(PAUSED)이면 **원인별 제목·할 일**(2~3줄 · 운영자 정지·잔반 남음·집기 실패·팔레트 가득은 flow 문구도 함께 · `derive.pauseKind` → `GUIDE_KO`): 운영자 정지 · 케이블 이상(코드 ROBOT_ERROR 에 '케이블' 문구) · 툴 놓침(TOOL_LOST) · 툴 집기 실패(TOOL_FAIL) · 잔반 남음(LEFTOVER_REMAIN) · 집기 실패(GRIP_FAIL) · 팔레트 가득(RACK_FULL) · 잔반통 교체 · **로봇 오류 = 일반 멈춤 카드(주황) '멈춤 — 로봇 확인'**(사람이 복구 · 중단 버튼 없음 · 신호 1 → 그리퍼 열림 → 받아 치움 → 재개 버튼 · E54 · E55). 운전 중에 마지막 코드가 정상이 아니면 노란 '최근 원인' | last_code · message |
| 버튼 | 시작(IDLE 만) · 재개(PAUSED 만) · 중단(PAUSED · 로봇 오류 멈춤 제외 — 케이블 이상은 가능) · 끊기면 전부 비활성 · 누르면 flow 의 대답 문구와 지연(ms) | `/api/start|stop|resume|abort` |
| 단계 표시줄 | 8단계 그림 카드 + 격리 · 지금 = 파랑 · 멈춤(로봇 오류 포함) = 주황(멈춘 단계를 기억해 가리킴) | step · 탭 저장소 |
| 지금 하는 일 | 큰 그림 · 한 줄 설명 · 이번 용기 경과 · 몇 번째 · 다음 할 일 · 상태 알약(`진행 중`·`일시 정지`·`멈춤 — 툴 놓침` …) | step · kind · 수량 |
| 무게 측정 | '지금 하는 일' 카드 안 — 무게를 재는 동안 표본을 읽는 대로 한 칸씩(방금 읽은 칸 강조) · 다 재면 **중앙값** 과 잔반 판정(`잔반 있음/없음 (기준 50 g)`) · 다 잰 뒤 10 s 동안 보이고 사라진다 · 0 g 아래(센서 오차)는 0 으로(이력의 무게와 같은 규칙) | `/flow/weigh` · `plan.leftover_threshold_g` |
| 이번 팔레트 | 4칸 입체 그림(넣는 순서 ① 그릇 1 → ④ 컵 2) · 가득 차면 교체 안내 · 아래에 **지금까지 처리 — 전체**(팔레트 · 그릇 · 컵 · 격리 · DB 전체 기록) | done_* · `flow.rack_order` · `/api/kpi?period=all` |
| 진행 · 사이클 · 소모품 | 그릇/컵 수량 막대 · 반납 구역 남은 수·상태(`비었음` 포함) · 격리 수 · 용기 1개 시간 · 수세미/세제 교체까지 | state · `/flow/event` · `flow.consumables` |
| 이력 | **버튼을 누르면 창으로** — [전체 / 문제만 / 멈춤 기록] · 끝난 용기마다 한 줄(완료 · 격리 · 오류 · 건너뜀 · 집기 다시 시도는 주황) · 원인(운영자 중단 · 잔반이 남음 · 빈 구역 · 툴 놓침 …) · **멈춤 기록** = 멈춘 적마다 시각·단계·원인·코드·풀림(재개 버튼/넛지/중단/재시작)·걸린 시간(DB pauses) | `/flow/event` · `/api/db/pauses` |
| 누적 KPI | **버튼을 누르면 창으로** — 처리량·처리율·용기당 평균·시간당·멈춤·잔반 6칸(이번 실행/오늘/전체) · 칸에 마우스를 올리면 아래 한 줄에 뜻 · 숫자는 바뀔 때 움직인다(소모품 남은 횟수·잔반통 무게도) | `/api/kpi` |
| 소리·알림 | 한 가지 음으로 두 경우만 — **로봇이 멈추면 1번(PAUSED 진입) · 다시 움직이면 2번**(PAUSED → 운전). 빈 구역(건너뜀)은 위쪽 주황 알림 6 s 만(로봇이 멈추지 않으니 소리 없음) · 브라우저는 페이지에서 한 번 클릭한 뒤부터 소리를 낸다 | message · step |

## 무게 실시간 표시 — 값이 오는 길
```
cc.weigh() 가 표본 1개를 읽는다 → flow_node 가 /flow/weigh 발행 → hmi_bridge(구독) → WebSocket type=weigh → 화면 무게 측정 칸
```
| 자리 | 모양 |
|---|---|
| 토픽 `/flow/weigh` (`cobot_msgs/WeighLive`) | `kind` · `target_n`(잴 횟수) · `samples_g[]`(지금까지 읽은 값 **전부** · 잰 순서 · 빈 용기 기준값을 뺀 g) · `done` · `median_g`(done 일 때만) · `stamp`. 표본마다 1건 + 다 재면 1건 |
| WebSocket `/ws/state` | `{"type": "weigh", "weigh": {kind, target_n, samples_g, done, median_g, stamp}}` — 값은 0.1 g 으로 반올림 · `median_g` 는 다 재기 전에는 `null` |
| `GET /api/state` · WS `type=state` | `weigh`: 위와 같은 모양 + `age_s`(마지막 값 뒤 지난 초). 30 s 넘게 새 값이 없으면 `null` · `plan.leftover_threshold_g`: 잔반 판정 기준(g) |

- 메시지마다 지금까지 읽은 값이 전부 들어 있다 → 중간에 하나를 놓치거나 화면을 도중에 열어도 칸이 맞는다.
- 표본 수·간격은 `params.yaml f2.weigh_samples` · `f2.weigh_sample_gap_s`. 화면은 `target_n` 만큼 칸을 그린다(설정을 바꿔도 화면은 그대로 따라간다).
- 가짜 flow(`fake_state_pub`)도 무게 단계에서 같은 토픽을 낸다 — 로봇 없이 이 칸을 볼 수 있다(`scenarios/_defaults.yaml` 의 `weigh`).

## 화면(`web/` — Next.js 정적 내보내기)
```bash
cd src/f4_hmi/web
npm run build      # → out/ 을 hmi_bridge 가 / 에서 보여 준다(out/ 이 없으면 / = 시험 페이지)
npm run illust     # 그림을 고쳤을 때만 — illust/*.py → public/illust/*.svg · app/lib/palletArt.js
```
그림(단계 18장 · 팔레트 조각 · 아이콘 9개)은 **코드로 그린 등각 일러스트**다(아이콘 brush · cable · robot 3개는 SVG 파일을 직접 넣었다 — `npm run illust` 대상 아님). 만들어진 파일은 손으로 고치지 않고 `illust/*.py` 를 고친 뒤 `npm run illust` 로 다시 만든다.

## 진행
- [x] F4-01 가짜 flow + 서버 뼈대 + 시험 페이지(`GET /api/state`)
- [x] F4-02 버튼(start·stop·resume·abort) · WebSocket `/ws/state` · 가짜 flow 의 버튼 응답(`--wait-start`)
- [x] F4-03 화면(Next.js 15) · 멈춤 원인별 안내 · 예외 대본 4종 · 재개 소리 · derive 시험(UT-F4 TC-11)
- [x] F4-04 기록(SQLite 표 5개) · F4-05 누적 KPI · 잔반통 한도(E57)

## 시험
```bash
python3 -m pytest -q src/f4_hmi                 # 웹 부품이 없으면 app 시험 1건은 건너뛴다
~/venvs/hmi/bin/python -m pytest -q src/f4_hmi  # 전부 실행
cd src/f4_hmi/web && node --test test/          # 화면 계산(derive.js — 버튼 규칙 · 멈춤 원인 · 알람 · 이력 원인 · 팔레트 칸 · 무게 측정 칸) · Node 18 내장, 설치 없음
```

## 로봇 없이 화면 확인하는 법
```bash
soc && ros2 run f4_hmi hmi_bridge                                                    # 터미널 1 → http://localhost:8000
soc && ros2 run f4_hmi fake_state_pub tool_lost --speed 0.5                          # 터미널 2 — 대본 이름을 바꿔 가며(멈춤을 천천히 보려면 --speed 0.4)
# 🚨 화면(web/app)을 고쳤으면 `cd src/f4_hmi/web && npm run build` 뒤 **브라우저를 새로고침(Ctrl+Shift+R)** — 열려 있던 탭은 옛 JS 를 계속 돈다. 브리지는 HTML 에 no-store 를 붙인다(app.py)
soc && ros2 bag play <bag 폴더> --topics /flow/state /flow/event --loop --rate 3   # 녹화해 둔 실행 재생(버튼은 안 됨 · bag 은 저장소에 없다)
```
🚨 가짜 flow 와 bag 재생, 실제 flow_node 는 **한 번에 하나만**(같은 토픽). UT-F4 TC-11 결과: `docs/test_logs/` 의 UT-F4 TC-11 HMI 시험 기록.

## 기록(SQLite · F4-04) · 누적 KPI(F4-05) · 잔반통 한도(E57)
- 파일 하나: `params.yaml hmi.db_path`(기본 `prewash.db` = 워크스페이스 루트 `<ws>/prewash.db` · 어느 폴더에서 켜도 같은 파일 · `hmi_db` 도 같음). 로봇 프로그램은 손대지 않는다 — 브리지가 듣는 값을 적는다(`db.py` · `recorder.py`).
- 표 5개: `events`(용기 1개 = 1줄 · 시각·실행 번호·종류·구역·칸·결과·코드·시도·무게 전/후·소요·버린 잔반 g) · `runs`(시작 1번 = 1줄) · `pauses`(멈춤 1번 = 1줄 · 단계·원인·어떻게 풀렸나) · `commands`(버튼 1번 = 1줄) · `replacements`(교체 1번 = 1줄 · 수세미/솔/세제/잔반통).
- 소모품 사용량 = **마지막 교체 뒤의 events** — 수세미 = 그릇 완료 수 · 솔 = 컵 완료 수 · 세제 = 완료 용기 수 · 잔반통 = 버린 잔반 g 합(잔반 판정이 난 그릇의 무게 전 − 후). 화면 소모품 칸의 **교체 완료** 버튼 → `POST /api/replace/{item}` → 0 부터.
- 잔반통 한도 `hmi.waste_bin_limit_g`(50 kg): 누적이 닿으면 브리지가 `/flow/stop`(일시 정지 · 다음 용기 집기 전)을 보내고 화면에 "잔반통 교체" 카드 → 교체 완료 → 재개.
- 화면 "누적" 칸(이번 실행 / 오늘 / 전체): 처리량(그릇·컵·**팔레트 장수**) · 처리율 · 용기당 평균 · 시간당 · 멈춤(횟수·시간·잦은 원인) · 잔반 비율·버린 양. `GET /api/kpi?period=run|today|all`. 팔레트 = 칸(`flow.rack_order` 합 = 4)을 다 채우고 끝난 실행 수(`kpi.pallets`).
- 터미널에서 보기: `ros2 run f4_hmi hmi_db tables` · `hmi_db dump events --limit 20` · `hmi_db dump pauses` · `hmi_db usage` · `hmi_db kpi --period today` · `hmi_db replace waste_bin`. (`--db 파일` 로 다른 파일)
- 웹 주소: `/api/usage` · `/api/kpi` · `/api/db/{표}?limit=` · `/api/history?limit=`. 브리지를 기록 없이 띄운 시험 서버는 503.
- 시험: `pytest src/f4_hmi/test/test_f4_db.py`(DB·기록자 · ROS 없이) · API 시험은 웹 부품 상자로 `~/venvs/hmi/bin/python -m pytest src/f4_hmi` · `node --test web/test/`.

