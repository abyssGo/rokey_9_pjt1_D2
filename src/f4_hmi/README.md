# f4_hmi — 시스템 모니터(웹 HMI) · 담당 황인재

설계: `docs/ref/20260920_F4-00_HMI_설계초안.md` · 인터페이스: IRD §6

| 프로그램 | 역할 | 실행 |
|---|---|---|
| `hmi_bridge` | ROS 방송(`/flow/state` 등)을 듣고 브라우저에 전달하고(REST · WebSocket), 버튼을 flow 의 서비스로 전하는 서버 | `ros2 run f4_hmi hmi_bridge` → http://localhost:8000 |
| `fake_state_pub` | **가짜 flow** — 대본대로 실제 flow 와 같은 토픽을 방송하고 버튼(`/flow/start·stop·resume·abort`)에 반응(로봇·브링업 불필요) | `ros2 run f4_hmi fake_state_pub [대본] [--speed N] [--once] [--wait-start]` |

대본(`scenarios/*.yaml`): `normal` 정상 · `isolate` 격리 · `error` 로봇 오류로 멈춤 · `paused` 일시정지→재개 · `empty_zone` 빈 구역
· 🆕 9/25 `tool_lost` 툴 놓침 → 멈춤 → 다시 집고 이어감(E37) · `leftover_remain` 잔반 남음 → 용기 든 채 멈춤 → 덜어내고 재개(E42) · `cable` 케이블 이상 → 멈춤 → 톡톡 재개(#93) · 🆕 9/26 `tool_fail` 툴 집기 실패 → 멈춤(홀더 확인 → 톡 → 다시 집기 · E52)
  — 세 대본은 `fail.action: pause_retry`(멈춘 뒤 **그 단계부터 다시** 이어 완료 · 실제 flow 의 RETRY_STEP). 멈춤은 `hold_s` 뒤 저절로 풀리고, 화면의 **재개** 를 누르면 바로 풀린다. 9/29 예외 실기 ①③④⑤ 의 화면 연습용.
🚨 `fake_state_pub` 와 실제 `flow_node` 를 **동시에 띄우지 않는다**(같은 토픽에 두 곳이 방송한다).

## 한 번만: 웹 서버 부품 설치 (HMI 를 돌리는 PC 에서만)
```bash
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
```
상자(venv)를 열지 않아도 된다 — `hmi_bridge` 가 `params.yaml` 의 `hmi.venv_dir` 에서 부품을 찾아 붙인다. 다른 팀원 PC 는 설치할 필요 없다(빌드·시험은 그대로 통과).

## 화면이 보여 주는 것 (F4-03 · 9/25 완성 범위 = 시연 INT-4 · UT-F4 TC-11)
| 구역 | 내용 | 값의 출처 |
|---|---|---|
| 맨 위 | 연결 점(`flow 연결됨` / `flow 연결 끊김 — 마지막 값` / `HMI 서버에 닿지 않는다`) · **일시 정지**(항상 표시 · 운전 중에만 활성) | `/api/state`.connected · step |
| 알람 상자 | 멈춤(PAUSED)이면 **원인별 제목·설명·할 일**(`derive.pauseKind` → `GUIDE_KO`): 운영자 정지 · 케이블 이상(코드 ROBOT_ERROR 에 '케이블' 문구) · 툴 놓침(TOOL_LOST) · 잔반 남음(LEFTOVER_REMAIN) · 집기 실패(GRIP_FAIL) · 팔레트 가득(RACK_FULL) · **로봇 오류(붉은색 · 사람이 복구)**. 운전 중에 마지막 코드가 정상이 아니면 노란 '최근 원인' | last_code · message |
| 버튼 | 시작(IDLE 만) · 재개(PAUSED 만) · 중단(PAUSED · 로봇 오류 멈춤 제외 — 케이블 이상은 가능) · 끊기면 전부 비활성 · 누르면 flow 의 대답 문구와 지연(ms) | `/api/start|stop|resume|abort` |
| 단계 표시줄 | 8단계 그림 카드 + 격리 · 지금 = 파랑 · 멈춤 = 주황(멈춘 단계를 기억해 가리킴) · 로봇 오류 = 붉음 | step · 탭 저장소 |
| 지금 하는 일 | 큰 그림 · 한 줄 설명 · 이번 용기 경과 · 몇 번째 · 다음 할 일 · 상태 알약(`진행 중`·`일시 정지`·`멈춤 — 툴 놓침` …) | step · kind · 수량 |
| 이번 팔레트 | 4칸 입체 그림(넣는 순서 ① 그릇 1 → ④ 컵 2) · 가득 차면 교체 안내 · 누적 | done_* · `flow.rack_order` |
| 진행 · 사이클 · 소모품 | 그릇/컵 수량 막대 · 반납 구역 남은 수·상태(`비었음` 포함) · 격리 수 · 용기 1개 시간 · 수세미/세제 교체까지 | state · `/flow/event` · `flow.consumables` |
| 이력 | 끝난 용기마다 한 줄(완료 · 격리 · 오류 · 건너뜀) · 원인(운영자 중단 · 잔반이 남음 · 빈 구역 · 툴 놓침 …) · 문제만 보기 | `/flow/event` |
| 소리 | 톡톡(넛지) 재개 요청이 감지되면 비프(#93 · flow 문구 '재개 요청 감지') · 🆕 멈춤이 풀리면(PAUSED → 운전) 짧은 두 음 | message · step |

## 화면(`web/` — Next.js 정적 내보내기)
```bash
cd src/f4_hmi/web
npm run build      # → out/ 을 hmi_bridge 가 / 에서 보여 준다(out/ 이 없으면 / = 시험 페이지)
npm run illust     # 그림을 고쳤을 때만 — illust/*.py → public/illust/*.svg · app/lib/palletArt.js
```
그림(단계 18장 · 팔레트 조각 · 아이콘 8개)은 **코드로 그린 등각 일러스트**다(9/21 Claude 디자인 시안 승인). 만들어진 파일은 손으로 고치지 않고 `illust/*.py` 를 고친 뒤 `npm run illust` 로 다시 만든다.

## 진행
- [x] F4-01 가짜 flow + 서버 뼈대 + 시험 페이지(`GET /api/state`)
- [x] F4-02 버튼(start·stop·resume·abort) · WebSocket `/ws/state` · 가짜 flow 의 버튼 응답(`--wait-start`)
- [x] F4-03 화면(Next.js 15 · 9/22) · 🆕 9/25 멈춤 원인별 안내 · 예외 대본 3종 · 재개 소리 · derive 시험(UT-F4 TC-11)
- [ ] F4-04 이력(SQLite) · F4-05 KPI — 시연 뒤

## 시험
```bash
python3 -m pytest -q src/f4_hmi                 # 웹 부품이 없으면 app 시험 1건은 건너뛴다
~/venvs/hmi/bin/python -m pytest -q src/f4_hmi  # 전부 실행
cd src/f4_hmi/web && node --test test/          # 🆕 화면 계산(derive.js — 버튼 규칙 · 멈춤 원인 · 알람 · 이력 원인 · 팔레트 칸) · Node 18 내장, 설치 없음
```

## 로봇 없이 화면 확인하는 법 (추석 · 9/25)
```bash
soc && ros2 run f4_hmi hmi_bridge                                                    # 터미널 1 → http://localhost:8000
soc && ros2 run f4_hmi fake_state_pub tool_lost --speed 0.5                          # 터미널 2 — 대본 이름을 바꿔 가며(멈춤을 천천히 보려면 --speed 0.4)
# 🚨 화면(web/app)을 고쳤으면 `cd src/f4_hmi/web && npm run build` 뒤 **브라우저를 새로고침(Ctrl+Shift+R)** — 열려 있던 탭은 옛 JS 를 계속 돈다(9/27). 브리지는 HTML 에 no-store 를 붙인다(app.py)
soc && ros2 bag play ~/rokey9_pjt1/_bags/0923_full_0.5 --topics /flow/state /flow/event --loop --rate 3   # 실제 9/23 실행 재생(버튼은 안 됨)
```
🚨 가짜 flow 와 bag 재생, 실제 flow_node 는 **한 번에 하나만**(같은 토픽). UT-F4 TC-11 결과: `docs/test_logs/20260925_UT-F4_TC-11_HMI_황인재.md`.
