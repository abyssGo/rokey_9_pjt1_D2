# -*- coding: utf-8 -*-
"""9/19 오후 — 재계획: ① 주말(9/19·9/20)은 교육장이 18시에 닫는다 → **주말 저녁 칸을 전부 비운다** ② 한석형은 9/19 에 티칭까지만
③ 분담 변경(PM 결정, DSN-03 에서 확인): 그리퍼 검증 V-01·V-05·V-23 + gripper.py = 민범진 · 이동 함수 motion.py(move_to·move_rel·관절 상대 이동)·
   cell.force 키 골격·F1 패키지 골격 = 황인재(F4 세션) · 한석형 = 티칭·cell.yaml 값·실기 검증·F1 기능 함수
④ 게이트: G1 9/20 오후 · L1 9/22 오후 · L2 9/23 오전 · L3 9/23 오후 · 동결 9/23 저녁(그대로)
구글 시트의 '현재' 내용에 변경만 얹는다(PM 이 시트에서 고친 상태·행 순서는 그대로). 다시 실행해도 같은 결과가 나온다.
실행: python3 tools/gen/patch_20260919_weekend.py ../_upload/출력.xlsx → tools/gen/sheet_push.sh ../_upload/출력.xlsx
이 파일이 9/19 오후 이후의 최신 패치다. patch_20260919_audit.py·rebalance.py 는 다시 실행하지 않는다(여기서 옮긴 칸이 되돌아간다)."""
import sys, os, re, tempfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import open_gantt_cols, gantt_col,  Book, Row, new_timeline_row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
VERSION = 'v24.7'
OUT = 'prewash_일정표_0919s.xlsx'
def S(*xs): return [tuple(x.split()) for x in xs]          # S('9/20 오전','9/20 오후')

# id: dict(task, owner, status, deliv, crit, note, slots) — 없는 키는 그대로 둔다
EDIT = {
 # --- 전원 구역
 'PM-01': dict(slots=S('9/18 저녁', '9/19 오후', '9/20 오후', '9/21 저녁', '9/22 저녁', '9/23 저녁'), note='주말은 교육장 마감(18시) 전에'),
 'PKG-01': dict(owner='H,M,P', note='V-20 의 재료 · ✅ F3(박진용) PR #4 · ✅ F2(민범진) PR #8 · F1 골격은 황인재 F4 세션이 대신 작성(패키지 주인은 한석형 그대로 — 9/19 PM 결정, 한석형은 티칭에 집중) · pytest 파일 이름은 test_f1_api.py'),
 'INF-02': dict(status='완료', task='cobot_common 2/4 · motion.py — 이동 함수(저수준) move_to · move_rel(dx,dy,dz,frame,*,vel_mm_s,acc_mm_s2) · move_joint_rel(관절 상대 이동, 털기용) · 속도 = cell.limits × run.vel_scale',
                owner='H', deliv='src/cobot_common/cobot_common/motion.py + cell.yaml 의 cell.force 키 골격(값 없음)·test_config 수정',
                crit='Virtual(격리)에서 move_to·move_rel·move_joint_rel 연속 3회 · 시험용 설정으로 pytest',
                note='✅ 9/19 PR #15 merge(예정보다 반나절 빠름) — Virtual rig 3바퀴 30건·pytest 23건 · 🚨 move_to 는 안전 높이 아래로 내려가지 않고 "남은 높이"를 돌려준다(하강은 부르는 쪽이 move_rel/contact_down) · 새 키 cell.motion 4개(100 % 기준 속도) — 값은 한석형, 비어 있으면 이동 함수가 KeyError · ✅ move_joint_rel 시간 지정 경로의 속도 상한 추가(PR #16) · 남은 것(안건): 사용자 좌표계·RACK_*·회전 포함 상대 이동 · 9/19 분담 변경: 한석형 → 황인재(F4 세션) · Virtual 만으로 완성(로봇 불필요) · 이슈 #7 ② move_rel 속도 선택 인자 · DSN-03 B11 관절 이동 함수 · 박진용 force.py 의 임시 stub _move_rel 을 대체 · 좌표는 cell.yaml(한석형)에서 읽기만',
                slots=S('9/19 오후')),
 'INF-02d': dict(status='진행 중', slots=S('9/19 오후', '9/20 오전'),   # 황인재가 시트에서 9/20 오후 → 오전으로 직접 옮김(9/20)
                note='R · ✅ 코드 merge(PR #17, 9/19 — 예정보다 하루 빠름, pytest 22건): 드라이버 소스 기준 구현(힘은 2.5 N 계단·처음에 0 N 으로 기준 맞춤, 폭은 관절각 → 환산, 완료는 effort 로) · 남은 것: ① 9/20 오전 V-05·V-23 실기 확인 ② setup_io 의 onrobot_rg_msgs import 가드(ws_dsr 없이 cc.init 이 죽는다) ③ 힘 기준 맞추기를 쥐지 않은 때(release)로 · 9/19 분담 변경: 한석형 → 민범진 · 박진용 제안서 참고'),
 'INF-02b': dict(slots=S('9/19 오후', '9/20 오전'), note='force.py 구현·시험은 브랜치에 있음 — V-03(9/20 오전) 전이라도 PR 을 올린다(값은 후속 PR) · F1-02(9/20 오후)가 contact_down 을 기다린다 · 이슈 #7: cell.force 키 골격은 황인재(INF-02), 값은 박진용이 그 절만 PR · move_rel 이 들어오면 임시 stub 삭제'),
 'INF-02c': dict(status='진행 중', slots=S('9/20 오전'), note='R · ✅ 코드 merge(PR #13, 9/19 — 중앙값·음수 실패값 거르기·reset 선택 동작, pytest 10건) → 남은 것은 9/20 오전 실기 확인(V-02 와 한 세션)과 빈 용기 기준값 측정(rig_f2.py empty) · f2.weigh(F2-01)가 이걸 불러 판정한다'),
 'DSN-03': dict(task='2차 회의 안건 — **회의 없이 PM 이 결정**(9/19): 반납 구역 = 고정 슬롯 · 그릇 = 옆면(벽) 세로 파지 · 그리퍼 폭 경로 · 이슈 #7 수락 · 9/19 선결정 확정. 나머지는 보류', status='진행 중', slots=S('9/19 오후'),
               crit='급한 안건 결정 + 팀 공지', note='시간 부족으로 회의를 열지 못함 → PM 결정 후 공지, 이의는 9/20 브리핑 · 결정 표 docs/meetings/20260919_결정기록_DSN-03.md · 확인 중: 실패 정책 마무리 순서(B7)·move_joint_rel(B11)·mock_f2(B12) · 보류: YAML 키·/cell 토픽·HMI 설계·정지 방식·rig 속도·C1~C5'),
 'DSN-04': dict(slots=S('9/20 오전')),
 'ARCH-01': dict(slots=S('9/20 오후')),
 'MID-01': dict(slots=S('9/20 오후', '9/21 오전'), note='구조 변경 근거 1장 포함(TS-01: 발견→재현→구조 5종 비교→결정) · 각자 자기 기능 1장을 9/20 오후까지 · 주말 저녁 없음'),
 'V-20': dict(note='재료: cobot_common(main) + flow_node(PR #8·#9) + f3_wipe(PR #4) + F1 골격(황인재 세션 대신 작성) · 격리 상태 Virtual · 안 되면 구조 ③(결정 기록 표)'),
 'INT-12a': dict(slots=S('9/22 저녁'), note='R · 9/22 저녁 첫 순서'),
 'INT-12b': dict(slots=S('9/22 저녁'), note='R · INT-12a 다음'),
 'INT-13': dict(slots=S('9/22 저녁', '9/23 오전'), note='R · INT-12b 다음 — 9/23 오전 첫 순서까지'),
 'INT-3a': dict(slots=S('9/23 오전'), note='R · L2(G3, 9/23 오전) 통과 뒤 바로'),
 'INT-3b': dict(slots=S('9/23 오전', '9/23 오후')),
 'FIX-01': dict(slots=S('9/23 오후')),
 'INT-4a': dict(slots=S('9/23 오후'), note='R · 🛡 범위 방어(SDD §9.9): L3 가 9/23 오후 첫 1시간 안에 안 끝나면 4개 연속 → 2개(그릇 1·컵 1)'),
 'INT-4b': dict(slots=S('9/23 저녁'), note='R · 🛡 범위 방어: 실패 주입 4종 → 2종(빈 구역·정지/재개)'),
 # --- F1 (한석형: 티칭·실기·기능 함수)
 'CELL-04': dict(prog='0.5', slots=S('9/19 오전', '9/19 오후', '9/20 오전'), note='R · 🚨 9/19 는 **그릇 쪽 좌표까지**, **컵 쪽 좌표는 9/20 오전에 끝낸다**(황인재 9/20) · ✅ 티칭 자세 = 그 기능이 동작을 시작하는 자세(황인재 확정 9/20 — 시험에서 맞지 않으면 좌표가 아니라 파라미터를 고친다) · V-19 를 이 세션 안에서 · 티칭 자세 = 그 기능의 시작 자세(WASTE·수조는 위에서, WEIGH 는 안전 높이 이상 권장 — SDD §5.3) · cell.motion 4개·limits 값도 같이 · 18시 교육장 마감'),
 'V-19': dict(slots=S('9/20 오전'), note='R · 좌표 작업(CELL-04)이 끝나야 할 수 있다 → 9/20 오전 좌표가 끝난 직후(황인재 9/20) · V-22 좌표 재현과 한 흐름으로'),
 'V-01': dict(owner='M', slots=S('9/20 오전'), crit='상태마다 10회 — 세 범위가 겹치지 않고, 그릇(≈ 2 mm) ↔ 빈손 간격이 흔들림(최대 − 최소)의 2배 이상', note='R · V-05·V-23 과 한 그리퍼 세션(9/20 오전 첫 순서) · 9/19 분담 변경: 한석형 → 민범진 · 🚨 9/19 PM 결정: **그릇은 옆면(벽)을 세로로 파지**(외경 114 mm > RG2 최대 폭 110 mm) — ✅ 9/19 검증: 파지 폭 ≈ 2 mm 이고 빈손과 구분된다(황인재) → **그릇도 폭으로 가른다(무게로 가르지 않음)** · 남은 것: 컵·빈손 포함 10회 기록, 허용 오차를 cell.yaml 에, 드라이버 경로(V-05)에서도 같은 값이 읽히는지 · 그릇 전용 허용 오차를 정하고, grip 의 닫는 목표 폭은 기대 폭보다 작게(같으면 빈손도 성공으로 읽힌다) · 미달이면 핑거 패드를 두껍게 · 결과가 gripper.py grip 과 F1-02 폭 판정값이 된다'),
 'V-05': dict(owner='M', slots=S('9/20 오전'), note='R · 절차는 박진용 제안서 docs/ref/20260919_제안_RG2_폭_힘_경로.md §5(30분): A 드라이버(관절각→폭 환산, 힘 2.5 N 계단) 먼저 → 안 되면 B Compute Box XML-RPC 를 읽기부터 · 9/19 분담 변경: 한석형 → 민범진'),
 'V-23': dict(owner='M', slots=S('9/20 오전'), note='R · V-05 와 한 세션 · grip_level 구현 방법을 정한다(gripper.py) · 9/19 분담 변경: 한석형 → 민범진'),
 'F1-01': dict(slots=S('9/20 오전', '9/20 오후'), note='R · 🚨 9/20 오전에 컵 쪽 티칭(CELL-04)이 더해져 오후로 넘어갈 수 있다 — 그릇 좌표만으로 먼저 짠다 · ✅ motion.py 는 9/19 에 main 에 들어왔다(#15) → 바로 착수 가능 · 먼저 cell.yaml 의 cell.motion 4개·limits 값을 채워야 cc.move_to 가 움직인다 · cc.move_to 는 상공까지만 가고 남은 높이를 돌려준다 · 티칭 2차 세션 뒤에'),
 'F1-02': dict(task='pick 고정 슬롯 파지 — 구역의 지정 슬롯을 순서대로: 슬롯 상공 → 힘 상한 감시 하강 → 파지 → 폭 판정 · 빈 슬롯이면 다음 슬롯 · 다 비면 EMPTY_ZONE (그릇은 옆면(벽) 세로 파지)', slots=S('9/20 오후'),
               crit='고정 슬롯(그릇 2·컵 2)에서 10회 ≥9 · 빈 슬롯은 다음 슬롯으로', note='R · 9/19 PM 결정: 구역 + 탐색 파지 → **고정 슬롯**(겹친·어긋난 용기 대응 제외) · pick 서명·EMPTY_ZONE·YAML 키는 그대로(offsets_mm = 슬롯 위치) · contact_down(박진용)을 부른다'),
 'V-14': dict(task='V-14 고정 슬롯 파지 성공률 — 그릇 슬롯 2·컵 슬롯 2, 빈 슬롯 포함 (이전: 겹친 용기 탐색 파지)', slots=S('9/20 오후'), crit='≥9/10, 낙하 0, 빈 슬롯은 다음 슬롯으로', note='R · F1-02 의 TC 로 한 흐름'),
 'V-15': dict(slots=S('9/21 저녁')), 'V-04': dict(slots=S('9/21 저녁')), 'F1-05': dict(slots=S('9/21 저녁')),
 'F1-03': dict(slots=S('9/22 오전')), 'V-08': dict(slots=S('9/22 오전')),
 'F1-04': dict(slots=S('9/22 오후')), 'V-06': dict(slots=S('9/22 오후')),
 'UT-F1': dict(slots=S('9/22 오후'), note='R · 함수별 TC 는 구현 직후 바로 수행, 이 칸은 남은 TC·녹화 마무리 · 🛡 F1 은 시연 필수 경로 — 밀리면 DSN-03 C5(F1 함수 초안을 다른 세션이 Virtual 에서 작성, 한석형은 실기 튜닝)'),
 'V-16': dict(slots=S('9/20 오후'), note='R · F2-01 shake 의 첫 단계로(V-07 과 한 세션) · gripper.py grip_level 이 있어야 한다 · 찾은 HOLD 값은 한석형이 cell.yaml 프리셋에 반영'),
 # --- F2·flow (민범진)
 'V-02': dict(slots=S('9/20 오전'), note='R · INF-02c weigh 이식과 한 세션 · 9/19 오후는 티칭이 로봇을 쓴다'),
 'FLOW-01': dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전'), note='✅ PR #8·#9 merge: 메인 뼈대·상태 머신·실패 정책·예외 보호 · 🔧 남은 것: 격리 마무리 동작(툴 반납 → ISOLATE 에 놓기 → HOME) — 순서는 DSN-03 B7, 로봇 교대 대기 시간에'),
 'V-07': dict(slots=S('9/20 오후')),
 'F2-01': dict(slots=S('9/20 오후', '9/21 저녁')),
 'F2-02': dict(slots=S('9/21 저녁')),
 'FLOW-02': dict(slots=S('9/22 오전')),
 'UT-F2': dict(slots=S('9/22 오전')),
 # --- F3 (박진용)
 'V-03': dict(slots=S('9/19 오후', '9/20 오전'), note='R · 닦기 설계를 결정 · 불가면 범위 방어 · 9/19 오후 착수(PM 시트 기준 진행 중) → 주말 저녁이 없어 남은 것은 9/20 오전 로봇 교대의 박진용 첫 순서'),
 'V-10': dict(slots=S('9/21 저녁')),
 'F3-03': dict(slots=S('9/21 저녁', '9/22 오전'), note='R · 시연 필수 경로 — 함수가 둘이라 2칸(9/21 저녁 V-10·뼈대, 9/22 오전 실기 마무리) · 🛡 밀리면 컵 닦기는 도전 과제, 그릇만 MVP(SDD §9.9)'),
 'UT-F3': dict(slots=S('9/22 오후')),
 # --- F4 (황인재)
 'F4-00': dict(slots=S('9/20 오전'), note='9/19 오후는 F1 골격·motion.py 가 먼저 · DSN-03 B5 는 9/20 브리핑에서 확인'),
 'F4-01': dict(slots=S('9/20 오후')),
 'F4-02': dict(slots=S('9/20 오후', '9/21 저녁')),
 'F4-03': dict(slots=S('9/22 오전', '9/22 오후'), note='DSN-03 결과 반영 · 이동 함수(INF-02)를 맡으면서 한 칸씩 뒤로'),
 'NOTE-02': dict(slots=S('9/22 오후'), note='F4-03 화면이 나온 뒤 gif — 강사 요구일(9/22) 안에'),
 'UT-F4': dict(slots=S('9/22 저녁')),
 'V-24': dict(status='보류', note='선택 과제 — 9/19 재계획에서 뺌(황인재가 motion.py 를 맡음). Virtual 에서는 모션 중 Ctrl+C 정지 확인됨(PR #3). 시간이 남으면 9/22 이후', slots=[]),
}
# 새 행: id, 뒤에 붙일 행, 서식 복제 행, 구분, 작업, 담당, 상태, 칸, 산출물, 기준, 비고
NEW = [
 ('V-26', 'V-25', 'V-25', '검증', 'V-26 Ctrl+C 정지 실기 확인 — 이동 **도중에** 터미널에서 Ctrl+C 를 누르면 로봇이 바로 서는가(move_stop · DR_QSTOP)',
  'H(P)', '시작 전', S('9/21 오후'), 'docs/test_logs/20260921_V-26_CtrlC정지_실기_황인재.md',
  '긴 이동(6 s 이상) 도중 Ctrl+C **3회 모두** 즉시 감속 정지 · 로그에 "정지 명령(move_stop) 완료" · 정지까지 움직인 거리(또는 각도) 기록 · 브링업이 살아 있어 다음 프로그램이 바로 뜬다 '
  '(실패하면: 정지 명령이 안 나갔는지 · move_stop 서비스가 안 보였는지 · 이동이 끝난 뒤에야 반응했는지를 구분해 적는다)',
  '황인재 9/21: 구현은 돼 있는데 **실기 기록이 없다** — cc.init() 이 ROS 기본 SIGINT 처리기를 끄고(rclpy 가 통신 통로부터 닫아 버려 정지 명령을 못 보내기 때문) 메인 스레드에 KeyboardInterrupt 를 일으키면, '
  'try/finally 의 cc.shutdown() 이 move_stop(stop_mode=1 · DR_QSTOP · Stop Category 2)을 보낸다(bootstrap.py). 이동 도중에도 먹는 이유는 PR #34 로 이동이 비동기(amovel + 폴링)가 됐기 때문. '
  'Virtual 은 rig_stop.py(V-24a) 5경우로 확인했고 실기만 남았다. 절차(30초): 긴 관절 이동 하나 걸고 2~3 s 뒤 Ctrl+C × 3회 · vel_scale 0.3. '
  '🚨 같이 볼 것 ① 한계: shutdown() 이 메인 스레드 밖에서 불리면 정지 명령을 안 보낸다(경고만) · move_stop 서비스가 안 보이면 못 세운다 → 그때는 E-Stop '
  '② **박진용 확인 대기**: stop_mode 가 DR_QSTOP(1)이 맞는지(선택지 DR_QSTOP_STO 0 · DR_QSTOP 1 · DR_SSTOP 2 · DR_HOLD 3) — SAFE-01 정지 항목과 같은 건. '
  '③ Ctrl+C 는 개발자용 수단이고 공식 정지 수단은 웹 일시 정지와 E-Stop 이다(SDD §9 위험표)'),
 ('FLOW-03', 'FLOW-02', 'FLOW-02', '개발', '정지·재개·중단 연결 — /flow/stop = 즉시 일시 정지(이동 도중 멈춤) · /flow/resume = 하던 동작을 이어서(실패로 멈춘 경우는 실패한 단계부터 다시) · /flow/abort 신설(툴 반납 → 용기를 격리 구역에 → HOME → 다음 용기, ROBOT_ERROR 에서는 거부) · 이벤트 DONE/ISOLATED/ERROR',
  'M', '시작 전', S('9/22 오전', '9/22 오후'), 'src/f2_sense_flow/f2_sense_flow/flow.py · flow_node.py + test_f2_policy.py',
  'mock 으로: 일시 정지 → 재개(이어서) · 실패 PAUSE → 재개(그 단계부터 다시) · abort → ISOLATED 기록·다음 용기 · ROBOT_ERROR 에서 abort 거부 · rig_v20.py probe 통과',
  '9/20 황인재 결정(IRD §6 · SDD §5.1): 사람이 확인하고 문제없으면 마저(resume), 문제라고 판단하면 접는다(abort) · motion.py 의 pause/resume 호출(V-24)이 main 에 들어온 뒤 연결 · FLOW-01 의 격리 마무리 동작(9/22 오후)과 같은 코드라 같이 한다 · 힘제어·접촉 구간은 그 동작을 마친 뒤 멈춤(9/20 오전에 만든 단계 사이 정지 그대로)'),
 ('V-25', 'F1-01', 'F1-01', '검증', 'V-25 F1-01 실기 확인 — f1.move_to · 일반 place 를 실기에서(가상 로봇에서는 진짜 그리퍼 release 를 못 돌린다)',
  'H(S)', '시작 전', S('9/21 저녁'), 'docs/test_logs/20260921_F1-01_실기_황인재.md',
  '3회 연속 OK · 용기가 홈 안에 놓임 · **놓은 뒤 올라올 때 용기를 끌지 않음** · MoveIncomplete 0회 · release 뒤 그리퍼 열림 (실패하면 접근점·place_clear_mm·presets 조정 후 재시도)',
  '황인재 9/20 21:30: "F1-01 은 가상으로만 확인했으니 일정에 실기 검증을 넣는다". R · 20~30분 · vel_scale 0.3 · 황인재가 직접 실행, 한석형 입회. 절차: ① HOME → WEIGH(BOWL) → WASTE(BOWL) → HOME 3회 ② 그릇을 쥐여 주고 place SPONGE_BED_B 3회(진짜 release) ③ 컵으로 SPONGE_BED_C 3회 ④ 좌표가 있으면 ISOLATE 각 1회. 🚨 9/21 저녁 **V-22·V-19 바로 뒤**(같은 좌표·같은 전제: limits·motion·presets + E7 코드) — 넘치면 9/22 오후 F1-03·V-08 앞. F1-03 은 V-08(실기 10회)이 곧 실기 검증이라 따로 두지 않는다'),
 ('CELL-02b', 'CELL-02', 'CELL-02', '기구', '툴·홀더 확정(수세미 툴·솔·홀더 2종 — 잡는 자리·놓는 방향) + 그릇 받침 유격 보강 — 9/21 에 확정(황인재 9/20)',
  'P(H,S)', '시작 전', S('9/21 저녁'), '확정된 툴·홀더 실물 + 사진 · 치수(세척부 높이·지름) 갱신',
  '툴을 홀더에서 10번 집고 놓아도 같은 자리 · 그릇을 손으로 5 N 밀어 안 밀림(CELL-02 의 완료 기준)',
  '9/20 한석형: 툴·홀더를 제작 중이라 툴 집기·SOAP·툴 반납 좌표를 못 찍는다 · 박진용 V-03 기록: 그릇이 스펀지 구멍 안에서 흔들린다(구멍이 그릇보다 크다) → CELL-02(9/19 완료 처리)의 완료 기준이 안 맞아 다시 연다. 🚨 9/21 저녁 **첫 순서** — 끝나면 바로 한석형이 홀더 좌표 티칭(CELL-04b) → F1-03(황인재)·F3-03(박진용)이 9/22 에 이 좌표로. 담당: 박진용(실물·파지 기준) · 황인재(제작 지원) · 한석형(홀더 위치가 집기 자세에 맞는지)'),
 ('INF-02d', 'INF-02', 'INF-02', '계약', 'cobot_common · gripper.py — 그리퍼 함수(저수준) grip · grip_level(NORMAL/HOLD) · release · grip_width(현재 폭 mm)',
  'M', '시작 전', S('9/20 오후'), 'src/cobot_common/cobot_common/gripper.py', '실기에서 명령 → 동작 → 폭(mm) 읽힘 · NORMAL↔HOLD 전환 · Virtual 에서는 가짜 그리퍼 노드로 호출 순서',
  'R · 9/19 분담 변경: 한석형(motion.py 안) → 민범진(새 파일) · V-05·V-23·V-01 결과가 곧 구현 · 박진용 제안서 참고, 박진용이 PR 리뷰 · F3 요청 grip_width() 포함 · 구독은 setup_io(node)'),
]
# 9/19 저녁 진척 취합(PM-01) — 근거: main 에 merge 된 PR #3~#18, 팀원 브랜치의 커밋 기록, 황인재 확인
PROGRESS = {
 'FLOW-02': dict(note_add='🆕 9/20 인터페이스 확정(황인재): flow_node 의 통신 노드가 **/cell/force**(Float32 10 Hz, 닦는 동안만)와 **/cell/gripping**(Bool, 바뀔 때 + 2 Hz)을 발행한다 — 9/22 오전까지(IRD §6). 파지 여부는 gripper.py 가 판정(공개 함수 gripping() 등), 힘 값은 박진용의 닦기 루프가 force.py 에 저장만'),
 'F3-02': dict(note_add='🆕 9/20: 닦기 루프에서 읽는 힘 값을 force.py 에 **저장만** 해 둔다(/cell/force 발행은 flow_node 통신 노드 — 기능 함수 안에서 발행기를 만들지 않는다) · 매 걸음 cc.force_check() 로 상한 감시'),
 'F4-03': dict(note_add='9/20 F4-00 결정: Next.js 15(Node 18) · [MOCK] 표시 없음 · 닦는 힘 그래프(/cell/force) · 파지 중/아님(/cell/gripping) · 팔레트 4칸(그릇 2·컵 2) · 버튼 이름은 **일시 정지**'),
 'V-02': dict(note_add='9/20 민범진: 측정 도구는 브랜치 beomjin/20260918-V-02-weigh-precision 의 tools/v02_weigh.py(아직 main 에 없음 — 브랜치를 지우지 않는다) → V-02 가 끝나면 결과와 함께 PR'),
 'CELL-03': dict(slots=S('9/20 오전'), note_add='9/20 오전에 한다(황인재 9/20) — 9/19 오전 칸에서 옮김'),
 'CELL-01': dict(task='반납 구역 2곳(그릇·컵)·식기세척기용 팔레트(그릇 2·컵 2 — 9/20 변경)·격리 구역 배치·핑거 패드', status='진행 중', slots=S('9/18 오후', '9/18 저녁', '9/19 오전', '9/19 오후', '9/20 오전'), note_add='좌표 측정(CELL-04)과 함께 진행 중(황인재 9/20) — 슬롯 자리 표시 포함'),
 'PKG-01': dict(status='완료', note_add='✅ 9/19 완료 — F1 골격 PR #12 · F2 PR #8 · F3 PR #4 전부 main'),
 'INF-02a': dict(note_add='후속 수정 merge: #10(콜백 예외로 통신 스레드가 끝나던 문제) · #18(robot=False 면 setup_io 훅 실패를 건너뛴다 — ws_dsr 없이도 init)'),
 'INF-02c': dict(prog='0.7'),
 'INF-02d': dict(prog='0.8', note_add='✅ 9/20 PR #26 merge: 힘 기준 맞추기를 빈손이 확실한 자리(release 뒤·grip 앞)로만, grip_level 은 기준이 없으면 거부 + 실기 시험대 rig_gripper.py(V-05·V-23·V-01 을 재고 판정, 팔은 안 움직임) → 남은 것은 실기 세션 결과 · 9/20 민범진: 힘 기준 맞추는 시점 수정은 **로봇 세션 전(오전)에** 한다(V-23 전) · 실측값 반영은 그리퍼 세션 뒤에 이어서'),
 'INF-02b': dict(prog='0.85', note_add='✅ 9/20 PR #24 merge: contact_down 을 시작 힘 대비 변화량으로(실기에서 공중 2 N 때문에 깊이 0.1 mm 에서 접촉 오판) · force_off 끝까지 시도 · force_check 추가 · PR #23 시험 파일 이름 · TS-05 문서 · 남은 것: safe_retreat 가 force_off 실패에도 후퇴하게 · 절대 힘 뒷받침 · periodic_search 힘 감시(V-04 전) · cell.force 값 PR · (이전) ✅ 9/19 17:40 PR #20 merge — force.py(순응·힘제어·접촉 하강·탐색·안전 후퇴·read_force·예외 2종) + pytest 23건 + Virtual rig · 남은 것: cell.force 값 PR(V-03 뒤)·force_off 끝까지 시도·force_on limit 감시 도우미·periodic_search 힘 감시(V-04 전) · (이전 메모) 9/19 17:16 기준(커밋 기록): 브랜치 jinyong/20260919-INF-02b-force-funcs 에 force.py·test_force.py·rig_force (15커밋), PR 은 아직 · motion.move_rel 이 main 에 들어왔으니(#15) 임시 stub 을 지우고 PR'),
 'V-03': dict(prog='0.6', note_add='9/19 오후 실기 4회차까지(커밋 기록 16:04~17:16): 힘제어 중 X·Y 이동 확인, 문지르기 방식 = 손목을 비틀며 나선으로 넓혀 벽을 찾고 벽 따라 2바퀴(8자 삭제) · 남은 것: 결과 문서(docs/test_logs)와 cell.force 값 PR'),
 'V-01': dict(prog='0.7', note_add='✅ 9/19 황인재 확인: 그릇(옆면 세로 파지 ≈ 2 mm)은 빈손과 폭으로 구분된다 · 컵은 벽이 아니라 **몸통을 통째로 파지**(폭 ≈ 컵 지름)라 빈손·그릇과 간격이 충분하다 → 3상태 구분은 사실상 확인됨 · 남은 것: 드라이버 경로(V-05)로 10회씩 기록 + 그릇 전용 허용 오차 값을 cell.yaml 에'),
 'V-05': dict(status='진행 중', prog='0.3', note_add='9/19: 드라이버 소스 분석으로 폭 읽는 경로를 구현(#17 — 관절각 → 폭 환산, 장치가 읽은 0.1 mm 폭과 같다) → 9/20 오전에 실기로 확인(닫힌 쪽 0~5 mm 반복 흔들림 포함), 확정은 그 뒤'),
 'V-20': dict(status='진행 중', prog='0.3', slots=S('9/19 오후', '9/20 오전'), note_add='9/19: cobot_common 실행 뼈대는 Virtual rig_motion 3바퀴·검사 30건으로 확인(#15) → 남은 것: flow_node + 세 모듈을 Virtual 에서 한 번에(로봇 불필요 — 로봇 교대 대기 시간에)'),
 'DSN-03': dict(prog='0.7'),
 'DSN-04': dict(status='진행 중', prog='0.7', slots=S('9/19 오후', '9/20 오전'), note_add='9/19 PM 결정분(고정 슬롯·그릇 옆면 파지·폭 판정·이슈 #7·motion/gripper 구현 방식)은 BR-SR·IRD·SDD·AGENTS·프롬프트·일정표에 반영 완료 · 남은 것: contracts.py pick docstring(황인재)·cell.yaml zones/presets 주석(한석형)·확인 대기 3건(B7 격리 마무리 순서·B11·B12)'),
}
for _tid, _e in PROGRESS.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 재계획 (황인재 지시: 좌표 작업 지연으로 쌓인 일 정리)
# 원칙: ① 한석형의 오늘 오전은 좌표 마무리(CELL-04·CELL-01·V-19)만 ② F1 사슬을 반 칸씩 뒤로 — 좌표 없이 되는 남의 일은 그대로
#       ③ 한석형 몫을 덜어 준다: V-22 → 황인재(motion.py 주인이 실기에서 확인) · V-20 → 황인재(bootstrap 주인, Virtual) · V-16 은 민범진 단독
#       ④ 동결(9/23 저녁)은 그대로 — 밀리면 SDD §9.9 범위 방어(컵 e2e·실패 주입 4종 → 2종·4개 연속 → 2개)
WHY = '9/20 재계획: 좌표 작업(CELL-04)이 9/20 오전까지 이어져'
REPLAN_0920 = {
 'CELL-04':  dict(owner='S', note_add='🚨 9/20 황인재: **팔레트 컵 칸 4 → 2**(RACK_C1·C2) — 좌표 PR 에서 cell.yaml 의 RACK_C3·C4 두 줄을 지운다. PM 이 그 PR 을 꼼꼼히 확인한 뒤 승인하고, 같은 때 contracts.py·params.yaml·시험 2개를 맞춘다 · 9/20 재계획: 9/19 민범진 참여, 9/20 오전 컵 쪽은 한석형 단독(민범진은 그리퍼 세션이 먼저)'),
 'CELL-04b': dict(slots=S('9/20 오후'), note_add=WHY + ' 오전 → 9/20 오후 첫 순서(박진용 참여 — F3-02 가 SPONGE_BED_B 를 기다린다)'),
 'V-22':     dict(owner='H(S)', slots=S('9/20 오후'), note_add=WHY + ' 한석형 → **황인재 주도**(motion.py 주인이 실기에서 YAML 좌표 재현을 확인한다, 한석형은 좌표 제공·입회) · 티칭 2차 뒤에'),
 'V-20':     dict(owner='H(M)', status='완료', slots=S('9/19 오후', '9/20 오전', '9/20 오후'),   # 9/20 오전 칸은 황인재가 시트에서 직접 추가(9/20)
             note_add='✅ 9/20 완료 — stop 위치 수정(PR #26) 뒤 rig_v20.py probe **4/4 통과**(민범진 재검증, 기록 docs/test_logs/20260920_V-20재검증_FLOW-01_민범진.md · 정지까지 5.8 s → 0.6 s) · (이전) 🟡 9/20 10:35 Virtual 실행(PR #22, 기록 docs/test_logs/20260920_V-20_황인재.md): **4개 중 3개 통과** — 세 모듈 실제 import·robot=True 로 용기 4개 × 함수 13회 ✅ · 모션 중 /flow/state 2.000 Hz ✅ · IDLE 에서 Ctrl+C 뒤 재실행 ✅ · 🔴 **stop 이 함수 사이가 아니라 용기 사이에서만 먹는다**(flow.py run_plan 에서만 stop 을 봄 — IRD §6·SDD §5.1 과 다름) → 민범진이 flow.py 수정 뒤 rig_v20.py probe 로 재검증(5분)하면 완료 · 9/20 재계획: 민범진 → 황인재 주도'),
 'V-16':     dict(owner='M', note_add='9/20 재계획: 한석형 참여 제외 — 찾은 HOLD 값만 한석형에게 전달(cell.yaml 프리셋)'),
 'F1-01':    dict(slots=S('9/20 오후'), note_add=WHY + ' 오전 → 9/20 오후(티칭 2차 뒤) · 그릇 좌표로 먼저'),
 'F1-02':    dict(slots=S('9/21 저녁'), note_add=WHY + ' 9/20 오후 → **9/21 저녁**(로봇 1시간 교대의 한석형 순서) · 코드는 9/20 오후~9/21 에 Virtual 로 미리'),
 'V-14':     dict(slots=S('9/21 저녁'), note_add=WHY + ' F1-02 와 함께 9/21 저녁'),
 'V-04':     dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전'),
 'V-15':     dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전'),
 'F1-05':    dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전(박진용 참여)'),
 'V-08':     dict(slots=S('9/22 오후'), note_add=WHY + ' 9/22 오전 → 오후'),
 'F1-03':    dict(slots=S('9/22 오후'), note_add=WHY + ' 9/22 오전 → 오후'),
 'V-06':     dict(slots=S('9/22 저녁'), note_add=WHY + ' 9/22 오후 → 저녁'),
 'F1-04':    dict(slots=S('9/22 저녁'), note_add=WHY + ' 9/22 오후 → 저녁'),
 'UT-F1':    dict(slots=S('9/22 저녁', '9/23 오전'), note_add=WHY + ' L1 의 F1 분은 9/22 저녁~9/23 오전 첫 순서(함수별 TC 는 구현 직후 바로)'),
 'INT-12b':  dict(slots=S('9/23 오전'), note_add=WHY + ' rack_place(F1-04)가 9/22 저녁이라 9/23 오전으로'),
 'INT-3a':   dict(slots=S('9/23 오후'), note_add='9/20 재계획: L2 가 9/23 오전까지라 그릇 e2e 는 9/23 오후'),
 'INT-3b':   dict(slots=S('9/23 오후', '9/23 저녁'), note_add='9/20 재계획: 🛡 범위 방어 1순위 — 밀리면 컵 e2e 는 1회로 줄이거나 도전 과제로'),
 'INT-4a':   dict(slots=S('9/23 저녁'), note_add='9/20 재계획: 9/23 오후 → 저녁 · 🛡 밀리면 4개 연속 → 2개'),
 'FIX-01':   dict(slots=S('9/23 오후', '9/23 저녁')),
 'F3-02':    dict(note_add='9/20 재계획: 셀 좌표(SPONGE_BED_B)는 9/20 오후 티칭 2차 뒤에 나온다 — 그 전에는 V-03 rig 좌표로 만든다'),
 'FLOW-01':  dict(prog='0.9', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/22 오후'), note_add='✅ 9/20 PR #26 merge: stop 을 단계 사이마다(멈출 때 그리퍼 명령 없음) — V-20 4/4 · 남은 것: 격리 마무리 동작(9/22 오후)·재시도/격리 도중의 stop 시험 1건 · 정지 방식 결정 요청 D1~D4(docs/meetings, 민범진 → 황인재) 대기 · ✅ 9/20 민범진 확인: (a) 문서대로 단계 사이마다 정지로 고친다 — 든 채 멈출 때 파지는 NORMAL 그대로·그리퍼 명령을 새로 보내지 않는다(SDD §5.1) · 🔴 9/20 V-20 에서 발견: **stop 을 process_one() 의 단계 사이에서도 봐야 한다**(지금은 용기 사이에서만 → 정지 버튼을 눌러도 용기 1개를 끝낸 뒤에야 멈춘다, IRD §6·SDD §5.1 과 다름) — 9/21 저녁 INT-4·V-13 전에 수정, rig_v20.py probe 로 재검증 · 9/20 재계획: 남은 것(격리 마무리 동작)은 로봇이 필요 없어 비어 있는 9/22 오후로 — 9/20 오전 민범진 7건을 덜어 준다(L2 9/22 저녁 전까지면 된다) · ✅ 9/20 황인재 확정: 격리 마무리 순서 = 툴 반납 → 용기를 ISOLATE 에 놓기 → HOME · ROBOT_ERROR = 그 자리 정지 + PAUSED + 사람이 복구(SDD §7)'),
 'DSN-03':   dict(status='완료', note_add='✅ 9/20 아침 황인재: B7(격리 순서·ROBOT_ERROR)·B11(move_joint_rel)·B12(mock_f2) 승인, 티칭 자세 규칙 확정 → 급한 안건 종료. 보류 안건은 필요할 때'),
 'DSN-04':   dict(status='완료', note_add='✅ 9/20 완료: 결정분을 BR-SR·IRD(§2·§10)·SDD(§3.1·§4.3·§5.2·§5.3·§7)·AGENTS·프롬프트·일정표에 반영, contracts.py pick 설명은 PR #21 · cell.yaml 의 zones/presets 주석은 한석형의 좌표 PR(CELL-04)에서'),
}
CH = '🚨 추석(9/24~28)은 교육장이 닫힌다 — 집에서 하는 원격 작업(황인재 9/20)'
CHUSEOK = {
 'DOC-02': dict(note_add=CH + ' · 기능별 1장은 각자, 취합은 황인재'),
 'DOC-03': dict(note_add=CH + ' · 영상 원본은 9/23 저녁에 드라이브에 올려 둔다(교육장 PC 에만 두지 않는다)'),
 'DOC-04': dict(note_add=CH),
 'DOC-05': dict(note_add=CH + ' · 측정 결과(records·KPI)·사진도 9/23 저녁에 저장소·드라이브에'),
 'REH-01': dict(note_add=CH + ' · 온라인(화상)으로'),
 'INT-4d': dict(note='R · 9/23 저녁 동결 · 🚨 추석에는 교육장에 못 들어간다 → 동결할 때 **영상 원본·측정 결과·사진·로그를 전부 드라이브·저장소에 올린다**(집에서 PPT·영상 편집에 쓴다) · ✅ 로봇·기구는 추석 동안 **세팅 그대로 둔다**(황인재 확인 9/20) — 재배치·재티칭 불필요'),
 'REH-02': dict(note='R · 9/29 · ✅ 로봇·기구는 추석 동안 세팅 그대로(황인재 확인 9/20) → 재배치·재티칭 없이, 브링업 뒤 **좌표 재현 빠른 확인(V-22 방식, 10분)**만 하고 바로 리허설'),
}
REPLAN_0920.update({k: {**REPLAN_0920.get(k, {}), **v} for k, v in CHUSEOK.items()})
for _tid, _e in REPLAN_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 14:50 최신화 (황인재 지시)
# "아직 끝나지 않은 일은 진행 중으로, 오늘 오후에도 이어서 하니 9/20 오후 칸에 표시" — 근거: main 의 PR #21~#29·문서, 팀원 브랜치 커밋, F4 세션 보고
AM, PM_ = '9/20 오전', '9/20 오후'
CONT = '9/20 오후에도 이어서 진행(황인재 9/20 14:50)'
LATEST_0920PM = {
 # 한석형 — 오늘 GitHub 기록 없음(cell.yaml PR 아직). 좌표 작업이 이어진다
 'CELL-04':  dict(status='진행 중', slots=S('9/19 오전', '9/19 오후', AM, PM_), note_add=CONT + ' · cell.yaml PR 은 아직 없다(limits·motion 값을 팀 전체가 기다린다)'),
 'CELL-01':  dict(status='진행 중', slots=S('9/18 오후', '9/18 저녁', '9/19 오전', '9/19 오후', AM, PM_), note_add=CONT),
 'V-19':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT + ' · 좌표가 끝난 직후에'),
 # 민범진 — 오전에 PR #26·#28·#29(코드)와 결정 요청 문서 2건. 그리퍼·무게 실기 세션 결과는 아직 올라오지 않았다
 'CELL-03':  dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'V-02':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'V-01':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT + ' · 시험대 rig_gripper.py 준비됨(#26·#29)'),
 'V-05':     dict(status='진행 중', prog='0.4', slots=S(AM, PM_), note_add=CONT + ' · 시험대 rig_gripper.py 준비됨(#26·#29) — 실기 결과 대기'),
 'V-23':     dict(status='진행 중', prog='0.3', slots=S(AM, PM_), note_add=CONT + ' · 🚨 시험대가 빈손으로도 통과하던 결함을 고침(#29 — 닫는 목표를 기대 폭보다 작게, 최초 파지 폭이 기대 범위 밖이면 중단)'),
 'INF-02c':  dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'INF-02d':  dict(status='진행 중', prog='0.85', slots=S('9/19 오후', AM, PM_), note_add='9/20 오후: PR #28(힘 기억을 명령마다 갱신·실패하면 버림) · #29(V-23 시험대) merge — 남은 것은 실기 세션 결과'),
 'FLOW-01':  dict(status='진행 중', prog='0.9', slots=S('9/19 오전', '9/19 오후', AM, PM_, '9/22 오후'), note_add='9/20 오후: PR #28 merge — 남은 resume 깃발이 다음 정지를 0초 만에 풀던 길 · 재시도 뒤 최신 실패 코드로 정책 재조회(ROBOT_ERROR 가 격리로 새던 길). 황인재 결정 대기 2건: 정지 방식(D1~D4) · PAUSE 로 멈춘 용기 처리(D1·D2) — docs/meetings/20260920_결정요청_*_민범진.md'),
 # 박진용 — PR #23·#24·TS-05. V-03 은 실기 7회차까지(브랜치의 기록), wipe_bowl 은 브랜치에서 작성 중
 'INF-02b':  dict(status='진행 중', slots=S('9/19 오후', AM, PM_), note_add=CONT),
 'V-03':     dict(status='진행 중', prog='0.8', slots=S('9/19 오후', AM, PM_), note_add='9/20: 실기 7회차까지(브랜치 jinyong/20260920-V-03-log 의 시험 기록 — 아직 PR 전) · rig 갱신 13:17 · ' + CONT),
 'V-18':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'F3-02':    dict(status='진행 중', prog='0.3', note_add='9/20: 브랜치 jinyong/20260920-F3-02-wipe-bowl 에서 작성 중(나선 → 벽 따라 2바퀴, 옆 힘 비상 정지) — 아직 PR 전'),
 # 황인재(F4 세션)
 'F4-00':    dict(status='완료', note_add='✅ 9/20 13:55 설계 확정 문서 merge(docs/ref/20260920_F4-00_HMI_설계초안.md): Next.js 15 + Node 18 · [MOCK] 표시 없음 · 힘 그래프 · 파지 중/아님 · 팔레트 4칸 — 정지 버튼 구성은 정지 방식 결정 뒤 갱신'),
 'V-24':     dict(status='진행 중', prog='0.3', slots=S(PM_), note_add='9/20 V-24a 가능성 시험(Virtual, F4 세션 — 브랜치 injae/20260920-V-24a-stop-feasibility, PR 은 황인재 확인 뒤): ✅ 동기 이동 중 move_stop 은 0.05 s 에 멈춘다(단 끊긴 movej 가 0(성공)을 돌려주고, 다음 명령을 보내면 다시 움직인다 → 정지 깃발·가드 필요) · ❌ 동기 이동 중 move_pause 는 안 먹는다 · ✅ 비동기(amovej + check_motion 폴링)에서는 pause → resume 으로 같은 동작이 이어진다 → "즉시 멈추고 재개"는 motion.py 를 비동기로 바꿔야 한다. 🚨 힘제어 중의 일시정지는 실기 확인 필요. **본작업 여부는 황인재 결정 대기**'),
}
for _tid, _e in LATEST_0920PM.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 15:30 황인재 결정: 즉시 일시 정지 → 재개로 이어서 · 중단(격리) · 웹 HMI 는 추석에도
CH_ = '9/24~28'
STOP_0920 = {
 'V-24':    dict(owner='H(M,P)', status='진행 중', prog='0.3',
                 task='V-24 즉시 일시 정지 — motion.py 를 비동기 이동(amovej/amovel) + check_motion 폴링으로 · bootstrap 에 pause/resume/stop 호출과 정지 깃발 · Virtual 시험 → 9/22 오전 실기 확인(이동 도중 멈춤 → 재개로 같은 동작을 이어서)',
                 slots=S('9/20 오후', '9/21 저녁', '9/22 오전'),
                 deliv='src/cobot_common/cobot_common/motion.py · bootstrap.py + test/rig_stop.py · docs/test_logs',
                 crit='Virtual: rig_motion 3바퀴 + rig_stop 통과(호출하는 쪽 코드 변경 없음) · 실기: 관절·직선·용기를 든 이동에서 멈춤 → 재개로 같은 동작 완료 3회',
                 note_add='✅ 9/20 황인재 결정: **선택 과제 → 한다**(목적: 문제가 생겼을 때 바로 멈췄다가, 사람이 보고 문제없으면 이어서). 범위: 자유 공간 이동만 즉시 멈춤 — 힘제어·접촉 구간(접촉 하강·닦기·안착 탐색)은 그 동작을 마친 뒤 멈춤(실기 확인 뒤 넓힐 수 있다). 되돌아갈 자리: 9/22 오전까지 실기 확인이 안 되면 지금의 단계 사이 정지로 시연(서비스 이름이 같아 HMI 는 그대로). 민범진의 연결은 FLOW-03'),
 'F4-01':   dict(slots=S('9/21 저녁'), note_add='9/20 재배치: V-24(이동 함수 비동기 전환)를 먼저 하느라 9/20 오후 → 9/21 저녁'),
 'F4-02':   dict(task='REST/WS 브리지·버튼 4종(시작 · 일시 정지 · 재개 · 중단) — 멈추면 "일시 정지됨 — 어느 단계" 를 크게 표시("E-STOP" 이라 쓰지 않는다)',
                 slots=S('9/21 저녁', '9/22 오전'), note_add='9/20 결정: /api/abort 추가(IRD §6) · 한계 문구 없음 · 9/20 재배치: 9/21 저녁~9/22 오전'),
 'V-13':    dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(F4-02 뒤)'),
 'INT-4':   dict(task='INT-4 flow(mock)+HMI — 시작·일시 정지·재개·중단', slots=S('9/22 오후'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오후 · 민범진의 FLOW-03 과 함께'),
 'F4-03':   dict(slots=S('9/22 오후', '9/22 저녁', CH_ + ' 오전'), note_add='🆕 9/20 황인재: **웹 HMI 는 추석에도 집에서 이어 간다**(로봇 불필요 — mock·fake_state_pub). 9/22 에는 시연·노션 gif 에 필요한 최소 화면(단계·버튼·연결 상태·힘 그래프 자리)까지, 다듬기는 추석에'),
 'NOTE-02': dict(slots=S('9/22 저녁'), note_add='9/20 재배치: 그날 저녁까지 나온 화면으로 gif(강사 9/22 요구) — 추석에 화면이 바뀌면 다시 올린다'),
 'F4-04':   dict(slots=S(CH_ + ' 오전', CH_ + ' 오후'), note_add='🆕 9/20 황인재: 추석에 집에서(mock 으로 /flow/event 를 받아 SQLite 기록·이력 API). 9/23 L3·L4 에는 없어도 된다(기록은 flow 의 records.csv 가 있다)'),
 'UT-F4':   dict(slots=S('9/23 오전', CH_ + ' 저녁'), note_add='9/20 재배치: 9/23 오전에 최소 범위(버튼 4종·상태·연결 끊김 표시) → 전체 TC-11 은 추석에 mock 으로'),
 'F4-05':   dict(slots=S('9/23 오전'), note_add='9/20 재배치: 9/23 오전만(INT-4c 측정 전에)'),
 'V-22':    dict(slots=S('9/20 오후', '9/21 저녁'), note_add='cell.yaml 의 limits·motion 값(한석형 PR)이 main 에 들어와야 한다 — 9/20 에 못 하면 9/21 저녁 첫 순서'),
 'INF-02b': dict(note_add='🆕 9/20 결정(V-24): force.py 의 접촉 하강·닦기·안착 탐색은 **즉시 멈춤을 보류하는 구간** — 그 동작을 마친 뒤 멈춘다. 표시 방법은 황인재의 motion/bootstrap API 가 나오면 맞춘다 · 9/22 오전 실기 확인에 참여(힘이 걸린 채 멈춤이 되는지는 그때 같이 본다)'),
 'FLOW-01': dict(note_add='🆕 9/20 황인재 결정 2건 → 구현은 FLOW-03(9/22): ① 일시 정지 = 즉시 멈춤 → 재개로 이어서 ② 실패로 멈춘 용기 = 사람이 확인해 마저(resume, 실패한 단계부터) 또는 접기(abort 신설 — 격리). 결정 요청 문서 2건에 답을 적었다'),
}
for _tid, _e in STOP_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 15:50 그리퍼 조작 방법(민범진 결정 요청 #32) — 검증한 뒤에 정한다
GRIP_0920 = {
 'V-23': dict(note_add='🆕 9/20 황인재: 그리퍼 조작 방법 D2(털기 뒤 HOLD 유지 vs NORMAL 복귀)는 **이 검증 결과로 정한다** — HOLD → NORMAL 로 낮출 때의 폭 변화·미끄러짐을 방향별로 기록(그릇·컵 각 10회)'),
 'V-16': dict(note_add='🆕 9/20 황인재: V-23 에서 낮출 때 미끄러지면 "HOLD 유지" 후보 → HOLD 힘으로 30 s 들고 있기 3회(용기 변형·자국 없음)를 같이 확인'),
 'V-05': dict(note_add='🆕 9/20 황인재: 그리퍼 조작 방법 D1(힘 기준을 0 N 쪽 vs 40 N 쪽)은 **검증한 뒤에 정한다** — 세션에서 ① 브링업 직후 힘이 40 N 인가 ② 빈손에서 양쪽 기준 맞추기 때 핑거가 움직이는가 ③ 그릇·컵을 쥔 채 40 N 까지 올렸을 때 폭 변화·변형(3회) ④ 빈손 폭(핑거팁 두께 × 2)·용기 높이(64/45 mm 제한)를 기록. 오늘은 지금 코드 그대로 진행'),
 'INF-02d': dict(note_add='🆕 9/20: 민범진 결정 요청 #32 — D1·D2 는 검증 뒤 결정, **버그 3건(파지할 때마다 10 s 타임아웃 · 무조건 success · 안전 스위치 감지)은 바로 수정**'),
}
for _tid, _e in GRIP_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:20 한석형 브랜치 확인(seokhyung/20260919-CELL-04-teaching)
SEOK_0920 = {
 'CELL-04': dict(prog='0.7', note_add='🔎 9/20 16:20 PM 확인 — 브랜치 seokhyung/20260919-CELL-04-teaching: **좌표 약 25개는 이미 티칭돼 있다**(그릇·컵 경로 전체: 집기 · 잔반통 앞 · 스펀지 홈 놓기(접근점+끝점) · 툴 집기/반납 · 닦는 자리 · 재파지 · 헹굼 앞 · 팔레트 그릇 2·컵 2). 다만 **cell.yaml 이 아니라 Virtual 단계 실행 스크립트(rig_f1.py v6) 안에 상수로** 들어 있어 팀이 쓸 수 없다. 늦어진 원인: ① cell.yaml 골격이 "기준점 + 오프셋·스테이션마다 자세 1개"인데, 실제 티칭은 "종류별(그릇은 위에서·컵은 옆에서) 절대 자세 + 접근점" 이라 맞지 않는다 ② 전체 경로를 Virtual 에서 한 번에 확인하는 스크립트를 6판까지 고쳤다(ChatGPT 웹이라 한 판이 오래 걸린다). 빠진 것: WEIGH · SOAP · ISOLATE · 구역의 두 번째 슬롯 · limits·motion·presets 값. 확인 필요: BOWL_RINSE_READY 의 z = −13.6 mm(로봇 받침면 아래)'),
}
for _tid, _e in SEOK_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:00 PR #34(V-24 본작업) merge
V24_0920 = {
 'V-24':    dict(prog='0.6', slots=S('9/20 오후', '9/21 저녁', '9/22 오전'),
                 note_add='✅ 9/20 17:00 PR #34 merge(예정보다 빠름): motion.py 비동기 + 폴링 · cc.pause/resume/halt/clear_halt · MotionHalted·MoveTimeout · 새 키 cell.motion.move_timeout_s — Virtual rig_pause 10/10 · rig_motion 30/30 · rig_v20 probe 12/12 · pytest 185건. 🚨 **실기 미검증 → 9/21 저녁 첫 순서로 실기 확인**(빈손·HOME 근처 짧은 이동의 도착 위치 → 일시 정지·재개 → 그다음 V-22·접촉 동작) · 9/22 오전: 힘이 걸린 채 일시 정지(박진용과) · 남은 것: 시간 초과 갈래도 멈춘 것을 기다리기 · rig_force Virtual 회귀'),
 'V-22':    dict(note_add='🚨 9/21 저녁: V-24 실기 확인(짧은 이동의 도착 위치·일시 정지) **다음에** 한다 — 이동 함수가 비동기로 바뀌었다(#34). V-22 가 "도착하기 전에 함수가 돌아오는가"를 같이 잡아낸다'),
 'FLOW-03': dict(note_add='✅ 9/20 #34 merge → 연결 가능: /flow/stop·/flow/resume 콜백에서 cc.pause()·cc.resume()(깃발만 — 콜백에서 불러도 된다), 상태 발행에 cc.is_paused() 반영 · /flow/abort 는 cc.halt() 로 하던 이동을 끊고 → 정리 동작 전에 cc.clear_halt() · 기능 함수는 MotionHalted·MoveTimeout 을 잡지 말고 위로'),
 'INF-02b': dict(note_add='🚨 9/20 #34: 이동 함수가 비동기로 바뀌어 contact_down 의 걸음(move_rel)이 그 위에서 돈다 — 9/21 저녁 실기 확인 뒤에 접촉 동작. contact_down 의 자체 시간 상한(timeout_s)이 일시 정지 시간을 포함한다 → cc.is_paused() 인 동안은 세지 않게. test_common_force.py 8줄(가짜 두산에 amovel·check_motion, 시험 설정 move_timeout_s)은 황인재(F4 세션)가 #34 에서 같이 고쳤다 — main 을 먼저 받을 것'),
 'CELL-04': dict(note_add='🆕 9/20 #34: cell.motion 에 **move_timeout_s**(이동 1번의 상한 시간) 키가 생겼다 — 비면 이동 함수가 KeyError. Virtual 시험 값 30 s'),
}
for _tid, _e in V24_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:30 PR #35(F2-01·F2-02) merge
F2_0920 = {
 'F2-01': dict(status='진행 중', prog='0.7', slots=S('9/20 오후', '9/21 저녁'),
               note_add='✅ 9/20 17:30 PR #35 merge — weigh(잔반 무게 = 측정값 − 빈 용기 기준값, 빈손이면 GRIP_FAIL)·leftover_loop·shake(WASTE) 구현 + 시험 44건(전체 229건). 값은 전부 임시 → 남은 것: **첫 실기 전에 rig_f2.py empty 로 빈 용기 기준값**, V-07·V-16 뒤 값 확정, 실기 단독 시험(9/21 저녁 — 황인재의 V-24 실기 확인 뒤에). 후속: _as_result 가 cc.MotionHalted 는 위로 올리게(FLOW-03 전)'),
 'F2-02': dict(status='진행 중', prog='0.6', slots=S('9/20 오후', '9/21 저녁'),
               note_add='✅ 9/20 17:30 PR #35 merge(예정 9/21 저녁보다 빠름) — dip(RINSE)·shake(RINSE), HOLD 적용·실패하면 쥔 채 먼저 올라온 뒤 힘 복귀·전후 폭으로 미끄러짐 판정. 남은 것: 실기(V-07: 빈 수조·vel_scale 0.3·작은 깊이부터)'),
 'FLOW-01': dict(note_add='🟡 9/20 #35: flow.policy 에 GRIP_FAIL: isolate 추가됨 — **황인재 결정 대기**(PM 권고 = pause: 용기를 놓친 경우 잔반통·수조에 남은 용기를 다음 용기가 찍을 수 있다). IRD §8·SDD §7 표 행 추가는 그 결정과 함께'),
}
for _tid, _e in F2_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:40 황인재 결정: 한석형의 좌표를 황인재가 작업 파일로 만들어 넘긴다
HANDOFF_0920 = {
 'CELL-04': dict(owner='S(H)', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁'),
                 note_add='✅ 9/20 17:40 황인재 결정: **한석형이 정리한 좌표를 황인재가 받아 작업 파일(cell.yaml 등)로 만들어 넘겨준다**(파일 주인은 그대로 한석형) — 양식을 데이터에 맞춘다(종류별 자세 · 접근점+끝점 · 슬롯별 절대 자세, move_to 에 kind). 한석형: 빠진 자세(WEIGH·SOAP·ISOLATE·구역 두 번째 슬롯)만 추가로 찍고 BOWL_RINSE_READY z(−13.6) 확인. 팔레트 컵 2칸 코드 변경(5곳)도 같은 PR. 재료 정리: _upload/0920_좌표이전_작업브리프.md'),
 'V-22':    dict(note_add='9/20 17:40: 옮긴 cell.yaml 값으로 확인한다(황인재가 만든 파일) — 9/21 저녁, V-24 실기 확인 다음'),
 'F1-01':   dict(slots=S('9/21 저녁'), note_add='9/20 17:40: 좌표가 cell.yaml 에 들어온 뒤(황인재 작업 PR) — 9/20 오후 → 9/21 저녁. 한석형의 Virtual 경로 스크립트(rig_f1.py v6)는 그대로 PR 하지 않고, cc.move_to 로 같은 경로를 도는 짧은 rig 로 바꾼다'),
}
for _tid, _e in HANDOFF_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:30 황인재 결정 E6: 그릇 닦기 = 고정 좌표 방식 (벽·바닥을 힘으로 찾지 않는다)
WIPE_0920 = {
 'V-03':  dict(prog='0.9', note_add='✅ 9/20 16:30 황인재 결정(E6): 검증 질문(힘제어 중 X·Y 이동)은 9/19 에 "가능"으로 답이 났다. 다만 수세미가 물러 닦는 도중에는 벽·힘을 잡을 수 없어(브랜치 커밋 56개 · 누르는 방식이 힘 → 깊이 → 띄우기 → 힘으로 한 바퀴) **닦기는 고정 좌표 방식으로 확정** — rig 다듬기는 여기서 끝. 남은 것: 시험 기록 PR(9/20 오후 회차 포함 · 판정 "가능") → 들어오면 완료'),
 'F3-02': dict(note_add='🆕 9/20 16:30 황인재 결정(E6): **고정 좌표 방식** — 시작 자세 Z 215.1 → 닦는 높이 Z 59.0(내려가는 거리 156.1 mm) · 벽 반지름 = (110 − 90) / 2 + 벽 누름 · 벽·바닥 찾기(contact_down)·목표 힘 유지(force_on) 없음 · 힘 감시는 남긴다(누르는 힘 10 N · 옆 힘 25 N → 후퇴, 힘 로그). 지금 브랜치(11:31 "나선으로 벽 찾기")는 이 방식으로 다시 맞춘다 · wipe.py 의 두산 API 직접 호출(199~211 줄)은 cobot_common 의 force.py 로 옮긴다 · 전제: 그릇이 받침에서 안 밀릴 것(SDD §5.4)'),
 'V-18':  dict(note_add='9/20 E6: 닦는 힘 기준이 "3~5 N"에서 "고정 높이로 누른 채"로 바뀜 — F3-02 첫 실기 3회 때 같이 본다(닦은 뒤 툴 자세 그대로인가)'),
}
for _tid, _e in WIPE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:41 PR #36 merge: 한석형 좌표 26개가 cell.yaml 에 들어왔다
PR36_0920 = {
 'CELL-04': dict(prog='0.7', note_add='✅ 9/20 16:41 PR #36 merge(황인재 F4 세션): 한석형 좌표 **26개가 cell.yaml 에 들어왔다**(값 그대로 · 기계 대조 일치 · Virtual 31번 이동 OK 51/FAIL 0 · 시험 243건). 양식 = 종류별(kind) · 용도별/슬롯(point) · 접근점+끝점, cc.move_to(station, carrying, kind, point). 🔴 **한석형에게 남은 것**: 새 자세 8개(WEIGH 그릇·컵 · SOAP 수세미·솔 · ISOLATE 그릇·컵 · 구역 슬롯 2 그릇·컵) + RACK_C2 접근점 재티칭(2.36 mm · 4.72°) + limits·motion 5개·presets 값 — 🚨 limits·motion 이 비어 있으면 실기에서 이동 함수가 KeyError 로 돌지 않는다 → **9/21 저녁 세션 전까지**'),
 'V-22':    dict(note_add='🚨 9/20 PR #36 검토에서 추가한 확인 항목: **posj 자세 5개**(RET_B·RET_C 슬롯 1 · TOOL_SPONGE/BRUSH pick · SPONGE_BED_C regrip)는 move_to 가 안전 높이와 무관하게 **그 자세까지 관절 이동**한다(물체 옆까지 바로) → HOME 출발 · 앞 스테이션 출발 두 경로를 vel_scale 0.3 으로 한 번씩. 위험하면 그 자세를 접근점+끝점(posx)으로 다시 읽는다. 그 밖에: 팔레트 그릇 칸은 접근점 없이 직접 들어감 · TOOL_SPONGE pick 의 J6 −220° · RINSE BOWL 하강 263 mm. 전제: 한석형이 limits·motion 을 채워야 시작할 수 있다'),
 'F1-01':   dict(note_add='9/20 #36: 좌표는 들어왔다 — cc.move_to(zone, False, point=슬롯) / (…, point=\'place\') 로 부른다. handling.py 설명글이 새 양식으로 바뀌었다(코드 변경 없음)'),
 'F2-01':   dict(note_add='9/20 #36: WEIGH·WASTE·RINSE 가 종류별 자리가 됐다 → sense.py 의 _goto 가 cc.move_to(station, carrying, kind) 로 kind 를 넘겨야 한다(지금은 진짜 cell.yaml 에서 ValueError). WEIGH 자세는 아직 🔴(한석형)'),
 'F3-02':   dict(note_add='9/20 #36: 닦기 시작 = cc.move_to(\'SPONGE_BED_B\', True, point=\'wash\') — 돌려주는 높이만큼 내려가면 wash 끝점(= 닦는 높이, E6 의 Z 59.0 · 지금 값 47.0 은 한석형 티칭 → 맞춰 본다). 세제 = cc.move_to(\'SOAP\', True, \'BOWL\') (아직 🔴)'),
}
for _tid, _e in PR36_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:00 황인재 결정 E7(이동에서 안전 높이 삭제) · E8(F1 약속에 kind)
E78_0920 = {
 'INF-02':  dict(note_add='🆕 9/20 17:00 결정 E7(한석형 요청 · 황인재 승인): **move_to 의 안전 높이 경유를 삭제** — 먼저 올라가기·안전 높이에서 멈추기를 없애고 티칭한 자세(접근점)로 직접 간다(팔레트 적재 자세가 안전 높이에서 안 나온다). 구현 = F4 세션 PR(motion.py · 시험 · rig_motion · rig_coords). safe_retreat 의 후퇴 높이(cell.limits.safe_z_mm)는 그대로'),
 'V-22':    dict(note_add='🆕 9/20 E7: 안전 높이 경유가 없어진다 → move_to 는 **앞 자리에서 다음 자리로 직접** 간다. 확인 방법을 바꾼다: 자세 하나씩이 아니라 **흐름 순서대로 구간마다**(슬롯 → WEIGH → WASTE → 스펀지 홈 → 툴 홀더 → SOAP → 닦는 자리 → 홀더 → 재파지 → RINSE → 팔레트 → HOME · 그릇 한 바퀴 + 컵 한 바퀴) vel_scale 0.3. 막히는 구간은 한석형이 접근점을 추가로 찍는다. 전제: F4 의 E7 PR 이 먼저 main 에'),
 'CELL-04': dict(note_add='9/20 E7: limits.safe_z_mm 은 이제 **접촉 동작 뒤 후퇴 높이**(safe_retreat)로만 쓴다 — 이동 경로와 무관. 닦는 자리·스펀지 홈에서 툴·용기가 그릇 밖으로 나오는 높이로 정한다(예: 닦는 자리 접근점 높이)'),
 'FLOW-01': dict(note_add='🆕 9/20 E8: F1 약속에 kind 선택 인자 — f1.move_to(station, carrying, kind=None) · f1.place(station, kind=None)(contracts·mock_f1·handling 골격은 PM 이 한 커밋으로 바꿈). 민범진: flow 의 (\'WEIGH\', \'f1\', \'move_to\', (\'WEIGH\', True)) 에 self.kind 추가 · sense.py _goto 에 kind · 시험의 가짜 cc/f1 서명'),
 'FLOW-03': dict(note_add='9/20 E7·E8: 격리로 옮길 때 f1.place(\'ISOLATE\', kind). 안전 높이 경유가 없어지므로 중단(abort) 정리 동작은 **임의 자세에서 출발**한다 → 첫 이동을 HOME(관절 이동)으로 두는 안을 PM 이 권고(황인재 확인 대기)'),
 'F1-01':   dict(note_add='9/20 E8: f1.move_to · f1.place 에 kind=None 추가됨(골격 서명은 이미 main) — 구현할 때 cc.move_to(station, carrying, kind) 로 그대로 넘긴다'),
}
for _tid, _e in E78_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:15 PR #39·#40 merge · #37 수정 요청 · V-03 기록 main · 한석형 회신
EVE_0920 = {
 'F4-01':   dict(status='완료', prog='1.0', note_add='✅ 9/20 17:10 PR #39 merge: 새 패키지 f4_hmi — 가짜 flow(fake_state_pub, 대본 5개) + hmi_bridge(GET /api/state) + 시험 페이지, 전체 시험 260건. 후속(F4-02 에 같이): cobot_msgs 시험에 importorskip · hmi.host 0.0.0.0 은 버튼이 붙기 전에 정한다'),
 'F4-02':   dict(note_add='9/20 #39 검토: 버튼(POST /api/start·abort)이 붙으면 같은 와이파이의 누구나 시작을 누를 수 있다 → hmi.host 기본값(127.0.0.1) 또는 버튼 확인 값 중 하나를 황인재가 정한다'),
 'V-03':    dict(status='완료', prog='1.0', note_add='✅ 9/20 17:00 시험 기록이 main 에(docs/test_logs/20260919_V-03_*, 15회차 · 강의자료 근거 · 두산 모션 API 에서 배운 것) — 판정 "가능". cell.force 값은 PR #40 으로 main 에. rig PR #37 은 수정 요청 1건(probe_spiral.py: 공중에서 순응·힘제어를 켜는 조합에 해제·상한이 없다 → 파일을 빼거나 감싸기)'),
 'CELL-04': dict(note_add='9/20 17:10 한석형 회신(결정기록 E9): ① 반납 구역은 **한 자리 공급 구조**(집으면 뒤 용기가 같은 자리로) → 슬롯 2 불필요(🟡 황인재 확인 대기 · 반복 정밀도 ±3 mm 확인 요청) ② WEIGH = 픽 자세 Z +100(값 받음) ③ 툴 집기·SOAP·툴 반납은 툴·홀더 확정 뒤(날짜 요청) ④ 그릇 칸의 "랙 밖 자리"를 접근점으로 추가 ⑤ 🚨 limits·motion·presets 값은 답이 없어 다시 요청 — 9/21 저녁 전'),
 'F1-04':   dict(note_add='9/20 한석형: 팔레트에서 나올 때 랙 안에서는 직선으로 되돌아 나온 뒤(컵 = 접근점까지 · 그릇 = Y 방향으로 랙 밖) HOME 은 관절 이동 — Virtual 확인 예정. 그릇 칸 접근점(랙 밖 자리) 티칭 필요'),
}
for _tid, _e in EVE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:25 황인재 결정 4건(E9 확인 · E10 · E11 · E12) + PR #41 merge
DEC_0920E = {
 'F4-02':   dict(status='완료', prog='1.0', note_add='✅ 9/20 17:25 PR #41 merge: 버튼 4종(start·stop·resume·abort) + WebSocket /ws/state + 가짜 flow 의 버튼 응답(--wait-start), 전체 시험 262건. ✅ 결정 E10: **웹 화면은 이 PC 의 브라우저에서만**(hmi.host 127.0.0.1 이 최종 · 태블릿용 비밀번호 F4-02b 는 하지 않는다). 후속(F4-03 과 같이): 버튼 요청에 사용자 지정 헤더 요구(다른 웹 페이지가 몰래 POST 하는 것 막기)'),
 'CELL-04': dict(note_add='✅ 9/20 17:25 황인재 확인(E9): 반납 구역은 **내리막 공급 구조** — 꺼내면 뒤 용기가 같은 자리로 내려온다 → 구역마다 집는 자리 1개(슬롯 2 폐기). cell.yaml zones.*.slots 를 1개로 · test_config 의 "슬롯 2개" 단언 · rig_coords 의 슬롯 2 항목은 F4 세션이 좌표 갱신 PR 에서. 조건: 다음 용기가 같은 자리에 오는 반복 정밀도 ±3 mm(한석형 5회 확인)'),
 'F1-02':   dict(note_add='9/20 E9: 구역마다 집는 자리 1개(내리막 공급 구조) — 같은 자리에서 count 번 집는다. 코드는 slots 목록을 도는 그대로(목록이 1개짜리). 헛잡으면 EMPTY_ZONE'),
 'FLOW-03': dict(note_add='✅ 9/20 17:25 결정 E11: 중단(/flow/abort) 정리 순서 = **HOME 먼저** → 툴 반납 → 용기를 격리(f1.place(\'ISOLATE\', kind)) → HOME → 다음 용기. ✅ E12: **GRIP_FAIL 정책 = pause**(멈추고 사람이 확인) — params.yaml flow.policy.GRIP_FAIL: isolate → pause, 주석의 🔔(IRD·SDD 에 행이 없다)는 이제 해결됨(IRD §8 · SDD §7 에 추가)'),
 'FLOW-01': dict(note_add='9/20 E12: flow.policy.GRIP_FAIL 을 pause 로(민범진 자기 절) — IRD §8 · SDD §7 반영됨'),
}
for _tid, _e in DEC_0920E.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 18:00 저녁 취합(GitHub 기준) + 9/21 부터 재배치 — 9/20 에 못 끝난 실기 작업을 9/21 저녁·9/22 로
R21 = '9/20 저녁 취합(GitHub 기준):'
REPLAN_0921 = {
 # ── 한석형 (F1·좌표) — 9/21 저녁은 남은 티칭 + V-22, F1 실기는 9/22 부터
 'CELL-04':  dict(prog='0.8', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁'),
                  note_add=R21 + ' 한석형이 좌표 정리 문서를 브랜치에 올림(docs/test_logs/20260920_CELL-04_티칭좌표_한석형.md · 17:07 · PR 전) — 그릇 잡기1(접근 [529, 8, 171, 157, 180, 157])·잡기2·컵 그립·WEIGH 후보·팔레트 J 값 포함, "컵 WASTE 는 다시 확인". 남은 것(9/21 저녁 첫 1시간): ISOLATE 2 · CUP_RACK2_1 · 그릇 칸 접근점 2 · 공급 구조 반복 정밀도 5회 · 🚨 limits·motion·presets 값'),
 'CELL-04b': dict(status='진행 중', prog='0.5', slots=S('9/20 오후', '9/21 저녁', '9/22 오후'),
                  note_add=R21 + ' 스펀지 홈(place·wash·regrip)은 티칭돼 main 에 있다(#36). 남은 것 = 툴 홀더(집기·반납)·SOAP — 🚨 툴·홀더를 제작 중이라 형상 확정 뒤에 찍는다(날짜 요청함). F1-03·F3-03 이 이 좌표를 기다린다'),
 'V-19':     dict(prog='0.5', slots=S('9/20 오전', '9/20 오후', '9/21 저녁'),
                  note_add=R21 + ' Virtual 에서는 전 자세 도달(#36 rig_coords OK 51·FAIL 0). 결정 E7 로 "안전 높이 경유" 조건은 없어졌다 → 실기 확인은 V-22(흐름 순서대로 구간)와 한 세션으로'),
 'V-22':     dict(slots=S('9/21 저녁'), note_add='9/21 저녁 순서: ① V-24 실기 확인(H 30분) ② 한석형 남은 티칭(1시간) ③ V-22 구간 확인(H·S) — 전제: E7 PR merge + limits·motion 값'),
 'F1-01':    dict(slots=S('9/21 저녁'), note_add=R21 + ' F1 코드는 아직 없음(브랜치 없음) — 골격만 main. 9/21 저녁은 책상에서 move_to·일반 place 부터'),
 'F1-02':    dict(slots=S('9/21 저녁', '9/22 오전'), note_add=R21 + ' 9/21 저녁 = 코드(책상), 9/22 오전 = 실기. 집는 자리 1개(E9) · 접근점 + 그립 자세'),
 'V-14':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(9/21 저녁 로봇은 V-24·남은 티칭·V-22·그리퍼 세션으로 찬다). 내용도 바뀜(E9): 슬롯 2개가 아니라 **같은 자리에서 연속 공급** — 집은 뒤 다음 용기가 같은 자리에 오는가 포함'),
 'F1-05':    dict(slots=S('9/22 오후')), 'V-04': dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(F1-02 실기가 오전으로 밀림)'),
 'V-15':     dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후'),
 'F1-03':    dict(slots=S('9/22 오후', '9/22 저녁'), note_add='9/20 재배치: 🚨 툴·홀더 확정과 좌표(CELL-04b)가 전제 — 늦어지면 9/22 저녁으로'),
 'V-08':     dict(slots=S('9/22 오후', '9/22 저녁')),
 # ── 민범진 (F2·flow) — 9/20 의 그리퍼·무게 실기 기록이 GitHub 에 없다 → 9/21 저녁 1시간
 'V-05':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' 실기 결과 기록이 GitHub 에 없다 → 9/21 저녁 그리퍼 세션(1시간: V-05 → V-23 → V-01 → V-16)으로'),
 'V-23':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')), 'V-01': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-02':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' 실기 측정 기록이 아직 없다 — WEIGH 자세(픽 자세 Z +100)가 정해졌으니 9/21 저녁 그리퍼 세션에 이어서'),
 'INF-02d':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁')), 'INF-02c': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-16':     dict(slots=S('9/21 저녁', '9/22 오전'), note_add='9/20 재배치: 9/20 오후 → 9/21 저녁(그리퍼 세션 끝에)·9/22 오전'),
 'V-07':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/20 오후 → 9/22 오전. 🔴 민범진 Virtual 실측(브랜치 42dc294): 털기 한 주기가 설정 0.60 s 보다 1.6배(0.954 s) — period_s 를 정할 때 전제로'),
 'CELL-03':  dict(prog='0.7', slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' WASTE·RINSE 자세가 티칭됐으므로 배치는 된 것으로 보인다 — 남은 것: 고정·배치 사진·잔반 대용품(≥100 g) 선정. 컵 WASTE 좌표는 한석형이 다시 확인'),
 'F2-01':    dict(prog='0.8', slots=S('9/20 오후', '9/21 저녁', '9/22 오전'), note_add=R21 + ' 코드는 main(#35). 민범진 브랜치에 Virtual 확인 추가(16:26 · 검사 13개 통과 · PR 전): weigh·shake·dip 연속 3회, 제자리 복귀 오차 0. 남은 것: _goto 에 kind(E8) · 실기(WEIGH 자세 확정 뒤, rig_f2.py empty 부터). 참고: "move_to 가 안전 높이를 왕복해 shake 1회의 37 % 가 이동" 은 E7 로 없어진다'),
 'F2-02':    dict(prog='0.75', slots=S('9/20 오후', '9/21 저녁', '9/22 오전')),
 'UT-F2':    dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(V-07·V-16·F2 실기가 오전)'),
 'FLOW-01':  dict(note_add=R21 + ' 남은 것: steps 의 f1.move_to·f3.soap 에 kind(E8) · policy.GRIP_FAIL = pause(E12)'),
 'FLOW-02':  dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(오전은 V-07·V-16·F2 실기와 FLOW-03 에 집중)'),
 'UT-FLOW':  dict(slots=S('9/22 저녁'), note_add='9/20 재배치: 9/22 오전 → 저녁(mock 시험이라 로봇 불필요 — INT-12a 교대 사이에)'),
 # ── 박진용 (F3) — V-03 완료, F3-02 는 고정 좌표 방식으로 다시
 'INF-02b':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/22 오전'), note_add=R21 + ' 남은 후속: safe_retreat 이 force_off 예외에도 후퇴 · contact_down 시간 상한이 일시 정지 시간을 세지 않게 · 나선·원호 공용 함수(F3-02 용) — 9/22 오전까지'),
 'F3-02':    dict(prog='0.4', slots=S('9/20 오전', '9/20 오후', '9/21 저녁', '9/22 오전'), note_add=R21 + ' 브랜치는 11:31 기준(벽 찾기) 그대로 — 고정 좌표 방식(E6)으로 다시 맞추는 일이 남음. 9/21 저녁: 코드 + 실기 연속 3회(V-18 같이) · 9/22 오전 마무리. PR #37(rig)은 probe_spiral.py 수정 요청 중'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add='9/20 재배치: F3-02 실기 3회 때 같이(9/21 저녁)'),
 'V-10':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(9/21 저녁은 F3-02 실기). 🚨 솔·홀더 확정이 전제'),
 'F3-03':    dict(slots=S('9/22 오전', '9/22 오후'), note_add='9/20 재배치: 9/21 저녁·9/22 오전 → 9/22 오전·오후. 🚨 SOAP·툴 좌표(CELL-04b)가 전제 — 늦어지면 soap 은 임시 좌표로 모션만'),
 'UT-F3':    dict(slots=S('9/22 오후', '9/22 저녁')),
 # ── 황인재 (F4·PM) — F4-01·F4-02 가 하루 앞서 끝남
 'V-13':     dict(status='진행 중', prog='0.7', slots=S('9/22 오전'), note_add=R21 + ' PR #41 에서 브라우저 시작 → 민범진 mock flow 반응 확인(1 ms · 이벤트 4건), 일시 정지·재개는 가짜 flow 로 확인. 남은 것: 실제 flow 의 PAUSED·재개 반영(FLOW-03 뒤) + 캡처'),
 'INT-4':    dict(status='진행 중', prog='0.3', note_add=R21 + ' 시작은 mock flow 와 연결 확인(#41). 일시 정지(이동 도중)·중단은 FLOW-03 이 main 에 들어온 뒤'),
 'F4-03':    dict(slots=S('9/21 저녁', '9/22 오후', '9/22 저녁', '9/24~28 오전'), note_add=R21 + ' F4-01·F4-02 가 하루 앞서 끝나 9/21 저녁부터 착수 가능. 후속: 버튼 요청에 사용자 지정 헤더'),
 'ARCH-01':  dict(status='진행 중', prog='0.6', slots=S('9/20 오후', '9/21 오전'), note_add=R21 + ' docs/images/system_architecture_pc.svg·drawio 는 최신 약속(kind 인자)까지 반영돼 있다(PM 도구로 생성). 남은 것: draw.io 다듬기·노션 업로드 — MID-01 과 같이'),
 'MID-01':   dict(note_add='🚨 9/21 14:00 중간점검(조별 30분 발표 + 30분 토론). 9/21 오전은 강의(강의 중 프로젝트 준비 금지 — 강사 노션) → **9/20 밤~9/21 아침·점심에 끝내야 한다.** 아직 시작 전 — PM 에이전트가 문서에서 초안을 뽑을 수 있다'),
 'V-24':     dict(note_add=R21 + ' E7(안전 높이 경유 삭제) 구현이 F4 브랜치에 올라옴(17:47 · PR 전) — 9/21 저녁 실기 확인은 그 코드로'),
 'REH-02':   dict(note_add='강사 노션(9/29 공지) 재확인 9/20: 오전 "통합테스트 진행" → 로봇으로 통합 디버깅 가능. 🛡 9/23 에 밀린 L4 항목(실패 주입·측정)의 예비 칸으로만 쓴다 — 새 기능은 넣지 않는다'),
}
for _tid, _e in REPLAN_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 20:40 황인재 지시: 한석형의 밀린 F1 과업을 나눈다 + PR #37 merge + 중간점검은 9/21 강사 확인 뒤
SH = '🔀 9/20 20:40 분담(황인재 지시 — 한석형은 좌표 지연으로 F1 이 3칸 밀려 9/22 하루에 함수 4개·검증 5개가 몰렸다):'
SHARE_0920 = {
 'F1-01':   dict(owner='H(S)', slots=S('9/21 저녁'), note_add=SH + ' **황인재(F4 세션)가 맡는다** — cc.move_to(station, carrying, kind) 를 감싼 f1.move_to + 일반 place(접근점 → 끝점 하강 → release → 되올라오기). 로봇 없이 짤 수 있다(Virtual). 한석형은 PR 검토만'),
 'F1-03':   dict(owner='H(S)', slots=S('9/22 오후', '9/22 저녁'), note_add=SH + ' **황인재(F4 세션)가 맡는다** — tool PICK/RETURN(폭 확인 · 반납은 힘 접촉). 전제: 툴·홀더 확정(CELL-02b, 9/21 저녁) → 한석형이 홀더 좌표 티칭(CELL-04b)'),
 'V-08':    dict(owner='H(S)', slots=S('9/22 오후', '9/22 저녁'), note_add=SH + ' F1-03 과 같이 황인재가'),
 'V-19':    dict(owner='H(S)', note_add=SH + ' 실기 도달 확인은 V-22(황인재 주도)와 한 세션 — 한석형은 옆에서 접근점이 필요한 구간만 추가로 찍는다'),
 'UT-F1':   dict(owner='S(H)', note_add=SH + ' TC 중 이동·일반 놓기·툴 부분은 황인재가, 집기·안착·팔레트는 한석형이'),
 'INT-12b': dict(owner='M(S)', note_add=SH + ' 주도를 민범진(통합 실행 리더)으로 — 한석형은 rack_place 만 지원'),
 'F1-05':   dict(note_add=SH + ' 담당은 그대로 한석형(박진용 참여). 🛡 범위 방어: 먼저 **단순 놓기**(접근점 → 끝점 하강 → release, F1-01 의 일반 place 와 같은 길)로 L2 를 통과시키고, 탐색(periodic_search)·SEAT_FAIL 판정은 시간이 남으면 얹는다 — 고정 좌표 + 무른 스펀지 홈이라 단순 놓기로 들어갈 가능성이 높다(V-04 에서 확인)'),
 'F1-02':   dict(note_add=SH + ' 한석형은 **집기(F1-02) → 안착(F1-05) → 팔레트(F1-04)** 세 개에 집중한다'),
 # 황인재 쪽 자리 만들기 — F4-03 은 추석에도 할 수 있다(AGENTS 규칙 9 예외)
 'F4-03':   dict(slots=S('9/24~28 오전', '9/24~28 오후'), note_add='9/20 20:40: F1-01·F1-03 을 맡으면서 9/21 저녁·9/22 오후 칸을 비운다 — 화면은 추석(집)에서. 9/22·23 노션 업로드용 gif 는 지금 시험 페이지로 충분(NOTE-02)'),
 'ENV-03':  dict(slots=S('9/22 오전'), note_add='9/20 20:40: 9/21 저녁 → 9/22 오전(9/21 저녁은 V-24 실기 확인·V-22·F1-01)'),
 'NOTE-01': dict(note_add='9/20 20:40: PM 에이전트가 초안을 만든다(노드 구조·인터페이스 — 문서에서 뽑기) → 황인재는 확인·업로드만'),
 'SAFE-01': dict(note_add='9/20 20:40: PM 에이전트가 초안을 만든다(SDD §7·§8 에서 뽑기) → 황인재·박진용은 확인만'),
 # 중간점검 — 형식 미확정
 'MID-01':  dict(note_add='❓ 9/20 20:40 황인재: 발표를 하는지 · 제출 문서가 있는지 **확정되지 않았다** → 9/21 아침 강사에게 확인한 뒤 이 행과 MID-02 를 고친다(강사 노션에는 "조별 30분 발표, 30분 토론, 8개팀 · 조별 자체점검"만 있고 양식·제출 안내는 없다)'),
 'MID-02':  dict(note_add='❓ 9/21 아침 강사 확인 뒤 수정(형식 미확정)'),
 # PR #37
 'V-03':    dict(note_add='✅ 9/20 20:35 PR #37 merge — rig_v03(바닥 나선 + 벽면 3바퀴)이 main 에. probe_spiral.py 는 PR 에서 빠짐, 나선 중 옆 힘 검사 추가'),
}
for _tid, _e in SHARE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 21:00 PR #42 merge — E7 구현(안전 높이 경유 삭제) + 도착 확인(MoveIncomplete)
PR42_0920 = {
 'INF-02':  dict(note_add='✅ 9/20 21:00 PR #42 merge(F4 세션 · 황인재가 rig_coords 를 직접 돌려 승인): move_to 가 티칭 자세로 곧장(E7) · 🆕 도착 확인 cc.MoveIncomplete — 이동이 끝났는데 목표에서 2 mm/1° 넘게 떨어져 있으면 오류(컨트롤러가 이동을 도중에 세워도 비동기 이동은 "끝남"으로만 보인다 — Virtual 에서 HOME → RACK_C1 이 122 mm 앞에서 섬). 시험 265건'),
 'V-19':    dict(task='V-19 도달 범위·특이점 — 모든 스테이션에 **티칭 경로대로(자리에서 자리로 곧장)** 도달 가능한가', note_add='9/20 #42: 작업명에서 "안전 높이 경유" 삭제(E7)'),
 'V-22':    dict(note_add='🚨 9/20 #42: ① 짧은 이동 3~4개로 **도착 확인(2 mm/1°)이 실기에서 헛경보를 내지 않는지** 먼저 ② **HOME → RACK_C1** 직선 이동을 가장 먼저·가장 천천히 — Virtual 에서 가상 컨트롤러가 수동 모드 속도 감시를 걸고 뜬 날에 122 mm 앞에서 섰다(원인 미확정). 서면 MoveIncomplete 로 멈추는 것이 맞는 동작 — 이어 내려가지 않는지 확인, 필요하면 경유 자세를 접근점으로 추가 ③ RET_B 접근 → 그립이 수평 2.78 mm 어긋남(그릇은 벽 2 mm 파지) — 그립 자세에서 z 만 올려 접근점 재티칭 ④ RET_C 는 접근 자세가 없어 관절 이동으로 그립 자세에 곧장 들어간다'),
 'V-24':    dict(note_add='9/20 #42: E7 코드가 main 에 → 9/21 저녁 실기 확인은 이 코드로(절차서·기록 양식은 F4 세션이 9/21 낮까지)'),
 'CELL-04': dict(prog='0.85', note_add='9/20 #42: WEIGH 2(픽 자세 Z +100) · 그릇 집기(접근 + 그립) 값이 cell.yaml 에 · 구역 슬롯 1개(E9). 남은 것: ISOLATE 2 · CUP_RACK2_1 · 그릇 칸 접근점 2 · RET_B 접근점 재티칭 · 컵 집기 접근 자세 · 툴·SOAP(홀더 확정 뒤) · limits·motion·presets'),
 'F1-01':   dict(note_add='9/20 #42 merge 됨 → F4 세션이 착수(황인재 확인 뒤)'),
 'FLOW-01': dict(note_add='9/20 #42: cc.MoveIncomplete 는 잡지 말고 위로(ROBOT_ERROR → PAUSED — 재시도·이어 하강 금지)'),
}
for _tid, _e in PR42_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 21:50 F1-01 Virtual 완료(실기 대기) · PR #43 보류(황인재 결정 대기)
LATE_0920 = {
 'F1-01':  dict(status='진행 중', prog='0.7', note_add='9/20 21:35 F4 세션: 구현·Virtual 확인 끝(브랜치 injae/20260920-F1-01-move-place · PR 은 황인재 승인 대기) — move_to WEIGH 3/3 · place SPONGE_BED_B/C 3/3 · 안 찍은 ISOLATE 는 움직이지 않고 KeyError. 🚨 가상 그리퍼 드라이버가 힘 명령을 몰라 **진짜 release 는 못 돌렸다** → 실기 확인 V-25(9/21 저녁)'),
 'F3-02':  dict(prog='0.6', note_add='9/20 21:34 PR #43(박진용): wipe_bowl 을 9/20 실기 14회차 절차 그대로 + 공용 함수(force.py: move_spiral·move_arc·move_periodic·compliance_on·force_release) + PM 후속 전부 반영 · 시험 309건. ⏸ **보류 — 황인재 결정 대기**: 결정 E6(고정 높이 · 벽면 힘제어 없음)과 두 군데 다르다(바닥을 힘으로 찾기 · 벽면 1.5 N). 코드에는 막는 사유 없음. 실기는 아직(9/21 저녁)'),
 'F3-03':  dict(status='진행 중', prog='0.5', note_add='9/20 21:34 PR #43 에 같이: soap(count, kind) · wipe_cup = 바닥 찾기 → 띄우기 → **Move Periodic 한 명령으로 위아래 ±15 mm + 비틀기 ±45° 동시** 5회(SR-09 의 "J6 ±180°"와 다름 — 황인재 결정 대기). 코드는 9/20 밤에 미리 작성됨 — 실기·V-10 은 일정대로 9/22 오전'),
 'INF-02b': dict(prog='0.95', note_add='9/20 PR #43 에 후속 전부 포함(safe_retreat 이 force_off 실패에도 후퇴 · contact_down 시간 상한이 일시 정지 시간을 빼고 셈 · 닦기 공용 함수) — merge 되면 완료'),
 'CELL-02b': dict(note_add='9/20 PR #43 본문(박진용): "그릇 받침 유격은 이대로 두기로 했다" → 완료 기준에서 빼 달라는 요청 — 황인재 확인 대기'),
}
for _tid, _e in LATE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 22:00 황인재 결정 E13 + PR #43·#44 merge
E13 = '✅ 9/20 밤 황인재 결정 E13(박진용 요청대로 — "직접 실기로 검증하고 확인한 사실만 얘기한 것"):'
PR43_0920 = {
 'F3-02':  dict(prog='0.8', note_add=E13 + ' 닦기 = **바닥은 contact_down 으로 찾고(시작 힘 대비 2 N) 벽면은 힘제어 1.5 N 유지** — E6 의 "고정 높이·힘제어 없음"을 정정(접촉 깊이가 실행마다 12~17 mm 로 달라 티칭 높이 하나로 못 맞춘다). 벽을 찾지 않는 것(치수로 계산)·힘 상한 10 N·옆 힘 25 N 은 그대로. PR #43 merge — 실기는 9/21 저녁'),
 'F3-03':  dict(prog='0.7', note_add=E13 + ' wipe_cup = 바닥 찾기 → 띄우기 → **Move Periodic 한 명령으로 위아래 + 비틀기 동시** → 아래쪽 끝에서 종료. SR-09 의 "J6 ±180°" 는 "툴 축 회전, 각도는 V-10 에서 확정"으로 완화. PR #43 merge — 실기·V-10 은 9/22 오전'),
 'V-10':   dict(task='V-10 컵 안쪽 솔 삽입 깊이·충돌 + 닦기 값 4개 확정(위아래 진폭·비틀기 각·주기·띄우는 양)',
                crit='정지 0 · 솔이 컵 밖으로 나오지 않음 · 컵이 딸려 올라오지 않음 · 10회 정상 · stroke_mm·twist_deg·period_s·lift_mm 확정',
                note_add=E13 + ' SR-09 가 각도를 정하지 않으므로 이 네 값이 V-10 의 산출물이다'),
 'V-03':   dict(note_add='✅ 9/20 22:00 PR #43 merge — 확정 절차가 제품 코드(wipe.py)에'),
 'INF-02b': dict(status='완료', prog='1.0', note_add='✅ 9/20 PR #43 merge 로 후속 전부 반영(safe_retreat 이 force_off 실패에도 후퇴 · contact_down 이 일시 정지 시간을 빼고 셈 · 닦기 접촉 모션 공용 함수 move_spiral·move_arc·move_periodic·compliance_on·force_release·where·motion_done) — force.py 완료'),
 'CELL-02b': dict(crit='툴을 홀더에서 10번 집고 놓아도 같은 자리 · 세척부 치수(높이·지름) 확정',
                  note_add=E13 + ' ⑤ **그릇 받침 유격은 그대로 둔다**(박진용 현장 판단) → 완료 기준에서 뺐다. 툴·홀더 확정만 남는다'),
 'F1-01':  dict(note_add='✅ 9/20 22:00 PR #44 merge(코드) — 실기 확인 V-25 뒤에 완료 처리한다'),
}
for _tid, _e in PR43_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 23:00 PR #45 merge(9/21 저녁 실기 준비물) + F4 선작업 2건(PR 전)
N45 = '✅ 9/20 23:00 PR #45 merge — 9/21 저녁에 그대로 쓸 도구·절차서:'
PR45_0920 = {
 'V-24':   dict(note_add=N45 + ' rig_pause.py 에 실기 모드(--real: 진짜 cell.yaml · J1 30°·옆 80 mm 의 작은 이동 · 단계마다 Enter · vel_scale>0.3 거부 · E-Stop 확인, --carrying) · 절차서 docs/test_logs/20260921_V-24_실기_일시정지_황인재.md. 🚨 --real 경로는 아직 끝까지 돈 적이 없다(값이 비어 있어 KeyError — 맞는 동작) → **1회차를 "절차가 도는지" 보는 회차로**. press_at_s 1.5 가 이동보다 늦으면 값 조정'),
 'V-22':   dict(note_add=N45 + ' rig_coords.py 에 실기 모드(--real · 구간마다 Enter · 하강 전 재확인 · **--from N 으로 막힌 구간부터 이어서** · 끝에 오차 표 = V-22 산출물) · 절차서 20260921_V-22_V-19_좌표재현_황인재.md'),
 'V-19':   dict(note_add='9/20 #45: V-22 와 같은 도구·같은 절차서로 한 세션에서 본다(rig_coords --real 의 구간별 도달 = V-19)'),
 'V-25':   dict(note_add=N45 + ' 절차서 20260921_F1-01_실기_황인재.md — PM 요청 2가지(놓은 뒤 되올라올 때 용기를 끌지 않는가 · place_clear_mm 100 이 충분한가) 포함'),
 'F1-03':  dict(status='진행 중', prog='0.6', note_add='9/20 밤 F4 세션 선작업(브랜치 injae/20260920-F1-03-tool · **PR 전** — 황인재: "실기 검증하고 승인하겠다"): tool PICK/RETURN 구현 — PICK = grip → 폭 판정, 헛잡으면 홀더에 두고 후퇴 / RETURN = contact_down 으로 바닥 찾기, **못 찾으면 release 하지 않고** TOOL_FAIL. 새 키 f1.tool_clear_mm 100 · tool_return_depth_mm 20. 가상에서는 프리셋이 비어 "안 움직이고 KeyError" 만 확인 → 9/22 V-08 뒤에 PR'),
 'F4-02':  dict(note_add='9/20 밤 F4 세션 선작업(브랜치 injae/20260920-F4-02b-button-header · **PR 전**): 버튼 POST 에 X-PreWash 헤더 요구(없으면 403) — 9/20 PM 검토에서 요청한 것. 실제 기동으로 403/200 확인. 황인재가 9/22 INT-4·V-13 때 보고 승인'),
}
for _tid, _e in PR45_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 07:45 아침 점검 — 값이 하나도 안 들어왔다 → 저녁을 시간으로 끊고 넘치는 것을 9/22 오전으로
A21 = '🔎 9/21 아침 점검:'
TIERS = ('🚨 **cell.yaml 빈 값 39개를 3단계로 나눈다**(무엇이 무엇을 막는지): '
         '**① 이동 11개** = limits 의 vel_free_pct·vel_carry_pct·safe_z_mm·timeout_s + motion 5개 → V-24·V-22·V-19·V-25 와 **모든 실기 이동**의 전제. 로봇 없이 책상에서 10분이면 채운다(스크립트 값: 관절 20 deg/s·40, 직선 60 mm/s·120). '
         '**② 그리퍼 16개** = presets BOWL·CUP·SPONGE·BRUSH → 집기(F1-02)·툴(F1-03)·V-14 의 전제. 9/21 저녁 그리퍼 세션(민범진)의 **산출물**이다. '
         '**③ 닦기 3개** = limits.contact_limit_n 2.0 + 닦는 자리 z(그릇 47→68 · 컵 156.54→128) → F3-02·F3-03 의 전제. '
         '그 밖: SOAP 2·ISOLATE 2·seat 8개는 그 기능을 돌릴 때까지만 있으면 된다')
MORNING_0921 = {
 'CELL-04':  dict(note_add=A21 + ' 밤사이 값이 **하나도 안 들어왔다**(한석형 마지막 커밋 9/20 17:07 = 좌표 정리 문서). ' + TIERS),
 'CELL-04b': dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전', '9/22 오후'),
                  note_add=A21 + ' 오늘 저녁 티칭은 1시간뿐이라 **급한 순서로 자른다** — 🔴 오늘: 툴 홀더 집기·반납 2종 + SOAP 2(툴·홀더 확정 직후 · F1-03·F3-03 이 9/22 오후에 이걸 기다린다) + 그릇 집기 접근점 재티칭(수평 2.8 mm). 🟡 9/22 오전: ISOLATE 2 · CUP_RACK2_1 · 팔레트 그릇 칸 접근점 2 · 컵 집기 접근 자세'),
 'V-24':     dict(note_add=A21 + ' 전제는 위 ①(이동 11개)뿐이다 — presets 는 필요 없다'),
 'V-22':     dict(note_add=A21 + ' 전제는 ①뿐. 안 찍은 자세(SOAP·ISOLATE)는 rig 가 건너뛴다'),
 'V-25':     dict(note_add=A21 + ' 전제는 ①. place 는 release 만 쓰므로 presets 없이도 돈다'),
 'V-05':     dict(note_add=A21 + ' 🔴 이 세션의 산출물이 **presets** 다. 저녁 슬롯이 35분뿐이라 **BOWL·CUP 의 grip_width_mm·grip_force_n·width_tol_mm 6개만** 오늘 확정한다(9/22 오전 F1-02 집기·V-14 가 이것만 기다린다) — HOLD 힘(V-16)·approach_z_mm·SPONGE·BRUSH(툴은 9/22 오후 F1-03) 와 무게(V-02)는 9/22 오전'),
 # 넘치는 것을 9/22 오전으로
 'F3-02':    dict(slots=S('9/20 오전', '9/20 오후', '9/22 오전'),
                  note_add=A21 + ' 저녁 3.5 h 에 7가지는 들어가지 않는다(합쳐 약 5 h) → **닦기 실기 3회를 9/22 오전 첫 순서로** 옮긴다. 전제는 위 ③(닦기 3개) — 그 값은 오늘 저녁 티칭 때 같이 받는다. 코드는 main 에 있으니 오늘 저녁은 책상에서 준비만'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/22 오전'), note_add=A21 + ' F3-02 실기와 함께 9/22 오전으로'),
 'V-10':     dict(slots=S('9/22 오전', '9/22 오후'), note_add=A21 + ' F3-02 실기가 9/22 오전 앞으로 와서 V-10 은 오전 뒤~오후로 걸친다'),
}
for _tid, _e in MORNING_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:15 황인재 지시: 좌표 작업 담당을 한석형 → 황인재(F4 세션)로 위임
DEL = '🔀 9/21 08:15 위임(황인재 — 한석형 쪽 좌표 작업이 계속 길어져서):'
DELEG_0921 = {
 'CELL-04':  dict(owner='H(S)', note_add=DEL + ' **좌표 작업 담당을 황인재(F4 세션)로.** 이미 PR #36·#42 로 해 오던 것을 공식화한다 — 파일(cell.yaml) 작업은 F4 가 한석형 확인을 기다리지 않고 진행하고, 한석형은 검토·입회. 어제까지 걸어 둔 "한석형 값이 올 때까지 넣지 말라"는 제한을 푼다. 🚨 다만 **티치펜던트로 자세를 찍는 것은 위임되지 않는다** — 로봇 앞에서 사람이 해야 한다(오늘 저녁 슬롯에서 한석형이 찍거나 황인재가 직접)'),
 'CELL-04b': dict(owner='H(S,P)', note_add=DEL + ' 스펀지 홈·툴 홀더 좌표도 같이 — 찍는 것은 로봇 앞에서, 파일에 넣는 것은 F4'),
 'V-22':     dict(note_add=DEL + ' 좌표 파일의 주인이 바뀌어도 확인 절차는 그대로(H 주도·S 입회)'),
 'F1-02':    dict(note_add=DEL + ' 한석형은 이제 **F1 함수 3개(집기·안착·팔레트)에만** 집중한다 — 좌표 파일 작업은 없다'),
}
for _tid, _e in DELEG_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:30 황인재가 08:00 경 V-22 그릇 한 바퀴를 혼자 돌렸다 — 결함 2건
R22 = '🔬 9/21 08:00 V-22 실기(황인재 · 그릇 한 바퀴 1~17번):'
REAL_0921 = {
 'V-22':     dict(status='진행 중', prog='0.5',
                  note_add=R22 + ' ✅ **좌표 정확도는 매우 좋다 — 전부 오차 0.11~0.24 mm · 관절 0.01~0.03°**(기준 2 mm). 스펀지 홈·닦는 자리 하강도 끝점에 정확히 도달. '
                  '❌ 결함 2건(아래 CELL-04 비고) · ⚠ RET_B 접근 → 그립 어긋남은 실기 **2.91 mm**(가상 2.78 과 일치) · 컵 한 바퀴(18~33)는 오늘 저녁에'),
 'V-19':     dict(prog='0.7', note_add=R22 + ' 도달 범위는 문제없다(WASTE BOWL 도 팔 길이 683 mm / 한계 900 — 안 닿는 게 아니라 특이점)'),
 'CELL-04':  dict(prog='0.9', note_add=R22 + ' 🚨 **오늘 저녁 티칭 최우선 2건(실기에서 실제로 막힌 것)**: '
                  '**① WASTE BOWL 재티칭** — 목표 6.0 mm 앞에서 컨트롤러가 세웠다(MoveIncomplete). ry = 179° 로 **손목 특이점(180°)에서 1°** 다 → 특이점에서 떨어진 자세로 다시 찍는다. 🔔 잔반 터는 자세라 방향이 바뀌면 털기(F2)에 영향 → **한석형·민범진과 같이 정한다**. '
                  '**② 팔레트 그릇 칸(RACK_B1·B2) 접근점 2개** — 접근점이 없어 꽂은 자리에서 HOME 으로 곧장 가다가 **그리퍼가 팔레트에 걸린다**(황인재 목격). 한석형 스크립트의 "y −25 → z +200 으로 빠진다"가 좌표로 안 옮겨져 있었다. 컵 칸(C1·C2)에는 접근점이 있다. '
                  '그다음 ③ 툴 홀더 집기·반납 2종 + SOAP 2 ④ 그릇 집기 접근점 재티칭(2.91 mm). 🟡 9/22 오전: ISOLATE 2 · CUP_RACK2_1 · 컵 집기 접근'),
 'CELL-04b': dict(note_add='9/21 08:30: F4 가 **값 21개를 채웠다**(브랜치 injae/20260921-CELL-04b-limits-motion · PR 은 황인재 확인 뒤) — limits 6 · motion 5 · seat 8 · 닦는 자리 z 2(E13). '
                  '🔑 safe_z_mm = **235**(SDD 예시 150 이 아니다): E7 로 뜻이 "접촉 뒤 후퇴 높이"가 됐는데 150 이면 **컵을 닦던 솔이 컵 밖으로 안 나온다**(용기 안 바닥 33 + 컵 깊이 95 = 입구 128, 솔 95 → 223 필요). 한석형의 닦기 접근점과 같은 높이다. '
                  '🟡 presets 16개는 **비워 둔다**(F4 권고 · 황인재 확인 대기): 비면 안 움직이고(안전) 임시값이면 틀린 값으로 실기가 돈다. 오늘 저녁 V-24·V-22·V-25 는 presets 를 읽지 않는다 — 필요한 곳은 F1-02 집기·F1-03 툴(9/22)뿐'),
 'F1-04':    dict(note_add=R22 + ' 🚨 팔레트에서 빠져나오는 동작이 **좌표로 없다** — 그릇 칸 접근점 2개를 찍은 뒤 rack_place 가 release → 접근점으로 되돌아 나오게 만든다(컵 칸과 같은 방식)'),
 'V-06':     dict(note_add=R22 + ' 그릇 칸 접근점이 생긴 뒤에 본다'),
 'V-07':     dict(note_add=R22 + ' 🔔 WASTE BOWL 자세가 특이점 회피로 바뀐다 → 털기 진폭·방향을 그 자세에서 다시 본다(한석형 재티칭 때 민범진 입회)'),
 'F2-01':    dict(note_add=R22 + ' 🔔 WASTE BOWL 재티칭으로 터는 자세가 바뀔 수 있다 — 저녁 티칭에 민범진 입회'),
 'V-24':     dict(note_add='9/21 08:00: 어제 넣은 도착 확인(MoveIncomplete)이 **실기에서 실제로 결함을 잡았다** — WASTE BOWL 이 6 mm 앞에서 섰는데 예전 코드였으면 성공으로 넘어갔다. 일시 정지·재개 자체의 실기 확인은 오늘 저녁 그대로'),
}
for _tid, _e in REAL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:45 황인재: 좌표는 티칭·파일·확인까지 전부 F4(황인재) 전담
FULL = '🔀 9/21 08:45 전담(황인재):'
FULLDEL_0921 = {
 'CELL-04':  dict(owner='H', note_add=FULL + ' **티칭까지 포함해 좌표 작업 전부를 황인재(F4 세션)가 한다.** 08:15 위임에서 "티치펜던트 티칭은 위임 안 됨"이라 했던 것도 황인재가 직접 하는 것으로 정리 — 황인재가 로봇 앞에 있다(오늘 08:00 V-22 를 혼자 돌렸다). 한석형은 **F1 함수에만** 집중하고, 기구 배치·의도를 묻는 질문에만 답한다'),
 'CELL-04b': dict(owner='H(P)', note_add=FULL + ' 티칭도 황인재. 툴 홀더 자리는 박진용의 기구 확정(CELL-02b)과 붙어 있어 P 만 남긴다'),
 'V-19':     dict(owner='H', note_add=FULL + ' 확인도 황인재 전담(한석형 입회 불필요)'),
 'V-22':     dict(owner='H', note_add=FULL + ' 확인도 황인재 전담. 🔸 티칭과 확인을 한 사람이 하므로 **티칭 직후 그 자세를 바로 rig_coords --from 으로 확인**하는 편이 빠르다(저녁 ③④를 묶는다)'),
 'F1-02':    dict(note_add=FULL + ' 한석형은 오늘 저녁 로봇 순서가 없다 → **저녁 내내 F1-02 집기 코드**(9/22 오전 실기). 그만큼 앞당길 수 있다'),
 'F1-05':    dict(note_add=FULL + ' 한석형이 저녁에 코드를 앞당길 수 있으면 9/22 오후가 수월해진다'),
 'V-14':     dict(note_add='9/21: 집기 검증은 한석형 몫 그대로(자기 함수) — 좌표 확인(V-22·V-19)만 황인재가 전담'),
}
for _tid, _e in FULLDEL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:50 황인재: 일정 재분담 — 민범진·황인재에 몰린 것을 한석형(좌표가 빠져 여유)·박진용(오늘 저녁이 빔)으로
RB = '🔀 9/21 08:50 재분담(황인재):'
REBAL_0921 = {
 # ① 민범진 — 그리퍼 세션에 시간을 준다(9/20 에 못 한 것으로 보인다 · 결과 기록 없음)
 'V-05':    dict(note_add=RB + ' 오늘 저녁 그리퍼 세션을 **35분 → 60분(21:00~22:00)** 으로 늘린다 — V-25(F1-01 실기)를 9/22 오후로 빼서 만든 25분. 절차는 박진용 제안서(docs/ref/20260919_제안_RG2_폭_힘_경로.md §5)라 **박진용이 옆에서 도울 수 있다**(오늘 저녁 박진용은 툴·홀더 확정 뒤 비어 있다)'),
 'V-01':    dict(note_add=RB + ' 그리퍼 세션 60분 안에서'),
 'V-25':    dict(slots=S('9/22 오후'), note_add=RB + ' 9/21 저녁 → **9/22 오후, F1-03·V-08 바로 앞**(같은 황인재 · 같은 place/release 경로라 이어서 보면 된다). 그리퍼 세션에 시간을 주려고 옮겼다 — F1-02 실기는 f1.move_to 가 아니라 cc.move_to 를 쓰므로 V-25 를 기다리지 않는다'),
 # ② INT-12b 주도를 한석형에게 되돌린다 — 어제 옮긴 이유(좌표 작업으로 과부하)가 없어졌다
 'INT-12b': dict(owner='S(M)', note_add=RB + ' **주도를 한석형에게 되돌린다.** 9/20 밤에 민범진으로 옮긴 이유(한석형이 좌표 작업으로 과부하)가 9/21 아침 좌표 전담 이관으로 없어졌고, 지금은 민범진이 가장 무겁다. INT-12b 는 F1(재파지·적재) + F2(헹굼·물 털기)라 F1 주인이 끌고 민범진이 F2 쪽을 돕는다'),
 # ③ SAFE-01 을 박진용이 주도 — 안전 파라미터 담당이고 오늘 저녁이 비어 있다
 'SAFE-01': dict(owner='P(H)', slots=S('9/21 저녁', '9/22 오전'),
                 note_add=RB + ' **박진용이 주도한다**(안전 파라미터 담당 · 오늘 저녁 툴·홀더 확정 뒤 비어 있다). PM 에이전트가 SDD §7·§8 에서 뽑은 초안을 넘기고, 박진용이 값(힘 상한·속도·후퇴 높이 235·정지 종류 DR_QSTOP)을 확인해 완성한다 → 황인재는 노션 업로드만(NOTE-01 과 묶음). 9/22 오전 황인재 부담을 던다'),
 'CR-01':   dict(note_add=RB + ' 9/22 오전 전원 — 안전 파라미터 절은 SAFE-01 을 만든 박진용이 설명'),
 # ④ 민범진 9/22 — 오전은 로봇(실기)만, 책상 작업은 오후·저녁으로 편다
 'FLOW-03': dict(slots=S('9/22 오후'), note_add=RB + ' 9/22 오전·오후 → **오후만**. 오전은 민범진이 로봇 실기(V-07·V-16·F2)에 집중하고, 정지·재개·중단 연결(mock 으로 되는 책상 작업)은 오후에 몰아서'),
 'FLOW-02': dict(slots=S('9/22 저녁'), note_add=RB + ' 9/22 오후 → **저녁**(FLOW-03 이 오후로 와서). 기록(records.csv)·소모품 카운트는 mock 으로 되는 책상 작업 — INT-12a 교대 사이에'),
}
for _tid, _e in REBAL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:40 실기 — 6번 관절 163° 회전으로 케이블 꼬임 · 로봇 정지
R840 = '🔬 9/21 08:40 실기(황인재):'
J6_0921 = {
 'CELL-04':  dict(note_add=R840 + ' WASTE BOWL 을 관절 자세(posj)로 바꾸니 그 자리에는 닿았지만 다음 스펀지 홈까지 **6번 관절이 약 163° 돌아 그리퍼 케이블이 꼬여 로봇이 멈췄다**(오류 상태 — 정지 명령 무응답). posx 로 되돌렸다(F4 브랜치). 🚨 **그릇 경로의 6번 관절 값이 자세마다 제각각**(0 · −16 · −179 · −220 · −117) → 자세 사이에서 손목이 크게 돈다 → **오늘 저녁 티칭은 WASTE BOWL 한 자세가 아니라 그릇 경로 전체를 6번 관절이 이어지게 다시 찍는 일**이 된다. 1 h 20 슬롯을 넘을 수 있다 → 넘치면 컵 한 바퀴 확인(④)을 9/22 오전으로'),
 'V-22':     dict(note_add=R840 + ' 🚨 rig_coords 안전 결함 발견·수정(F4 브랜치 8ae86d2): 실기에서 이동이 실패하면 도구가 **자동으로 HOME 으로 가려 했다**(케이블이 꼬인 채 자동 이동하면 더 꼬인다 — 다행히 컨트롤러가 오류 상태라 거부). → --real 이면 **어떤 이동 실패든 그 자리에서 멈추고 사람에게 넘긴다**(--from N 으로 이어서). 이 수정이 main 에 들어간 뒤에 저녁 실기를 돌린다'),
 'V-19':     dict(note_add=R840 + ' 도달 범위가 아니라 **관절 경로**(6번 관절 연속성) 문제가 드러났다 — V-19 의 판정 항목에 "자세 사이 6번 관절 회전이 과하지 않은가"를 더한다'),
 'V-07':     dict(note_add=R840 + ' WASTE BOWL 이 경로 재티칭으로 바뀐다 — 털기 방향도 같이'),
}
for _tid, _e in J6_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:55 프리셋의 흐름을 분명히 — 민범진이 재고 → 황인재(F4)가 cell.yaml 에 넣는다
PS = '🔧 9/21 프리셋 흐름:'
PRESET_0921 = {
 'V-16':  dict(note_add=PS + ' ~~찾은 HOLD 값은 한석형이 cell.yaml 프리셋에 반영~~ → **황인재(F4)가 반영**(9/21 좌표·cell.yaml 전담 이관). 민범진은 값을 단톡방·기록으로 넘긴다'),
 'V-01':  dict(note_add=PS + ' 이 행에서 나오는 **그릇·컵의 파지 폭(grip_width_mm)·폭 허용 오차(width_tol_mm)** 와 쥐어 본 **평소 힘(grip_force_n)** 이 cell.yaml presets 의 BOWL·CUP 값이 된다 — 오늘 저녁 그리퍼 세션에서 재고, **황인재(F4)가 cell.yaml 에 넣는다**. 내일 오전 한석형의 집기(F1-02)·V-14 가 이 값을 기다린다'),
 'CELL-04b': dict(note_add=PS + ' presets 16개는 **민범진이 재고(V-01·V-16) 황인재가 넣는다** — 그때까지 비워 둔다(권고 · 황인재 확인 대기). 수세미·솔(SPONGE·BRUSH)은 툴·홀더 확정(CELL-02b) 뒤 9/22'),
}
for _tid, _e in PRESET_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 09:00 황인재 확인: 오늘 발표 없음(노션 차시 표는 이전 기수 내용) · 9/22~23 1차 산출물 제출
NP = '✅ 9/21 09:00 황인재가 강사에게 확인:'
NOPRES_0921 = {
 'MID-01': dict(status='해당 없음', prog='1.0', slots=[],
                note_add=NP + ' **오늘 중간점검 발표는 없다** — 노션의 차시별 강의 일정표("6차시 오후 프로젝트 중간점검 · 조별 30분 발표")는 **이전 기수 내용**으로 보인다. 발표 자료(10장)는 만들지 않는다. 날짜가 적힌 공지 페이지(9/14 · 9/22·23 · 9/29 · 9/30)는 이번 기수 것이 맞다'),
 'MID-02': dict(status='해당 없음', prog='1.0', slots=[], note_add=NP + ' 오늘 중간점검 없음 — 행을 남겨 두되 해당 없음'),
 # 9/22~23 1차 산출물 제출 (노션 "9/22, 9/23 일정(7,8차시)" 공지)
 'NOTE-01': dict(task='노션 — ROS2 노드 구조(노드 2 + 패키지 구조)·인터페이스 정의서(ROS + 기능 함수) 업로드 — **9/22~23 1차 산출물 제출**',
                 crit='9/22~23 제출 기한 안에 노션에 올라감',
                 note_add=NP + ' **9/22~23 에 1차 산출물 제출이 있다.** 노션 공지의 제출 항목 = ① 코드 최신으로 GitHub 업로드 ② **ROS2 노드 구조를 노션에 추가**(이 행) ③ 관리자 HMI·사용자 UI 화면 업로드(NOTE-02 · 여러 장이면 gif). PM 에이전트가 초안을 만든다'),
 'NOTE-02': dict(task='노션 — 관리자 HMI·사용자 UI 화면 업로드(여러 장이면 gif) — **9/22~23 1차 산출물 제출**',
                 crit='9/22~23 제출 기한 안에 노션에 올라감',
                 note_add=NP + ' 1차 산출물 제출 항목 ③. 지금 시험 페이지로도 찍을 수 있다(F4-03 화면을 기다리지 않아도 된다)'),
 'ARCH-01': dict(note_add=NP + ' 1차 산출물(9/22~23)의 노드 구조 그림으로 쓴다 — NOTE-01 과 같이 올린다. 중간점검 발표가 없어졌으므로 "MID-01 과 같이 작업"은 해당 없음'),
 'PM-01':  dict(note_add=NP + ' 🚨 **1차 산출물 제출(9/22~23) 목록을 하나로 모아 확인한다** — ① GitHub 최신(동결 전 push) ② 노드 구조(NOTE-01) ③ HMI 화면(NOTE-02). 강사 산출물 10종 목록과 대조'),
}
for _tid, _e in NOPRES_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 09:10 발표가 없어져 오후가 열렸다 → 밀린 일을 반나절 앞당긴다
AF = '🔄 9/21 09:10 재배치(발표 취소로 오후가 열림):'
PULL_0921 = {
 # ── 9/21 오후: 로봇은 "툴·홀더 → 이동 함수 → 티칭·확인" (전제가 되는 것부터)
 'CELL-02b': dict(slots=S('9/21 오후'), note_add=AF + ' 저녁 → **오후 첫 순서(14:00)**. 티칭(툴 홀더·SOAP)의 전제라 가장 먼저'),
 'V-24':     dict(slots=S('9/20 오후', '9/21 오후', '9/22 오전'), note_add=AF + ' 실기 확인을 **9/21 오후(14:30)** 로 — 뒤의 티칭·확인이 이 코드로 돈다'),
 'CELL-04':  dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 오후', '9/21 저녁'),
                  note_add=AF + ' 티칭을 **오후 15:00~17:00(2 h)** 로 앞당긴다 — 08:40 에 드러난 **그릇 경로 6번 관절 재티칭**이 커서 저녁 1 h 20 으로는 부족했다. 순서: 경로 재티칭(6번 관절 연속) → 팔레트 그릇 칸 접근점 2 → 그릇 집기 접근점 → 툴 홀더 2종 + SOAP 2(툴·홀더 확정 뒤) → ISOLATE 2'),
 'CELL-04b': dict(slots=S('9/20 오후', '9/21 오후', '9/22 오전'), note_add=AF + ' 툴 홀더·SOAP 좌표도 오후 티칭에서'),
 'V-22':     dict(slots=S('9/21 오후', '9/21 저녁'), note_add=AF + ' 오후 17:00~18:00 에 그릇·컵 한 바퀴 — 티칭 직후 바로'),
 'V-19':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후'), note_add=AF + ' V-22 와 한 세션'),
 'SAFE-01':  dict(slots=S('9/21 오후', '9/22 오전'), note_add=AF + ' 박진용이 툴·홀더 확정(14:00~14:30) 뒤 오후에 — 로봇이 필요 없다'),
 # ── 9/21 저녁: 프리셋 → 집기 실기 → 닦기 → F1-01 실기 (오늘 안에 L1 앞부분을 끝낸다)
 'V-05':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=AF + ' **저녁 첫 순서 18:30~19:30(60분)** — 여기서 나온 프리셋으로 바로 뒤 F1-02 집기 실기를 돌린다'),
 'V-01':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')), 'V-23': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-16':     dict(slots=S('9/21 저녁', '9/22 오전')), 'V-02': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁', '9/22 오전')),
 'INF-02c':  dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')), 'INF-02d': dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁')),
 'F2-01':    dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전')), 'F2-02': dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전')),
 'F1-02':    dict(slots=S('9/21 오후', '9/21 저녁'), note_add=AF + ' 한석형은 **오후에 코드**(로봇은 다른 사람이 쓴다) → **저녁 19:30~20:30 에 실기**. 전제: 저녁 첫 순서 그리퍼 세션의 프리셋'),
 'V-14':     dict(slots=S('9/21 저녁'), note_add=AF + ' F1-02 실기와 같이 — 9/22 오전 → 9/21 저녁'),
 'F3-02':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=AF + ' 닦기 실기 3회를 **9/22 오전 → 9/21 저녁 20:30~21:10** 로. 전제: 오후 티칭에서 닦는 자리 z 확인'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=AF + ' 닦기 3회와 같이'),
 'V-25':     dict(slots=S('9/21 저녁'), note_add=AF + ' 9/22 오후 → **9/21 저녁 21:10~21:35**(오늘 안에 F1-01 을 닫는다)'),
 # ── 9/22: 앞당겨진 만큼 한 칸씩 당긴다
 'F1-05':    dict(slots=S('9/22 오전'), note_add=AF + ' 9/22 오후 → **오전**(F1-02 가 어제 끝났으므로)'),
 'V-04':     dict(slots=S('9/22 오전')), 'V-15': dict(slots=S('9/22 오전')),
 'F1-03':    dict(slots=S('9/22 오후'), note_add=AF + ' 툴 좌표는 9/21 오후 티칭에서 나온다 → 9/22 오후에 실기(황인재의 9/22 오전은 남은 티칭·ENV-03·노션으로 이미 찬다)'),
 'V-08':     dict(slots=S('9/22 오후')),
 'F1-04':    dict(slots=S('9/22 오후'), note_add=AF + ' 9/22 저녁 → 오후'), 'V-06': dict(slots=S('9/22 오후')),
 'UT-F1':    dict(slots=S('9/22 오후', '9/22 저녁'), note_add=AF + ' 9/22 저녁·9/23 오전 → **9/22 오후·저녁** — G2(L1) 를 9/22 안에 닫는 것이 목표'),
 'F3-03':    dict(slots=S('9/22 오전', '9/22 오후')), 'V-10': dict(slots=S('9/22 오전')),
 'UT-F3':    dict(slots=S('9/22 오후')), 'UT-F2': dict(slots=S('9/22 오후')),
 'INT-12a':  dict(slots=S('9/22 저녁')), 'INT-13': dict(slots=S('9/22 저녁')),
 'INT-12b':  dict(slots=S('9/22 저녁', '9/23 오전'), note_add=AF + ' 9/23 오전 → **9/22 저녁부터** 시작할 수 있다(F1-04 가 9/22 오후로 당겨졌다)'),
 'FLOW-03':  dict(slots=S('9/21 저녁', '9/22 오후'), note_add=AF + ' 민범진은 저녁에 로봇 순서가 앞(18:30~19:30)이라 그 뒤 책상 시간이 길다 → FLOW-03 을 9/21 저녁부터'),
 'FLOW-01':  dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁'), note_add=AF + ' kind·GRIP_FAIL 수정은 오늘 저녁 책상 시간에'),
}
for _tid, _e in PULL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 09:40 같은 결함이 제품 코드·flow 에도 — "위치를 모르면 움직이지 않는다"
NM = '🚨 9/21 09:40 "위치를 모르면 자동으로 움직이지 않는다"(SDD §7 추가):'
NOMOVE_0921 = {
 'FLOW-01': dict(note_add=NM + ' **flow.py 의 call() 이 예외를 잡으면 무조건 safe_retreat 을 부른다**(263행 부근) → cc.MoveIncomplete 일 때는 **후퇴도 하지 않아야** 한다(그 오류는 "어디 있는지 모른다"는 뜻). 힘·순응은 끄되 움직이지 않고 PAUSED. 힘 상한(ForceLimitError)은 로봇이 정상이므로 설계대로 후퇴 — 구분해서. 오늘 저녁 책상 시간에 kind·GRIP_FAIL 과 같이'),
 'F3-02':   dict(note_add=NM + ' ✅ 박진용이 **제품 코드(wipe.py)·rig_v10 에도 같은 결함**이 있는 것을 찾아 고쳤다 — **PR #46 merge**(09:45, 시험 319건) — _off_and_retreat(move=…) 로 나눠 "힘 해제는 언제나·이동은 위치를 알 때만", MoveIncomplete 는 MotionHalted 와 같이 그대로 올린다 · 힘 상한(ForceLimitError)은 설계대로 후퇴(구분) · 시험 4개로 "후퇴를 부르지 않는다"를 검사'),
 'SAFE-01': dict(note_add=NM + ' 안전 대책 표에 이 줄을 넣는다 — "이동 실패(위치 불명) 뒤에는 어떤 자동 이동도 하지 않는다: 도구·기능 함수·flow 세 곳 모두"'),
}
for _tid, _e in NOMOVE_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 09:50 점검에서 나온 마무리 2건
CK = '🔎 9/21 점검:'
FINAL_0921 = {
 'ARCH-01': dict(slots=S('9/20 오후', '9/22 오전'), note_add=CK + ' 9/21 오전(강의 시간) 칸을 뺀다 — 중간점검이 없어져 "MID-01 과 같이"가 사라졌으므로 **1차 산출물(9/22~23)의 노드 구조 그림**으로 NOTE-01 과 같은 칸(9/22 오전)에서 마무리'),
 'PM-01':   dict(note_add=CK + ' 일정표 점검(v9.6): 지난 칸에만 남은 미완료 0건 · 칸 없는 미완료 0건 · 상태 완료 31 · 진행 25 · 시작 전 49 · 해당 없음 2(중간점검)'),
}
for _tid, _e in FINAL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 10:00 민범진 지연의 원인 = 로봇 경합(좌표가 독점) → 민범진을 오후 맨 앞으로
RC = '🔎 9/21 10:00 원인(민범진 보고):'
ROBOT_0921 = {
 'V-05':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후'),
                 note_add=RC + ' 밀린 이유는 준비 부족이 아니라 **로봇 경합** — 좌표 작업이 로봇을 계속 써서 검증을 못 했고 그동안 다른 작업을 했다. '
                 '🔑 그런데 **그리퍼 세션은 좌표와 무관하다** — `rig_gripper.py` 는 자기 설정 폴더(rig_gripper_config)를 쓰고 팀 cell.yaml 의 limits·motion 도 읽지 않는다(파일 머리말 ②④). '
                 '→ **9/21 오후 맨 앞(14:00~15:00)으로 옮긴다.** 좌표·값 PR 을 기다릴 필요가 없고, 여기서 나온 프리셋이 저녁 F1-02 집기 실기의 전제다'),
 'V-23':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'V-01':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'V-02':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후'), note_add=RC + ' 무게도 좌표가 필요 없다(추를 손으로 올린다) → 그리퍼 세션에 이어서'),
 'INF-02c': dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'INF-02d': dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 오후')),
 'V-07':    dict(slots=S('9/21 저녁', '9/22 오전'), note_add=RC + ' 털기는 **WASTE 자세가 필요하다** → 오후 티칭(15:30~17:30)에서 재티칭한 뒤 **저녁 예비 시간(20:35~)** 에. 민범진에게 오늘 두 번째 로봇 순서를 준다'),
 'V-16':    dict(slots=S('9/21 저녁', '9/22 오전')),
 'F2-01':   dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전'), note_add=RC + ' 실기는 WASTE·RINSE 자세가 필요 → 저녁 예비 시간부터, 남으면 9/22 오전'),
 'F2-02':   dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전')),
 'CELL-03': dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후'), note_add=RC + ' 배치 사진·잔반 대용품은 로봇이 필요 없다 — 오후에'),
 'BRF':     dict(note_add=RC + ' 🚨 **교훈: 로봇 1대 경합이 가장 큰 지연 원인**이다. 아침 브리핑에서 **그날 로봇 시간을 분 단위로 먼저 배분**하고, 한 사람이 2시간 넘게 연속으로 쓰지 않는다. 좌표처럼 긴 작업 앞뒤로 짧은 검증(그리퍼·무게처럼 좌표가 필요 없는 것)을 끼워 넣는다'),
 'PM-01':   dict(note_add=RC + ' 지연 원인을 사람이 아니라 **자원(로봇 1대)** 으로 기록한다 — 민범진은 막힌 동안 다른 작업을 했다'),
}
for _tid, _e in ROBOT_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 10:05 오전도 작업 시간(황인재) → 민범진을 지금 바로 로봇에, 전체를 두 시간 더 앞으로
AM = '🔄 9/21 10:05 재배치(오전도 작업 가능 · 황인재):'
MORN_0921 = {
 'V-05':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전'),
                  note_add=AM + ' **오후 14:00 → 지금(오전) 바로.** 이틀 로봇을 못 잡았고 좌표와 무관하므로 남은 오전(약 3 h)을 민범진이 먼저 쓴다. 60분: V-05 → V-23 → V-01 → V-02'),
 'V-23':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전')),
 'V-01':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전')),
 'V-02':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전')),
 'INF-02c':  dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전')),
 'INF-02d':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 오전')),
 'CELL-03':  dict(slots=S('9/20 오전', '9/20 오후', '9/21 오전')),
 'CELL-02b': dict(slots=S('9/21 오전'), note_add=AM + ' 오후 14:00 → **오전**(작업대 작업이라 민범진이 로봇을 쓰는 동안 나란히). 끝나야 툴 홀더·SOAP 티칭을 한다'),
 'SAFE-01':  dict(slots=S('9/21 오전', '9/21 오후', '9/22 오전')),
 'F1-02':    dict(slots=S('9/21 오전', '9/21 오후'), note_add=AM + ' 코드는 **오전부터**(책상) → 실기를 **오후 17:30~18:30 으로 당긴다**(저녁 → 오후). 프리셋은 오전 그리퍼 세션에서 나온다'),
 'V-14':     dict(slots=S('9/21 오후'), note_add=AM + ' F1-02 실기와 같이 — 저녁 → 오후'),
 'CELL-04':  dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 오전', '9/21 오후'),
                  note_add=AM + ' 값·좌표 마무리와 PR 은 오전에(F4) → 티칭은 오후 14:30~16:30'),
 'V-24':     dict(slots=S('9/20 오후', '9/21 오후', '9/22 오전'), note_add=AM + ' 실기 확인을 **오후 14:00** 으로(값 PR 이 오전에 merge 된 뒤)'),
 'F3-02':    dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=AM + ' 닦기 3회를 **저녁 첫 순서 18:30** 으로(20:30 → 18:30)'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-25':     dict(slots=S('9/21 저녁'), note_add=AM + ' 저녁 19:10(20:10 → 19:10)'),
 'V-07':     dict(slots=S('9/21 저녁', '9/22 오전'), note_add=AM + ' 민범진 두 번째 순서를 **19:35~** 로 당긴다(20:35 → 19:35) — 오후 티칭에서 WASTE 자세를 다시 찍은 뒤'),
 'INT-12a':  dict(slots=S('9/21 저녁', '9/22 저녁'), note_add=AM + ' 저녁에 시간이 남으면 **오늘 착수**(20:40~) — L2 를 하루 앞당길 기회'),
 'BRF':      dict(note_add=AM + ' 오늘 오전도 작업 가능(강의가 비었다) — 로봇을 아침에 배분했으면 이틀 밀린 검증을 더 빨리 풀 수 있었다'),
}
for _tid, _e in MORN_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 10:15 황인재: 좌표 작업이 가장 먼저 — 로봇 순서를 좌표 우선으로
FIRST = '🥇 9/21 10:15 황인재: **좌표 작업이 가장 먼저**'
COORD_FIRST = {
 'CELL-04':  dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 오전', '9/21 오후'),
                  note_add=FIRST + ' — 오늘 로봇 순서의 **1번**이다. 오전: 값 마무리·PR(책상) → V-24 이동 함수 실기 → **티칭 착수**, 오후: 티칭 마무리 → V-22·V-19. 뒤의 모든 실기(집기·닦기·F2)가 이 좌표 위에서 돈다 — 9/21 08:00·08:40 에 드러난 경로 문제(손목 특이점 · 팔레트 걸림 · 6번 관절 163° 회전)를 먼저 잡지 않으면 남이 같은 곳에서 막힌다'),
 'V-24':     dict(slots=S('9/20 오후', '9/21 오전', '9/22 오전'), note_add=FIRST + ' → 이동 함수 실기를 **오전**으로(값 PR 직후). 티칭이 이 코드로 돈다'),
 'CELL-04b': dict(slots=S('9/20 오후', '9/21 오전', '9/21 오후', '9/22 오전')),
 'V-22':     dict(slots=S('9/21 오후'), note_add=FIRST + ' → 티칭 마무리 직후 오후에'),
 'V-19':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 # 민범진 — 좌표 뒤로. 다만 값 작업(책상) 동안 로봇이 비면 그때 끼워 넣는다
 'V-05':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후'),
                  note_add=FIRST + ' → 그리퍼 세션은 **좌표 뒤(오후)**. 🔸 다만 좌표의 **값 마무리는 책상 작업이라 그동안 로봇이 빈다** — 그 시간(오전)에 끼워 넣으면 좌표를 늦추지 않는다(황인재 판단). 좌표 실기가 시작되면 바로 로봇을 넘긴다'),
 'V-23':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'V-01':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'V-02':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'INF-02c':  dict(slots=S('9/20 오전', '9/20 오후', '9/21 오후')),
 'INF-02d':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 오후')),
 'F1-02':    dict(slots=S('9/21 오전', '9/21 오후', '9/21 저녁'), note_add=FIRST + ' → 집기 실기는 좌표·프리셋 뒤 — 오후 늦게나 저녁 첫 순서로'),
 'V-14':     dict(slots=S('9/21 오후', '9/21 저녁')),
 'INT-12a':  dict(slots=S('9/22 저녁'), note_add='9/21 10:15: 오늘 착수는 무리 — 좌표를 먼저 하기로 해 저녁이 다시 찬다'),
}
for _tid, _e in COORD_FIRST.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 10:20 황인재: 2차 티칭 일정을 잡지 않는다(E14) — 좌표 수정은 요청 기반
E14 = '🔁 9/21 10:20 황인재(결정 E14): **2차 티칭 일정 없음**'
NO_2ND = {
 'CELL-04':  dict(note_add=E14 + ' — 좌표는 **9/21 안에 한 번에 전부** 찍어 끝낸다. 그 뒤 F1~F3 이 기능 함수를 만들다 이상한 자리를 만나면 **그때 요청**하고 황인재가 확인해서 고친다(통합 중 요청 기반 수정). 요청 3줄: ① 설정 키 이름(예 `stations.WASTE.BOWL`) ② 무엇이 몇 mm 어느 방향으로 이상한지 / 자세가 안 나오는지 / 가는 길에 걸리는지 ③ 지금 막혔는지 나중이어도 되는지'),
 'CELL-04b': dict(slots=S('9/20 오후', '9/21 오전', '9/21 오후'),
                  note_add=E14 + ' → 9/22 오전 여유 칸을 뺀다. 값(limits·motion·좌표)은 9/21 오후까지 · 프리셋 6개는 그리퍼 세션 직후 채운다'),
}
for _tid, _e in NO_2ND.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 11:00 결정 E15 — 경로 제약 3가지(몸통 가로지르기 금지)
E15 = '🚧 9/21 결정 E15(경로 제약)'
PATH15 = {
 'F1-04': dict(note_add=E15 + ' → **`cell.rack.via` 경유 필수**(HOME 의 x·y·방향 그대로 z 338). 곧장 칸으로 가면 손목 J4 가 휘둘려 몸통에 부딪힌다(황인재 실기 2회 실패 — 한석형 스크립트에 있던 자세가 cell.yaml 로 옮길 때 빠졌다). 그릇 칸은 놓은 뒤 `exit_rel_mm`(y −25 → z +100)으로 빠져나온다 — 곧장 올라가면 그리퍼가 팔레트에 걸린다. 담당: 한석형'),
 'F2-01': dict(note_add=E15 + ' → **털기 반복(`leftover_loop`)에 HOME 경유 추가**. 잔반통 그릇 자세를 로봇 뒤쪽 posj 로 옮겨서, 잔반통(뒤) ↔ 스펀지 홈·저울·반납 구역(앞) 사이를 곧장 가면 로봇 몸통을 가로지른다. 담당: 민범진'),
 'V-07':   dict(note_add=E15 + ' → 털기 자세가 **로봇 뒤쪽**으로 바뀌었다(posj [-180, 0, 90, 0, 90, 0]) — 진폭·속도 확인을 새 자세에서 다시 한다'),
 'SAFE-01':dict(note_add=E15 + ' → 안전 대책에 한 줄 추가: "팔이 쭉 펴지는 자세(J3 ≈ 0°)를 티칭하지 않는다 · 잔반통(뒤)과 앞쪽 자리 사이는 HOME 을 거친다". 9/21 08:40 케이블 꼬임의 원인은 손목(J6)이 아니라 **팔꿈치 특이점(J3 = 1.7°)** 이었다'),
 'CELL-04':dict(note_add='📋 9/21 11:00 F4 회신 — 오늘 남은 좌표 **11개**: 안 찍은 자세 4(SOAP BOWL·CUP · ISOLATE BOWL·CUP) · 다시 찍을 것 4(WASTE CUP 은 그릇 잔반통과 615 mm 떨어져 있다 · TOOL_SPONGE.pick 은 J6 −220° · RET_B slots[1] 접근점 2.78 mm 어긋남 · RACK_C2 접근점이 끝점 위가 아님) · 새 접근점 3(RACK_B1·B2 · rack.via 는 HOME 에서 `--where` 로 읽어 계산). RINSE 접근점 2개는 임시값으로 넣고 실기에서 숫자만 조정'),
}
for _tid, _e in PATH15.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 11:30 민범진 회신 — 막힌 진짜 원인은 그리퍼 드라이버(pymodbus) + 분담
DRV = '🚨 9/21 11:30 민범진 회신 — **지연 원인 정정: 로봇 경합이 아니라 그리퍼 드라이버가 안 뜬 것**'
FIX = ('OnRobot 드라이버가 0.8 초 만에 죽는다 — **pymodbus 미설치**. 배포본 `onrobot_rg_control/setup.py:17` 이 `pymodbustcp` 로 잘못 적혀 있어 자동 설치가 안 된다'
       '(코드는 `from pymodbus.client import ModbusTcpClient` — PM 확인 ✅). 조치: `sudo apt install python3-pymodbus`(3.6.9). '
       '🚨 pip 최신(3.7+)은 인자가 `slave=` → `device_id=` 로 바뀌어 드라이버가 또 죽는다(코드가 `slave=` 를 쓴다 — PM 확인 ✅). '
       '확인: `ros2 node list | grep -i onrobot` → `/dsr01/OnRobotRGControllerServer` 가 보이면 정상. '
       '🚨 **PC 4대 전부 확인** — PM 이 이 PC(PC-B)에서 확인하니 여기도 없었다')
GRIP_BLOCKED = {
 'V-05':   dict(note_add=DRV + ' · ' + FIX + ' → 이것만 풀리면 V-01·V-23·V-02·V-16 은 바로 돈다(코드·절차는 준비돼 있다)'),
 'V-01':   dict(note_add=DRV + ' — 드라이버가 떠야 폭을 읽는다. 9/21 11:30 기준 미완'),
 'V-23':   dict(note_add=DRV + ' — 9/21 11:30 기준 미완'),
 'V-02':   dict(note_add=DRV + ' — 9/21 11:30 기준 미완'),
 'V-16':   dict(note_add=DRV + ' — 9/21 11:30 기준 미완'),
 'V-07':   dict(note_add='📐 9/21 민범진 Virtual 시험대(9/20 기록 중 **E7 뒤에도 유효한 것**): 털기가 주기당 약 **0.35 s 느리다** → `period_s` 를 정할 때 반영. '
                         '❌ 무효가 된 기록: "move_to 가 안전 높이를 왕복한다"(E7 로 없어짐) · ⚠ 용기 1개 소요 시간(12 s/30 s)은 다시 재야 한다'),
 'FLOW-01':dict(prog='0.9', note_add='✅ 9/21 11:30 민범진: kind 전달(flow steps·sense._goto·시험) · GRIP_FAIL = pause **+ 재개 의미 버그 수정** — PAUSE 갈래가 재개 뒤 "다음 용기"로 가서 그 용기를 버리고 있었다 → IRD §8 대로 **실패한 그 단계부터 다시**. ROBOT_ERROR 만 다음 용기 + ERROR 기록(RACK_FULL 도 같은 버그였다). 덧붙임 2건(MoveIncomplete 후퇴 금지 · E15 HOME 경유)도 완료. **PR 올리는 일만 남았다** · 🟡 GRIP_FAIL 안내 문구는 다음에'),
 'ENV-03': dict(owner='H(M)', note_add='🔁 9/21 11:30 분담 — 민범진 → **황인재**(민범진 회신: "전부 넘겨도 됩니다"). 이미 9/22 오전 황인재의 로봇 불필요 칸에 들어 있어 추가 부담이 없다. 민범진은 PC-A 쪽만 확인해 준다'),
 'FLOW-02':dict(note_add='🔁 9/21 11:30 분담 — **둘로 나눈다**: ① 기록(records.csv)·소모품 카운트 = 넘길 준비됨(후보 **박진용** — F3 가 9/22 오후에 끝난다) ② `/cell/force`·`/cell/gripping` 발행 = **민범진이 계속**(gripper.py 를 아는 쪽이 빠르다는 본인 판단). ①을 실제로 넘길지는 9/22 오전 브리핑에서 민범진의 남은 양을 보고 정한다'),
 'UT-FLOW':dict(note_add='🔁 9/21 11:30 — **민범진이 그대로 한다**. 넘길 수는 있지만 정책 시험은 `test_f2_policy` 가 이미 많이 덮고 있어 새로 맡는 쪽이 더 오래 걸린다(본인 판단)'),
 'CR-01':  dict(note_add='🔁 9/21 11:30 — 전원이 하는 작업이라 분담 대상이 아니다(민범진 지적)'),
}
for _tid, _e in GRIP_BLOCKED.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 12:10 황인재: 환경 셋팅 작업은 전부 끝났다
ENVDONE = {
 'ENV-03': dict(status='완료', prog='1.0', slots=[],
                note_add='✅ 9/21 12:10 황인재: **환경 셋팅 작업은 전부 끝났다** — PC-A↔PC-B 가 DOMAIN 60 에서 서로의 토픽·서비스를 본다. '
                         'v10.2 에서 민범진 → 황인재로 넘겼던 것인데 그 사이에 끝나 분담 자체가 없어졌다. 환경 4건(ENV-01·02·03·04)이 모두 완료다'),
}
for _tid, _e in ENVDONE.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 12시대 민범진 보고 → 결정 E16(D-A~D-E) + 진행률 정정
E16 = '📌 9/21 결정 E16'
M_REPORT = {
 'V-05':     dict(prog='0.7', note_add='📈 9/21 민범진 실기 확인값: 브링업 직후 **40.0 N** · `d` 한 번에 40.0 → 37.5 N · **빈손 닫힘 폭 10.5~10.9 mm(0 이 아니다)** · 완료 판정을 폭으로 바꾸니 **0.20~0.34 s**(전에는 매번 10 s 타임아웃). 남은 것: 자로 대조 1회 · 본 측정. 새 산출물 `src/cobot_common/test/rig_gripper_probe.py`(고치기 **전에** 드라이버 실동작을 보는 읽기 전용 시험대 — 위 두 결함을 이것으로 찾았다)'),
 'V-01':     dict(note_add=E16 + ' D-A ㉠ — **폭 판정은 영점을 뺀 값으로**. V-01 에서 종류별 `grip_zero_mm`(빈손 꽉 닫힘 폭)을 **그 종류의 파지 힘으로** 같이 잰다(영점이 힘에 따라 0.2~0.4 mm 달라진다). 값 3쌍: 빈손·그릇·컵 × 10회'),
 'V-23':     dict(prog='0.5', note_add='📈 9/21 민범진: 힘 전환 **방법 확정 + 코드 반영**(현재 힘을 읽어서 맞춘다 — 드라이버가 힘을 기억해 40→35→30→25 N 으로 흘러서 "브링업 직후 40 N" 전제를 못 쓴다). 남은 것: 실기 전환 10회 낙하 0. ' + E16 + ' D-E: 9/20 D1(힘 기준 잡는 쪽) **철회** · **D2(HOLD → NORMAL 되돌리기)는 이 실기 뒤에 정한다**'),
 'V-02':     dict(status='시작 전', prog='0.0', slots=S('9/21 저녁', '9/22 오전'),
                  note_add=E16 + ' **D-C: 오후 세션에서 빼고 저녁 2차로** — 60분에 V-05·V-23·V-01 까지가 한계(민범진 산정 50분)이고, **WEIGH 자세가 오늘 티칭에서 바뀌므로 빈 용기 기준값은 티칭 뒤에 재는 것이 맞다**. '
                           + E16 + ' **D-D: 완료 기준을 바꾼다** — 옛 기준 "±20 g"(절대 오차)는 의미가 없다. 로봇 하중에 항상 +42~45 g 옵셋이 있는데 잔반 판정이 `측정값 − 빈 용기값` 이라 **옵셋이 상쇄**된다. '
                           '🆕 새 기준: **같은 추 10회의 (최대−최소) ≤ 20 g**(잔반 임계 50 g 의 절반 이하) · 중앙값의 절대 오차는 **기록만**. 전용 도구는 만들지 않고 `rig_f2.py empty` 로 한다. 9/18 기록은 펜던트 화면 판독이라 진척으로 안 센다'),
 'INF-02d':  dict(prog='0.95', note_add='📈 9/21 민범진: 코드 끝(`0893b78` — `_anchor_force` 삭제 · 완료를 폭으로 판정 · 안전 스위치 감지). 남은 것은 **실기 재확인뿐**'),
 'INF-02c':  dict(note_add='9/21: 코드는 9/19 merge 됐고 남은 것은 V-02 와 한 덩어리 — V-02 가 0 이라 진행률을 올리지 않는다(민범진)'),
 'FLOW-01':  dict(status='완료', prog='1.0', note_add='✅ 9/21 PR #48 merge(main `65d590f`) — kind 전달 · GRIP_FAIL=pause + **재개 의미 버그 수정**(PAUSE 재개가 그 용기를 버리고 있었다 · RACK_FULL 도 같은 버그) · MoveIncomplete 후퇴 금지 · E15 HOME 경유. PM 검토: 두 환경 326 passed'),
 'FLOW-03':  dict(status='진행', prog='0.15', note_add='9/21: 이 항목에 든 **MoveIncomplete 분기를 먼저 넣었다**(`be52062`). 남은 것은 `cc.pause`·`resume`·`abort` 연결'),
 'F2-01':    dict(prog='0.85', note_add='📈 9/21 민범진 Virtual 재검증 **24/24 통과** — 도착 오차 < 1 mm · 흔든 뒤 J5 복귀 오차 0.00° × 3 · `leftover_loop` 이동 순서 `WEIGH → HOME → WASTE → HOME → WEIGH`(E15). 새 산출물: `rig_f2_virtual.py` 의 `loop` 모드(`leftover_loop` 이 시험대에 아예 없었다). 남은 것: V-07·V-16 실기'),
 'F2-02':    dict(prog='0.8', note_add='📈 9/21 Virtual 재검증에 `dip` 3회 포함'),
 'V-07':     dict(note_add='🚨 9/21 민범진 실측 정정 — 털기 한 주기가 설정 0.60 s 인데 **9/20 0.954 s → 9/21 1.099 s**(V-24 비동기 이동·폴링 뒤 0.15 s 더 늘었다 · 4주기 1회가 4.46 s, 설정대로면 2.40 s). '
                           '앞서 적은 "주기당 0.35 s" 를 **"주기당 약 0.5 s 느리게 돈다"** 로 고친다 — `period_s` 를 정할 때 이 전제로. 털기는 빠르기가 잔반을 떨어뜨리는 요인이라 무시할 수 없다. 🚨 **WASTE 자세 재티칭 뒤에만** 가능(민범진이 오후 티칭에 입회)'),
 'V-16':     dict(note_add='🚨 9/21: **V-23(힘 전환)이 먼저** 돼야 한다. 또 ' + E16 + ' D-A 로 폭 판정이 영점 뺀 값이 되므로, "폭 변화 ≤ 2 mm" 기준에 **힘이 바뀔 때 영점이 0.2~0.4 mm 움직이는 것**을 포함해 잡는다'),
 'UT-FLOW':  dict(note_add='9/21 민범진: 정책·재개·실패 주입은 자동 시험이 이미 상당 부분 덮는다(F2 pytest 98건) — 남은 것은 `flow_node` 를 실제로 띄워 HMI·Ctrl+C 까지 보는 것(반나절). 🚨 **TC-12(기록)는 FLOW-02 가 전제** — FLOW-02 기록·소모품을 박진용에게 넘기면 **TC-12 만 그 뒤로** 미룬다'),
 'CELL-03':  dict(note_add='🚨 9/21 민범진: 남은 3가지(고정 · 배치 사진 · 잔반 대용품 ≥ 100 g)를 오늘 아직 손대지 못했다 — 오늘 안에 끝내야 V-07 털기가 돈다'),
 'CELL-04':  dict(note_add=E16 + ' **D-B: `ISOLATE.BOWL`·`ISOLATE.CUP` 을 오늘 티칭에 반드시 넣는다**(SOAP 2개와 함께 앞쪽으로). 없으면 `/flow/abort` 정리 순서(HOME → 툴 반납 → ISOLATE → HOME)와 실패 정책의 `isolate` 갈래를 **실기로 확인할 수 없고**, E14 로 2차 티칭이 없다(민범진 요청). '
                           '🆕 같이: `cell.presets.<kind>.grip_zero_mm` 키 4개를 양식에 추가(값은 V-01 에서 잰다 · ' + E16 + ' D-A ㉠)'),
}
for _tid, _e in M_REPORT.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 13시대 박진용 회신 → 결정 E17 + 로봇 시간 재배치
E17 = '📌 9/21 결정 E17'
P_REPORT = {
 'V-10':     dict(status='진행', prog='0.5', slots=S('9/21 저녁'),
                  note_add='📈 9/21 박진용: **가상 검증 끝, 실기만 남음** — 값 확정: **위아래 40 mm · 비틀기 ±18° · 띄우기 2 mm** + 세척 속도(SR-09 "각도는 V-10 에서" → ±18°). '
                           + E17 + ' `move_periodic` 회전은 손목(J4)을 기울여 쓰지 않고 **직선을 이어 붙인다**. 🗓 실기는 **오늘 저녁 첫 순서(60분)** — 오후 로봇은 좌표·그리퍼·집기로 차 있다(가장 밀린 F1·F2 먼저)'),
 'F3-03':    dict(slots=S('9/21 저녁', '9/22 오전'),
                  note_add='📈 9/21 박진용: `wipe_cup` 코드 완료(가상) → **오늘 저녁 V-10 과 같이 실기**. `soap` 은 그다음 — **9/22 오전 첫 순서(90분)**, SOAP 좌표가 오늘 티칭에 들어간다(툴·홀더 확정 ✅)'),
 'F3-02':    dict(slots=S('9/21 저녁'),
                  note_add='📈 9/21 박진용: **오늘 바뀐 방식으로 실기 재검증**(60분 · 저녁 두 번째) — ' + E17 + ' 닦기는 HOME 에서 시작해 HOME 으로 끝남(F3 가 직접 복귀) · 그릇은 HOME 바로 아래 → 135 mm 빠르게 → 3 mm 씩 바닥 찾기 · 바닥은 힘으로만. 🔎 PR 에서: 거리(135·40·140·80 mm)가 코드가 아니라 `params.yaml` `f3` 절에 있는지'),
 'V-18':     dict(slots=S('9/21 저녁'), note_add='9/21: F3-02 재검증과 같은 시간(저녁 두 번째)'),
 'CELL-02b': dict(status='완료', prog='1.0', slots=[],
                  note_add='✅ 9/21 박진용: **툴·홀더는 지금 상태 그대로 간다 — 추가 변경 없음** → 툴 홀더 자세 2종 · SOAP 2개를 바로 티칭(' + E17 + '). 그릇 받침 유격은 E13 ⑤ 로 완료 기준에서 뺐다'),
 'SAFE-01':  dict(note_add='✅ 9/21 박진용 확인: **stop_mode = 1(DR_QSTOP) 맞다** — 최대 감속 정지(Stop Category 2)라 서보 전원·위치 유지 → 일시 정지 뒤 재개 가능 · SSTOP 은 감속 시간 약 1.5배 · QSTOP_STO 는 전원 차단(Category 1)이라 재개 흐름과 안 맞음(중급교육1 p.104~105). 확인 칸·🟡 줄 채우기 + 안전 대책 두 줄(위치 불명 뒤 자동 이동 금지 · J3≈0° 금지/HOME 경유 E15) 추가 예정. ⚠️ 표에 한 줄 더: **F3 세척 속도는 vel_scale 예외(E17)** — 0.3 으로 띄워도 닦기는 감속되지 않는다'),
 'V-26':     dict(note_add='✅ 9/21 박진용: stop_mode = 1(DR_QSTOP) 확인 완료 — 바꿀 필요 없음. 실기 때 같이 본다'),
 'CELL-04':  dict(note_add=E17 + ' **`SPONGE_BED_B/C.wash` 좌표는 티칭하지 않아도 된다**(F3 가 안 쓴다 — HOME 기준 상대 이동으로 바뀜). 🚨 **대신 HOME 을 다시 찍지 않는다** — 닦는 자리가 HOME 기준이라 HOME 이 움직이면 닦는 자리가 같이 움직인다. 툴 홀더 2종 · SOAP 2개는 **툴·홀더 확정(CELL-02b ✅)** 으로 바로 찍어도 된다'),
 'FLOW-02':  dict(note_add='🔁 9/21 13시대 확정: **민범진이 계속한다** — 후보였던 박진용은 오늘 18:30 까지 F3 세 개 · 저녁 F3 실기 · 9/22 soap·UT-F3·INT-13 으로 여력이 없다(' + E17 + ' ⑤)'),
 'UT-FLOW':  dict(note_add='9/21: FLOW-02 가 민범진에게 남아 TC-12 도 뒤로 밀 필요가 없어졌다'),
 'CELL-03':  dict(note_add='🔁 9/21 13시대: **민범진이 계속한다**(박진용에게 넘기지 않음 — ' + E17 + ' ⑤). 민범진은 책상 작업이 끝났고 로봇을 기다리는 중이라 **지금(그리퍼 세션 전)** 할 수 있다 — 이게 있어야 저녁 V-07 털기가 돈다'),
}
for _tid, _e in P_REPORT.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 오후 F4 회신 → E15 ④ · E18 + PR #50 변경 요청
F4PM = {
 'CELL-04':  dict(note_add='📈 9/21 오후 F4: **남은 티칭은 ISOLATE 1곳(그릇·컵 공용)뿐** — SOAP·툴 홀더·rack.via·WASTE.CUP 은 끝났다(SOAP 은 E18 로 계산값 · WASTE.CUP 은 그릇과 같은 통 posj · rack.via 는 HOME 실측에서 z 만 338). 팔레트 그릇 칸 실기 오차 0.16~0.24 mm. 🚨 **팔레트에 부딪힌 사고 1건** → E15 ④. 팔레트가 밀렸는지 확인 대기(밀렸으면 RACK_B1·B2 재티칭)'),
 'F1-04':    dict(note_add='🚧 9/21 E15 ④(황인재): **팔레트에서 다른 구역으로 갈 때는 HOME 을 거친다** — 팔레트 그릇 칸 → 컵 반납 구역을 곧장 가다가 로봇이 팔레트에 부딪혔다(팔레트 자세 J4 101°·J6 −118°). 팔레트 칸끼리는 곧장 가도 된다. 🔓 구현하면서 필요 없다고 판단되면 **실기 근거와 함께** 빼고 PM 에 알린다'),
 'FLOW-01':  dict(note_add='🚧 9/21 E15 ④: flow 의 RACK 다음 단계는 HOME 을 거친다(지금 steps 는 rack_place 뒤 move_to HOME 이라 맞다 — 새 단계를 넣을 때 주의). 🔓 필요 없으면 근거와 함께 뺄 수 있다'),
 'F3-03':    dict(note_add='🔄 9/21 E18(황인재): **세제 수조를 따로 두지 않는다 — 툴 홀더의 비눗물 컵에서 위아래로 담근다.** SOAP 자세 = 툴 홀더 좌표 + `f3.soap.depth_mm`(40) 계산값(🟡 BOWL z 105.24 · CUP z 167.27). 🚨 **depth_mm 을 바꾸면 SOAP 의 z 도 같이** 바꿔야 한다'),
 'CELL-03':  dict(note_add='🔄 9/21 E18: 세제 수조가 없어져 **수조는 헹굼 1개만** 고정하면 된다(잔반통 1 + 헹굼 수조 1 + 잔반 대용품)'),
 'FLOW-03':  dict(note_add='🔴 9/21 PR #50 **변경 요청**(PM): 이동 도중 중단 경로에서 `stop`·`abort` 깃발이 안 내려가 — 마지막 용기였으면 **다음 실행의 GRIP_FAIL 이 사람 확인 없이 자동 중단 정리**된다(mock 재현 확인). 고치는 법 3줄(abort_container 에서 깃발 내리기 · run_plan 시작에서 abort 도 지우기 · 용기 사이 wait_resume 반환값 처리) + 시험 2개. 나머지(is_paused 로 막다른 길 막기 · ROBOT_ERROR 에서 abort 거부 · 콜백은 깃발만)는 맞다'),
}
for _tid, _e in F4PM.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 오후 PR #51 merge — 좌표 마감(임시 좌표)
Y51 = '🟡 9/21 PR #51(좌표 마감 · 임시 좌표) — **실기 미확인**'
PR51 = {
 'CELL-04':  dict(status='완료', prog='1.0',
                  note_add='✅ 9/21 PR #51 merge(main `8643b82`) — **빈 자세 0개**, 남은 빈 값은 그리퍼 프리셋뿐(V-01·V-05). 🔔 **임시 좌표**(황인재): 기능을 구현하다 수정이 필요하거나 필요 없는 동작이 보이면 **직접 수정·삭제한 뒤 보고**(① 설정 키 ② 무엇이 어떻게 ③ 무엇으로 바꿨는지 · 실기 근거). 좌표 등급표(✅ 실기 확인 / 🟡 티칭 미확인 / 🟡 계산값 / ⚪ 안 씀)는 PR #51 본문'),
 'CELL-04b': dict(status='완료', prog='1.0',
                  note_add='✅ 9/21 PR #51 merge — limits·motion·beds.seat 값 · rig 안전 수정(실기에서 이동 실패 시 자동으로 안 움직임 · STANDBY 아니면 멈춤 — 연결 끊긴 브링업의 [0,0,0,0,0,0] 을 좌표로 적는 것 방지) · motion.py 가 거부(-1) 때 로봇 상태를 오류 문구에. PM 검토에서 rig ③ 구간이 채워진 자세로 확인 없이 움직이던 것을 고치고 merge(회귀 시험 추가)'),
 'V-22':     dict(note_add='✅ 9/21 PR #51: 그릇 쪽 · 팔레트 그릇 칸(0.16~0.24 mm) · 격리 자리 실기 확인. ' + Y51 + ': 컵 한 바퀴(반납 구역 컵 ~ 헹굼 컵) · 팔레트 컵 칸 2개 · 툴 홀더'),
 'F1-04':    dict(note_add=Y51 + ': **팔레트 컵 칸의 `exit_rel_mm`**(그릇 칸과 같게 y −25 → z +100 — 전에는 접근점으로 수직 복귀) · `rack.via` 계산값 — 처음 돌릴 때 눈으로. 그릇 칸은 "칸 바로 위 → z 만 하강 → 빼기" 실기 확인(내려온 뒤 y 로 밀기는 칸막이 벽에 걸려 철회)'),
 'F2-02':    dict(note_add=Y51 + ': **`RINSE.CUP` 끝점 144.33 → −13.6**(158 mm 내림 — 같은 수조인데 그릇보다 158 mm 높아 수조에 안 닿았다) · RINSE 접근점 2개(z 150) 계산값 → 🚨 처음 내려갈 때 반드시 눈으로 보며 Enter'),
 'F3-03':    dict(note_add=Y51 + ': SOAP 2개는 툴 홀더 + 40 계산값(E18) — 내일 오전 soap 실기 때 처음 확인'),
 'FLOW-03':  dict(note_add=Y51 + ': **격리 자리(ISOLATE)는 "HOME → 허리만 −264° → 팔 뻗기" 경로만 확인됐다.** posj 로 곧장 관절 이동하면 허리를 돌리며 팔을 뻗어 툴 홀더·수조 위를 멀리 지난다(미확인) → abort 첫 실기 때 E-Stop 에 손을 두고'),
}
for _tid, _e in PR51.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 오후 황인재 확인 3건 — 팔레트 복귀 · HOME 경유 · 구현 방식 > 임시 좌표
RACKMOVED = {
 'F1-04': dict(note_add='🚨 9/21 오후: 팔레트가 충돌 때 **실제로 밀렸고 황인재가 손으로 원위치**했다 → RACK_B1·B2 는 오늘 0.16~0.24 mm 로 확인됐지만 **복귀 뒤로는 미확인**(rig 오차는 로봇 정확도만 재고 팔레트 위치는 못 잡는다 — 눈으로만 확인). '
                         '→ **첫 적재 실기 전에 2분 재확인**: `rig_coords.py --real --from 15 --skip 16,18` 로 그리퍼가 칸 **한가운데**로 내려가는지 본다. 안 맞으면 E14 보완대로 직접 고치고 보고. 🟢 팔레트 바닥에 **테이프로 위치 표시**(다시 밀려도 원위치를 알 수 있게)'),
 'CELL-04': dict(note_add='🔁 9/21 오후 황인재: **구현 방식 > 임시 좌표** — 좌표가 기능에 맞춰 바뀌는 것이지 기능을 좌표에 맞출 필요는 없다. 만드는 방식에 따라 좌표가 바뀌거나 아예 필요 없어질 수 있다(사례: E17 로 SPONGE_BED wash 2개가 필요 없어짐). HOME 경유(E15 ④)는 "필요할 때만"'),
}
for _tid, _e in RACKMOVED.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 16시대 한석형 — 그릇 칸 경유점을 실기값으로(E14 보완 적용 사례)
EDIT.setdefault('F1-04', {}).setdefault('note_add', '')
EDIT['F1-04']['note_add'] = (EDIT['F1-04']['note_add'] + ' · ' if EDIT['F1-04']['note_add'] else '') + (
    '🔁 9/21 14시 한석형(E14 보완 — 직접 수정 후 보고): **그릇 칸 경유점 = 실기값 posj [-8, 0, 107.8, 86.2, 101.5, -108]** — 그릇을 든 채 HOME → 경유 → B1 접근 → 하강 → 놓기 → y −25 → z +100 을 간섭 없이 확인. '
    'rack.via(HOME 위 z 338 · 계산값) 대신. PM 권고: `stations.RACK_B_VIA` 로 두면 코드 수정 없이 `cc.move_to` 로 부를 수 있다(move_to 는 stations·beds·zones·rack.slots 에서만 이름을 찾는다 — 지금 rack.via 는 부를 수 없는 자리). 컵 칸은 rack.via 유지(실기값이 생기면 같은 방식). RINSE.CUP 은 main 값 그대로(한석형)')
# ---------------------------------------------------------------- 9/21 16시대 V-22·V-19 실기 기록(main 81331f9)
VLOG = {
 'V-22': dict(status='완료', prog='1.0', slots=S('9/21 오전', '9/21 오후'),
              note_add='✅ 9/21 실기 기록(docs/test_logs/20260921_V-22_V-19_좌표재현_황인재.md): 도착에 성공한 모든 자세 **0.00~0.24 mm** · 관절 자세 ≤ 0.03° → 완료 기준 ≤ 2 mm **통과**'),
 'V-19': dict(status='진행', prog='0.8',
              note_add='🟡 9/21 실기: **부분 통과** — 팔레트 **컵 칸 2곳 미확인**(경유 자세를 넣은 뒤 아직 안 돌림) · 손목 큰 회전 경고 5구간. 남은 것은 한석형 F1-04 적재 실기에서 컵 칸을 돌 때 같이 닫는다(E14 보완 — 경유점도 한석형이 실기로 정한다)'),
}
for _tid, _e in VLOG.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #50 merge — FLOW-03 코드 완료
EDIT.setdefault('FLOW-03', {}).update(dict(status='진행', prog='0.8',
    note_add='✅ 9/21 PR #50 merge — /flow/stop = 즉시 정지(cc.pause) · /flow/resume(cc.is_paused 로 막다른 길 막음) · 🆕 /flow/abort(PAUSED 에서만 · ROBOT_ERROR 면 거부 · 정리 순서 HOME → 툴 반납 → 격리 → HOME). PM 검토에서 찾은 결함(이동 도중 중단 뒤 깃발이 남아 다음 실행의 GRIP_FAIL 이 사람 확인 없이 중단 정리됨)을 고친 뒤 merge — 재현 시험 통과. **남은 것 = abort 실기**(격리 자리 가는 길 미확인 → E-Stop 에 손을 두고)'))
# ---------------------------------------------------------------- 9/21 16시대 민범진 지적 — E17 코드가 main 에 없다 · SAFE-01 진척 정정
P_FIX = {
 'SAFE-01': dict(status='진행', prog='0.8',
                 note_add='📈 9/21 정정: **확인 칸은 박진용이 오전에 이미 다 채웠다**(PR #47 merge 10:08 · 🟡 0줄) — 일정표가 0.0 으로 남아 있었다. 남은 것: ① **실측 4줄**(오늘 저녁 닦기·컵 바닥 찾기에 얹어 채움 — 실측 기록지는 박진용 브랜치에 있고 main 에 없다) ② PM 이 부탁한 **안전 대책 3줄**(위치 불명 뒤 자동 이동 금지 · J3≈0°·HOME 경유 · F3 세척 속도 vel_scale 예외)'),
 'F3-02':   dict(note_add='🚨 9/21 14시(민범진 지적 · PM 확인): **E17 의 바뀐 닦기 코드(HOME 시작·끝)가 아직 main 에 없다** — 박진용 PC 에만 있고 원격 브랜치에도 없다. main 의 wipe.py 는 옛 방식(안전 높이에서 끝, HOME 복귀는 flow). → 오늘 저녁 실기 뒤 **PR** 필요(INT-13 · flow 통합이 main 기준으로 돈다)'),
 'F3-03':   dict(note_add='🚨 9/21 14시: wipe_cup 의 바뀐 코드(직선 이어 붙이기 · HOME 시작·끝)도 main 에 없다 — F3-02 와 같은 PR 로'),
 'FLOW-01': dict(note_add='9/21 14시 민범진: flow 에는 wipe 앞뒤 move_to(HOME) 이 없다 — 더하거나 뺄 것 없음. F3 가 끝나는 자세(E17 전: 안전 높이 / 후: HOME)에 따라 **툴 반납까지 가는 경로**가 달라진다 → 첫 실기 때 그 구간을 눈으로'),
}
for _tid, _e in P_FIX.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 15:40 진척 반영 — 저장소에 올라온 것 기준(박진용 V-10 브랜치 · 황인재 F4-03)
B = '`jinyong/20260921-V-10-cup`'
PROG_1540 = {
 'V-10':    dict(status='진행', prog='0.7',
                 note_add='📈 9/21 15:40(브랜치 ' + B + ' 11:27~15:33 커밋 기준 · main 미반영): **오후에 컵 실기를 대부분 진행했다.** 값이 바뀌었다 — '
                          '문지르기 = **올라가며 6번 축 360° 반시계 · 내려오며 반대로 360° × 3회**(비틀기 ±18° 에서 바꿈) · 컵 바닥 찾는 힘 **컵 전용 5 N**(공용 15 N 이면 컵이 스펀지 홈에 눌렸다) · 가장 낮은 자리 **바닥 + 4 mm**(2 mm 면 솔이 끼어 컵이 딸려 올라왔다) · 문지르기 속도 4배(F3 관리 · vel_scale 무관 — E17). '
                          '15:31 Move Periodic 한 명령(위아래 ±20 mm + 6번 축 ±180°) 시도 → 15:33 **되돌림**(실기에서 4번 축이 움직였다). '
                          '🔎 PM: 6번 축 360° 왕복은 오늘 08:40 케이블 꼬임(163°)을 생각해 **그리퍼 케이블이 당기지 않는지 · 6번 축 한계(±360°) 여유**를 확인할 것'),
 'F3-03':   dict(prog='0.8', note_add='📈 9/21 15:40: wipe_cup 실기 반영 코드가 ' + B + ' 에 있다(main 미반영) — V-10 과 같은 PR 로'),
 'F3-02':   dict(note_add='📈 9/21 15:40: E17 의 바뀐 닦기 코드(HOME 시작·끝 · 그릇 빠른 하강 135 mm · 바닥은 힘으로만)가 ' + B + ' 12:25 커밋에 있다(14시 확인 뒤 push — main 미반영). 그릇 재검증 실기는 아직 기록 없음'),
 'SAFE-01': dict(prog='0.9', note_add='📈 9/21 15:40: **안전 대책 4줄 + 컵 실기값 + 바뀐 닦기 반영**이 ' + B + ' 14:36 커밋에 있다(main 미반영). 남은 것: 실측 줄 · PR'),
 'F4-03':   dict(status='진행', prog='0.5', note_add='📈 9/21 15:40(브랜치 `injae/20260921-F4-03-hmi-screen` · PR 전): STEP 1 Next.js 15 화면 뼈대(hmi_bridge 가 / 에서 보여줌) · STEP 2·3 운영 화면(값 받기 + 화면 전체)'),
 'F1-03':   dict(note_add='9/21 15:40: tool PICK/RETURN 구현은 `injae/20260920-F1-03-tool`(9/20 22:11)에 있다 — PR 전 · 실기 미검증(V-08). 툴 홀더 좌표는 PR #51 로 main 에 들어왔다'),
}
for _tid, _e in PROG_1540.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #53 merge — 그리퍼 세션 결과 · 결정 E19(컵 고정 폭)
E19 = '📌 9/21 결정 E19(컵 고정 폭 · 파지 확인 생략)'
GRIP53 = {
 'V-05':  dict(status='완료', prog='1.0', note_add='✅ 9/21 PR #53 — 폭 경로 확인 끝. 영점은 힘과 무관(20·35 N 모두 10.50 — 오전의 "0.2~0.4 mm" 는 타임아웃 때문에 닫는 중간을 읽은 것)'),
 'V-01':  dict(status='완료', prog='1.0', note_add='✅ 9/21 PR #53 — **그릇 확정**: 영점 10.58 · 폭 2.15(실측 벽 두께 2 mm 와 일치) · tol 0.6 · 세 범위 겹침 없음. 컵은 ' + E19 + ' 로 폭 판정을 안 한다(해당 없음). 값은 F4 가 팀 cell.yaml 에'),
 'V-23':  dict(status='완료', prog='1.0', note_add='✅ 9/21 PR #53 — 그릇 NORMAL 20 ↔ HOLD 35 N 전환 10회 낙하 0. 컵은 ' + E19 + ' 로 HOLD 가 안 먹는다(고정 폭이라 다시 잡기가 없다). **D2 = ㉠(털기 끝나면 NORMAL 로 되돌리기) 로 닫음** — 힘을 낮출 때 미끄러짐 0'),
 'V-16':  dict(note_add='🔄 9/21 ' + E19 + ': **컵은 HOLD 가 없다** → 컵은 V-07 에서 "NORMAL 5 N 으로 털기를 버티나" 로 확인. 그릇은 35 N 이 V-23 에서 낙하 0'),
 'V-07':  dict(note_add='🚨 9/21 ' + E19 + ': 컵은 고정 폭 · HOLD 없음 · 놓쳐도 무게로만 안다(컵이 30 g 미만이면 모른다) → **컵으로 털기를 꼭 확인**. 그 전에 **78 mm 에서 컵이 실제로 들리는지**(들어 올려 당겨 보기) — 컵·빈손 차이 0.10 mm 라 손가락이 거의 안 닿았을 수 있다. 버티지 못하면 컵만 털기 진폭·속도를 낮춘다'),
 'F1-02': dict(note_add='🔄 9/21 ' + E19 + ': **컵 집기는 폭 판정·EMPTY_ZONE 을 쓰지 않는다** — `cc.grip(presets.CUP.grip_target_mm, grip_force_n)` 으로 정해진 폭까지만 닫는다(컵 있음은 HMI 개수 + 내리막 공급으로 보장). 그릇은 E16 폭 판정 그대로(영점 10.58 · 2.15 ± 0.6)'),
 'INF-02d': dict(note_add='9/21 PR #53: 시험대 결함 1건 고침(--target-mm 로 빈손이 통과하던 것) · 🟡 v01 이 컵을 20 N 으로 잡은 원인 미상(진단 로그 추가 — 안전 스위치가 걸린 직접 원인) → 컵 시험은 --force-n 5 를 명시'),
}
for _tid, _e in GRIP53.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #55 merge — 팀 cell.yaml 에 그리퍼 프리셋
P55 = {
 'INF-02d': dict(note_add='✅ 9/21 PR #55: **20 N 사고 원인 찾아 고침** — rig_gripper main() 이 --force-n 을 yaml 기본값(20 N)으로 미리 채워, "직접 줬을 때만 덮는다" 검사가 늘 참이 돼 컵도 20 N 으로 닫혔다(안전 스위치 작동의 직접 원인)'),
 'F1-02':   dict(note_add='✅ 9/21 PR #55: **프리셋이 팀 cell.yaml 에 들어갔다** — 그릇 영점 10.58 · 2.15 ± 0.6 · 20 N / 컵 grip_target_mm 78(E19 · 🟡 들리는지 미확인). 집기 실기가 풀렸다'),
 'V-07':    dict(note_add='✅ 9/21 PR #55: 프리셋이 들어가 grip_level KeyError 가 풀렸다 · rig_f2 에 grip/release 명령과 E15 HOME 경유가 생겼다'),
}
for _tid, _e in P55.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #56 merge — F3 닦기 main 반영 · 컵 세척 확정
P56 = {
 'V-10':    dict(status='완료', prog='1.0', note_add='✅ 9/21 PR #56 — **컵 세척 실기 확정**: Move Periodic 한 명령(TOOL z ±15 mm + **6번 관절 ±90°**) · 3.0 s × 5 · 바닥 + 3 mm · 컵 바닥 힘 5 N · 1·4번 관절 안 움직임(감시 — 1° 넘으면 즉시 정지) · 컵 안 딸려 옴. 오후의 6번 축 360° 는 ±90° 로 줄어 케이블 걱정도 덜었다'),
 'F3-03':   dict(prog='0.9', note_add='✅ 9/21 PR #56 merge — wipe_cup 코드 main 반영(HOME 시작·끝). 남은 것: soap 실기(9/22 오전 · SOAP = 툴 홀더 + 40 계산값)'),
 'F3-02':   dict(prog='0.85', note_add='✅ 9/21 PR #56 merge — **E17 닦기 코드(HOME 시작·끝 · 그릇 빠른 하강 135 mm · 바닥은 힘으로만)가 main 에 들어왔다.** 남은 것: 그릇 재검증 실기(rig_f3.py bowl) → 기록'),
 'SAFE-01': dict(note_add='✅ 9/21 PR #56 — 안전 파라미터 표·실측 기록지를 바뀐 닦기에 맞추고 **안전 대책 4줄** 추가(main 반영). 남은 것: 실측 줄'),
 'F1-05':   dict(note_add='🔎 9/21 PR #56 박진용 요청: `cell.limits.insert_limit_n`(15)은 컵 닦기가 더 이상 안 쓴다 · **`force_max_n` 15 와 여유 0** — 삽입·안착 힘 상한이 공용 최대와 같다 → F1 에서 판단(한석형)'),
}
for _tid, _e in P56.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #57 merge — 감시 정지 뒤 자동 이동 금지 · V-18 완료
P57 = {
 'V-18':  dict(status='완료', prog='1.0', note_add='✅ 9/21 박진용(PR #57): SAFE-01 실측 기록지 기준 **지난 실기로 갈음** — 닦는 힘에서 툴이 밀리지 않음'),
 'F3-03': dict(note_add='✅ 9/21 PR #57 — 컵 세척 중 1·4번 관절 감시에 걸려 멈추면 **힘만 끄고 자동으로 움직이지 않는다**(JointGuardStop → ROBOT_ERROR · 기운 솔이 컵을 끌고 올라오지 않게 — PM #56 리뷰)'),
}
for _tid, _e in P57.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 17:10 GitHub 기준 최신화 — PR #58 merge · 브랜치 진척
UPD_1710 = {
 'V-07':    dict(note_add='🔁 9/21 17:10(PR #58 · 민범진 제안 → PM 동의): **CELL-03 없이 해도 된다** — V-07 완료 기준은 "털기 진폭·속도에서 충돌 감지 오작동 10회 정지 0" 이라 흔드는 동작만 본다. 잔반 대용품은 F2-01("진짜로 털려 나가나")의 전제로 옮긴다. 저녁 순서: V-02 → **컵 78 mm 들리는지** → V-07(그릇·컵) → V-16(그릇만) — 절차서 docs/test_logs/20260921_저녁_F2실기_절차와기록_민범진.md · run_tonight.sh'),
 'F2-01':   dict(note_add='🔁 9/21 17:10: **잔반 대용품(구슬·쌀 등 ≥ 100 g)은 여기의 전제** — "진짜로 털려 나가는가" 는 F2-01 에서 본다(V-07 은 대용품 없이)'),
 'CELL-03': dict(note_add='🔁 9/21 17:10: 잔반 대용품은 **F2-01 전까지**면 된다(V-07 은 대용품 없이 가능 — PR #58)'),
 'V-02':    dict(note_add='📋 9/21 17:10 PR #58: 저녁 실기 절차 준비 끝(run_tonight.sh bowl-weigh · cup-weigh) — 오후 티칭으로 WEIGH 가 바뀌어 빈 용기 기준값을 다시 잰다. 합격 = 같은 추 10회 (최대−최소) ≤ 20 g(E16 D-D)'),
 'F4-03':   dict(prog='0.7', note_add='📈 9/21 17:10(브랜치 injae/20260921-F4-03-hmi-screen · PR 전): STEP 4 닦는 힘 그래프 · STEP 5 이력 표(전체/문제만) · 팔레트를 실제 배치 모양(위에서 본 그림)으로 · 팔레트 처리 개수(가짜 flow 가 적재 완료를 한 박자 먼저 세던 것 수정)'),
 'INF-02d': dict(note_add='📈 9/21 17:10(브랜치 beomjin/20260921-INF-02d-grip-safety-reset · PR 전): **그리퍼 안전 스위치 읽기·풀기** `cc.grip_safety` · `cc.grip_reset`(TS-06) — 오늘 20 N 사고 때 그리퍼를 수동 분리해야 했던 것의 후속'),
 'V-24':    dict(note_add='📈 9/21 17:10(브랜치 injae/20260921-INF-02-public-stop · PR 전): 공개 정지 함수 `cc.stop()`(지금 바로 move_stop DR_QSTOP) — 박진용 stop_now() 가 motion 내부 함수를 쓰던 것을 대신한다(PR #56·#57 요청)'),
}
for _tid, _e in UPD_1710.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 PR #59 merge — 검증 수준을 밝혀 둔다(실기 미확인 지적)
V59 = '🟡 9/21 PR #59 — **자동 시험만 확인 · 실기 미확인**(팀 지적으로 명시)'
P59 = {
 'INT-4b':  dict(note_add=V59 + ': flow 재시도 인덱스 겹침 수정(재시도가 성공하면 이미 적재한 용기로 공정을 한 바퀴 더 돌던 것)의 **실제 재시도 경로는 여기(실패 주입 — 팔레트 걸림 → 후퇴·재시도)에서 처음 실기로 본다**. 회귀 시험은 호출 횟수로 못 박혀 있다'),
 'UT-FLOW': dict(note_add='✅ 9/21 PR #59 — 재시도 인덱스 겹침 수정 + 회귀 시험(기능 함수 호출 횟수). 기존 test_retry_recovers 는 결과(DONE)만 봐서 이 버그를 통과시키고 있었다 — PM 이 #48 검토 때도 놓침'),
 'V-02':    dict(note_add=V59 + ': rig_f2 가 바뀌었다(grip 은 "열기 → 댐 → 쥐기" 한 프로그램 · empty 가 **HOME 을 거쳐 그 종류의 WEIGH 자세로 이동**해서 잰다) — **오늘 저녁 첫 실행이 곧 실기 검증.** 첫 왕복 vel_scale 0.3 · 단계마다 Enter · 손은 E-Stop'),
 'V-07':    dict(note_add=V59 + ': weigh 도 HOME 경유로 바뀌었다(E15) — 털기 뒤 저울로 갈 때 용기를 쥔 채 J1 180° 를 도는 것은 **오늘 저녁이 처음**'),
}
for _tid, _e in P59.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 17시대 결정 E21 · PR #60 merge
E21 = '📌 9/21 결정 E21(/cell/force · /cell/gripping 삭제)'
P21 = {
 'FLOW-02': dict(note_add=E21 + ' → **`/cell/force`·`/cell/gripping` 발행은 만들지 않는다**(HMI 힘 그래프·파지 표시 삭제). FLOW-02 는 기록(records.csv)·이벤트·소모품 카운트만 남는다'),
 'F4-03':   dict(note_add=E21 + ' → HMI 에서 힘 그래프·파지 표시를 뺐다(F4 `d9a8d2d`). 대신 **셀 평면도에 로봇 위치·동작**을 그린다(cell.yaml 좌표 + /flow/state — 새 인터페이스 없음)'),
 'NOTE-02': dict(note_add=E21 + ' → HMI gif 에 힘 그래프를 넣지 않는다(실제 로봇에서는 안 나오는 기능이었다). 발표에서 힘제어를 보이려면 F3 CSV(force_log_path)로 그래프를 따로'),
 'V-24':    dict(note_add='✅ 9/21 PR #60 merge — 공개 정지 함수 `cc.stop()`(지금 바로 move_stop DR_QSTOP · halt 깃발은 안 건드림). 🟡 실기 미확인 — 박진용이 stop_now() 를 바꾼 뒤 F3 컵 세척 실기에서'),
}
for _tid, _e in P21.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 17:40 팀원 보고 3건 반영
R = '📣 9/21 17:40 보고'
REP = {
 'FLOW-03': dict(prog='0.9', note_add=R + '(민범진): **코드는 끝** — 정지·재개·중단(PR #50). 🟡 남은 것은 abort 실기뿐(격리 자리 가는 길 미확인 — E-Stop 에 손)'),
 'F1-02':   dict(status='진행', prog='0.3', note_add=R + '(한석형): **그릇 집기 실기 검증 중** — 실제 TCP GripperDA_v1 확인, REAL STEP 스크립트로 RET_B 집기부터 전체 경로를 순서대로 확인 중(그릇 값 영점 10.58 · 2.15 ± 0.6 · 20 N 반영). 로컬 cell.yaml 이 옛것이라 limits/motion 이 비어 막혔다가 main 최신으로 맞춤. 🔜 실기 끝나면 handling.py pick() 본 구현 → push. GitHub push 아직 없음'),
 'INT-12a': dict(note_add='🚨 9/21 17:40(민범진 보고): **한석형 f1.pick() 이 main 에서 아직 빈 함수** — INT-12a(9/22 저녁 · 민범진 주도)의 전제. 한석형 pick() PR 이 **9/22 오후까지** 들어와야 한다'),
 'F1-05':   dict(note_add=R + '(한석형): insert_limit_n 15 = force_max_n 15 여유 0 문제는 F1 구현하며 같이 정리하겠다'),
 'F3-02':   dict(note_add=R + '(박진용): 그릇 재검증 = HOME 시작·끝 + 135 mm 빠른 하강을 가상에서 바닥 조건 흉내로 그릇→컵 연속 디버깅 중 → **오늘 저녁 실기(rig_f3.py bowl)** 로 기록. 빠른 하강·곧게 올라오기 1.5 배(fast_vel_mm_s 180 → vel_scale 0.3 에서 54 mm/s)는 브랜치 jinyong/20260921-F3-guard-cleanup(#57 뒤 커밋 · main 미반영) → 그릇 실기 뒤 새 PR'),
 'SAFE-01': dict(note_add=R + '(박진용): 실측 줄은 그릇 재검증 뒤 find_max_mm(40 → 25 여부)와 함께 오늘 저녁'),
 'CELL-03': dict(note_add=R + '(민범진): 0.7 그대로 — 아직 손 못 댐(잔반 대용품은 F2-01 전까지면 된다)'),
 'V-07':    dict(note_add=R + '(민범진): 준비 끝(run_tonight.sh check 통과) · 털기 최고 회전 계산 150~200 °/s 로 225 °/s 한계 안 — 알람 1212 가 뜨면 진폭부터 줄인다'),
}
for _tid, _e in REP.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 18:00 분담 조정(E22) — 한석형 짐을 박진용·민범진에게
E22 = '🔁 9/21 18:00 분담 조정(결정 E22 · 황인재)'
RB22 = {
 'F1-05':   dict(owner='P(S)', slots=S('9/22 오전'),
                 note_add=E22 + ' — **한석형 → 박진용.** 안착 놓기는 `contact_down`·`periodic_search`(박진용 force.py)를 그대로 쓰고, 박진용이 오늘 컵 세척에서 Periodic 을 실기로 다뤘으며, 박진용이 주도하는 INT-13 의 **첫 단계**다. '
                          '박진용은 `f1_handling/handling.py` 의 **place() 안착(SPONGE_BED) 부분만** 고친다(일반 place·pick·rack_place 는 한석형). 힘 상한 여유 0 문제(insert 15 = force_max 15)도 같이 정리. 한석형은 집기·적재에 집중'),
 'V-04':    dict(owner='P(S)', slots=S('9/22 오전'), note_add=E22 + ' — F1-05 와 같이 박진용(Periodic 탐색 안착 · 2 mm 오프셋)'),
 'V-15':    dict(note_add=E22 + ' — 한석형 그대로(재파지는 pick() 이 한다). 🔄 E19 로 **컵은 폭으로 판정하지 않으므로 그릇만** 본다'),
 'INT-12b': dict(owner='M(S)', note_add=E22 + ' — **주도를 한석형 → 민범진.** INT-12a(9/22 저녁)를 같은 flow·F3 가짜로 이어서 돌리는 것이 자연스럽고, 한석형은 그 시간에 적재(F1-04)·UT-F1 을 마무리한다. 한석형은 F1 쪽으로 참여(재파지·적재)'),
 'F1-02':   dict(note_add=E22 + ' — 한석형은 **집기(F1-02·V-14) → 적재(F1-04·V-06) → UT-F1** 에 집중. 🚨 pick() PR 은 **9/22 오후까지**(INT-12a 전제)'),
 'F1-04':   dict(slots=S('9/22 오후'), note_add=E22 + ' — 한석형 그대로 · 9/22 오후(RACK_B 경유점은 오늘 실기로 확인됨)'),
 'UT-F1':   dict(note_add=E22 + ' — F1-05 가 박진용에게 가서 UT-F1 의 TC-05(안착)는 박진용 실기 결과를 붙인다'),
 'INT-13':  dict(note_add=E22 + ' — 첫 단계(안착 놓기 F1-05)도 이제 박진용 것이라 INT-13 을 박진용이 거의 혼자 돌릴 수 있다(한석형은 툴 집기·반납 F1-03 쪽 — 황인재 구현)'),
}
for _tid, _e in RB22.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 18:05 — F1-02 칸을 9/22 오후까지(pick() 구현·PR)
EDIT.setdefault('F1-02', {}).update(dict(slots=S('9/21 오전', '9/21 오후', '9/21 저녁', '9/22 오전', '9/22 오후')))
EDIT.setdefault('V-14', {}).update(dict(slots=S('9/21 오후', '9/21 저녁', '9/22 오전')))

# ---------------------------------------------------------------- 9/21 PR #61 merge — FLOW-02 기록
EDIT.setdefault('FLOW-02', {}).update(dict(status='진행', prog='0.9', note_add='✅ 9/21 PR #61 merge — records.csv 용기 1줄(SDD §4.2 14열 · 격리된 용기도) · 소모품 임계 경고(멈추지 않고 알리기만) · FlowEvent 빈 필드 4개 채움. 검증: 자동 시험 354 passed + 로봇 없이 진짜 flow_node 로 4행. 🟡 실제 값(무게·닦기 시간·힘 로그 경로)은 INT-12a·INT-13(9/22 저녁)의 records.csv 로 확인'))
EDIT.setdefault('UT-FLOW', {}).update(dict(note_add='✅ 9/21 PR #61 — TC-12(용기 4개 → 4행 · 열 누락 0)가 test_f2_records.py 로 덮였다. 남은 것: TC-10 정책 · flow_node 를 실제로 띄워 HMI·Ctrl+C'))
# ---------------------------------------------------------------- 9/21 PR #62 merge — UT-FLOW 로봇 없는 범위 완료
EDIT.setdefault('UT-FLOW', {}).update(dict(status='진행', prog='0.9', note_add='✅ 9/21 PR #62 — flow_node 를 **로봇 없이 실제로 띄워** 정지·재개 · 정지·중단 · 함수가 터짐(mock BOOM 예외 주입) · Ctrl+C 4시나리오 통과(TC-10) + TC-12(#61). 🟡 로봇이 움직이는 중의 정지 · 힘이 걸린 채 정지 · abort 실기 정리는 V-24 · FLOW-03 · INT-4(9/22)에서. 함정 기록: 내 PC 안에서도 flow_node 가 두 개 뜨면 응답이 섞인다 · `&` 로 띄우면 셸이 SIGINT 를 무시한다'))
# ---------------------------------------------------------------- 9/21 18:50 그리퍼는 시뮬레이션에서 검증되지 않는다 — 해당 검증 삭제
EDIT.setdefault('INF-02d', {}).update(dict(
    status='완료', prog='1.0',
    crit='실기에서 명령 → 동작 → 폭(mm) 읽힘 · NORMAL↔HOLD 전환  (🔄 9/21: 그리퍼는 시뮬레이션에서 검증되지 않아 "Virtual 에서 가짜 그리퍼 노드로 호출 순서" 는 뺐다)',
    note_add='✅ 9/21 18:50 — **그리퍼는 시뮬레이션(가상 로봇)에서 검증되지 않는다**(팀 보고 · 황인재) → 완료 기준의 Virtual 확인을 뺐다. 남은 실기 확인은 **9/21 오후 그리퍼 세션(PR #53 — V-05·V-01·V-23, PR #49 의 새 gripper.py 로)** 에서 끝났다 → 완료'))
# ---------------------------------------------------------------- 9/21 18:55 결정 E23 — 툴 프리셋은 황인재가 V-08 시작 때
EDIT.setdefault('V-08', {}).update(dict(note_add='📌 9/21 결정 E23: **시작 때 툴 프리셋(SPONGE·BRUSH — 폭·힘·허용 오차 · 영점 10.58)을 rig_gripper.py 로 잰다**(황인재 — 값을 쓰는 f1.tool 담당) → cell.yaml 에 넣고 V-08 10회. 민범진 확인 요청(담당이 SDD·일정표에서 엇갈려 아무도 안 잡고 있었다)'))
EDIT.setdefault('F1-03', {}).update(dict(note_add='📌 9/21 E23: 툴 프리셋이 비어 있으면 f1.tool 이 못 잡는다 → V-08 첫 단계에서 황인재가 잰다'))
# ---------------------------------------------------------------- 9/21 21:35 GitHub 기준 — 한석형 그릇 한 바퀴 실기 스크립트(브랜치)
SB = '📈 9/21 21:35(브랜치 seokhyung/20260921-CELL-04-final-coords · PR 전)'
P2135 = {
 'F1-02':   dict(prog='0.4', note_add=SB + ': 한석형이 **실제 로봇으로 그릇 한 바퀴 전체**(반납 구역 집기 → 저울 → 잔반통 → 스펀지 홈 → 툴 → 헹굼 → 팔레트)를 도는 스크립트(`rig_bowl_scenario_real.py`)로 18:25~21:26 경로를 다듬었다. '
                          '그릇 집기는 **관절값(접근·집기 2개)** 으로 새로 확인 — `cell.yaml` 은 아직 옛 좌표값. 🔴 handling.py **pick() 본 구현·PR 은 아직**(9/22 오후까지 — INT-12a 전제)'),
 'F1-04':   dict(prog='0.3', note_add=SB + ': 그릇 칸 적재 경로(경유점 RACK_B_VIA → 칸 바로 위 → 하강 → 놓기 → y −25 → z +100)를 스크립트로 실기 확인. 🔴 경유점 실기값이 **스크립트 안에만** 있고 `cell.yaml` 은 아직 계산값(HOME 위 z 338) → rack_place 구현과 함께 cell.yaml 반영 필요'),
 'CELL-04': dict(note_add='🚨 9/21 21:35: 한석형 실기로 확인한 **좌표 2개가 스크립트 상수에만 있다** — ① 반납 구역 그릇 집기(관절값 접근·집기) ② 팔레트 경유점 RACK_B_VIA posj. E14 보완대로 **cell.yaml 에 직접 반영 + 보고** 가 필요하다(제품 코드·INT-12a 는 cell.yaml 을 읽는다). 9/20 에도 같은 이유(스크립트 상수)로 옮기는 데 하루가 걸렸다'),
 'INT-12a': dict(note_add='🚨 9/21 21:35: 전제 2개 — ① 한석형 pick() 이 main 에 ② 그릇 집기·팔레트 경유점 실기 좌표가 cell.yaml 에(지금은 한석형 스크립트 상수에만)'),
}
for _tid, _e in P2135.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 21:45 황인재 확인 — 한석형 F1 은 그릇만 구현, 컵은 구현 중
CUPW = '🔄 9/21 21:45(황인재 확인): 한석형 F1 은 **그릇만 구현 · 컵 동작은 지금 구현 중**'
CUP = {
 'F1-02':   dict(note_add=CUPW + ' — 컵 집기는 E19(고정 폭 78 · 판정 없음)로'),
 'F1-04':   dict(note_add=CUPW + ' — 컵 칸(RACK_C1·C2 · rack.via · exit_rel_mm 🟡 실기 미확인)은 아직'),
 'V-14':    dict(note_add=CUPW + ' — 컵 슬롯 쪽은 컵 집기 구현 뒤'),
 'UT-F1':   dict(note_add=CUPW + ' — TC-09(팔레트 4칸) 의 컵 칸 2개는 컵 적재 구현 뒤'),
 'INT-3b':  dict(note_add='⚠ 9/21 21:45: 컵 1개 끝까지 — 전제인 **F1 컵 동작(집기·놓기·재파지·적재)을 한석형이 지금 구현 중**. 컵 경로 좌표도 🟡 실기 미확인(컵 한 바퀴 · 팔레트 컵 칸)'),
 'INT-4a':  dict(note_add='⚠ 9/21 21:45: 시연(그릇 2·컵 2) — 그릇은 한석형 실기 스크립트로 한 바퀴 확인 · **컵은 F1 구현 중**(한석형)'),
}
for _tid, _e in CUP.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 21:50 F4 보고 — F4-03 화면 진척
F4R = '📈 9/21 21:50 F4 보고(브랜치 injae/20260921-F4-03-hmi-screen `1ac917b` · PR 전)'
P4 = {
 'F4-03':   dict(prog='0.85', note_add=F4R + ': Next.js 15 정적 화면을 hmi_bridge 가 / 에서 서빙 · 상단 막대(연결 + 항상 보이는 빨간 일시 정지) · 알람 띠(ROBOT_ERROR 면 복구 3단계) · 시작·재개·중단(확인 창) · **9단계 그림 카드**(그릇/컵별) · 지금 하는 일(큰 그림·경과·다음 할 일) · **팔레트 입체 그림**(적재됨/넣는 중/비어 있음) · 숫자 패널(반납 구역 남은 수 · 소모품 교체까지 N회) · 이력 표(전체/문제만). 그림 = 등각 일러스트(황인재 승인). '
                          '검증: 화면 빌드 · f4_hmi pytest 30 · **가짜 flow 대본 5개**(정상·일시 정지·격리·오류·빈 구역)를 브라우저로(격리 환경). 🟡 **실제 flow_node 연결은 L3**. 🔜 9/22 황인재 그림 수정 → 직접 확인·승인 → PR. 열린 질문: 실제 컵1·컵2 칸 자리가 배치 그림과 맞는지(좌표상 그릇 옆 칸이 C2)'),
 'NOTE-02': dict(note_add='9/21 21:50: HMI 화면이 거의 완성(F4-03 0.85) — 9/22 그림 수정 뒤 가짜 flow 대본으로 gif 를 찍으면 된다(1차 산출물 9/22~23)'),
}
for _tid, _e in P4.items():
    EDIT.setdefault(_tid, {}).update(_e)

# 황인재가 시트에서 직접 바꾼 상태는 그대로 둔다(덮어쓰지 않게 여기서 마지막에 맞춘다)
USER_SET = {'CELL-01': dict(status='완료', note_add='✅ 9/20 황인재가 시트에서 완료 처리')}
for _tid, _e in USER_SET.items():
    EDIT.setdefault(_tid, {}).update(_e)





# 팀(구역) 이동: id → (새 팀, 이 ID 행 바로 뒤에 둔다) — 이미 그 구역에 있으면 PM 이 정한 행 순서를 건드리지 않는다
MOVE = {'V-01': ('F2·flow', 'V-02'), 'V-05': ('F2·flow', 'V-01'), 'V-23': ('F2·flow', 'V-05')}
EASY = {
 'INF-02': '공용 로봇 함수 중 이동(지정 위치로 이동 move_to, 상대 이동 move_rel, 관절 상대 이동)을 motion.py 에 만든다. 가상 로봇만으로 완성한다. 접촉 하강이 쓰도록 속도 선택 인자를 넣고, cell.yaml 에 힘 관련 키 골격도 추가한다',
 'INF-02d': '공용 로봇 함수 중 그리퍼(잡기 grip, 힘 2단계 grip_level, 놓기 release, 현재 폭 읽기 grip_width)를 새 파일 gripper.py 에 만든다. 그리퍼 검증(V-05·V-23·V-01)에서 확인한 방법 그대로',
 'V-01': '그리퍼로 그릇·컵을 잡았을 때와 빈손일 때의 "벌어진 폭" 값이 확실히 다른지 10번씩 잰다. 그릇은 옆면(벽)을 세로로 잡아 폭이 약 2 mm 로 나온다 → 빈손(완전히 닫힘)과 겹치지 않는지가 핵심',
 'V-05': '그리퍼 드라이버가 제대로 붙었는지, 현재 폭을 어디서 읽을지 정한다(박진용 제안서의 30분 절차): 드라이버의 관절각을 폭으로 바꿔 자로 잰 값과 비교 → 안 맞으면 Compute Box 를 읽기부터',
 'PKG-01': '내 패키지 뼈대를 만든다: 약속(cobot_api)에 적힌 이름·인자 그대로 빈 함수를 만들고, 내 함수만 불러 보는 시험 스크립트 rig 를 만든다. F1 골격은 황인재 세션이 대신 만들어 준다(주인은 한석형)',
 'DSN-03': '2차 회의 안건을 회의 없이 PM 이 결정했다(시간 부족): 반납 구역은 고정 슬롯, 그릇은 옆면을 세로로 잡기, 그리퍼 폭은 드라이버 방식 먼저, 박진용의 힘 함수 요청 수락. 이의는 9/20 아침 브리핑에서',
 'F1-02': '"슬롯에서 집기"(pick)를 만든다: 반납 구역의 정해진 자리(슬롯)를 순서대로 가서, 닿을 때까지 내려가 잡고, 폭으로 성공을 판정한다. 빈 자리면 다음 자리로, 다 비었으면 "구역 비었음". 그릇은 옆면(벽)을 세로로 잡는다',
 'V-14': '정해진 자리(슬롯)에 놓인 그릇 2개·컵 2개를 10번 집어 9번 이상 성공하는지 본다. 빈 자리가 있으면 다음 자리로 넘어가는지도',
 'V-24': '(보류) 로봇이 움직이는 도중에도 정지 버튼이 먹게 하는 선택 과제 — 이번 재계획에서 뺐다',
}
TITLES = {'할일_한석형': '한석형 — 팀장 · F1 파지·이송·적재 + 좌표 계산·티칭(cell.yaml 값) + 실기 검증',
          '할일_민범진': '민범진 — F2 무게·털기·헹굼 + flow_node + mock · 통합 실행 리더 + cobot_common weigh.py · gripper.py + 그리퍼 검증',
          '할일_박진용': '박진용 — F3 접촉 닦기 + cobot_common 힘 함수(force.py)·패키지 정리·리뷰 + 안전 파라미터',
          '할일_황인재': '황인재 — PM · F4 웹 HMI + cobot_api·cobot_msgs·cobot_common bootstrap·config·motion.py·런치·일정표·제출'}
LECTURE = {'9/19 토 · 9/20 일': ('휴일(로봇 사용 가능 — 🚨 교육장 18시 마감, **저녁 칸 없음**)',
                                 '9/19 구조 변경 적용 → 티칭 1차(한석형) + 공용 함수·기능 골격 → 17:15 DSN-03 2차 회의 / 9/20 오전 그리퍼·무게·힘 검증 + 티칭 2차 → 오후 구현 + 함수별 TC · 발표 자료')}
LECTURE['9/24 목~9/28 월'] = ('추석 — 🚨 **교육장 닫힘**(로봇·현장 작업 불가) · 집에서 각자 하는 원격 작업만(황인재 9/20)',
                            'PPT(5장 양식)·영상 편집·대본·as-built 문서·온라인 리허설 — 전부 집에서. 필요한 자료(영상 원본·측정 결과·사진)는 **9/23 저녁 동결 때 드라이브·저장소에 올려 둔다**')
LECTURE['9/19 토 · 9/20 일'] = (LECTURE['9/19 토 · 9/20 일'][0], '9/19 구조 변경 적용 → 티칭 1차(그릇 쪽) + 공용 함수 전부 main / 9/20 오전 좌표 마무리(컵 쪽)·그리퍼·무게·힘 검증 → 오후 티칭 2차·V-22·F1-01·구현 + 함수별 TC · 발표 자료')
GATE = {
 'G1 리그·검증': {'B': '9/20 오후', 'C': '티칭 1·2차 완료, 기구 완성(✅ 9/19), 공용 함수(cobot_common: motion·gripper·force·weigh) v0, 실행 뼈대 확인(V-20), 설계를 정하는 검증(V-01·02·03·05·23) 결과 확보'},
 'G2 L1': {'B': '9/22 오후', 'C': 'UT-F1·F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · UT-F4 는 9/22 저녁'},
 'G3 L2': {'B': '9/23 오전', 'C': 'INT-12a·12b·13·4 통과 (flow_node + use_mock) — 9/22 저녁 시작, 9/23 오전 첫 순서까지. 노션 업로드는 9/22'},
 'G4 L3': {'B': '9/23 오후', 'C': '그릇 1·컵 1 end-to-end + HMI 3회 연속'},
 'G5 L4·동결': {'C': '4개 연속·실패 주입·측정·영상, v1.0-demo 태그 · 🛡 밀리면 SDD §9.9 범위 방어(4개 → 2개, 실패 주입 4종 → 2종)'},
}
SLOT = {        # 로봇 슬롯 표 (A 열 → {열: 글})
 '9/19 토': {'C': 'CELL-04 티칭 1차 계속 + V-19(S·M) — 18시 교육장 마감까지 · 로봇 불필요: F1 골격·motion.py 착수(H)·V-20 Virtual(M·H)·force.py PR(P)·V-12(P) → 17:15 DSN-03 2차 회의(전원)',
             'D': '🚫 교육장 마감(주말 18시) — 일정 없음'},
 '9/20 일': {'B': '1시간씩 교대: 그리퍼 세션 V-05·V-23·V-01(M) → V-02 + weigh 이식(M) / V-03 → V-18·F3-02(P) / CELL-04b 티칭 2차 + V-22 → F1-01(S·P) · 로봇 불필요: motion.py PR·DSN-04·F4-00(H)',
             'C': 'F1-02·V-14(S) / F3-02(P) / V-07·V-16 → F2-01(M) — 1시간씩 교대, 18시 마감 · 로봇 불필요: gripper.py(M)·F4-01·F4-02·MID-01·ARCH-01(H)',
             'D': '🚫 교육장 마감(주말 18시) — 일정 없음'},
 '9/21 월': {'D': '1시간씩 교대(순서는 DSN-03 C1): V-04·V-15 → F1-05(S, P 참여) / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: INT-4·V-13·ENV-03·F4-02(H·M)'},
 '9/22 화': {'B': 'F1-03·V-08(S) / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-03·노션 업로드(H)',
             'C': 'F1-04·V-06 → UT-F1(S) / UT-F3(P) — G2(L1) 마감 · 로봇 불필요: F4-03·F4-04·NOTE-02(H)',
             'D': 'L2: INT-12a(M·S) → INT-12b(S·M) → INT-13(P·S)'},
 '9/23 수': {'B': 'INT-13 잔여 — G3(L2) → INT-3a·INT-3b L3(M 실행, 전원)', 'C': 'INT-3b·FIX-01 — G4(L3) → INT-4a 연속 처리',
             'D': 'INT-4b 실패 주입 · INT-4c 측정 → INT-4d 영상·동결 (G5)'},
}
GATE['G1 리그·검증']['C'] = '티칭 1차(9/20 오전 마무리)·2차(9/20 오후), 기구 완성(✅ 9/19), 공용 함수(cobot_common: motion·gripper·force·weigh) ✅ 전부 main(9/19), 실행 뼈대 확인(V-20), 설계를 정하는 검증(V-01·02·03·05·23) 결과 확보'
GATE['G2 L1']['C'] = 'UT-F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · 🚨 **F1(UT-F1)은 좌표 지연으로 9/22 저녁~9/23 오전 첫 순서** · UT-F4 는 9/22 저녁'
GATE['G3 L2']['C'] = 'INT-12a·13·4 는 9/22 저녁 시작, **INT-12b 는 9/23 오전**(rack_place 가 9/22 저녁) — flow_node + use_mock. 노션 업로드는 9/22'
GATE['G4 L3']['C'] = '그릇 1개 end-to-end + HMI 3회 연속이 먼저, 컵 1개는 이어서(🛡 밀리면 컵은 1회 또는 도전 과제)'
SLOT['9/20 일'] = {'B': '1시간씩 교대: 그리퍼 세션 V-05·V-23·V-01 → V-02(M) / V-03 → V-18·F3-02(P) / **좌표 마무리 CELL-04(컵 쪽)·CELL-01 → V-19(S)** · 로봇 불필요: CELL-03 배치(M)·DSN-04·F4-00(H)',
                   'C': '1시간씩 교대: **CELL-04b 티칭 2차(S·P) → V-22(H·S) → F1-01(S)** / F3-02(P) / V-07·V-16 → F2-01(M) — 18시 마감 · 로봇 불필요: V-20 Virtual(H)·gripper.py 수정(M)·F4-01·F4-02·MID-01·ARCH-01(H)',
                   'D': '🚫 교육장 마감(주말 18시) — 일정 없음'}
SLOT['9/21 월']['D'] = '1시간씩 교대: **F1-02 pick + V-14(S)** / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: INT-4·V-13·ENV-03·F4-02(H·M)'
SLOT['9/22 화'] = {'B': '**V-04·V-15 → F1-05 안착(S, P 참여)** / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-03·노션 업로드(H)',
                   'C': '**F1-03·V-08(S)** / UT-F3(P) / UT-F2 잔여(M) — G2(L1) 마감(F1 제외) · 로봇 불필요: F4-03·F4-04·NOTE-02(H)',
                   'D': '**F1-04·V-06 → UT-F1(S)** / L2: INT-12a(M·S) → INT-13(P·S)'}
SLOT['9/23 수'] = {'B': 'UT-F1 잔여 → **INT-12b(S·M)** · INT-13 잔여 — G3(L2)', 'C': 'INT-3a 그릇 e2e → INT-3b 컵 e2e · FIX-01 — G4(L3)',
                   'D': 'INT-4a 연속 처리 → INT-4b 실패 주입 · INT-4c 측정 → INT-4d 영상·동결 (G5) · 🛡 범위 방어: 4개 → 2개, 실패 주입 4종 → 2종'}
GATE['G2 L1']['C'] = 'UT-F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · 🚨 **F1(UT-F1)은 좌표 지연으로 9/22 저녁~9/23 오전 첫 순서** · UT-F4 는 9/23 오전(최소 범위 — 버튼·상태·연결), 전체는 추석에 mock 으로'
SLOT['9/21 월']['D'] = '🚨 **첫 순서: V-24 실기 확인(H, 30분 — 짧은 이동의 도착 위치·일시 정지·재개) → V-22(H·S)** → 1시간씩 교대: F1-02 pick + V-14(S) / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: F4-01·F4-02·ENV-03(H·M)'
SLOT['9/22 화'] = {'B': '**V-04·V-15 → F1-05 안착(S, P 참여)** / **V-24 실기 확인 — 이동 도중 일시 정지 → 재개(H·P, 1시간)** / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: FLOW-03·UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-02·V-13·노션 업로드(H)',
                   'C': '**F1-03·V-08(S)** / UT-F3(P) / UT-F2 잔여(M) — G2(L1) 마감(F1 제외) · 로봇 불필요: FLOW-03·FLOW-01 격리 마무리(M)·INT-4 flow(mock)+HMI(H·M)·F4-03(H)',
                   'D': '**F1-04·V-06 → UT-F1(S)** / L2: INT-12a(M·S) → INT-13(P·S) · 로봇 불필요: F4-03·NOTE-02 gif(H)'}
# 9/20 20:40 재배치·분담 반영(v8.3)
SLOT['9/21 월']['D'] = ('🚨 **18:30~22:00 (3.5 h) — 시간으로 끊는다**(전부 넣으면 약 5 h). ①②④⑤ 의 전제 = cell.yaml 이동 값 11개(limits 4 + motion 5). '
                        '**18:30 ① 툴·홀더 확정(P 주도·H·S)** — 이동 값 11개는 **황인재(F4)가 18:30 전에 파일에 넣는다**(9/21 위임 · 없으면 뒤가 전부 KeyError) / '
                        '**18:50 ② V-24 실기**(H · rig_pause --real, 빈손 → 용기 → 용기 3회차) / '
                        '**19:20 ③ 티칭 + 그 자리에서 확인**(H 전담, 1 h 20 — 🚨 아침에 막힌 것 먼저: **그릇 경로를 6번 관절이 이어지게 다시 찍기**(08:40 케이블 꼬임 · WASTE BOWL 특이점 포함 · M 입회 — 털기 자세가 바뀐다) → **팔레트 그릇 칸 접근점 2개** → 툴 홀더 2종 + SOAP 2 → 그릇 집기 접근점. 한 자세 찍을 때마다 rig_coords --from 으로 바로 확인) / '
                        '**20:40 ④ V-22·V-19 컵 한 바퀴**(H · 그릇 한 바퀴는 아침에 봤다 — 18~33번) / '
                        
                        '**21:00 ⑤ 그리퍼 세션**(M, **60분** · P 가 옆에서 — 🔴 먼저 **BOWL·CUP 의 폭·힘·허용 오차 6개**(V-05 → V-01, 내일 오전 집기가 기다린다), 시간이 남으면 V-23·V-16. 무게(V-02)·SPONGE·BRUSH 는 9/22 오전) · 로봇 불필요: **한석형은 저녁 내내 F1-02 집기 코드**(로봇 순서 없음) · F2 kind·GRIP_FAIL(M) · **박진용은 SAFE-01 완성 + F3-02 준비** · 🛡 밀리면 ⑤ 를 9/22 오전 첫 순서로')
SLOT['9/22 화'] = {'B': '🚨 순서: **① F3-02 닦기 3회 + V-18(P, 40분 — 어제 밀린 것)** → ② 한석형 나머지 티칭(ISOLATE 2·CUP_RACK2_1·팔레트 그릇 칸 접근점 2·컵 집기 접근) → ③ **F1-02 집기 + V-14(S)** — presets 가 어제 저녁 그리퍼 세션에서 나왔어야 한다 → ④ V-07·V-16 → F2 실기 rig_f2 empty 부터(M) · 로봇 불필요: CR-01(전원)·ENV-03·NOTE-01·SAFE-01·V-13(H)·FLOW-03(M)·INF-02b 후속(P)',
                   'C': '**V-04·V-15 → F1-05 안착(S, P 참여 — 🛡 단순 놓기부터)** / **V-25 F1-01 실기 → F1-03·V-08 툴 집기·반납(H, S 검토)** / F3-03·UT-F3(P) / UT-F2(M) · 로봇 불필요: FLOW-02·FLOW-03·FLOW-01 마무리(M)·INT-4(H·M)',
                   'D': '**F1-04·V-06 → UT-F1(S·H)** / F1-03 잔여(H) / L2: INT-12a(M·S) → INT-13(P·S) · 로봇 불필요: UT-FLOW(M)·NOTE-02 gif(H)'}
SLOT['9/23 수']['B'] = 'UT-F1 잔여(S·H) → **INT-12b(S 주도·M)** · INT-13 잔여(P·S) · UT-F4·F4-05(H) — G3(L2)'
# 9/21 09:10 — 발표 취소로 오후가 열렸다(v9.5)
SLOT['9/21 월']['C'] = ('🆕 **중간점검 발표 없음 → 프로젝트 시간**(14:00~18:30, 4.5 h). 전제가 되는 것부터: '
                        '**14:00 툴·홀더 확정(P 주도·H·S, 30분)** → **14:30 V-24 이동 함수 실기(H, 30분)** → '
                        '**15:00 티칭 2 h(H 전담 · M 입회)** — 🚨 그릇 경로 **6번 관절이 이어지게 재티칭**(08:40 케이블 꼬임) → 팔레트 그릇 칸 접근점 2 → 그릇 집기 접근점 → 툴 홀더 2종 + SOAP 2 → ISOLATE 2 · 한 자세마다 rig_coords --from 으로 바로 확인 → '
                        '**17:00 V-22·V-19 그릇·컵 한 바퀴(H)** · 로봇 불필요: **F1-02 집기 코드(S)** · SAFE-01(P) · FLOW-01 kind·GRIP_FAIL(M)')
SLOT['9/21 월']['D'] = ('🚨 **18:30~22:00 — 오후에 좌표가 끝난 뒤라 오늘 안에 L1 앞부분을 닫는다.** '
                        '**18:30 ① 그리퍼 세션(M, 60분 · P 옆에서)** — 프리셋(그릇·컵 폭·힘·허용 오차)이 여기서 나온다 → '
                        '**19:30 ② F1-02 집기 실기 + V-14(S, 60분)** — ①의 프리셋이 전제 → '
                        '**20:30 ③ F3-02 닦기 3회 + V-18(P, 40분)** → **21:10 ④ V-25 F1-01 실기(H, 25분)** · '
                        '로봇 불필요: FLOW-03·FLOW-02(M) · SAFE-01 마무리(P) · NOTE-01·02(H) · 🛡 밀리면 ④ → 9/22 오전')
SLOT['9/22 화'] = {'B': '**F1-05 안착 + V-04·V-15(S, P 참여 — 🛡 단순 놓기부터)** / V-10 → F3-03(P) / V-07·V-16 → F2 실기(M) / 남은 티칭·V-24 접촉 중 일시정지(H) · 로봇 불필요: CR-01(전원)·ENV-03·NOTE-01·V-13(H)·FLOW-03(M)·SAFE-01 마무리(P)',
                   'C': '**F1-03·V-08 툴 집기·반납(H)** / **F1-04·V-06 팔레트(S)** → **UT-F1(S·H)** / UT-F3(P) / UT-F2(M) / F3-03 마무리(P) — G2(L1) 마감 · 로봇 불필요: FLOW-01·FLOW-03 마무리(M)·INT-4(H·M)',
                   'D': 'L2: **INT-12a(M·S) → INT-13(P·S) → INT-12b(S·M) 착수** / UT-F1 잔여 · 로봇 불필요: FLOW-02·UT-FLOW(M)·NOTE-02 gif(H)'}
SLOT['9/23 수']['B'] = 'INT-12b 마무리(S 주도·M) · INT-13 잔여(P·S) · UT-F4·F4-05(H) — G3(L2) · 🛡 L1 잔여가 있으면 여기서 닫는다'
# 9/21 09:50 — 발표 취소·일정 앞당김 반영(v9.6)
LECTURE['9/21 월'] = ('6차시 오전 DRL srv·launch · **오후 중간점검 없음**(강사 확인 9/21 — 노션 차시표는 이전 기수 내용)',
                      '오후·저녁 전부 프로젝트: 오후 = 툴·홀더 → V-24 실기 → 티칭 2 h → V-22·V-19 / 저녁 = 그리퍼 → F1-02 집기 실기 → 닦기 3회 → V-25')
LECTURE['9/22 화'] = ('7차시 모듈 구현 프로그래밍 · 🆕 **9/22~23 1차 산출물 제출**(① GitHub 최신 ② ROS2 노드 구조 노션 ③ 관리자 HMI·사용자 UI 화면)',
                      '오전 F1-05 안착·F2 실기·컵 닦기 + 노션 업로드, 오후 F1-03·F1-04 → UT-F1·F2·F3 로 **G2(L1) 마감**, 저녁 L2(INT-12a·13·12b 착수)')
GATE['G2 L1'] = {'B': '9/22 오후', 'C': 'UT-F1·F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로) + 코드리뷰 CR-01 · 🆕 **F1 도 9/22 안에** — 9/21 오후가 열려 집기·닦기·F1-01 실기를 하루 앞당겼다(UT-F4 는 최소 범위로 9/23 오전)'}
GATE['중간점검'] = {'B': '—', 'C': '❌ **없음**(강사 확인 9/21). 대신 **9/22~23 1차 산출물 제출** — ① 코드 최신 GitHub 업로드 ② ROS2 노드 구조 노션(NOTE-01·ARCH-01) ③ 관리자 HMI·사용자 UI 화면 gif(NOTE-02)'}
GATE['G3 L2']['C'] = 'INT-12a·13 은 9/22 저녁 시작, **INT-12b 도 9/22 저녁 착수 → 9/23 오전 마무리**(F1-04 가 9/22 오후로 당겨졌다) — flow_node + use_mock'
# 9/21 10:00 — 로봇 경합을 풀어 민범진을 오후 맨 앞으로(v9.7)
SLOT['9/21 월']['C'] = ('🆕 **발표 없음 → 프로젝트 시간**(14:00~18:30). 🚨 순서를 바꿨다 — **좌표를 기다리지 않아도 되는 것부터**(민범진이 이틀 로봇을 못 잡았다): '
                        '**14:00 ① 그리퍼·무게 세션(M, 60분 · P 옆에서)** — rig_gripper 는 팀 cell.yaml 을 읽지 않아 좌표·값 PR 과 무관하다. V-05 → V-23 → V-01 → V-02. 여기서 나온 **프리셋이 저녁 집기 실기의 전제** · 같은 시간에 **툴·홀더 확정(P, 작업대)** 과 **F1-02 코드(S, 책상)** 를 나란히 / '
                        '**15:00 ② V-24 이동 함수 실기(H, 30분)** — 값 PR 이 들어온 뒤 / '
                        '**15:30 ③ 티칭 2 h(H 전담 · M 입회)** — 그릇 경로 6번 관절 재티칭 → 팔레트 그릇 칸 접근점 2 → 그릇 집기 접근점 → 툴 홀더 2종·SOAP 2 → ISOLATE 2 · 한 자세마다 바로 확인 / '
                        '**17:30 ④ V-22·V-19 그릇·컵 한 바퀴(H)** · 로봇 불필요: SAFE-01(P) · CELL-03 배치 사진(M) · FLOW-01 kind·GRIP_FAIL(M)')
SLOT['9/21 월']['D'] = ('**18:30~22:00 — 오후에 좌표가 끝난 뒤. 오늘 안에 L1 앞부분을 닫는다.** '
                        '**18:30 ① F1-02 집기 실기 + V-14(S, 60분)** — 오후 그리퍼 세션의 프리셋을 쓴다 → '
                        '**19:30 ② F3-02 닦기 3회 + V-18(P, 40분)** → **20:10 ③ V-25 F1-01 실기(H, 25분)** → '
                        '**20:35 ④ 예비(M): V-07 털기 진폭 · V-16 HOLD 힘 · F2-01·02 실기** — 오후에 WASTE 자세를 다시 찍었으므로 가능 · '
                        '로봇 불필요: FLOW-03·FLOW-02(M) · SAFE-01 마무리(P) · NOTE-01·02(H)')
# 9/21 10:05 — 오전도 작업 시간(v9.8)
SLOT['9/21 월']['B'] = ('🆕 **오전도 작업 시간**(강의가 비었다 · 10:05 기준 약 3 h 남음) — 🚨 **민범진이 먼저 로봇을 쓴다**(이틀 못 잡았다): '
                        '**① 그리퍼·무게 세션(M, 60분 · P 옆에서)** V-05 → V-23 → V-01 → V-02 — 좌표와 무관(rig_gripper 는 팀 cell.yaml 을 안 읽는다) · '
                        '같은 시간에 **툴·홀더 확정(P, 작업대)** · **F1-02 집기 코드(S, 책상)** · **좌표 값 마무리·PR(H)** · CELL-03 배치 사진(M) · SAFE-01 착수(P)')
SLOT['9/21 월']['C'] = ('**14:00 ① V-24 이동 함수 실기(H, 30분)** — 값 PR 이 merge 된 뒤 → '
                        '**14:30 ② 티칭 2 h(H 전담 · M 입회)** 그릇 경로 6번 관절 재티칭 → 팔레트 그릇 칸 접근점 2 → 그릇 집기 접근점 → 툴 홀더 2종·SOAP 2 → ISOLATE 2 (한 자세마다 바로 확인) → '
                        '**16:30 ③ V-22·V-19 그릇·컵 한 바퀴(H, 1 h)** → **17:30 ④ F1-02 집기 실기 + V-14(S, 60분)** — 오전 세션의 프리셋을 쓴다 · 로봇 불필요: SAFE-01(P)·FLOW-01 kind·GRIP_FAIL(M)')
SLOT['9/21 월']['D'] = ('**18:30 ① F3-02 닦기 3회 + V-18(P, 40분)** → **19:10 ② V-25 F1-01 실기(H, 25분)** → '
                        '**19:35 ③ 민범진 두 번째 순서**: V-07 털기 진폭 · V-16 HOLD 힘 · F2-01·02 실기(오후에 WASTE 자세를 다시 찍었다) → '
                        '**20:40 ④ 여유가 되면 L2 착수: INT-12a(M·S)** · 로봇 불필요: FLOW-03·FLOW-02(M)·SAFE-01 마무리(P)·NOTE-01·02(H)')
# 9/21 10:15 — 좌표가 가장 먼저(v9.9)
SLOT['9/21 월']['B'] = ('🥇 **좌표가 1번**(황인재 10:15) — 뒤의 모든 실기가 이 좌표 위에서 돈다: '
                        '**① 값 마무리·PR(H, 책상)** → **② V-24 이동 함수 실기(H, 30분)** → **③ 티칭 착수(H · M 입회)** 그릇 경로 6번 관절 재티칭부터 · '
                        '같은 시간에 로봇 없이: **툴·홀더 확정(P, 작업대 — 툴 홀더 티칭 전까지 끝낸다)** · **F1-02 집기 코드(S)** · SAFE-01 착수(P) · FLOW-01 kind·GRIP_FAIL·MoveIncomplete(M) · '
                        '🔸 ① 은 책상 작업이라 그동안 로봇이 빈다 → 그 틈에 **민범진 그리퍼 세션(60분)** 을 넣을 수 있다(좌표 실기가 시작되면 바로 넘긴다)')
SLOT['9/21 월']['C'] = ('**④ 티칭 마무리(H)** → **⑤ V-22·V-19 그릇·컵 한 바퀴(H)** → **⑥ 그리퍼·무게 세션(M, 60분 · P 옆에서)** V-05 → V-23 → V-01 → V-02 → '
                        '**⑦ F1-02 집기 실기 + V-14(S)** — ⑥ 의 프리셋과 ④⑤ 의 좌표가 전제 · 로봇 불필요: SAFE-01(P)·FLOW-03(M)')
SLOT['9/21 월']['D'] = ('**⑧ F3-02 닦기 3회 + V-18(P, 40분)** → **⑨ V-25 F1-01 실기(H, 25분)** → **⑩ 민범진 두 번째: V-07 털기 · V-16 HOLD · F2-01·02 실기** '
                        '(오후 티칭에서 WASTE 자세를 다시 찍은 뒤) · 🛡 밀리면 ⑦ 집기 실기를 저녁 첫 순서로 · 로봇 불필요: FLOW-02·FLOW-03(M)·NOTE-01·02(H)')
# 9/21 10:20 — 2차 티칭 없음(E14, v10.0)
_o = '남은 티칭·V-24 접촉 중 일시정지(H)'
assert _o in SLOT['9/22 화']['B']
SLOT['9/22 화']['B'] = SLOT['9/22 화']['B'].replace(_o,
    'V-24 접촉 중 일시정지(H) · 🔁 **2차 티칭 없음**(E14) — 좌표는 9/21 에 끝. 기능 함수를 만들다 이상한 자리가 나오면 '
    '**그때 황인재에게 요청**(① 설정 키 이름 ② 무엇이 어떻게 ③ 지금 막혔는지) → 급하면 그 자리에서, 아니면 모아서 한 번에 다시 찍는다')
_o = '**④ 티칭 마무리(H)**'
assert _o in SLOT['9/21 월']['C']
SLOT['9/21 월']['C'] = SLOT['9/21 월']['C'].replace(_o, '**④ 티칭 마무리(H) — 🔁 오늘 안에 전부 끝낸다, 2차 티칭 칸은 없다(E14)**')
# 9/21 11:30 — 그리퍼 드라이버가 진짜 병목이었다(v10.2)
SLOT['9/21 월']['B'] = ('🚨 **최우선(5분): 그리퍼 드라이버 `sudo apt install python3-pymodbus` — PC 4대 전부.** '
                        '이것이 안 돼서 민범진의 그리퍼·무게 검증이 전부 멈춰 있었다(로봇 경합이 아니었다). 되면 V-05 → V-01 → V-23 → V-02 가 바로 돈다 · '
                        ) + SLOT['9/21 월']['B']
# 9/21 — V-26 Ctrl+C 정지 실기(30초짜리)를 오후 좌표 확인에 끼운다(v10.3)
SLOT['9/21 월']['C'] = SLOT['9/21 월']['C'].replace('**⑤ V-22·V-19 그릇·컵 한 바퀴(H)**',
    '**⑤ V-22·V-19 그릇·컵 한 바퀴(H)** → **⑤-b V-26 Ctrl+C 정지(H, 30초 — 긴 이동 도중 Ctrl+C × 3회)**')
# 9/21 12:10 — ENV-03 완료 → 9/22 오전 칸에서 뺀다(v10.4)
SLOT['9/22 화']['B'] = SLOT['9/22 화']['B'].replace('CR-01(전원)·ENV-03·NOTE-01', 'CR-01(전원)·NOTE-01')
# 9/21 12시대 — 오후 그리퍼 세션에서 V-02 를 빼고 저녁으로(E16 D-C, v10.5)
SLOT['9/21 월']['C'] = SLOT['9/21 월']['C'].replace(
    'V-05 → V-23 → V-01 → V-02', '**V-05 → V-23 → V-01**(E16 D-C: V-02 는 저녁으로 — 60분에 안 들어가고 WEIGH 자세가 오늘 바뀐다)')
SLOT['9/21 월']['D'] = SLOT['9/21 월']['D'].replace(
    'V-07 털기 · V-16 HOLD · F2-01·02 실기', 'V-02 무게 → V-07 털기 · V-16 HOLD · F2-01·02 실기')
# 9/21 13시대 — 박진용 실기를 저녁 앞으로, soap 은 9/22 오전 첫 순서(v10.6)
SLOT['9/21 월']['D'] = ('**18:30 ① V-10 컵 실기 + wipe_cup(P, 60분)** → **19:30 ② F3-02 그릇 재검증 + V-18(P, 60분 — E17 바뀐 방식: HOME 시작·끝)** → '
                        '**20:30 ③ V-25 F1-01 실기(H, 25분)** → **20:55 ④ 민범진 두 번째: V-02 무게 → V-07 털기 → V-16 HOLD**(오후 티칭에서 WEIGH·WASTE 를 다시 찍은 뒤 · CELL-03 이 끝나 있어야 V-07 가능) · '
                        '🛡 넘치면 V-16·F2 실기 → 9/22 오전 · ⚠ F3 닦기는 vel_scale 예외(E17) — 첫 실기는 f3 절 속도를 낮춰서 · 로봇 불필요: FLOW-03(M)·SAFE-01(P)·NOTE-01·02(H)')
_o = 'V-10 → F3-03(P)'
assert _o in SLOT['9/22 화']['B']
SLOT['9/22 화']['B'] = SLOT['9/22 화']['B'].replace(_o, '**soap 실기(P, 90분 — 첫 순서 · SOAP 좌표는 9/21 티칭)** → UT-F3 준비(P)')
# 9/21 15:40 — 박진용이 오후에 컵 실기를 대부분 했다(v11.4)
_o = '**18:30 ① V-10 컵 실기 + wipe_cup(P, 60분)**'
if _o in SLOT['9/21 월']['D']:
    SLOT['9/21 월']['D'] = SLOT['9/21 월']['D'].replace(_o, '**18:30 ① V-10 컵 마무리(P — 오후에 실기 대부분 진행 · 15:33 Move Periodic 시도는 되돌림)**')
# 9/21 17:10 — 민범진 저녁 순서(PR #58) · V-07 은 CELL-03 없이
_o = '**20:55 ④ 민범진 두 번째: V-02 무게 → V-07 털기 → V-16 HOLD**(오후 티칭에서 WEIGH·WASTE 를 다시 찍은 뒤 · CELL-03 이 끝나 있어야 V-07 가능)'
if _o in SLOT['9/21 월']['D']:
    SLOT['9/21 월']['D'] = SLOT['9/21 월']['D'].replace(_o, '**20:55 ④ 민범진 두 번째: V-02 무게 → 🔴 컵 78 mm 들리는지(E19) → V-07 털기(그릇·컵 · 대용품 없이) → V-16(그릇만)** — run_tonight.sh')
# 9/21 17:40 — 보고 반영: V-10·V-18 은 오후에 끝났으니 저녁을 당긴다(v12.2)
SLOT['9/21 월']['D'] = ('🔁 17:40 재배치(보고 반영 — V-10·V-18 은 오후에 끝남): '
                        '**18:30 ① F3-02 그릇 재검증 + SAFE-01 실측(P, 40분 · rig_f3.py bowl)** → '
                        '**19:10 ② 민범진: V-02 무게 → 🔴 컵 78 mm 들리는지(E19) → V-07 털기(그릇·컵) → V-16(그릇만)** (약 100분 · run_tonight.sh) → '
                        '**20:50 ③ V-25 F1-01 실기(H, 25분)** · '
                        '🔸 한석형 F1-02 그릇 집기 실기는 **오후(지금) 진행 중 → 18:30 전에 로봇을 넘긴다**, 남으면 ③ 뒤 · '
                        '로봇 불필요: 한석형 pick() 본 구현 · 민범진 FLOW-02 · NOTE-01·02(H)')
# 9/21 18:00 — 분담 조정(E22)에 맞춰 9/22 로봇 순서 다시(v12.3)
SLOT['9/22 화'] = {
 'B': ('🔁 E22 분담 반영: **① 박진용 soap 실기(60~90분 — SOAP = 툴 홀더 + 40 계산값)** → **② 박진용 F1-05 안착 놓기 + V-04(Periodic 탐색) — 스펀지 홈에서 한 번에** → '
       '**③ 한석형 F1-02 집기 마무리 + V-14·V-15(그릇)**(오늘 저녁에 못 끝낸 만큼) → **④ 민범진 V-07·V-16 남은 것**(오늘 밤에 못 끝낸 만큼) · '
       'V-24 접촉 중 일시정지(H) · 로봇 불필요: 한석형 pick() 본 구현·PR · CR-01(전원) · NOTE-01(H) · FLOW-02·UT-FLOW(M)'),
 'C': ('**G2(L1) 마감**: **한석형 F1-04 적재 + V-06** → **UT-F1(S·H · TC-05 안착은 박진용 결과를 붙인다)** / **UT-F3(P)** / **UT-F2(M)** / **F1-03·V-08 툴 집기·반납(H)** · '
       '🚨 한석형 **pick() PR 은 이 시간까지**(저녁 INT-12a 가 main 의 pick 을 쓴다) · 로봇 불필요: FLOW-02 마무리(M) · INT-4(H·M)'),
 'D': ('L2: **INT-12a(M 주도 · S 참여)** → **INT-13(P 주도 — 안착부터 닦기·반납까지)** → **INT-12b(M 주도로 바뀜 · S 참여) 착수** / UT-F1 잔여(S) · '
       '로봇 불필요: UT-FLOW(M) · NOTE-02 gif(H)'),
}
_b, _c = LECTURE['9/24 목~9/28 월']
LECTURE['9/24 목~9/28 월'] = (_b, _c + ' · 🆕 **F4 웹 HMI**(F4-03 화면 다듬기·F4-04 기록/이력·UT-F4 전체)도 집에서 mock·fake_state_pub 로 이어 간다(황인재 9/20 — ROS 인터페이스·로봇 쪽 코드는 9/23 동결 그대로)')
RULES = {       # (A 열, B 열 글자) → (새 B, 새 C)
 ('마감', '9/22(화) 오전'): ('9/22(화) 오후', 'L1 단위기능 테스트(UT-F1·F2·F3·FLOW) 통과 — 함수별 TC 는 구현 직후 바로 수행. UT-F4 는 9/22 저녁. 미통과 기능은 범위 방어표대로 축소 · 코드리뷰(CR-01) · 노션에 노드 구조·HMI 화면·안전 자료 업로드 · GitHub 최신'),
 ('마감', '9/22(화) 저녁'): ('9/23(수) 오전', 'L2 단위기능 통합 완료 (flow_node 에서 실행, 나머지 기능은 use_mock) — 9/22 저녁 시작'),
 ('로봇', '비고 R'): ('비고 R', 'R 표시 작업은 실기 로봇 필요. 🚨 추석(9/24~28)은 교육장이 닫힌다 — 로봇·현장 작업 불가, 집에서 하는 문서·PPT·영상만. 🚨 주말(9/19·20)은 교육장이 18시에 닫는다 → 하루 2슬롯(오전·오후), 저녁 칸 없음. 평일은 3슬롯(오전·오후·저녁). 배정은 전날 브리핑에서, 로봇 1대를 1시간씩 교대. 9/24~28 불가'),
}
NEW_RULES = [
 ('공용 파일', 'cobot_common · config', 'cobot_common 은 사람별 파일: bootstrap.py·config.py·__init__.py·motion.py = H / gripper.py·weigh.py = M / force.py = P (부르는 쪽은 그대로 cc.함수()). config/cell.yaml 은 한석형 혼자(단 cell.force 절의 값은 박진용이 그 절만 PR), params.yaml 은 자기 절만'),
]
HISTORY2 = ['v5.1', '결정', 'DSN-03, F1-02, V-14, V-01', 'DSN-03 회의를 열지 못해 PM 이 결정: 반납 구역 = 고정 슬롯(겹친·어긋난 용기 대응 제외, pick 서명·EMPTY_ZONE·YAML 키는 그대로) · 그릇 = 옆면(벽) 세로 파지(폭 차이가 작으면 무게로 확인) · 그리퍼 폭 경로·이슈 #7 수락 · 9/19 선결정 확정. 나머지 안건은 보류',
            '시간 부족(교육장 18시 마감) — PM 결정 9/19 16시', 'S,M,P,H']
HISTORY3 = ['v5.2', '결정', 'V-01', '그릇의 파지 성공도 파지 폭으로 가른다 — 옆면 세로 파지 폭 ≈ 2 mm 확인(황인재), 무게(WEIGH)로 가르는 대안은 뺐다. V-01 완료 기준을 "세 값 간격 ≥ 6 mm" → "세 범위가 겹치지 않고 그릇 ↔ 빈손 간격이 흔들림의 2배 이상"으로. grip 의 닫는 목표 폭은 기대 폭보다 작게',
            'PM 결정 9/19 (실측 확인)', 'S,M']
HISTORY4 = ['v5.3', '진척', 'V-01', '그릇 옆면 세로 파지 폭 ≈ 2 mm 가 빈손과 구분되는 것을 검증(황인재 9/19). V-01 의 남은 것은 컵·빈손 포함 10회 기록과 허용 오차 값, 드라이버 경로(V-05) 확인',
            '실기 확인 9/19', 'M,S']
HISTORY5 = ['v5.4', '진척', 'INF-02, F1-01', 'INF-02 motion.py 완료(PR #15, 9/19 — 예정보다 반나절 빠름): move_to 는 상공까지만 + 남은 높이 반환, 새 키 cell.motion 4개(값은 한석형). PR #14(rig_f2 안내) merge. F1-01 은 cell.motion·limits 값이 들어오면 바로 착수 가능',
            'PR #14·#15 merge', 'H,S,M,P']
HISTORY6 = ['v5.5', '진척', 'INF-02d, INF-02', 'INF-02d gripper.py 코드 merge(PR #17, 예정보다 하루 빠름) — 실기 확인(V-05·V-23)과 수정 2건(import 가드·힘 기준 맞추는 시점)이 남음. INF-02 move_joint_rel 속도 상한(PR #16) merge',
            'PR #16·#17 merge', 'M,H']
HISTORY7 = ['v5.6', '진척', 'PKG-01, V-20, V-03, V-05, V-01, DSN-04, INF-02b·c·d', '9/19 저녁 진척 취합(GitHub 기록 기준): PKG-01 완료(#4·#8·#12) · INF-02 완료(#15·#16) · INF-02c 0.7(#13·#14) · INF-02d 0.6(#17) · INF-02a 후속 #10·#18 · V-03 실기 4회차(문지르기 방식 확정) · V-05 경로 구현 · V-20 일부 확인 · DSN-04 결정분 문서 반영',
            'PM-01 9/19 저녁', 'S,M,P,H']
HISTORY8 = ['v5.7', '진척', 'INF-02b', 'INF-02b force.py merge(PR #20) — 공용 로봇 함수 파일 5개(bootstrap·motion·gripper·weigh·force)가 모두 main 에 들어왔다. F1-02 pick 이 기다리던 contact_down 사용 가능. 남은 것은 cell.force·cell.motion·limits 값과 실기 확인',
            'PR #20 merge', 'P,S,M']
HISTORY9 = ['v5.8', '진척', 'V-01', 'V-01: 그릇은 빈손과 폭으로 구분됨(검증), 컵은 벽이 아니라 몸통을 통째로 파지해 폭이 충분 — 3상태 구분은 사실상 확인. 남은 것은 드라이버 경로 기록과 허용 오차 값',
            '황인재 확인 9/19', 'M,S']
HISTORY10 = ['v5.9', '일정', 'CELL-04, V-19, F1-01', '티칭 1차(CELL-04)는 9/19 에 그릇 쪽 좌표까지, 컵 쪽은 9/20 오전으로(좌표 작업이 예상보다 오래 걸림). V-19 도 같이 나뉨. F1-01 은 9/20 오후까지 걸칠 수 있음 — 그릇 좌표로 먼저. 9/20 오전 한석형 4건(CELL-04 컵·CELL-04b·V-22·F1-01)',
             '황인재 확인 9/19 17:50', 'S']
HISTORY11 = ['v6.0', '일정', 'CELL-04, V-19, CELL-03, CELL-01', '9/20 아침 황인재 확인: 좌표 작업은 9/20 오전에 끝낸다 · V-19 는 좌표가 끝난 뒤(9/20 오전) · CELL-03 은 9/20 오전으로 · CELL-01 은 좌표 측정과 함께 진행 중 · 티칭 자세 = 기능의 시작 자세로 확정',
             '황인재 9/20', 'S,M']
HISTORY12 = ['v6.1', '재계획', 'CELL-04b, V-22, V-20, V-16, F1-01~05, V-04·06·08·14·15, UT-F1, INT-12b, INT-3a·3b·4a, DSN-03', '좌표 작업 지연에 따른 재계획(황인재 지시): ① 9/20 오전 한석형은 좌표 마무리만 ② F1 사슬을 반 칸씩 뒤로(F1-01 9/20 오후 · F1-02 9/21 저녁 · F1-05 9/22 오전 · F1-03 9/22 오후 · F1-04·UT-F1 9/22 저녁~9/23 오전 · INT-12b 9/23 오전) ③ 한석형 몫 덜기: V-22·V-20 → 황인재 주도, V-16 민범진 단독 ④ L3·L4 는 9/23 오후·저녁, 동결 그대로 — 밀리면 범위 방어 ⑤ DSN-03 완료(B7·B11·B12 승인)',
             '황인재 9/20 (좌표 지연)', 'S,M,P,H']
HISTORY13 = ['v6.2', '일정', 'DOC-02~05, REH-01, REH-02, INT-4d', '추석(9/24~28)은 교육장이 닫힌다(황인재 9/20) — 추석 칸의 일(PPT·영상 편집·대본·문서·온라인 리허설)은 집에서 각자 하는 원격 작업으로 명시. 9/23 저녁 동결 때 영상 원본·측정 결과·사진을 드라이브·저장소에 올린다. 9/29 오전은 브링업·좌표 재현부터 다시 확인',
             '황인재 9/20', 'S,M,P,H']
HISTORY14 = ['v6.3', '확인', 'INT-4d, REH-02', '추석 동안 로봇·기구는 세팅 그대로 둘 수 있다(황인재 확인) → 9/29 오전은 재배치·재티칭 없이 좌표 재현 빠른 확인 뒤 바로 리허설',
             '황인재 9/20', 'S,M,P,H']
HISTORY15 = ['v6.4', '서식·진척', 'DSN-04, 완료 행 전체', '완료한 일은 간트 칸을 회색으로(황인재 9/20 — G6 칸과 같은 서식) — 앞으로 완료 처리하면 자동으로 회색이 된다. DSN-04 완료(contracts.py 설명 PR #21)',
             '황인재 9/20', 'H']
HISTORY16 = ['v6.5', '진척·결함', 'V-20, FLOW-01', 'V-20 Virtual 실행(PR #22): 4개 중 3개 통과 — 실행 뼈대 정상. 결함 1건: flow 의 stop 이 기능 함수 사이가 아니라 용기 사이에서만 먹는다(문서와 다름) → FLOW-01 에 수정 항목 추가(9/21 저녁 INT-4 전), 고친 뒤 rig_v20.py probe 로 재검증하면 V-20 완료',
             'PR #22 · F4 세션 보고', 'M,H']
HISTORY17 = ['v6.6', '진척', 'FLOW-01, INF-02d, V-02', '민범진 회신(9/20): stop 위치는 문서대로(단계 사이마다 정지)로 고친다 — 든 채 멈출 때 파지는 NORMAL 그대로 · gripper.py 수정은 오전 로봇 세션 전에 · V-02 도구 브랜치는 유지(끝나면 PR)',
             '민범진 회신', 'M']
HISTORY18 = ['v6.7', '진척', 'INF-02b', 'PR #23(f3 시험 파일 이름 — 이제 pytest -q src 가 제외 없이 166건)·#24(contact_down 을 시작 힘 대비 변화량으로 · force_off 끝까지 · force_check 추가) merge, TS-05(두산 오류 뒤 복구) 문서 merge',
             'PR #23·#24', 'P,S']
HISTORY19 = ['v6.8', '진척', 'V-20, FLOW-01, INF-02d', 'PR #26(민범진) merge: flow 의 stop 을 단계 사이마다 · 그리퍼 힘 기준 맞추기를 빈손 자리로만 · 그리퍼 실기 시험대 → **V-20 완료(4/4)**, FLOW-01 0.9, INF-02d 0.8. 민범진의 정지 방식 결정 요청 D1~D4 접수(황인재 결정 대기)',
             'PR #26', 'M,H']
HISTORY20 = ['v6.9', '결정', 'CELL-04, CELL-01, FLOW-02, F3-02, F4-03', '황인재 9/20: ① 팔레트 컵 칸 4 → 2(RACK_C1·C2) ② HMI 토픽 확정 — /cell/force(힘 그래프) · /cell/gripping(파지 중/아님) 신설, /cell/grip_width 삭제 — 발행은 flow_node, 9/22 오전까지 ③ HMI 정지 버튼 이름 = "일시 정지"(E-STOP 이라 부르지 않는다)',
             '황인재 9/20', 'S,M,P,H']
HISTORY21 = ['v7.0', '진척', '9/20 오전 칸의 미완료 작업 전부, F4-00, V-24', '9/20 14:50 최신화(황인재 지시): 끝나지 않은 일은 진행 중 + 9/20 오후 칸에 표시. 오늘 merge: PR #21~#24·#26·#28·#29 · TS-05 · F4-00 설계 확정(완료) · V-20 완료. V-24a 정지 가능성 시험 결과 기록(본작업은 결정 대기). 한석형 cell.yaml PR 은 아직 없음',
             '황인재 9/20 · GitHub 기록', 'S,M,P,H']
HISTORY22 = ['v7.1', '결정·재배치', 'V-24, FLOW-03(신규), F4-01~05, UT-F4, V-13, INT-4, NOTE-02, V-22', '황인재 9/20 15:30: ① 일시 정지 = **즉시 멈춤 → 재개하면 하던 동작을 이어서**(V-24 를 선택 과제에서 본작업으로 — motion.py 비동기 전환, 황인재 · 연결은 민범진 FLOW-03 신규) ② 멈춘 용기는 사람이 확인해 마저(resume) 또는 접기(/flow/abort 신설 — 격리) ③ **웹 HMI 는 추석에도 집에서 이어 간다** → F4-01·02 는 9/21 저녁~9/22 오전, F4-03 다듬기·F4-04·UT-F4 전체는 추석으로. 범위: 힘제어·접촉 구간은 그 동작을 마친 뒤 멈춤. 되돌아갈 자리: 단계 사이 정지',
             '황인재 9/20 (V-24a 시험 결과)', 'H,M,P']
HISTORY23 = ['v7.2', '결정 보류', 'V-05, V-23, V-16, INF-02d', '민범진 결정 요청(그리퍼 조작 방법 D1 힘 기준 방향 · D2 HOLD 유지): 황인재 — **검증해 보고 정한다**. 오늘 그리퍼 세션은 지금 코드 그대로, 세션에서 잴 항목을 V-05·V-23·V-16 비고에 적음. gripper.py 버그 3건은 바로 수정. PR #33(V-24a 시험 도구·기록) merge',
             '황인재 9/20 15:50', 'M']
HISTORY24 = ['v7.3', '진척', 'CELL-04', '한석형 브랜치 확인: 좌표 약 25개는 티칭됨(스크립트 안 상수) → cell.yaml 로 옮기는 일이 남음. 늦어진 원인 = cell.yaml 골격과 실제 티칭 방식이 안 맞음 + 전체 경로 Virtual 스크립트 반복. CELL-04 진행 0.7',
             'PM 확인 9/20 16:20', 'S']
HISTORY25 = ['v7.4', '진척', 'V-24, V-22, FLOW-03, INF-02b, CELL-04', 'PR #34 merge — V-24 본작업(이동 함수 비동기 + 폴링 · pause/resume/halt)이 예정(9/21 저녁)보다 빨리 main 에 들어옴. 실기 미검증이라 **9/21 저녁 첫 순서 = V-24 실기 확인 → V-22 → 접촉 동작**. 새 키 cell.motion.move_timeout_s(한석형). FLOW-03 연결 가능',
             'PR #34', 'H,M,P,S']
HISTORY26 = ['v7.5', '진척', 'F2-01, F2-02', 'PR #35 merge — F2 기능 함수 4개(weigh·leftover_loop·shake·dip) 구현, 전체 시험 229건. 값은 임시라 실기 전에 빈 용기 기준값 측정부터. GRIP_FAIL 정책(isolate vs pause)은 황인재 결정 대기',
             'PR #35', 'M']
HISTORY27 = ['v7.6', '결정', 'CELL-04, V-22, F1-01', '황인재 9/20 17:40: 한석형이 정리한 좌표를 황인재가 작업 파일(cell.yaml 등)로 만들어 넘겨준다 — 양식을 데이터에 맞추고(종류별 자세·접근점·슬롯별 절대 자세), 한석형은 빠진 자세만 추가 티칭. F1-01 은 9/21 저녁으로',
             '황인재 9/20 17:40', 'S,H']
HISTORY28 = ['v7.7', '결정', 'V-03, F3-02, V-18', '황인재 9/20 16:30(결정기록 E6): 그릇 닦기를 고정 좌표 방식으로 — 벽 찾기 포기(반지름 고정) · 높이도 고정(Z 215.1 → 59.0) · 힘은 감시·기록만(상한 10 N · 옆 힘 25 N). 원인: 수세미가 로봇 순응보다 물러 닦는 도중에는 벽이 안 잡힌다(V-03). FR-08·SR-08·TR-05·SDD §5.4 수정. V-03 은 기록 PR 만 남음',
             '황인재 9/20 16:30', 'P']

HISTORY29 = ['v7.8', '진척·리스크', 'CELL-04, V-22, F1-01, F2-01, F3-02', 'PR #36 merge — 한석형 좌표 26개가 cell.yaml 에(양식: kind · point · 접근점+끝점, cc.move_to 인자 2개 추가, 팔레트 컵 2칸 5곳). 🚨 리스크: 한석형의 새 자세 8개 + limits·motion·presets 가 9/21 저녁 세션 전에 없으면 실기 이동 불가. V-22 에 posj 자세 5개의 경로 확인 추가',
             'PR #36 · PM 검토', 'S,M,P,H']

HISTORY30 = ['v7.9', '결정·인터페이스', 'INF-02, V-22, CELL-04, FLOW-01, FLOW-03, F1-01', '황인재 9/20 17:00: ① E7 이동에서 안전 높이 경유 삭제(한석형 요청 — 팔레트 적재 자세가 안 나온다) → move_to 는 티칭한 접근점으로 직접, V-22 는 흐름 순서대로 구간 확인, 구현은 F4 세션 PR ② E8 F1 약속에 kind 선택 인자(move_to · place) — contracts·mock_f1·handling 골격 반영, flow·sense 호출부는 민범진',
             '황인재 9/20 17:00', 'S,M,P,H']

HISTORY31 = ['v8.0', '진척', 'F4-01, V-03, CELL-04, F1-04, F4-02', '9/20 17:15: PR #39(F4-01 HMI 뼈대)·#40(cell.force 값) merge → F4-01·V-03 완료. #37(V-03 rig)은 수정 요청 1건. 한석형 회신(E9): 반납 구역은 한 자리 공급 구조 · WEIGH = 픽 +100 · 툴 좌표는 홀더 확정 뒤 · limits·motion·presets 재요청. E7 확인: 후퇴 높이는 남기고 안전 높이는 없앤다',
             'PR #39·#40 · 한석형 회신 · 황인재 9/20 17:10', 'S,M,P,H']

HISTORY32 = ['v8.1', '결정', 'F4-02, CELL-04, F1-02, FLOW-03, FLOW-01', '황인재 9/20 17:25: E9 확인(반납 구역 = 내리막 공급 구조 → 집는 자리 1개) · E10 웹 화면은 이 PC 에서만 · E11 중단의 첫 이동은 HOME · E12 GRIP_FAIL = pause. PR #41(F4-02 버튼·WebSocket) merge → F4-02 완료. FR-02·IRD §2·§6·§8 · SDD §5.2·§7 반영',
             '황인재 9/20 17:25 · PR #41', 'S,M,H']

HISTORY33 = ['v8.2', '진척·재배치', 'CELL-04·04b, V-19·22, F1-01~05, V-14·04·15·08, V-05·23·01·02·16·07, F2-01·02, UT-F2, F3-02·03, V-18·10, UT-F3, V-13, INT-4, F4-03, ARCH-01, MID-01', '9/20 저녁 취합(GitHub 기준) + 9/21 부터 재배치. 9/20 에 못 끝난 실기(그리퍼·무게 세션 · F3-02 고정 좌표 · 남은 티칭)를 9/21 저녁으로 → F1-02 실기·V-14·V-10 은 9/22 오전, F1-05·V-04·V-15·UT-F2 는 9/22 오후로 한 칸씩. F4-01·02 가 하루 앞서 끝나 F4-03 을 9/21 저녁부터. 강사 노션 재확인 — 일정 변동 없음(9/21 오후 중간점검 · 9/29 오전 통합테스트·14시 시연 · 9/30 11시 발표). 🚨 위험: F1 은 코드가 아직 없다 / 툴·홀더 미확정 / MID-01 미착수',
             'GitHub 9/20 17:50 · 강사 노션', 'S,M,P,H']

HISTORY34 = ['v8.3', '분담', 'F1-01, F1-03, V-08, V-19, UT-F1, INT-12b, F1-05, F4-03, ENV-03, NOTE-01, SAFE-01, MID-01·02', '황인재 9/20 20:40: 한석형의 밀린 F1 과업 분담 — F1-01(이동·일반 놓기)·F1-03(툴 집기·반납)+V-08 → 황인재(F4 세션, 한석형 검토) · V-19 실기 확인은 V-22 와 한 세션(황인재 주도) · INT-12b 주도 → 민범진 · 한석형은 집기·안착·팔레트 3개에 집중(🛡 안착은 단순 놓기부터). 황인재 자리: F4-03 은 추석으로, ENV-03 은 9/22 오전, NOTE-01·SAFE-01 초안은 PM 에이전트. 중간점검(MID-01·02)은 9/21 강사 확인 뒤 수정. PR #37 merge',
             '황인재 9/20 20:40', 'S,H,M,P']

HISTORY35 = ['v8.4', '진척', 'INF-02, V-19, V-22, V-24, CELL-04, F1-01, FLOW-01', 'PR #42 merge(9/20 21:00): E7 구현 — move_to 가 티칭 자세로 곧장 + 도착 확인 cc.MoveIncomplete(이동이 도중에 서면 오류) · WEIGH·그릇 집기(접근+그립) 값 · 구역 슬롯 1개(E9). V-22 확인 항목 추가(도착 확인 헛경보 · HOME → RACK_C1 구간 · RET_B 접근점 어긋남). SDD §3.1 · AGENTS §1 · 할일 시트 쉬운 말 3곳(V-24·V-19·F4-02) 정리',
             'PR #42 · PM 검토', 'S,M,H']

HISTORY36 = ['v8.5', '진척·신규', 'V-25(신규), F1-01, F3-02, F3-03, INF-02b, CELL-02b', '9/20 21:50: F1-01 구현·Virtual 확인 끝(F4 세션) → 황인재 지시로 **실기 확인 V-25 신설**(9/21 저녁, V-22 바로 뒤). PR #43(박진용 F3-02·F3-03)은 코드에 막는 사유가 없지만 결정 E6·SR-09 와 다른 곳이 있어 **황인재 결정 대기로 보류**',
             '황인재 9/20 21:30 · PR #43', 'H,S,P']

HISTORY37 = ['v8.6', '결정·진척', 'F3-02, F3-03, V-10, V-03, INF-02b, CELL-02b, F1-01', '황인재 결정 E13(9/20 밤): 닦기는 바닥을 contact_down 으로 찾고 벽면은 힘제어 1.5 N — E6 의 고정 높이를 정정(박진용 실기 근거) · wipe_cup 은 Move Periodic 동시 왕복 · SR-09 각도 완화 · 그릇 받침 유격은 그대로. PR #43(F3-02·F3-03)·#44(F1-01) merge. FR-08·SR-08·SR-09 · SDD §3.1·§4.3·§5.4·§8 · TC-06·07 반영',
             '황인재 9/20 22:00 · PR #43·#44', 'P,S,H']

HISTORY38 = ['v8.7', '진척', 'V-24, V-22, V-19, V-25, F1-03, F4-02', 'PR #45 merge(9/20 23:00): 9/21 저녁 실기 준비물 — rig_pause·rig_coords 실기 모드(작은 이동 · 단계마다 Enter · vel_scale 0.3 상한 · E-Stop 확인 · --from 으로 이어서) + 절차서·기록 양식 3종. F4 선작업 2건은 PR 전(F1-03 툴 집기·반납 · F4-02b 버튼 헤더) — 황인재가 실기에서 보고 승인',
             'PR #45 · F4 세션', 'H']

HISTORY39 = ['v8.8', '재배치', 'CELL-04, CELL-04b, V-24, V-22, V-25, V-05, F3-02, V-18, V-10, 로봇 슬롯', '9/21 아침 점검: 한석형 값이 밤사이 하나도 안 들어왔다 → ① cell.yaml 빈 값 39개를 3단계로 나눔(이동 11 / 그리퍼 16 = 오늘 저녁 세션 산출물 / 닦기 3) ② 저녁 3.5 h 에 7가지(약 5 h)는 안 들어가 **시간으로 끊고** 박진용 닦기 실기·V-18 을 9/22 오전 첫 순서로 ③ 오늘 저녁 티칭은 툴 홀더·SOAP·그릇 접근점만, 나머지는 9/22 오전',
             'PM 9/21 07:45', 'S,M,P,H']

HISTORY40 = ['v8.9', '위임', 'CELL-04, CELL-04b, V-22, F1-02', '황인재 9/21 08:15: 좌표 작업 담당을 한석형 → 황인재(F4 세션)로 위임 — 한석형 쪽이 계속 길어져서. cell.yaml 파일 작업은 F4 가 기다리지 않고 진행(어제의 "값이 올 때까지 넣지 말라" 제한 해제) · 티치펜던트 티칭은 위임되지 않음(로봇 앞에서 사람이) · 한석형은 F1 함수 3개에 집중',
             '황인재 9/21 08:15', 'S,H']

HISTORY41 = ['v9.0', '실기 결과', 'V-22, V-19, CELL-04, CELL-04b, F1-04, V-06, V-07, F2-01, V-24', '황인재 9/21 08:00 V-22 그릇 한 바퀴 실기: ✅ 좌표 정확도 0.11~0.24 mm(기준 2 mm) · ❌ WASTE BOWL 이 손목 특이점(ry 179°)으로 6 mm 앞에서 멈춤 → 재티칭(털기 자세 영향, 민범진 입회) · ❌ 팔레트 그릇 칸에 접근점이 없어 그리퍼가 팔레트에 걸림 → 접근점 2개. 두 건을 저녁 티칭 최우선으로. F4 가 값 21개를 채움(safe_z_mm 235 — 솔이 컵 밖으로 나오는 높이) · presets 16개는 비워 두는 안(황인재 확인 대기)',
             '황인재 실기 · F4 세션 9/21 08:30', 'S,M,H']

HISTORY42 = ['v9.1', '전담', 'CELL-04, CELL-04b, V-19, V-22, F1-02, F1-05, V-14', '황인재 9/21 08:45: 좌표는 **티칭·파일·확인까지 전부 황인재(F4 세션) 전담** — 08:15 위임에서 남겨 뒀던 티치펜던트 티칭도 포함. 한석형은 F1 함수에만 집중(오늘 저녁 로봇 순서 없음 → F1-02 코드를 앞당긴다). 저녁 ③④를 묶어 티칭 직후 그 자세를 바로 확인',
             '황인재 9/21 08:45', 'S,H']

HISTORY43 = ['v9.2', '재분담', 'V-05, V-01, V-25, INT-12b, SAFE-01, CR-01, 로봇 슬롯', '황인재 9/21 08:50 재분담 — 민범진·황인재에 몰린 것을 옮김: ① 그리퍼 세션 35 → 60분(V-25 F1-01 실기를 9/22 오후 F1-03 앞으로 빼서) · 박진용이 옆에서(절차 제안서 작성자) ② INT-12b 주도를 한석형에게 되돌림(좌표가 빠져 여유가 생겼다) ③ SAFE-01 을 박진용이 주도(안전 파라미터 담당 · 오늘 저녁이 비어 있다)',
             '황인재 9/21 08:50', 'S,M,P,H']

HISTORY44 = ['v9.3', '실기 결과', 'CELL-04, V-22, V-19, V-07, 로봇 슬롯', '황인재 9/21 08:40 실기: WASTE BOWL 을 관절 자세로 바꾸자 다음 자리로 가며 6번 관절이 163° 돌아 케이블이 꼬여 로봇 정지 → 그릇 경로 6번 관절 값이 제각각(0·−16·−179·−220·−117) → 오늘 저녁 티칭 = 그릇 경로를 6번 관절이 이어지게 다시 찍기(넘치면 컵 확인을 9/22 오전). rig_coords 가 실기 실패 뒤 자동으로 HOME 가려던 안전 결함을 F4 가 발견·수정(브랜치)',
             '황인재 실기 9/21 08:40', 'H,M']

HISTORY45 = ['v9.4', '일정 정정', 'MID-01, MID-02, NOTE-01, NOTE-02, ARCH-01, PM-01', '황인재 9/21 09:00 강사 확인: **오늘 중간점검 발표 없음** — 노션의 차시별 강의 일정표는 이전 기수 내용으로 보인다(날짜가 적힌 공지 페이지는 이번 기수 것이 맞다) → MID-01·MID-02 해당 없음, 발표 자료 10장 만들지 않는다. 대신 **9/22~23 에 1차 산출물 제출**(① GitHub 최신 ② 노드 구조 노션 ③ HMI 화면) → NOTE-01·NOTE-02 를 그 제출물로 명시',
             '황인재 9/21 09:00', '전원']

HISTORY46 = ['v9.5', '대거 재배치', '9/21 오후·저녁 전부, F1-02·05·03·04, V-14·25·04·15·08·06, F3-02·03, V-18·10, UT-F1·F2·F3, INT-12a·12b·13, 그리퍼 세션, FLOW-01·03', '황인재 9/21 09:10: 중간점검 발표가 없어져 **오후 4.5 h 가 열렸다** → 밀린 일을 반나절 앞당긴다. 오후 = 툴·홀더 → 이동 함수 실기 → 티칭 2 h(6번 관절 경로 재티칭 포함) → 좌표 확인. 저녁 = 그리퍼 60분 → F1-02 집기 실기 → 닦기 3회 → F1-01 실기. 9/22 는 한 칸씩 당겨 **G2(L1) 를 9/22 안에** 닫는 것을 목표로',
             '황인재 9/21 09:10', 'S,M,P,H']

HISTORY47 = ['v9.6', '점검·정리', 'ARCH-01, PM-01, 게이트·강사 일정 표', '9/21 09:50 일정표 점검: 지난 칸에만 남은 미완료 0건 · 칸 없는 미완료 0건 — 구조는 정상. 고친 것 2건: ARCH-01 을 강의 시간(9/21 오전)에서 9/22 오전(NOTE-01 과 같이)으로 · 게이트/강사 일정 표에서 중간점검 삭제하고 9/22~23 1차 산출물 제출 · G2(L1)를 9/22 안에 F1 까지 포함으로. merge 된 원격 브랜치 22개 정리(9/21)',
             'PM 9/21 09:50', '전원']

HISTORY48 = ['v9.7', '원인·재배치', 'V-05·23·01·02, INF-02c·02d, V-07·16, F2-01·02, CELL-03, BRF, PM-01, 로봇 슬롯', '민범진 보고(9/21): 밀린 이유는 **로봇 경합** — 좌표 작업이 로봇을 계속 써서 검증을 못 했고 그동안 다른 작업을 했다. 🔑 그리퍼 세션은 rig_gripper 가 팀 cell.yaml 을 읽지 않아 **좌표와 무관** → 9/21 오후 맨 앞(14:00)으로 옮기고, 좌표가 필요한 V-07·V-16·F2 실기는 저녁 예비 시간으로. 같은 시간에 툴·홀더(P)·F1-02 코드(S) 를 나란히. 교훈은 BRF 에: 아침에 로봇 시간을 먼저 배분한다',
             '민범진 보고 · 황인재 9/21 10:00', 'M,S,P,H']

HISTORY49 = ['v9.8', '재배치', '9/21 오전·오후·저녁 전부, V-05·23·01·02, CELL-02b, F1-02, V-14, V-24, F3-02, V-18, V-25, V-07, INT-12a', '황인재 9/21 10:05: **오늘 오전도 작업 시간**(강의가 비었다) → 전체를 두 시간 더 앞으로. 오전 = 민범진 그리퍼·무게 세션(이틀 밀린 것 · 좌표와 무관) + 툴·홀더(P) + F1-02 코드(S) + 값 PR(H). 오후 = V-24 실기 → 티칭 2 h → V-22 → **F1-02 집기 실기**. 저녁 = 닦기 → V-25 → 민범진 2차 → 여유되면 INT-12a(L2 착수)',
             '황인재 9/21 10:05', 'M,P,S,H']

HISTORY50 = ['v9.9', '우선순위', 'CELL-04·04b, V-24, V-22, V-19, V-05·23·01·02, INF-02c·02d, F1-02, V-14, INT-12a', '황인재 9/21 10:15: **좌표 작업이 가장 먼저** — 오늘 로봇 순서 1번. 오전 = 값 PR → V-24 실기 → 티칭 착수 / 오후 = 티칭 마무리 → V-22·V-19 → 그리퍼 세션 → F1-02 집기 실기 / 저녁 = 닦기 → V-25 → 민범진 2차. 뒤의 모든 실기가 좌표 위에서 돌고, 08:00·08:40 에 드러난 경로 문제를 먼저 잡지 않으면 남이 같은 곳에서 막힌다. 🔸 값 마무리는 책상 작업이라 그동안 로봇이 비면 그리퍼 세션을 끼워 넣을 수 있다',
             '황인재 9/21 10:15', 'H,M,S,P']

HISTORY51 = ['v10.0', '결정 E14', 'CELL-04, CELL-04b, 9/22 오전 로봇 슬롯', '황인재 9/21 10:20: **2차 티칭 일정을 잡지 않는다** — 좌표는 9/21 안에 한 번에 전부 찍어 끝내고, 그 뒤 F1~F3 이 기능 함수를 만들다 이상한 자리를 만나면 그때 요청 → 황인재가 확인해서 고친다(통합 중 요청 기반 수정). 9/22 오전의 "남은 티칭"과 CELL-04b 의 9/22 오전 여유 칸을 뺐다. 이유: 어느 자세가 어떻게 틀렸는지는 함수를 돌려 봐야 나오므로, 미리 잡은 2차 티칭은 고칠 것을 모른 채 로봇을 묶는다. 요청 3줄 양식 = ① 설정 키 이름 ② 무엇이 몇 mm 어느 방향 / 자세 안 나옴 / 길에 걸림 ③ 지금 막혔는지',
             '황인재 9/21 10:20', 'H,S,M,P']

HISTORY52 = ['v10.1', '결정 E15·진단 정정', 'F1-04, F2-01, V-07, SAFE-01, CELL-04', '황인재 9/21 오전(F4 세션 실기) 결정 E15 — 경로 제약 3가지: ① 잔반통(로봇 뒤) ↔ 앞쪽 자리 사이는 HOME 경유(f2.leftover_loop·f1.place) ② 팔레트 칸은 cell.rack.via 경유 + 그릇 칸은 exit_rel_mm 으로 빠져나오기(f1.rack_place) ③ 팔이 쭉 펴지는 자세(J3 ≈ 0°) 금지. 🔄 **9/21 08:40 케이블 꼬임 원인 정정** — 손목(J6 163°)이 아니라 **팔꿈치 특이점(J3 = 1.7°)** 이었다(J6 회전은 posj·posx 어느 쪽이든 비슷하게 난다). 잔반통 그릇 자세를 로봇 뒤쪽 posj [-180,0,90,0,90,0] 로 재티칭. 남은 좌표 11개 목록은 CELL-04 비고',
             '황인재 9/21 11:00', 'S,M,P,H']

HISTORY53 = ['v10.2', '원인 정정·분담', 'V-05, V-01, V-23, V-02, V-16, V-07, FLOW-01, ENV-03, FLOW-02, UT-FLOW, CR-01', '민범진 회신 9/21 11:30: **그리퍼 검증이 막힌 진짜 원인은 로봇 경합이 아니라 그리퍼 드라이버가 안 뜬 것** — pymodbus 미설치(배포본 setup.py 가 pymodbustcp 로 오타). `sudo apt install python3-pymodbus`(3.6.9 · pip 최신은 인자 이름이 바뀌어 안 된다). PM 이 코드에서 확인 ✅, 이 PC 에도 없었다 → PC 4대 점검. 분담: ENV-03 = 민범진 → 황인재 · FLOW-02 를 기록/소모품(넘길 준비, 후보 박진용)과 발행(민범진)으로 나눔 · UT-FLOW·CR-01 은 그대로. FLOW-01 은 코드 완료(PR 대기) — GRIP_FAIL 재개가 그 용기를 버리던 버그까지 고쳤다',
             '황인재 9/21 11:30', 'M,H,P,S']

HISTORY54 = ['v10.3', '신규', 'V-26', '황인재 9/21: **V-26 Ctrl+C 정지 실기 확인**을 새로 넣었다(9/21 오후 · 30초). 구현은 돼 있으나(cc.init 이 SIGINT 를 가로채 → shutdown 이 move_stop stop_mode=1 DR_QSTOP) Virtual(rig_stop.py)만 확인했고 실기 기록이 없다. 긴 이동 도중 Ctrl+C 3회 · 정지 거리 기록 · 브링업 생존 확인. 한계 2가지(메인 스레드 밖에서는 정지 명령이 안 나간다 · move_stop 서비스가 없으면 못 세운다 → E-Stop)와 박진용의 stop_mode 확인 대기도 같이 적었다',
             '황인재 9/21 12:00', 'H,P']

HISTORY55 = ['v10.4', '완료', 'ENV-03', '황인재 9/21 12:10: 환경 셋팅 작업은 전부 끝났다 → 마지막으로 남아 있던 ENV-03(다중 PC 통신 · PC-A↔PC-B DOMAIN 60 에서 토픽·서비스 보임)을 완료 처리. ENV-01·02·04 는 이미 완료였다. v10.2 에서 민범진 → 황인재로 넘긴 분담도 같이 없어졌고, 9/22 오전 "로봇 불필요" 칸에서도 뺐다',
             '황인재 9/21 12:10', 'H,M']

HISTORY56 = ['v10.5', '결정 E16·진행률', 'V-05·01·23·02·07·16, INF-02c·02d, FLOW-01·03, F2-01·02, UT-FLOW, CELL-03, CELL-04', '민범진 보고(9/21 12시대) → 결정 E16: D-A 폭 판정을 **영점 뺀 값**으로(㉠ — grip_zero_mm 새 키, grip_width() 반환값은 그대로 · 빈손으로 꽉 닫아도 10.5~10.9 mm 가 읽혀 BOWL 2.0 은 도달 불가였다) · D-B ISOLATE 2개를 오늘 티칭에 포함 · D-C 오후 세션에서 V-02 를 빼고 저녁으로 · D-D V-02 완료 기준을 "±20 g" → "같은 추 10회의 최대−최소 ≤ 20 g"(하중 옵셋 +42~45 g 은 빈 용기값을 빼며 상쇄된다) · D-E 9/20 D1 철회 확인, D2 는 V-23 뒤. 진행률 정정: FLOW-01 완료 · INF-02d 0.95 · V-05 0.7 · V-23 0.5 · F2-01 0.85 · F2-02 0.8 · FLOW-03 0.15 · V-02 는 진행 중 → 시작 전(실기 측정을 한 적이 없다). 털기 주기 실측 1.099 s(설정 0.60)로 V-07 전제 정정',
             '황인재 9/21 12:30', 'M,H,S,P']

HISTORY57 = ['v10.6', '결정 E17·재배치', 'V-10, F3-02, F3-03, V-18, CELL-02b, SAFE-01, V-26, CELL-04, FLOW-02, CELL-03, UT-FLOW, 9/21 저녁·9/22 오전 로봇 슬롯', '박진용 회신(9/21 13시대) → 결정 E17: ① stop_mode = 1(DR_QSTOP) 확정 ② CELL-02b 툴·홀더 지금 상태로 확정(완료) → 툴 홀더·SOAP 바로 티칭 ③ F3 닦기가 HOME 시작·HOME 끝 + HOME 기준 상대 이동으로 바뀌어 SPONGE_BED wash 좌표 티칭 불필요, 대신 HOME 재티칭 금지 · wipe_cup 은 move_periodic 대신 직선 이어 붙이기 ④ 세척 속도는 vel_scale 예외(황인재 승인 — 0.3 으로 띄워도 닦기는 감속 안 됨) ⑤ FLOW-02·CELL-03 은 민범진이 계속. 진행률 V-10 0.0 → 0.5(값 확정 · 실기만 남음). 로봇: 박진용은 18:30 까지 셋 다 끝내길 원했지만 오후 로봇이 좌표·그리퍼·집기로 차 있어(가장 밀린 F1·F2 먼저) 저녁 첫 두 순서(V-10·F3-02 각 60분)로, soap(90분)은 9/22 오전 첫 순서로',
             '황인재 9/21 13:10', 'P,M,H,S']

HISTORY58 = ['v10.7', '결정 E15④·E18·PR #50', 'CELL-04, F1-04, FLOW-01, F3-03, CELL-03, FLOW-03', 'F4 회신(9/21 오후): 남은 티칭은 ISOLATE 1곳(공용)뿐. **팔레트 그릇 칸 → 컵 반납 구역을 곧장 가다가 로봇이 팔레트에 부딪힌 사고** → 결정 E15 ④ "팔레트에서 다른 구역으로 갈 때는 HOME 을 거친다"(황인재 — 기본 규칙이되 구현하며 불필요하다고 판단되면 실기 근거와 함께 뺄 수 있다). 결정 E18(황인재): 세제 수조를 따로 두지 않고 툴 홀더의 비눗물 컵에서 담근다 → SOAP 자세는 계산값, depth_mm 과 연동 · CELL-03 수조는 헹굼 1개. PR #50(FLOW-03) 변경 요청: 이동 도중 중단 뒤 깃발이 남아 다음 실행의 GRIP_FAIL 이 사람 확인 없이 자동 중단 정리됨(mock 재현)',
             '황인재 9/21 14:00', 'S,M,P,H']

HISTORY59 = ['v10.8', '완료', 'CELL-04, CELL-04b, V-22, F1-04, F2-02, F3-03, FLOW-03', 'PR #51 merge(9/21 오후 · main 8643b82): 좌표 마감 — 빈 자세 0개(남은 빈 값은 그리퍼 프리셋뿐). **임시 좌표**(황인재) — 구현하다 수정·삭제가 필요하면 직접 하고 보고. CELL-04·04b 완료. 🟡 실기 미확인 자세를 각 기능의 첫 실기 항목에 옮김(컵 한 바퀴 → V-22 · 컵 칸 빠져나오기·rack.via → F1-04 · RINSE.CUP 끝점 −13.6 → F2-02 · SOAP 계산값 → F3-03 · 격리 자리 가는 길 → FLOW-03). PM 검토에서 rig_coords ③ 이 채워진 자세로 확인 없이 움직이던 결함을 찾아 고친 뒤 merge. 브랜치 2개 정리',
             '황인재 9/21 15:00', 'H,S,M,P']

HISTORY60 = ['v10.9', '확인', 'F1-04, CELL-04', '황인재 9/21 오후 확인 3건: ① 팔레트가 충돌 때 실제로 밀렸고 손으로 원위치 → RACK_B1·B2 는 복귀 뒤 미확인, F1-04 첫 적재 실기 전 2분 재확인 + 바닥 테이프 표시 ② HOME 경유(E15 ④)는 "필요할 때만" — 기존 기록과 같은 뜻 ③ **구현 방식 > 임시 좌표** — 좌표가 기능에 맞춰 바뀐다, 기능을 좌표에 맞출 필요 없다(E14 보완에 한 줄 추가)',
             '황인재 9/21 15:20', 'S,M,P,H']

HISTORY61 = ['v11.0', '좌표 변경 보고', 'F1-04', '한석형 9/21 14시: 그릇 칸 경유점을 실기로 찾은 posj [-8, 0, 107.8, 86.2, 101.5, -108] 로(그릇 든 채 간섭 없음 확인) — rack.via(HOME 위 z 338 계산값) 대신. E14 보완(직접 수정 후 보고)의 첫 적용 사례. PM 권고: stations.RACK_B_VIA 로 두면 cc.move_to 로 바로 부를 수 있다(지금 rack.via 자리는 move_to 가 못 찾는다). RINSE.CUP 은 main 값 그대로',
             '한석형 9/21 14:07', 'S,H']

HISTORY62 = ['v11.1', '실기 결과', 'V-22, V-19', '황인재 9/21 실기 기록(main 81331f9): V-22 좌표 재현 오차 0.00~0.24 mm → 완료. V-19 도달 범위는 부분 통과 — 팔레트 컵 칸 2곳 미확인(경유 자세를 넣은 뒤 안 돌림) · 손목 큰 회전 경고 5구간 → 한석형 F1-04 적재 실기에서 같이 닫는다',
             '황인재 9/21 14:08', 'H,S']

HISTORY63 = ['v11.2', '진척', 'FLOW-03', 'PR #50 merge(9/21): FLOW-03 정지·재개·중단 연결 코드 완료(진행 0.8). PM 변경 요청(이동 도중 중단 뒤 깃발이 남아 다음 실행이 사람 확인 없이 중단 정리됨)을 민범진이 고쳐 재현 시험 통과. 남은 것 = abort 실기',
             '황인재 9/21 14:11', 'M']

HISTORY64 = ['v11.3', '정정', 'SAFE-01, F3-02, F3-03, FLOW-01', '민범진 지적(9/21 14시)으로 확인: E17 의 바뀐 닦기 코드(HOME 시작·끝 · 직선 이어 붙이기)는 **아직 main 에 없다**(박진용 PC 에만 · 원격 브랜치에도 없음) — SDD·결정기록에 상태 표시, F3-02·03 에 PR 필요 적음. 같이 발견: SAFE-01 확인 칸은 박진용이 오전에 이미 채워 merge(PR #47) — 일정표 0.0 → 0.8, 남은 것은 실측 4줄 + 안전 대책 3줄',
             '황인재 9/21 14:13', 'P,M']

HISTORY65 = ['v11.4', '진척', 'V-10, F3-02, F3-03, SAFE-01, F4-03, F1-03', '9/21 15:40 저장소 기준 진척: 박진용 — 오후에 컵 실기(V-10) 대부분 진행(브랜치 jinyong/20260921-V-10-cup · main 미반영): 문지르기를 6번 축 360° 왕복 × 3 으로 · 컵 바닥 힘 5 N · 바닥 +4 mm · Move Periodic 시도는 4번 축이 움직여 되돌림. E17 닦기 코드·SAFE-01 안전 대책 4줄도 같은 브랜치에. 황인재 — F4-03 운영 화면 STEP 1~3(브랜치). 한석형·민범진 — 오늘 12:30 뒤 push 없음, 진척 미확인. 앞 회차 변경이력의 시각 4개(미래 시각으로 잘못 적음)를 커밋 시각으로 바로잡음',
             '황인재 9/21 15:40', 'P,H']

HISTORY66 = ['v11.5', '결정 E19·완료', 'V-05, V-01, V-23, V-16, V-07, F1-02, INF-02d', 'PR #53 merge(민범진 그리퍼 세션): 그릇 확정(영점 10.58 · 폭 2.15 · tol 0.6 · 20/35 N) → V-05·V-01·V-23 완료. 결정 E19(황인재 "(나)"): 컵은 고정 폭으로 잡고 파지 확인 생략 — 너무 물러 5 N 에도 눌려 빈손과 구분 불가. 한계: 놓쳐도 모름(무게로만 · 컵 30 g 미만이면 불가) · HOLD 안 먹음. 78 mm 에서 실제로 들리는지는 미확인(V-07 전에). D2 = ㉠(털기 뒤 NORMAL 복귀). 정정: 영점은 힘과 무관',
             '황인재 9/21 16:30', 'M,S,H']

HISTORY67 = ['v11.6', '진척', 'INF-02d, F1-02, V-07', 'PR #55 merge(민범진): 팀 cell.yaml 에 그리퍼 프리셋(그릇 E16 확정값 · 컵 E19 고정 폭 78) — 집기 실기·V-07 이 풀림. 20 N 사고의 원인(rig_gripper 가 기본 힘을 미리 채워 컵도 20 N 으로 닫힘)을 찾아 고침. 같은 값의 PR #54(F4)는 충돌로 닫힘 예정',
             '황인재 9/21 16:45', 'M,S,H']

HISTORY68 = ['v11.7', '진척', 'V-10, F3-03, F3-02, SAFE-01, F1-05', 'PR #56 merge(박진용): E17 닦기 코드(HOME 시작·끝 · 바닥은 힘으로만)가 main 에 — 한때 main 에 없던 것이 해결. V-10 완료: 컵 세척 = Periodic 한 명령(TOOL z ±15 + 6번 관절 ±90°) · 3.0 s × 5 · 바닥 + 3 mm · 컵 바닥 힘 5 N · 1·4번 관절 감시. SR-09 각도 ±90° 로 닫음. F3-02 는 그릇 재검증만 남음',
             '황인재 9/21 16:55', 'P']

HISTORY69 = ['v11.8', '진척', 'V-18, F3-03', 'PR #57 merge(박진용): 컵 세척 중 관절 감시 정지 뒤 자동 이동 금지(PM #56 리뷰 반영) · move_line 삭제. V-18 완료(지난 실기로 갈음). SDD §4.3 f3 설정 예시 · §5.4 wipe_bowl·wipe_cup 절차를 #56·#57 동작으로 갱신',
             '황인재 9/21 17:10', 'P']

HISTORY70 = ['v11.9', '최신화', 'V-07, F2-01, CELL-03, V-02, F4-03, INF-02d, V-24', 'GitHub 기준 최신화(9/21 17:10): PR #58 merge(민범진 저녁 F2 실기 절차서) — V-07 은 CELL-03 없이 가능(완료 기준이 충돌 감지 오작동뿐 · 잔반 대용품은 F2-01 전제로). 저녁 순서 V-02 → 컵 78 mm 들리는지 → V-07 → V-16. 브랜치 진척: F4-03 STEP 4·5(0.7) · 민범진 그리퍼 안전 스위치 읽기·풀기(TS-06) · 황인재 공개 정지 함수 cc.stop(). 한석형 — 오늘 push 없음(진척 미확인) · 박진용 — 그릇 재검증 기록 대기',
             '황인재 9/21 17:15', 'M,H']

HISTORY71 = ['v12.0', '검증 수준', 'INT-4b, UT-FLOW, V-02, V-07', 'PR #59 merge(민범진 — flow 재시도 인덱스 겹침 수정 + 저녁 실기 도구). 팀 지적 "실기 검증 없이 가상 검증만 했다" — 사실이다: ① flow 수정은 자동 시험(회귀 시험)만, 실제 재시도 경로는 INT-4b 에서 ② rig_f2 변경(로봇을 움직임)은 오늘 저녁 첫 실행이 검증. PR 에 검증 수준 코멘트를 보충하고 일정표에 "실기 미확인" 표시. 되돌리지 않음(버그 재발 · 저녁 절차가 이 도구를 씀)',
             '황인재 9/21 17:30', 'M,H']

HISTORY72 = ['v12.1', '결정 E20·E21', 'FLOW-02, F4-03, NOTE-02, V-24', '결정 E20(황인재 A): PR merge 는 자동 시험으로 하되 PM 승인 코멘트·일정표에 검증 수준(자동 시험/가상/실기)을 항상 밝힌다. 결정 E21(황인재): /cell/force·/cell/gripping 삭제 — 발행한 적이 없고 힘제어는 몇 초뿐·컵은 파지 판정 안 함 → HMI 힘 그래프·파지 표시 대신 셀 평면도. 민범진·박진용은 발행을 만들지 않는다. PR #60 merge(cc.stop() 공개 정지 함수 · 🟡 실기 미확인)',
             '황인재 9/21 17:40', 'M,P,H']

HISTORY73 = ['v12.2', '보고 반영', 'FLOW-03, F1-02, INT-12a, F1-05, F3-02, SAFE-01, CELL-03, V-07, 9/21 저녁 슬롯', '팀원 보고 3건(9/21 17:40): 민범진 — FLOW-03 코드 끝(0.9 · abort 실기만) · V-02/07/16 준비 끝 · 막힘: 저녁 로봇 시간 · INT-12a 가 한석형 pick() 을 기다림. 한석형 — F1-02 그릇 집기 실기 검증 중(0.3 · push 전 · 실기 뒤 pick() 구현). 박진용 — 막힘 없음 · 그릇 재검증 오늘 저녁 · 속도 1.5 배는 브랜치. 저녁 재배치: V-10·V-18 이 오후에 끝나 18:30 박진용 그릇 40분 → 19:10 민범진 약 100분 → 20:50 V-25. 민범진이 요청한 "force.py 최신 힘 저장 함수" 는 E21(/cell/force 삭제)로 필요 없어짐',
             '황인재 9/21 17:45', 'M,S,P,H']

HISTORY74 = ['v12.3', '분담 조정 E22', 'F1-05, V-04, V-15, INT-12b, F1-02, F1-04, UT-F1, INT-13, 9/22 로봇 슬롯', '황인재 9/21 18:00: 진척 차이에 따라 분담 조정 — 한석형(가장 밀림: F1 기능 4 + 검증 4 가 9/22 에 몰림 · 집기 코드 아직 main 에 없음)의 짐을 덜어 **F1-05 안착 놓기 + V-04 → 박진용**(가장 앞섬 · contact_down·periodic_search 가 본인 force.py · INT-13 첫 단계), **INT-12b 주도 → 민범진**(INT-12a 와 같은 flow 로 이어서). 한석형은 집기 → 적재 → UT-F1 에 집중, pick() PR 은 9/22 오후까지. 9/22 로봇: 오전 박진용 soap → 박진용 안착 → 한석형 집기 마무리 → 민범진 잔여 / 오후 G2 마감 / 저녁 L2',
             '황인재 9/21 18:00', 'S,P,M,H']

HISTORY75 = ['v12.5', '진척', 'FLOW-02, UT-FLOW', 'PR #61 merge(민범진): FLOW-02 기록 — records.csv 용기 1줄 · 소모품 임계 경고 · FlowEvent 빈 필드 채움 → 0.9(실제 값은 L2 에서). UT-FLOW 의 TC-12 가 덮임',
             '황인재 9/21 18:20', 'M']

HISTORY76 = ['v12.6', '진척', 'UT-FLOW', 'PR #62 merge(민범진): UT-FLOW — flow_node 실기동(로봇 없이)으로 정지·재개·중단·예외·Ctrl+C 확인(TC-10) + mock 예외 주입 BOOM → 0.9(로봇 없는 범위 완료 · 실기 항목은 V-24·FLOW-03·INT-4)',
             '황인재 9/21 18:35', 'M']

HISTORY77 = ['v12.7', '검증 범위', 'INF-02d', '팀 보고(황인재 9/21 18:50): 그리퍼는 시뮬레이션에서 검증되지 않는다 → INF-02d(gripper.py) 완료 기준의 "Virtual 에서 가짜 그리퍼 노드로 호출 순서" 를 뺐다. 실기 확인은 9/21 그리퍼 세션(PR #53)에서 끝나 INF-02d 완료. 그리퍼 관련 확인은 앞으로 실기로만 — 리마인드 문서 §6 에 적음',
             '황인재 9/21 18:50', 'M']

HISTORY78 = ['v12.8', '결정 E23', 'V-08, F1-03', '민범진 확인 요청(툴 프리셋 담당이 SDD 한석형 / 일정표 황인재로 엇갈림) → 황인재 확정: V-08 시작 때 황인재가 rig_gripper 로 잰다(값을 쓰는 f1.tool 담당). SDD §9 V-08 담당 정정',
             '황인재 9/21 18:55', 'H,M']

HISTORY79 = ['v12.9', '진척', 'F1-02, F1-04, CELL-04, INT-12a', 'GitHub 기준(9/21 21:35): 새로 merge 된 팀원 PR 은 #63(툴 프리셋 확인 요청 — E23 으로 처리)뿐. 한석형이 브랜치에 실기 그릇 한 바퀴 스크립트를 올림(18:25~21:26) → F1-02 0.4 · F1-04 0.3. 🚨 실기로 확인한 좌표 2개(그릇 집기 관절값 · 팔레트 경유점)가 스크립트 상수에만 있어 cell.yaml 반영 필요. 민범진·박진용의 저녁 실기 결과는 아직 올라오지 않음',
             '황인재 9/21 21:35', 'S']

HISTORY80 = ['v13.0', '진척', 'F1-02, F1-04, V-14, UT-F1, INT-3b, INT-4a', '황인재 확인(9/21 21:45): 한석형 F1 은 그릇만 구현(실기 스크립트로 한 바퀴 확인) · 컵 동작은 지금 구현 중. 컵에 걸리는 항목(V-14 컵 슬롯 · UT-F1 컵 칸 · INT-3b · INT-4a)에 표시',
             '황인재 9/21 21:45', 'S']

HISTORY81 = ['v13.1', '진척', 'F4-03, NOTE-02', 'F4 보고(9/21 21:50): F4-03 운영 화면 0.7 → 0.85 — 그림 카드 · 팔레트 입체 그림 · 숫자 패널 · 이력 표 · 알람 띠까지, 가짜 flow 대본 5개로 확인(🟡 실제 flow_node 연결은 L3). 9/22 그림 수정 → 확인·승인 → PR',
             '황인재 9/21 21:50', 'H']

HISTORY = ['v5.0', '재계획', '주말 저녁 칸 전체, V-01·05·23, INF-02·02d(신규)·02b·02c, PKG-01, DSN-03·04, F1-01~05, F2-01·02, F3-03, F4-00~03, UT-*, INT-*, 게이트·로봇 슬롯·규칙',
           '① 주말(9/19·20)은 교육장 18시 마감 → 주말 저녁 칸을 전부 비움(DSN-03 은 9/19 17:15 교육장) ② 한석형은 9/19 티칭까지만 ③ 분담 변경: 그리퍼 검증 V-01·05·23 + gripper.py(신규 INF-02d) = 민범진, '
           '이동 함수 motion.py(INF-02)·cell.force 골격·F1 패키지 골격 = 황인재, 한석형 = 티칭·cell.yaml 값·실기·F1 기능 함수 ④ 게이트: G1 9/20 오후 · L1 9/22 오후 · L2 9/23 오전 · L3 9/23 오후 · 동결 9/23 저녁 그대로(밀리면 범위 방어) ⑤ V-24 보류',
           '교육장 주말 운영 시간(18시 마감) · 한석형 티칭 지연 · 이슈 #7·B11·grip_width 요청을 한석형 부담 없이 수락하기 위함 (PM 결정, DSN-03 에서 확인)', 'S,M,P,H']


# ---------------------------------------------------------------- 9/22 07:50 9/21 밤 팀원 보고 3건 + PR #64 → 새 작업 ENV-05 · 진척 · 9/22 로봇 순서
NEW.append(
 ('ENV-05', 'ENV-02', 'ENV-02', '환경', '툴(그리퍼) 무게·무게중심 등록 + TCP 확인 — Dart 툴 설정(자동 측정). 🆕 요구사항(BR-SR §5.2·SR-04)엔 전제인데 일정표에서 빠져 있던 작업',
  'H(M)', '시작 전', S('9/22 오전'),
  '`cell.yaml` 주석에 툴 이름·무게·무게중심·TCP (M0609_환경설정 문서가 정한 자리) + `docs/meetings/20260921_확인요청_툴무게등록_민범진.md` §3 빈칸',
  '① 빈 그리퍼 무게·무게중심 등록(필수) → 브링업 다시 → ② 민범진 R2: `rig_weigh_probe -n 10` 을 WEIGH 자세 z 158 · z 235 에서 빈손·그릇 — 등록 전(z 235 빈손 24 g · z 158 은 0 에 잘림)보다 **자세 사이 차이가 줄었는가** · '
  '③ 값 기록(R3). 🟡 수세미 툴 쥔 상태(2종째)는 등록만 해 둔다 — 코드에 툴을 바꿔 끼우는 부분(set_tool)이 없어 지금은 안 쓴다(F3 는 힘 "변화량" 으로 판정해 영향이 작다)',
  '민범진 확인요청(9/21 밤 · PR #64): 무게가 자세마다 60 g 다르다(WEIGH.BOWL z 158 그릇 9 g · z 235 그릇 68 g) → 관절 토크로 무게를 추정하는데 그리퍼 무게·무게중심이 컨트롤러에 안 맞으면 자세마다 오차가 달라진다. '
  'ENV-02 는 "확인" 만이었고 등록 기록이 없다. 🚨 **9/22 첫 로봇 작업** — V-02·V-07·INT-12a(무게) 와 F3 힘제어가 이 위에서 돈다. Dart 와 ROS 동시 제어 금지 → 브링업 내리고 한다 · 안전 암호가 필요할 수 있다(강사). '
  '등록 뒤에도 z 158 빈손이 0 근처면 WEIGH.BOWL z 를 235 로(민범진이 직접 고치고 보고 — E14 보완)'))

N21 = '📥 9/21 밤 보고'
REP0922 = {
 'ENV-02':  dict(note_add='🔎 9/21 밤: 툴 **무게·무게중심 등록**은 이 작업에 없었다(확인만) → **ENV-05 로 새로 뺐다**(9/22 오전 첫 순서)'),
 'V-02':    dict(slots=S('9/22 오전'), note_add=N21 + '(민범진 · PR #64): 🔴 `get_workpiece_weight()` 단위가 **kg** 이었다(그동안 g 로 계산 → 무게가 전부 "0 g" → GRIP_FAIL) — weigh.py × 1000 수정 merge. '
                          '자세마다 오차가 다르다(z 158 그릇 9 g · 0 에 잘림 / z 235 그릇 68 g · 빈손 24 g) → **ENV-05 툴 무게 등록 뒤** 재측정(R2 15분) → V-02(`rig_f2.py empty -n 10` → params.yaml `f2.empty_weight_g` — 지금 BOWL 180 은 임시값). 저녁 INT-12a 의 전제'),
 'INF-02c': dict(prog='0.85', note_add=N21 + ': PR #64 merge — 하중 단위 kg→g(🟢 실기로 단위 확인) + 원값 탐침 `rig_weigh_probe.py`(로봇 안 움직임). 남은 것 = V-02 기준값'),
 'F2-01':   dict(note_add=N21 + ': HOME↔저울↔잔반통 경로 실기 OK(케이블 꼬임 없음 · 털기는 안 함). 무게 단위 수정(PR #64)으로 첫 실행 GRIP_FAIL 원인 해결 · 🟡 판정값은 V-02 뒤'),
 'V-07':    dict(slots=S('9/22 오후'), note_add=N21 + ': 9/21 저녁엔 못 함(무게 문제로 시간 씀 · 로봇 넘김) → 9/22 오후 첫 순서. 그릇 저속 1회 → 원속 3회(알람·미끄러짐·실제 주기) → 컵(E19 — HOLD 안 먹음, NORMAL 로 버티는지). rig_f2 연속 3회라 UT-F2 와 같이'),
 'V-16':    dict(slots=S('9/22 오후'), note_add=N21 + ': 9/22 오후 V-07 과 같이. ✅ 컵 78 mm 로 **들린다**(강하게 고정 · 약간 눌리지만 허용 · 놓으면 복원 — E19 숙제 끝) · 그릇 폭 2.42 mm × 2회 재현'),
 'UT-F2':   dict(slots=S('9/22 오후'), note_add='9/22: V-07·V-16 을 rig_f2 로 연속 3회 돌리면 TC-03·04·08 과 겹친다 — 같이 기록'),
 'INT-12a': dict(note_add=N21 + '(민범진 · PR #64): 시험대 `rig_int12.py` 준비 — flow.py 와 같은 순서·인자로 5회 · `check` 가 로봇 없이 F1 빈 껍데기·좌표를 먼저 거른다 · 🟢 가상 그릇·컵 12/12(**이동·순서만**) · 🟡 실기 미확인. '
                          '절차서 `docs/test_logs/20260922_INT-12_절차와기록_민범진.md`. 🚨 전제 3개: ① 한석형 pick() merge ② V-02 값 ③ ENV-05. **그릇부터** — 컵은 한석형 컵 구현 뒤'),
 'INT-12b': dict(note_add=N21 + ': 같은 시험대(rig_int12.py b) · 가상 12/12(이동·순서만 · 회차당 ≈ 20 s 일정). 전제: 한석형 rack_place(F1-04) merge. 그릇부터'),
 'F3-02':   dict(note_add=N21 + '(박진용): ✅ 한석형 경로 + 9/20 확정 닦기(rig_v03)로 **그릇 한 바퀴 통합 실기 1회 끝까지 성공**(합계 177 s · 닦기 19 s · 바닥 2.7 N · 나선 반지름 14.5 mm). '
                          '🔴 그러나 main 의 wipe_bowl 재검증은 **실기 5회 모두 실패** — 4회: 바닥 6~7 N 까지 눌린 채 나선이 시작 안 함(알람 없음) → 올라와 HOME · 1회: 바닥 찾기가 출발 안 함 + 컨트롤러 연결 끊김. '
                          '→ 9/20 확정본 값·순서로 되돌림 · 바닥 찾기 = 순응 + 힘제어 3 N · 빠른 하강 135 → 140 mm · 그릇 빠른 하강 속도도 9/20 값(200 mm/s)으로(컵은 1.5 배 그대로) · 컨트롤러 상태·알람 로그 추가. '
                          '🟡 실기 전 → **9/22 오전 재검증 3회** → 통과하면 PR(cc.stop() 교체 포함). ❓ PR 에 "전체 120 s 상한 없앰" — 황인재 확인 대기'),
 'UT-F3':   dict(note_add='9/22: 오전 그릇 재검증 3회를 **제품 코드(wipe.py)로** 돌리면 TC-06(연속 3회)으로 갈음 · TC-07 컵은 V-10(9/21)'),
 'SAFE-01': dict(note_add=N21 + ': 실측 줄 아직 — 9/22 재검증 결과로 채운다 · `find_max_mm` 는 9/20 확정본 값 **30** 유지(25 로 줄이지 않음)'),
 'F3-03':   dict(note_add='❓ 9/22: soap 실기 결과는 아직 보고 없음 — 안 했으면 오후 F1-05 슬롯에 20분'),
 'F1-05':   dict(slots=S('9/22 오후'), note_add='❓ 9/22: 9/21 밤 박진용 보고에 없다(E22 로 받은 작업) → 오후 로봇 슬롯에 넣었다. 저녁 INT-13 의 첫 단계라 오늘 안에'),
 'V-04':    dict(slots=S('9/22 오후'), note_add='9/22 오후 F1-05 와 같이(스펀지 홈에서 한 번에)'),
 'F1-02':   dict(prog='0.5', note_add=N21 + '(한석형): 그릇 전체 실기 동선 1회 완주 · 컵은 **집기 → 스펀지 홈 놓기·재파지까지** 구성. 🚨 브랜치 `seokhyung/20260921-CELL-04-final-coords` 는 **시험 스크립트 1개(rig_bowl_scenario_real.py)뿐** — handling.py pick() · cell.yaml 좌표는 아직. '
                          '⚠ 마지막 push(82fcba4)는 **345행 들여쓰기 오류로 실행되지 않는다**(PM 확인) — 시연한 것은 그 앞 버전. pick() PR 은 **9/22 오후까지**(INT-12a 전제) · 좌표 2개는 그 PR 에 같이'),
 'F1-04':   dict(note_add=N21 + '(한석형): 컵 C1 — 기존 접근 높이·경유점이 실물과 안 맞아 **릴리즈 좌표 +100 mm 에서 X·Y 를 맞춘 뒤 수직 하강**으로 재검증 중 · C1 릴리즈 재티칭(posx [266.41, 459.33, 267.91, 91.59, 80.0, -86.5]) · C2 는 C1 뒤. 9/22 오전 30~60분'),
 'CELL-04': dict(note_add=N21 + ': ① 한석형 실기 좌표는 아직 스크립트 안에만(pick() PR 때 cell.yaml) ② 박진용 지적 "잔반통 → HOME 직선(XYZ)으로 몸통 위를 지난다" — 9/21 21:02 버전(e4ffaaf)이 그랬고, 21:26 버전(82fcba4)은 관절 이동(J6 유지)으로 바꿨으나 **들여쓰기 오류로 아직 한 번도 안 돌았다** → 오전 한 바퀴 재검증 때 확인(E15 — 몸통을 가로지르지 않는다)'),
 'V-08':    dict(slots=S('9/22 오후'), note_add=N21 + '(박진용): 한석형 스크립트의 수세미 잡는 폭은 **30 mm** 인데 실측 손잡이는 **25.6 mm** — 못 잡을 수 있다 → E23 대로 **V-08 첫 단계에서 황인재가 잰 프리셋 하나로 통일**(한석형 스크립트도 그 값). 끝나면 F1-03 PR(저녁 INT-13 전제)'),
 'F1-03':   dict(note_add='🚨 9/22: 저녁 INT-13 이 f1.tool 을 쓴다 → **V-08 뒤 바로 PR**(지금 브랜치에만). 박진용 지적 "수세미를 홀더에서 꺼내 HOME 까지 가는 동작이 양쪽 다 없다" 는 두 사람 **시험 스크립트** 이야기 — 제품 코드는 이 브랜치의 tool(PICK) 이 홀더에서 빼내고(↑) → soap → wipe_bowl 이 HOME 으로 간다'),
 'INT-13':  dict(note_add='🚨 9/22 저녁 전제 3개: ① F1-05 안착(박진용 · 오후) ② F1-03 tool merge(황인재 · V-08 뒤) ③ soap 실기. 박진용 9/21 밤: 한석형 경로 + 9/20 닦기로 그릇 한 바퀴 1회 성공 — 흐름 자체는 실기로 한 번 돌았다'),
 'V-24':    dict(slots=S('9/22 오후'), note_add='9/22 오후 H 20분 칸(V-25·V-26 과 같이 — 안 한 것만)'),
 'V-25':    dict(slots=S('9/22 오후'), note_add='9/21 저녁 슬롯(20:50)에 있었으나 기록 없음 → 9/22 오후 H 20분 칸. 이미 했으면 결과만 적는다'),
 'V-26':    dict(slots=S('9/22 오후'), note_add='9/21 기록 없음 → 9/22 오후 H 20분 칸(30초 작업). 이미 했으면 결과만 적는다'),
}
# 지난 칸(9/21)에만 남은 진행 작업을 오늘 칸으로 · 부하 조정
for _tid, _sl in {'F3-02': S('9/22 오전'), 'UT-F3': S('9/22 오전', '9/22 오후'), 'F3-03': S('9/22 오후'), 'INF-02c': S('9/22 오전'),
                  'F1-01': S('9/22 오후'), 'F1-04': S('9/22 오전', '9/22 오후'), 'INT-4': S('9/22 저녁', '9/23 오전'),
                  'V-19': S('9/22 오후'), 'CELL-03': S('9/22 오전')}.items():
    REP0922.setdefault(_tid, {})['slots'] = _sl
REP0922['V-19']['note_add'] = '9/22: 남은 팔레트 컵 칸 2곳 · 손목 큰 회전 구간은 한석형 F1-04 컵 칸 실기(오전 경로 · 오후 적재) 때 같이 보고 닫는다'
REP0922['CELL-03']['note_add'] = '9/22: 잔반 대용품(≥100 g)은 저녁 INT-12a 에서 쓴다 → 오전(로봇 불필요 시간)에 마무리'
REP0922['INT-4']['note_add'] = '9/22: 황인재 오후가 V-08·F1-03·V-24~26 으로 차서 저녁 → 9/23 오전(G3 L2 마감)으로'
# 진행 중인 작업은 지난 칸(한 일의 기록)을 지우지 않는다 — 9/22 칸 앞에 v13.1 의 지난 칸을 붙인다
_PAST = {'INF-02c': S('9/20 오전', '9/20 오후', '9/21 오후'), 'V-19': S('9/20 오전', '9/20 오후', '9/21 오후'), 'F1-01': S('9/21 저녁'),
         'CELL-03': S('9/20 오전', '9/20 오후', '9/21 오전'), 'F3-02': S('9/21 저녁'), 'F3-03': S('9/21 저녁'), 'V-24': S('9/20 오후', '9/21 오전')}
for _tid, _sl in _PAST.items():
    REP0922[_tid]['slots'] = _sl + [x for x in REP0922[_tid]['slots'] if x not in _sl]
for _tid, _e in REP0922.items():
    EDIT.setdefault(_tid, {}).update(_e)

LECTURE['9/22 화'] = (LECTURE['9/22 화'][0],
  '🔁 9/21 밤 보고 반영: 오전 **툴 무게 등록(ENV-05) → V-02 → 그릇 닦기 재검증 → 컵 팔레트 경로**, 오후 V-07·V-16 · V-08(→ F1-03 PR) · F1-05 안착 · F1-04 적재 → UT 로 **G2(L1) 마감**, 저녁 L2(INT-12a 그릇 · INT-13 · INT-12b 착수) · 노션 업로드(1차 산출물)')
SLOT['9/22 화'] = {
 'B': ('🔁 9/21 밤 보고 반영 — 🥇 **① 황인재 ENV-05 툴 무게·무게중심 등록(20분 · Dart · 브링업 내림)** — 무게·힘 판정이 전부 이 위에서 돈다, 그래서 맨 앞(브리핑 전 09:00 에 시작하면 여유) → '
       '**② 민범진 R2 자세별 재측정 + V-02 빈 용기 기준값(35분 — 저녁 INT-12a 전제)** → **③ 박진용 F3-02 그릇 닦기 재검증 3회(25분 · 9/20 확정본 · 제품 코드로 = UT-F3 TC-06)** → '
       '**④ 한석형 컵 C1·C2 경로 + 한 바퀴 재검증(45분)** → **⑤ 박진용 + 한석형 그릇 동선 통합 1회(15분)** · '
       '로봇 불필요: 한석형 pick() 본 구현(그릇 · 컵)·좌표 cell.yaml 반영 · 황인재 F4-03 그림 수정 → PR · NOTE-01 · CR-01(전원)'),
 'C': ('**G2(L1) 마감**: **① 민범진 V-07 털기 · V-16(그릇 → 컵 · 40분 · rig_f2 연속 3회 = UT-F2)** → **② 황인재 V-08 툴 프리셋 측정 + 10회(45분 · 수세미 폭 하나로 통일 — E23) → F1-03 PR** → '
       '**③ 박진용 F1-05 안착 놓기 + V-04(45분 · E22) + soap(안 했으면 20분)** → **④ 한석형 F1-04 적재 + V-06(그릇 칸 · 45분)** → UT-F1(S·H) · V-24·V-25·V-26(H · 20분 · 안 한 것만) · '
       '🚨 한석형 **pick() PR 은 이 시간까지**(저녁 INT-12a) · 🚨 **F1-03·F1-05 도 이 시간까지**(저녁 INT-13) · 로봇 불필요: INT-4(H·M) · NOTE-02 gif(H)'),
 'D': ('L2: **INT-12a 그릇(M 주도·S · 60분 — 먼저 `rig_int12.py check`)** → **INT-13(P 주도·S · 60분)** → **INT-12b 그릇 착수(M 주도·S)** · 컵은 한석형 컵 구현 뒤(9/23 오전) / UT-F1 잔여(S) · '
       '로봇 불필요: UT-FLOW(M) · NOTE-02 gif(H)'),
}
EASY['ENV-05'] = '로봇 컨트롤러(Dart)에 그리퍼의 무게와 무게중심을 등록한다. 로봇은 관절 힘으로 무게를 추정하는데, 이 값이 틀리면 자세마다 무게가 다르게 읽힌다(9/21 60 g 차이). 브링업을 내리고 하고, 끝나면 민범진이 두 자세에서 다시 재 본다'
SLOT['9/23 수']['B'] = 'INT-12b 마무리(**M 주도**·S) · INT-12a·12b **컵** · INT-13 잔여(P·S) · UT-F4·F4-05(H) — G3(L2) · 🛡 L1 잔여가 있으면 여기서 닫는다'

HISTORY82 = ['v13.2', '보고 반영·신규', 'ENV-05(신규), V-02, V-07, V-16, INF-02c, INT-12a·12b, F3-02, SAFE-01, F1-02, F1-04, F1-05, V-08, F1-03, INT-13, V-24·25·26, 9/22 로봇 슬롯',
             '9/21 밤 팀원 보고 3건 + PR #64(민범진) 반영. 🆕 **ENV-05 툴 무게·무게중심 등록**(황인재 · 9/22 오전 첫 순서) — 요구사항엔 전제인데 일정표에 없었다(민범진: 무게가 자세마다 60 g 다름). '
             '민범진 — 하중 단위 kg 발견·수정(merge) · 컵 78 mm 들림(E19 숙제 끝) · INT-12 시험대(가상 12/12) · V-02·07·16 → 9/22. 박진용 — 그릇 한 바퀴 통합 실기 1회 성공 · 그러나 main wipe_bowl 재검증 5회 모두 실패 → 9/20 확정본으로 되돌려 9/22 오전 재검증. '
             '한석형 — 그릇 동선 완주 · 컵 집기·재파지 구성 · 팔레트 C1 조정 중 · 브랜치는 시험 스크립트뿐(마지막 push 는 들여쓰기 오류로 실행 불가). 9/22 로봇: 오전 ENV-05 → V-02 → 닦기 재검증 → 컵 경로 / 오후 V-07·16 → V-08 → F1-05 → F1-04 / 저녁 INT-12a → INT-13 → INT-12b',
             '황인재 9/22 07:50', 'S,M,P,H']


# ---------------------------------------------------------------- 9/22 08:15 황인재 결정(120 s 상한 남김) + F4 확인(V-24·25·26 실기 9/21 미실시)
F4C = '🔎 9/22 08:15 F4 확인'
P0815 = {
 'F3-02': dict(note_add='✅ 9/22 08:05 황인재 결정: **그릇 닦기 전체 120 s 상한(`f3.wipe_bowl.duration_s`)은 남긴다** — 박진용 요청은 실기 근거가 아니었다(본인 보고 "실기 확인 전" · 어젯밤 5회 실패 중 120 s 에 걸린 것 없음 · 되돌린 9/20 rig_v03 에 전체 상한이 없어 같이 빠진 것으로 보임). '
                          '정상 19 s 라 평소엔 안 걸리고, 있어야 flow 의 TIMEOUT 정책(재시도 1 → 격리)이 닦기에서 작동한다. 오늘 단위시험(재검증 · UT-F3)에서 상한 때문에 막히면 **몇 초에 걸렸는지 기록과 함께** 삭제 요청'),
 'V-24':  dict(note_add=F4C + ': 실기 기록(`docs/test_logs/20260921_V-24_실기_일시정지_황인재.md`)의 결과 칸이 비어 있다 → **실기는 아직**(Virtual 10/10 만). 9/22 오후 H 30분 칸'),
 'V-25':  dict(note_add=F4C + ': 9/21 **안 함** — 기록 양식(`docs/test_logs/20260921_F1-01_실기_황인재.md`) 결과 칸 전부 빈칸 · 저녁엔 F4-03 작업. 9/22 오후 H 30분 칸'),
 'V-26':  dict(note_add=F4C + ': 9/21 **안 함** — 기록 파일(`20260921_V-26_CtrlC정지_실기_황인재.md`)이 main 에 없다. 9/22 오후 H 30분 칸(30초 작업)'),
}
for _tid, _e in P0815.items():
    EDIT.setdefault(_tid, {}).update(_e)
SLOT['9/22 화']['C'] = SLOT['9/22 화']['C'].replace('V-24·V-25·V-26(H · 20분 · 안 한 것만)', 'V-24·V-25·V-26(H · 30분 — 셋 다 9/21 실기 안 함 · F4 확인)')
HISTORY83 = ['v13.3', '결정·확인', 'F3-02, V-24, V-25, V-26, 9/22 오후 로봇 슬롯',
             '황인재 9/22 08:05: 그릇 닦기 전체 120 s 상한은 남긴다 — 박진용 요청은 실기 근거가 아니었다(9/20 rig_v03 에 맞추다 같이 빠진 것) · 오늘 단위시험에서 막히면 기록과 함께 요청. '
             'F4 확인(08:15): V-24 실기 · V-25 · V-26 은 9/21 에 하지 않았다(기록 칸 빈칸 · 파일 없음) → 9/22 오후 황인재 칸 20 → 30분',
             '황인재 9/22 08:15', 'P,H']


# ---------------------------------------------------------------- 9/22 08:40 F4 보고 — ENV-05 툴 무게 등록 끝 · 황인재가 시트에서 MID-01·02 행 삭제
for _k in ('MID-01', 'MID-02'):          # 황인재 9/22 시트에서 행 삭제(해당 없음) — 없는 행을 고치려 하지 않게
    EDIT.pop(_k, None)
TW = '✅ 9/22 08시대 F4 보고(황인재 실기 · Dart 자동 측정 2회)'
P0840 = {
 'ENV-05': dict(status='완료', prog='1.0', note_add=TW + ': 툴 무게 **1.400 → 1.440 kg** · 무게중심 (0.17, 4.85, 10.91) → **(3.98, −3.21, 2.45) mm** — 1·2회 차이 10 g · 3.5 mm(흔들림), 실습 때 값과 40 g · 12 mm 달라 실습값이 틀렸다고 보고 2회 값을 **기존 `Tool Weight` 항목에** 저장. '
                          'TCP `GripperDA_v1`(Z 208 mm)은 확인만 → cell.yaml 좌표 전부 그대로. 이름을 안 바꾼 이유: 박진용 rig_v03·rig_v10 이 툴 이름 `Tool Weight`·TCP `GripperDA_v1` 이 아니면 실행을 거부한다. '
                          '수세미 툴 쥔 상태(2종째)는 등록 안 함(코드가 안 씀). 남은 것: R2 재측정은 민범진(V-02) · R3 cell.yaml 주석 + 기록 `docs/test_logs/20260922_ENV-05_툴무게등록_황인재.md` 는 F4 작은 PR(황인재 확인 뒤)'),
 'V-02':   dict(note_add='🔔 9/22 08시대 ENV-05 끝(툴 1.440 kg) → R2·V-02 는 **새 설정으로** 잰다. 9/21 값(z 158 그릇 9 g · z 235 68 g/24 g)은 "등록 전" 비교용으로만 — 기준값으로 쓰지 않는다. R2 의 핵심 = 자세 사이 차이가 줄었는가. params.yaml empty_weight_g(BOWL 180 · CUP 120)는 아직 임시값이라 버릴 실측값 없음'),
 'F3-02':  dict(note_add='🔔 9/22 08시대 툴 무게 변경(1.400 → 1.440 kg): 닿음 찾기·힘 상한·옆 힘 감시·벽면 목표 1.5 N 은 전부 "공중 기준 대비 변화량"이라 누르는 힘은 그대로여야 정상(F4 코드 확인). 공중 기준값(9/19 V-03 1.9~2.3 N)이 0 쪽으로 줄었으면 오히려 맞게 된 신호 — 값을 다시 맞추지 않는다'),
}
for _tid, _e in P0840.items():
    EDIT.setdefault(_tid, {}).update(_e)
_o = ('🥇 **① 황인재 ENV-05 툴 무게·무게중심 등록(20분 · Dart · 브링업 내림)** — 무게·힘 판정이 전부 이 위에서 돈다, 그래서 맨 앞(브리핑 전 09:00 에 시작하면 여유) → ')
assert _o in SLOT['9/22 화']['B']
SLOT['9/22 화']['B'] = SLOT['9/22 화']['B'].replace(_o, '✅ **① ENV-05 툴 무게 등록 끝(08시대 · 1.400 → 1.440 kg · TCP 그대로 — 오늘 평소와 다른 충돌 알람이 나면 이것부터 떠올린다)** → ')
HISTORY84 = ['v13.4', '완료', 'ENV-05, V-02, F3-02, MID-01·02(행 삭제 보존)',
             'F4 보고(9/22 08:40): ENV-05 툴 무게·무게중심 등록 끝 — 1.400 → 1.440 kg · 무게중심 (3.98, −3.21, 2.45) mm · TCP 그대로(좌표 영향 없음) · 기존 항목 이름 유지(박진용 시험대가 이름을 확인). '
             '민범진 R2·V-02 는 새 설정으로(9/21 값은 비교용만) · 박진용 힘 판정은 변화량이라 영향 없음이 정상. 황인재가 시트에서 지운 MID-01·02 행은 패치가 되살리지 않게 함',
             '황인재 9/22 08:45', 'M,P,H']


# ---------------------------------------------------------------- 9/22 09:50 PR #66 merge(F4-03 운영 화면) · F4 보고 V-26 통과 · V-24 ① 끝
P0950 = {
 'F4-03':   dict(status='완료', prog='1.0', note_add='✅ 9/22 PR #66 merge(황인재 직접 실행 확인·승인): 운영 화면 — `/` = Next.js 정적 화면(web/out) · `/test` = 시험 페이지 · 단계 그림 카드 · 팔레트 입체 그림 · 숫자 패널 · 이력 · 누적. '
                          '검증: 병합본 370 통과(두 환경) · f4_hmi 29+1 · 가짜 flow 대본 5개 · 🟡 실제 flow_node 연결은 INT-4 · L3. 🔔 후속(막는 사유 아님): ① 연결 끊김이면 일시 정지 버튼이 꺼진다 → 켜 두는 쪽 권장 ② 화면 PC(PC-B)에서 `npm install && npm run build` 필요(안 하면 / 가 시험 페이지)'),
 'V-13':    dict(status='완료', prog='1.0', note_add='✅ 9/22 PR #66: 운영 화면에서 가짜 flow 대본 5개(정상 · 일시 정지 · 격리 · 오류 · 빈 구역)로 PAUSED·재개 반영 확인(황인재 직접). 버튼 → 실제 flow 반응은 INT-4'),
 'V-26':    dict(status='진행', prog='0.9', note_add='✅ 9/22 오전 F4 보고: Ctrl+C 정지 실기 **5/5 통과**(0.47~0.50 s). 기록 PR 은 황인재 확인 뒤 → merge 되면 완료'),
 'V-24':    dict(note_add='📈 9/22 오전 F4 보고: 실기 ① 관절 이동 일시 정지 → 재개 2회 OK. ②③④ 는 로봇이 빌 때 다시(움직이는 중 누른 q 가 다음 입력으로 들어가 시험 도구가 일찍 끝났다 — 결함 아님)'),
 'NOTE-02': dict(note_add='9/22: 운영 화면이 main 에 들어왔다(PR #66) → 가짜 flow 대본으로 gif 를 찍으면 된다'),
 'INT-4':   dict(note_add='9/22 PR #66 뒤: 화면 PC(PC-B)에서 `cd src/f4_hmi/web && npm install && npm run build` 먼저 — 안 하면 / 가 시험 페이지'),
}
for _tid, _e in P0950.items():
    EDIT.setdefault(_tid, {}).update(_e)
_o = 'V-24·V-25·V-26(H · 30분 — 셋 다 9/21 실기 안 함 · F4 확인)'
assert _o in SLOT['9/22 화']['C']
SLOT['9/22 화']['C'] = SLOT['9/22 화']['C'].replace(_o, 'V-25 · V-24 ②③④(H · 25분 — V-26 은 오전에 5/5 통과 · V-24 ① 끝)')
HISTORY85 = ['v13.5', '완료·진척', 'F4-03, V-13, V-26, V-24, NOTE-02, INT-4, 9/22 오후 로봇 슬롯',
             'PR #66 merge(9/22 · 황인재 확인·승인): F4-03 운영 화면 완료 · V-13 완료(가짜 flow 대본 5개로 PAUSED·재개 반영). F4 보고: V-26 Ctrl+C 정지 실기 5/5 통과(0.47~0.50 s · 기록 PR 대기) · V-24 ① 관절 일시 정지→재개 OK(②③④ 남음). 오후 황인재 칸 = V-25 + V-24 ②③④',
             '황인재 9/22 09:50', 'H']


# ---------------------------------------------------------------- 9/22 10:10 박진용 · 한석형 아침 답 반영
P1010 = {
 'F3-03':   dict(note_add='📥 9/22 박진용: soap 실기는 **아직 안 했다**(구현만 · 실기 기록 없음) → 오늘 오후 F1-05 슬롯에 20분'),
 'F1-05':   dict(note_add='📥 9/22 박진용: 오후 가능 — 저녁 INT-13 전에'),
 'F3-02':   dict(note_add='📥 9/22 박진용: 120 s 상한 **PR 에서 삭제 뺐다(남김)** · 오전 재검증 3회에서 공중 기준 Fz 를 9/19(1.9~2.3 N)와 비교해 보고. wipe_bowl 은 9/20 확정본(rig_v03) 명령·순서 그대로(두산 호출은 force.py 안에서만) + 바꾼 것 3가지: 빠른 하강 135 → 140 mm · 바닥 판정 힘 2 → 3 N(그릇) · 올라오는 속도 = 빠른 하강 속도(200 mm/s · 스케일 미적용 — 컵 1.5 배와 다름). '
                          '실패 시 "곧게 올라와 HOME" 은 지금 main 과 같은 규칙(위치를 아는 실패만 · 강제정지·MoveIncomplete 는 안 움직임) — PR 에서 그 갈래가 남았는지 본다'),
 'F1-02':   dict(note_add='📥 9/22 한석형: ① 들여쓰기 오류 → 10:05 고침(`1644620` · 실행 가능 PM 확인) ② 잔반통 → HOME 은 관절 이동(J6 유지) — 오전 재검증에서 그 구간 충돌부터 본다 ③ 수세미 폭은 V-08 값 ④ pick() PR + 좌표 cell.yaml 은 오후'),
}
for _tid, _e in P1010.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY86 = ['v13.6', '답 반영', 'F3-03, F1-05, F3-02, F1-02',
             '9/22 아침 묶음 답: 박진용 — 안착 놓기(F1-05·V-04) 오후 가능 · soap 실기 안 했음 → 오후 20분 · 120 s 상한은 PR 에서 삭제 뺌(남김) · wipe_bowl 은 9/20 rig_v03 그대로 + 3가지 변경. 한석형 — 들여쓰기 오류 고침(10:05 · 실행 가능) · 잔반통 → HOME 구간을 오전 재검증에서 먼저 확인 · 수세미 폭은 V-08 값 · pick() PR 오후',
             '황인재 9/22 10:10', 'P,S']


# ---------------------------------------------------------------- 9/22 10:30 황인재 결정 — PR #66 후속 ①·② (F4 전달)
P1030 = {
 'F4-03': dict(note_add='🔒 9/22 황인재: 후속 ① "연결 끊기면 일시 정지 버튼 꺼짐" 은 **그대로 둔다**("크게 상관있는 기능은 아니다") — 제안 닫음'),
 'INT-4': dict(note_add='🖥 9/22 황인재: 시연 PC 2대 — **화면(hmi_bridge + web) = PC-B 황인재**(npm build 끝남 · 화면 고치면 PC-B 에서만 다시) · **flow_node = PC-A 한석형** → PC-A 는 `git pull` + `cbc` 만(npm 불필요). '
                        '두 PC 가 통신할 때만(INT-4 · L3 · 리허설 · 시연) 두 터미널에서 `team60`, 끝나면 `solo`(AGENTS 규칙 13) — 그동안 다른 PC 는 team60 을 켜지 않는다'),
}
for _tid, _e in P1030.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY87 = ['v13.7', '결정', 'F4-03, INT-4',
             '황인재 9/22(F4 전달): PR #66 후속 ① 연결 끊김 때 일시 정지 버튼이 꺼지는 것은 그대로 둔다 ② 시연 PC 2대 — 화면 = PC-B(황인재) · flow_node = PC-A(한석형, git pull + cbc 만 · npm 불필요) · 두 PC 통신 때만 team60 → 끝나면 solo',
             '황인재 9/22 10:30', 'H,S']


# ---------------------------------------------------------------- 9/22 10:45 PR #67 merge — V-26 기록
EDIT.setdefault('V-26', {}).update(dict(status='완료', prog='1.0', note_add='✅ 9/22 PR #67 merge — 기록 `docs/test_logs/20260922_V-26_CtrlC정지_실기_황인재.md`: 허리 180° 회전 도중 Ctrl+C **5/5 즉시 정지** · 정지 완료까지 0.47~0.50 s · 멈춘 뒤 스스로 안 움직임 · 브링업 유지. 한계: 정지까지 움직인 각도는 계산 상한(9°)만 · 용기 든 이동·직선 이동은 V-24 에서'))
HISTORY88 = ['v13.8', '완료', 'V-26', 'PR #67 merge(9/22): V-26 Ctrl+C 정지 실기 완료 — 5/5 즉시 정지 · 0.47~0.50 s · 브링업 유지(황인재 9/22 09:05~09:10)', '황인재 9/22 10:45', 'H,P']


# ---------------------------------------------------------------- 9/22 11:45 황인재 결정 — 무게 측정(R2 · V-02)은 황인재가 이어받는다
P1145 = {
 'V-02': dict(owner='H(M)', note_add='🔄 9/22 11:40 황인재 결정: **무게 측정(R2 두 자세 재측정 · V-02 빈 용기 기준값)은 황인재가 이어받는다** — 민범진은 flow_node 등 다른 작업에 집중(메시지 보냄). '
                                     '도구는 민범진이 만든 그대로(`rig_weigh_probe.py -n 10` · `rig_f2.py empty --kind BOWL/CUP` · 절차 `docs/test_logs/20260921_저녁_F2실기_결과_민범진.md` §3·§4). params.yaml `f2.empty_weight_g` 반영은 민범진 절이라 PR 에 멘션. '
                                     'V-07 · V-16 · INT-12a·12b 는 그대로 민범진'),
 'F2-01': dict(note_add='🔄 9/22: 무게 기준값(V-02)은 황인재가 잰다 — 값이 들어오면 판정(잔반 50 g · 하한) 확인은 INT-12a'),
}
for _tid, _e in P1145.items():
    EDIT.setdefault(_tid, {}).update(_e)
_o = '**② 민범진 R2 자세별 재측정 + V-02 빈 용기 기준값(35분 — 저녁 INT-12a 전제)**'
assert _o in SLOT['9/22 화']['B']
SLOT['9/22 화']['B'] = SLOT['9/22 화']['B'].replace(_o, '**② 황인재 R2 자세별 재측정 + V-02 빈 용기 기준값(35분 — 저녁 INT-12a 전제 · 🔄 11:40 민범진 → 황인재)**')
HISTORY89 = ['v13.9', '분담', 'V-02, F2-01, 9/22 오전 로봇 슬롯',
             '황인재 9/22 11:40: 무게 측정(R2 두 자세 재측정 · V-02 빈 용기 기준값)은 황인재가 민범진이 만든 도구로 이어받는다 — 민범진은 flow_node 등 다른 작업에 집중. V-07 · V-16 · INT-12a·12b 는 민범진 그대로',
             '황인재 9/22 11:45', 'H,M']


# ---------------------------------------------------------------- 9/22 12:00 결정 E24(잔반 버리기 ≠ 물기 털기) · 민범진 답(flow_node 진척 · 무게 인수인계)
NEW.append(
 ('FLOW-04', 'FLOW-03', 'FLOW-03', '통합', 'flow_node 첫 실기 — 진짜 기능 모듈(use_mock=f3)로 그릇 1개 PICK → RACK',
  'M(S,H)', '시작 전', S('9/22 저녁', '9/23 오전'), 'docs/test_logs/ 에 실행 기록(단계별 통과·멈춘 곳·코드) · records.csv 1줄',
  '`ros2 launch prewash_bringup prewash.launch.py use_mock:=f3` 로 그릇 1개가 PICK~RACK 끝까지 돈다(또는 멈춘 단계·코드·원인을 기록) · 🚨 전제: f1 pick·rack_place(한석형) · tool(황인재 F1-03) PR 이 main 에',
  '민범진 9/22 답: flow_node 는 지금까지 **가짜 기능 3개로만** 띄웠다(9/21 UT-FLOW) — main 의 f1 pick·tool·rack_place 가 빈 껍데기라 진짜 f1 을 넣으면 "안 움직이고 성공" 이 된다. '
  'INT-12a·12b 는 flow_node 가 아니라 같은 순서의 시험대(rig_int12)로 한다 → flow_node 실기를 따로 둔다. 세 PR 이 오늘 오후 오면 저녁 INT-12 슬롯 끝 15분, 안 오면 9/23 오전 L2 마무리 때. L3(INT-3a · 9/23 오후) 전에 한 번은 돌아야 한다'))
EASY['FLOW-04'] = 'flow_node(전체를 묶는 메인 프로그램)를 처음으로 진짜 기능 함수와 실제 로봇으로 돌려 본다. 그릇 1개가 집기부터 팔레트 적재까지 끝까지 가는지, 멈추면 어디서 왜 멈췄는지 기록한다'
M12 = '📥 9/22 민범진 답'
P1200 = {
 'INT-12a': dict(task='INT-12a F1+F2 — 집기→무게→잔반 버리기 5회 (주도) · 시험대 rig_int12 (flow.py 와 같은 순서 · flow_node 없이 — flow_node 실기는 FLOW-04)'),
 'INT-12b': dict(task='INT-12b F1+F2 — 재파지→헹굼→물털기→팔레트 적재 5회 (주도) · 시험대 rig_int12 (flow.py 와 같은 순서 · flow_node 없이 — flow_node 실기는 FLOW-04)'),
 'FLOW-02': dict(status='완료', prog='1.0', note_add=M12 + ': 코드 전부 main(#61) → 완료. 🟡 실제 값(무게·닦기 시간·힘 로그)은 INT-12a · FLOW-04 · L3 의 records.csv 로 확인'),
 'FLOW-03': dict(status='완료', prog='1.0', note_add=M12 + ': 코드 전부 main(#50 + 검토 후속 — 중단 깃발 정리) → 완료. 이동 도중 정지는 V-24·V-26 실기. 🟡 **abort 의 실기 정리 순서(HOME → 툴 반납 → 격리 → HOME)는 미확인** → INT-4b(실패 주입 + 정지·재개)에서'),
 'UT-FLOW': dict(status='완료', prog='1.0', note_add=M12 + ': 로봇 없는 범위 완료(9/21 · #62). 🟡 실기 항목은 V-24 · INT-4 · FLOW-04'),
 'F2-01':   dict(note_add='🔄 9/22 결정 E24: **잔반 버리기(shake WASTE)는 물기 털기와 다른 동작으로** — 지금은 같은 5번 관절 왕복·숫자만 다름. 서명 shake(mode, count, kind) 그대로 · 방식은 민범진 · V-07 로 확인(HMI 그림 = 기울여 쏟기) · 크게 기울일 때 손목 회전(케이블) 주의'),
 'F2-02':   dict(note_add='🔄 9/22 E24: 물기 털기(shake RINSE)는 잔반 버리기와 다른 동작 — RINSE 는 지금 왕복 동작 유지 가능'),
 'V-07':    dict(task='V-07 털기 실기 — 잔반 버리기(새 동작 · E24)와 물기 털기 각각에서 충돌 감지 오작동·놓침 여부',
                 note_add='🔄 9/22 E24: 잔반 버리기가 새 동작으로 바뀐다 → V-07 은 **바뀐 동작으로**(저속부터 · 컵은 HOLD 없이 놓치는지). 저녁 INT-12a 가 leftover_loop 를 쓴다'),
 'INF-02c': dict(note_add=M12 + ': `get_workpiece_weight` 는 **Fz 의 절댓값**이었다 — 무게가 늘면 Fz 가 음수로 가다 0 을 지나며 되튄다(어제 "0 에 잘림" 의 정체) → weigh.py 를 툴 힘센서 Fz 부호 그대로(−Fz × 101.97 g/N) 읽게 고침. 🚨 **민범진 로컬 커밋만**(beomjin/20260922-V-02-weigh-r2 · d4d44bc · push 전) → 무게 기능은 F4(황인재)가 이어받음(E24 와 같은 때 황인재 결정). 0.85 유지(실기 재확인 전)'),
 'V-02':    dict(note_add=M12 + '(오전 z 235 · 툴 등록 뒤 · 10회): 빈손 89 g · 그릇 10 g · 그릇+43 g 13 g · 그릇+107 g 80 g(하중 API — 절댓값이라 판정 불가) · 옛 경로 rig_f2 empty 폭 70 g → 기준값으로 못 씀. '
                          '🔴 **11:17 뒤 하중이 1.33 kg 에 고정**(10표본 전부 같은 값 · 원인 미확인 — 툴 무게 설정이 풀렸거나 센서 값이 멈춘 것으로 보임) → F4 가 Dart 툴 설정 · 브링업 재시작부터 확인. '
                          '11:22 WEIGH.BOWL z 235 로 옮겨 본 경로에서 그릇이 바닥에 닿아 46.6 mm 앞에서 섬(MoveIncomplete) — cell.yaml 되돌림(변경 없음). 제안(민범진 f2 절): weigh_settle_s 0.5 → 5.0 · 표본 5 → 10 · min_net_g −30 → −60'),
}
for _tid, _e in P1200.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY90 = ['v14.0', '결정 E24·신규·완료', 'F2-01, F2-02, V-07, FLOW-04(신규), INT-12a·12b, FLOW-02, FLOW-03, UT-FLOW, INF-02c, V-02',
             '결정 E24(황인재 9/22): 잔반 버리기와 물기 털기는 다른 동작으로 — shake 서명 그대로 · mode 마다 동작 · 방식은 민범진 · V-07 로 확인. '
             '민범진 답: flow_node 는 가짜 기능으로만 띄웠다(main 의 f1 세 함수가 빈 껍데기) → 🆕 FLOW-04 flow_node 첫 실기(use_mock=f3 · 그릇 1개 · 오늘 저녁 또는 9/23 오전) · INT-12a·12b 는 시험대 rig_int12 로 명시 · FLOW-02·FLOW-03·UT-FLOW 완료(🟡 실기 항목은 INT-4b·FLOW-04·L3). '
             '무게: 하중 API 는 Fz 절댓값 → Fz 부호 방식으로 고침(민범진 로컬 · push 전) · 11:17 뒤 1.33 kg 고정(원인 미확인) → F4 확인',
             '황인재 9/22 12:00', 'M,S,H']


# ---------------------------------------------------------------- 9/22 12:00 GitHub 기준 최신화 — F4 브랜치 3개 · 1.33 kg 가설
G12 = '📈 9/22 12:00 GitHub(브랜치 · PR 전)'
P1205 = {
 'NOTE-01': dict(prog='0.6', status='진행', note_add=G12 + ': `injae/20260922-NOTE-01-ros2-docs`(3b2a700) — 노션 제출용 ROS 2 노드 구조 · 인터페이스 정의서 · 발표 설명 메모 + 노드 구조도 SVG(`tools/gen/draw_ros2_nodes.py` 로 생성). 남은 것: 황인재 확인 → PR → 노션 업로드(1차 산출물 9/22~23)'),
 'V-08':    dict(note_add=G12 + ': `injae/20260920-F1-03-tool` 에 V-08 도구 `rig_f1 tool --action CYCLE`(집기 → 반납 한 쌍 × n · 1회차만 Enter · 성공 횟수·폭 요약) 추가 · 🟡 실기 전(오후 · 툴 프리셋 측정부터 — E23)'),
 'V-02':    dict(note_add=G12 + ': F4 도구 `rig_weigh_poses.py`(`injae/20260922-V-02-weigh-baseline` · 두 높이 비교 · −Fz 부호 그대로 + 하중 API 나란히 · 도착 뒤 5 s) 준비 · 🟡 실기 미실행. '
                          '한석형 동선은 반납 구역 바로 위 WEIGH z 158 에서 잰다 → 좌표는 그대로 두고 R2 결과를 본다. '
                          '🔴 1.33 kg 고정 — F4 가설: 툴 무게 보정이 통째로 빠지면 약 1.33~1.35 kg 로 읽힌다(값이 맞음) → **로봇 안 움직이는 확인부터**(현재 툴 이름 · probe · 펜던트 값) · 원인 질문은 13시 묶음(민범진 · 박진용)'),
}
for _tid, _e in P1205.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY91 = ['v14.1', '최신화', 'NOTE-01, V-08, V-02',
             'GitHub 기준(9/22 12:00): F4 브랜치 3개 — NOTE-01 노션 제출 문서(0.6) · V-08 도구(rig_f1 tool CYCLE) · V-02 두 높이 비교 도구(Fz 부호). 1.33 kg 고정은 "툴 보정이 빠진 값" 가설 → 로봇 안 움직이는 확인부터. 팀원 push 는 오늘 한석형 10:05 뒤 없음(민범진 무게 수정 d4d44bc 는 로컬)',
             '황인재 9/22 12:05', 'H,M']


# ---------------------------------------------------------------- 9/22 12:15 F4 보고 — 컨트롤러 툴·TCP 선택이 풀려 있었다(복구 끝)
TCPX = ('🚨 9/22 F4 보고: 컨트롤러의 **현재 툴·TCP 선택이 풀려 있었다**(get_current_tool · tcp = 빈 값 · 등록 값은 그대로) — 10:54 정상(민범진 무게) · 11:17 풀림 → 12시 무렵 황인재가 펜던트에서 다시 골라 복구'
        '(빈손 1.316 → 0.123 kg · HOME z 214.73 · ROS set 서비스는 거절). 풀린 동안 posx 이동은 손끝 208 mm 아래로 · 무게 1.3 kg 고정 · 힘 값도 달랐다 → 그 시간(10:54~12:00) 실기 결과는 다시 확인. 원인 미확인')
P1215 = {
 'ENV-05': dict(note_add=TCPX + '. 🔜 F4: cobot_common.init 이 시작할 때 두 이름을 확인하고 다르면 움직이지 않게(V-02 뒤 PR)'),
 'V-02':   dict(note_add='✅ 9/22 12:15: 1.33 kg 고정 원인 = 툴·TCP 선택 풀림(복구 끝 · ENV-05 비고). 10:48~10:54 민범진 값은 정상 때 · 11:17 뒤 값은 버린다 → R2 · V-02 진행 가능'),
 'F1-02':  dict(note_add='🔴 9/22 12:15: 10:54~12:00 사이 툴·TCP 선택이 풀려 있었다 → 그 사이 찍은 컵 C1·C2 등 posx 는 플랜지 값일 수 있다(z +208) — pick() PR 전에 다시 확인(묶음 ①)'),
 'F3-02':  dict(note_add='🔴 9/22 12:15: 10:54~12:00 사이 툴 선택이 풀려 힘 값이 그리퍼 무게만큼 달랐다 → 그 시간에 한 재검증은 다시(묶음 ③)'),
}
for _tid, _e in P1215.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY92 = ['v14.2', '사고·복구', 'ENV-05, V-02, F1-02, F3-02',
             'F4 보고(9/22 12:15): 컨트롤러 툴·TCP 선택이 10:54~11:17 사이부터 12시 무렵까지 풀려 있었다(등록 값은 그대로) → posx 이동 손끝 208 mm 아래 · 무게 1.3 kg 고정 · 힘 값 다름. 펜던트에서 다시 골라 복구. 그 시간 실기 결과는 다시 확인 · 앞으로 로봇 움직이기 전 두 이름 확인(리마인드 §6) · 전원 공지는 13시 묶음',
             '황인재 9/22 12:15', '전원']


# ---------------------------------------------------------------- 9/22 12:25 황인재 — 실기 시작·끝 규칙 2개(툴·TCP 선택 풀림 방지)
NEW_RULES.append(('🚨 실기 시작', '툴·TCP 이름 확인', '로봇을 움직이기 전에 get_current_tcp → GripperDA_v1 · get_current_tool → Tool Weight 를 확인한다. 비어 있거나 다르면 움직이지 말고 브링업을 끈 뒤 펜던트에서 다시 고른다(ROS 명령으로는 안 된다) — 9/22 오전 선택이 풀려 posx 이동이 손끝 208 mm 아래로 갔다'))
NEW_RULES.append(('🔌 실기 끝', '연결부터 끊고 랜선', '실기가 끝나면 ① 프로그램 터미널 Ctrl+C → 브링업 터미널 Ctrl+C 로 로봇 연결부터 끊고 ② 다 꺼진 것을 확인한 뒤 랜선을 뽑는다(다음 사람에게 넘길 때도). 연결된 채로 랜선부터 뽑지 않는다 — 9/22 툴·TCP 풀림 원인은 못 찾았지만 방지(황인재 9/22)'))
HISTORY93 = ['v14.3', '규칙', '규칙 시트',
             '황인재 9/22 12:25: 실기 규칙 2개 — 🚨 실기 시작 전 툴·TCP 이름 확인 · 🔌 실기 끝나면 터미널 Ctrl+C 로 연결부터 끊고 그다음 랜선. 툴·TCP 선택 풀림 원인은 못 찾았지만 방지. 리마인드 §6 · 13시 전원 공지',
             '황인재 9/22 12:25', '전원']


# ---------------------------------------------------------------- 9/22 12:40 F4 R2 그릇 결과
R2B = ('📈 9/22 F4 R2 그릇(실기 · 툴·TCP 복구 뒤 · vel 0.3 · 도착 뒤 5 s · 10회 · −Fz 중앙값): z 158 빈손 −34.0 · 그릇 쥠 +8.3 → **그릇 42.3 g · 흔들림 9.5 g** / z 235 빈손 +1.3 · 그릇 쥠 +50.1 → 48.8 g · 🔴 흔들림 60 g(77 → 17 로 떨어지는 추세). '
       '9/21 민범진 값(≈ 44.5 g)과 맞다. 높이마다 오차는 더해지는 옵셋 → 같은 자세 빈 값을 빼면 지워진다 → **WEIGH 좌표는 z 158 그대로**(z 235 는 그릇을 쥐면 불안정). '
       '9/21 "0 에 잘림" = 하중 API 절댓값 탓(옵셋 −34 + 그릇 42 ≈ +8 g). 🔴 V-02 전제: 민범진 Fz 부호 방식(d4d44bc) push — main weigh.py 는 아직 절댓값. 컵 R2 진행 중')
P1240 = {
 'V-02':    dict(prog='0.3', status='진행 중', note_add=R2B),
 'INF-02c': dict(note_add='🔎 9/22 F4 R2: 무게는 **Fz 부호 방식이어야** 판정이 된다(절댓값이면 옵셋 −34 g 자리에서 부호가 떨어진다) → d4d44bc merge 가 V-02 전제'),
 'F2-01':   dict(note_add='🔔 9/22 F4 참고: 그릇 놓침 판정 min_net_g −30 g 의 여유가 얇다 — 그릇 ≈ 42 g 라 놓치면 −42 g · 문턱까지 12 g 인데 흔들림 10~15 g → V-02 반복 값을 보고 민범진 절에 제안(지금은 안 바꿈 · 민범진 브랜치는 −60 제안)'),
}
for _tid, _e in P1240.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY94 = ['v14.4', '실기 결과', 'V-02, INF-02c, F2-01',
             'F4 R2 그릇(9/22 · 툴 복구 뒤): WEIGH z 158 그대로 — 그릇 42.3 g · 흔들림 9.5 g(9/21 값과 맞음) · z 235 는 쥐면 불안정. 9/21 "0 에 잘림" 은 하중 API 절댓값 탓 → Fz 부호 방식(민범진 d4d44bc · push 전)이 V-02 전제. 놓침 문턱 −30 g 여유가 얇다(참고). 컵 R2 진행 중',
             '황인재 9/22 12:40', 'H,M']


# ---------------------------------------------------------------- 9/22 12:45 황인재 — 단위 기능 테스트 먼저, 통합은 통합 슬롯에서
NEW_RULES.append(('🧪 테스트 순서', '단위 먼저 · 통합은 슬롯에서', '기능 코드를 다 짰으면 단위 기능 테스트(내 함수만 · rig · UT-F1/F2/F3)부터 한다. 한 바퀴 전체 통합 테스트는 일정표의 통합 슬롯(L2 · L3)에서 같이 한다 — 혼자 통합 테스트로 로봇을 오래 잡지 않는다(로봇 1대 · 남의 단위 테스트가 밀린다 · 황인재 9/22)'))
HISTORY95 = ['v14.5', '규칙', '규칙 시트', '황인재 9/22 12:45: 테스트는 단위 기능 먼저, 통합은 통합 슬롯(L2 · L3)에서 — 혼자 통합 테스트로 로봇을 오래 쓰지 않는다. 리마인드 §8 · 13시 전원 공지', '황인재 9/22 12:45', '전원']


# ---------------------------------------------------------------- 9/22 12:50 F4 R2 컵 결과
R2C = ('📈 9/22 F4 R2 컵(실기 · 5 N · 78 mm · 도착 뒤 5 s · 10회 · −Fz 중앙값): WEIGH.CUP z 147.4 빈손 −36.9 · 컵 쥠 −16.2 → **컵 20.7 g** · 흔들림 20.8/17.8 g(시간 따라 오르는 추세) / z 235 빈손 −180.9 · 컵 쥠 −164.7 → 컵 16.2 g · 흔들림 8.8/5.7 g ✅. '
       '🔴 main 방식(하중 API 절댓값)으로 빼면 컵이 −18 g 로 부호가 뒤집히고 잔반이 늘면 값이 줄어든다 → 컵 잔반 판정이 틀린다 → d4d44bc 가 V-07 · INT-12a 전제. '
       '🟡 컵 자체가 16~21 g < 30 g → 놓쳐도 순무게 ≈ −20 g 라 min_net_g −30 에 안 걸린다(GRIP_FAIL 이 아니라 "잔반 없음" 으로 흐른다) — E19 ③ 한계가 실제로 걸린다 → 황인재·민범진 결정 대기. '
       '컵 WEIGH 높이(z 147 유지 / z 235)는 F4 가 도착 뒤 10 s 재측정으로 정한다(E14 · 옮기면 cell.yaml PR). 5 N · 78 mm 로 HOME → WEIGH → z 235 → HOME 떨어뜨리지 않음(털기 전 확인 · V-07 아님)')
P1250 = {
 'V-02':  dict(prog='0.5', note_add=R2C),
 'V-07':  dict(note_add='🔴 9/22 F4 컵 R2: main weigh.py(절댓값)로는 컵 잔반 판정이 틀린다 → 민범진 d4d44bc(Fz 부호) merge 뒤에 V-07'),
}
for _tid, _e in P1250.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY96 = ['v14.6', '실기 결과', 'V-02, V-07', 'F4 R2 컵(9/22): 컵 16~21 g · 절댓값 방식이면 부호가 뒤집혀 컵 잔반 판정이 틀림 → d4d44bc 가 V-07 · INT-12a 전제. 컵이 30 g 보다 가벼워 놓침을 무게로 못 잡는다(E19 ③ 한계가 실제로 걸림 — 결정 대기). 컵 WEIGH 높이는 F4 가 재측정으로 정한다', '황인재 9/22 12:50', 'H,M']


# ---------------------------------------------------------------- 9/22 12:55 황인재 — 컵 놓침 판정은 F4 가 다시 본다 · 13시 묶음 전파
EDIT.setdefault('V-02', {}).update(dict(note_add='🔄 9/22 12:55 황인재: **컵 놓침 판정(컵 16~21 g < 30 g · min_net_g)은 F4 가 다시 본다** — 민범진은 f2 절 문턱을 지금 바꾸지 않는다'))
HISTORY97 = ['v14.7', '분담', 'V-02', '황인재 9/22 12:55: 컵 놓침 판정(컵이 30 g 보다 가벼워 무게로 못 잡는 문제)은 F4 가 다시 본다. 13시 전원 공지(툴·TCP 풀림 · 실기 끝낼 때 순서 · 단위 먼저) 전파', '황인재 9/22 12:55', 'H,M']


# ---------------------------------------------------------------- 9/22 13:20 PR #68 merge(민범진) — 무게 Fz 부호 · 문지기 · 잔반 버리기 기울이기
M68 = '✅ 9/22 PR #68 merge(민범진)'
P1320 = {
 'INF-02c': dict(prog='0.9', note_add=M68 + ': weigh() = −Fz(get_tool_force · BASE) × 101.97 g · 표본 10 × 간격 0.7 s · 도착 뒤 5 s. 🟡 기준값·판정은 V-02(F4)'),
 'V-02':    dict(note_add=M68 + ': main 이 이제 Fz 부호 방식 → V-02 기준값을 main 으로 잴 수 있다(F4)'),
 'F2-01':   dict(prog='0.9', note_add=M68 + ': 잔반 버리기 = J5 −90° 기울여 흔들고 되돌림(E24 · tilt_deg · 상한 max_tilt_deg 100) · 잔반통 자세 WASTE.BOWL J6 0 → 180(그릇이 잔반통 위로 · 🟡 케이블 감김은 계속 눈으로) · 문지기(TS-07 — 툴·TCP 이름이 다르면 시작 거부)'),
 'F2-02':   dict(note_add=M68 + ': 헹굼 담금 1 → 2회(flow.counts.rinse_dips · 회당 약 6 s) · 물 털기는 기울이지 않음 · 🟡 물 털기 실기는 아직'),
 'V-07':    dict(prog='0.5', status='진행', note_add=M68 + ': 그릇 잔반 버리기(기울이기) 🟢 실기 — 저속 1회 + 원속 눈 확인 · 알람 0 · 미끄러짐 0.3 mm · 잔반 털림. 🟡 남은 것: 컵(HOLD 없음 · E19) · 물 털기 RINSE'),
 'UT-F2':   dict(note_add=M68 + ': rig_f2 · rig_int12 에 문지기 연결. 🟡 TC-03·04·08 연속 3회 기록은 아직'),
 'FLOW-04': dict(note_add='9/22 PR #68: flow_node 가 로봇을 쓸 때(use_mock 에 f1·f2·f3 가 다 있지 않으면) 시작 전 툴·TCP 문지기를 통과해야 한다 — 다르면 종료 코드 2'),
}
for _tid, _e in P1320.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY98 = ['v14.8', '진척', 'INF-02c, V-02, F2-01, F2-02, V-07, UT-F2, FLOW-04',
             'PR #68 merge(민범진 9/22): 무게는 부호 있는 Fz 로(V-02 전제 해소) · 움직이기 전 툴·TCP 문지기(TS-07) · 잔반 버리기 = J5 −90° 기울여 흔들기(E24 · V-07 그릇 🟢 실기) · 잔반통 J6 180 · 헹굼 담금 2회. 🟡 컵 V-07 · 물 털기 · UT-F2 연속 기록 남음',
             '황인재 9/22 13:20', 'M,H']


# ---------------------------------------------------------------- 9/22 13:55 결정 E25 — 컵은 무게·잔반 버리기 없음(헹굼·물 털기는 함) · PR #69 수정 요청
NEW.append(
 ('FLOW-05', 'FLOW-04', 'FLOW-04', '개발', 'flow 에서 컵은 WEIGH 단계(move_to WEIGH · leftover_loop)를 건너뛴다 — 결정 E25(컵은 액체만 · 잔반 없음) · 헹굼 담금·물 털기는 그대로',
  'M', '시작 전', S('9/22 오후'), '`flow.py process_one` 수정 + 자동 시험(컵 계획에서 WEIGH 호출 0회 · 그릇은 그대로) · PR',
  '가짜 기능(use_mock=f1,f2,f3)으로 컵 1개 돌릴 때 f1.move_to("WEIGH") · f2.leftover_loop 가 **한 번도 불리지 않고** SEAT 로 간다 · 그릇은 예전 그대로 · /flow/state 의 step 이 컵에서 WEIGH 를 안 거친다 · 자동 시험 통과(두 환경)',
  '황인재 9/22 13:55 결정 E25: 컵에는 액체만 있고 음식물이 없다고 가정 → 무게 재기·잔반 버리기를 하지 않는다. 헹굼 담금·물 털기는 한다. 계기: 한석형 PR #69 주석. 로봇 불필요(가짜 기능으로 확인) · **9/23 동결 전** · 컵 기준값·컵 WEIGH 자세·컵 놓침 무게 판정은 필요 없어진다'))
EASY['FLOW-05'] = '메인 프로그램이 컵을 처리할 때 "무게 재기 → 잔반 버리기" 단계를 건너뛰게 고친다. 컵에는 국물 같은 액체만 있고 음식물은 없다고 보기로 했기 때문이다. 헹굼과 물 털기는 그대로 한다'
E25N = '🔄 9/22 E25(황인재): 컵은 무게·잔반 버리기 없음(헹굼·물 털기는 함)'
P1355 = {
 'INT-12a': dict(task='INT-12a F1+F2 — 집기→무게→잔반 버리기 5회 · **그릇만**(E25 컵은 무게 단계 없음) · 시험대 rig_int12(flow_node 없이 — flow_node 실기는 FLOW-04)', owner='M(S)',
                 note_add=E25N + ' → INT-12a 는 그릇만. rig_int12 의 CUP a 는 쓰지 않는다'),
 'INT-12b': dict(note_add=E25N + ' → INT-12b(재파지 → 헹굼 → 물 털기 → 적재)는 **컵도 한다**'),
 'V-02':    dict(note_add=E25N + ' → **컵 빈 용기 기준값 · 컵 WEIGH 자세 · 컵 놓침 무게 판정은 필요 없다** — F4 컵 R2 중단 · 그릇만 마무리'),
 'V-07':    dict(task='V-07 털기 실기 — 잔반 버리기(그릇 · E24 새 동작)와 물기 털기(그릇·컵)에서 충돌 감지 오작동·놓침 여부', note_add=E25N + ' → 컵은 **물 털기만**(잔반 버리기 없음). 남은 것: 물 털기 RINSE 그릇·컵'),
 'V-16':    dict(note_add=E25N + ' → 컵은 물 털기에서만 본다'),
 'F2-01':   dict(note_add=E25N + ' — weigh · leftover_loop 는 그릇 전용이 된다. flow 수정은 FLOW-05'),
 'INT-3b':  dict(note_add=E25N + ' → 컵 끝까지 = PICK → SEAT → SOAP → WIPE → RINSE → RACK(WEIGH 없음) — FLOW-05 merge 뒤'),
 'F1-02':   dict(note_add='🔴 9/22 13:45 PR #69 **수정 요청**(merge 보류): ① 컵 잡는 힘 5 → 40 N — E19 근거(15 N 변형 · 20 N 안전 스위치)와 반대 · 설명 필요(황인재) ② 주석 "RINSE SHAKE 생략" 은 틀림(E25: 물 털기는 한다) · E19 한계 설명 복원 ③ 자동 시험 1건(KNOWN_TILTED 에서 RACK_C2 제거). 🚨 pick()·rack_place 코드는 이 PR 에 없음 — 저녁 INT-12·FLOW-04 전제'),
 'F1-04':   dict(note_add='9/22 PR #69: 컵 칸 C1·C2 접근점이 끝점 바로 위로 고쳐짐(👍) · 새 키 rack.cup_via · cup_entry_z_mm(제품 코드 미사용). rack_place 코드는 아직'),
}
for _tid, _e in P1355.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY99 = ['v14.9', '결정 E25·신규·PR', 'FLOW-05(신규), INT-12a·12b, V-02, V-07, V-16, F2-01, INT-3b, F1-02, F1-04',
             '황인재 9/22 13:55 결정 E25: 컵은 무게·잔반 버리기를 하지 않는다(액체만 · 잔반 없음) — 헹굼 담금·물 털기는 한다 → 🆕 FLOW-05(민범진 · flow 에서 컵 WEIGH 건너뛰기 · 동결 전) · INT-12a 그릇만 · 컵 기준값·컵 WEIGH 자세·컵 놓침 판정 불필요(F4 컵 R2 중단). '
             'PR #69(한석형 컵 좌표) 수정 요청: 컵 힘 40 N 설명 필요 · 주석 정정 · 시험 목록 갱신 · pick()/rack_place 코드는 아직',
             '황인재 9/22 13:55', 'M,S,H']


# ---------------------------------------------------------------- 9/22 14:15 F4 V-02 그릇 1차 — 흔들림 45 g(기준 20 초과) · 제안 4개
V02B = ('📈 9/22 F4 V-02 그릇 1차(실기 13:54~14:01 · main #68 weigh · 도착 뒤 5 s · 10 표본 × 0.7 s · WEIGH.BOWL z 158): `rig_f2 empty -n 10` 회차 중앙값 −12.9 ~ −46.5 → **중앙값 −20.4 g · 폭 44.8 g(기준 20 g 초과)**. '
        '원값은 −1 ~ −52 를 10~20 s 주기로 오르내린다(툴·TCP 복구 뒤에도 그대로). 이어서 weigh 2회는 같은 자세인데 −65/−62 로 45 g 낮음(그릇 안 내용물 황인재 확인 중). '
        '→ 판정식 "읽음 − 기준값" 의 전제(옵셋이 시간·방문에 걸쳐 같다)가 지금 정밀도에서는 안 선다. F4 제안(결정 = 민범진 f2 절 · PM): ① leftover_threshold_g 50 → 100(SDD §9.9 대안) ② min_net_g −30 → −60 이하(놓침은 폭 slip_tol 로) ③ 표본 창을 주기보다 길게(30 × 0.7 = 21 s) ④ 기준값은 flow 와 같은 경로(pick → WEIGH → 5 s → 1회)로 INT-12a 에서 다시. '
        '우선 기준값 −20(🟡 폭 45)을 F4 브랜치 params 에 넣어 PR(민범진 멘션). ⚠ 정정: min_net_g −30 되돌림의 근거였던 "복구 뒤 PM 실측 9.5 g" 은 12 s 창 값 — 65 s 로 재면 폭 45 g → 근거 약함')
P1415 = {
 'V-02':    dict(prog='0.6', note_add=V02B),
 'F2-01':   dict(note_add='🔔 9/22 14:15 F4: 정지 중 흔들림이 복구 뒤에도 폭 45 g(10~20 s 주기) → 임계 50 g · min_net_g −30 · 기준값 뺄셈 모두 여유가 없다 — F4 제안 ①~④(V-02 비고)를 민범진이 판단(f2 절)'),
 'INT-12a': dict(note_add='🔔 9/22 F4 제안 ④: 그릇 빈 용기 기준값을 flow 와 같은 경로(pick → WEIGH → 5 s → 1회)로 여기서 다시 잰다'),
}
for _tid, _e in P1415.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY100 = ['v15.0', '실기 결과', 'V-02, F2-01, INT-12a',
              'F4 V-02 그릇 1차(9/22 14:00): 기준값 −20.4 g · 폭 44.8 g(기준 20 초과) · 10~20 s 주기 흔들림이 복구 뒤에도 그대로 → 판정식 전제가 약함. F4 제안: 임계 50 → 100 · min_net_g −60 · 표본 창 21 s · 기준값은 INT-12a 에서 같은 경로로. 결정 = 민범진(f2 절)·PM. min_net_g −30 주석의 "9.5 g" 근거 정정',
              '황인재 9/22 14:15', 'H,M']


# ---------------------------------------------------------------- 9/22 14:25 PR #69 merge(한석형) — 컵 동선 좌표 확정
M69 = '✅ 9/22 PR #69 merge(한석형 · 수정 요청 반영 뒤)'
P1425 = {
 'CELL-04': dict(note_add=M69 + ': 컵 집기 RET_C(접근점 z 215 → 끝점 z 47) · 스펀지 홈 C(→ z 110 · exit +140) · 팔레트 C1·C2(끝점 바로 위 350 → 258 · exit z +92 → y) 실기값이 cell.yaml 에 · 컵 76 mm · 힘 5 N(E19 유지 — 40 N 은 근거 없어 되돌림) · RACK_C2 가 수직 접근이 됨(시험 예외에서 제거). 🟡 제품 코드(pick·rack_place)로는 미확인'),
 'F1-02':   dict(prog='0.6', note_add=M69 + ': 컵 집기 좌표·프리셋 main 에. 🔴 **pick() 본 구현은 아직**(저녁 INT-12a · FLOW-04 전제 — 시점 확인 중)'),
 'F1-04':   dict(prog='0.4', note_add=M69 + ': 컵 칸 C1·C2 좌표 확정 · 새 키 rack.cup_via · cup_entry_z_mm(제품 코드 미사용). 🔴 rack_place 코드는 아직'),
 'V-06':    dict(note_add='9/22 PR #69: 컵 칸 좌표는 실기 동선으로 확정 — rack_place 구현 뒤 여기서 제품 코드로 확인'),
}
for _tid, _e in P1425.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY101 = ['v15.1', '진척', 'CELL-04, F1-02, F1-04, V-06', 'PR #69 merge(한석형 9/22 14:25): 컵 집기·스펀지 홈·팔레트 C1/C2 실기 좌표 cell.yaml 반영 · 컵 76 mm · 힘 5 N 유지 · RACK_C2 수직 정렬. 🔴 pick()·rack_place 코드는 아직 — 저녁 INT-12 · FLOW-04 전제', '황인재 9/22 14:25', 'S']


# ---------------------------------------------------------------- 9/22 14:50 한석형 보고 — CELL-04 완료 확인 · 남은 것 · 다음 작업
S1450 = '📥 9/22 14:50 한석형 보고'
P1450 = {
 'CELL-04': dict(status='완료', prog='1.0', note_add=S1450 + ': 컵 동선 좌표 확정 — 반납 구역 집기(접근 z 215.11 → 파지 z 46.95) · 스펀지 홈(접근 z 300 → 삽입 z 110 → 놓은 뒤 z +140) · 팔레트 C1·C2(cup_entry_z 250 → cup_via → 칸 위 z 350 → 놓기 z 258 → z 350 → y 350 퇴피) · RACK_C2 수직 정렬 · 컵 76 mm / 5 N. PR #69(02164ac · 자동 시험 382 통과) · 9/22 실기 동선(집기 → 홈 → 재파지 → 헹굼 → 팔레트) 확인. 완료 유지'),
 'F1-02':   dict(note_add=S1450 + ': 경로만 검증 — **pick() 제품 코드는 남음**. 다음 작업 = 확정한 컵 경로를 handling.py pick()·rack_place() 에 반영 → 단위시험(UT-F1)'),
 'F1-04':   dict(note_add=S1450 + ': 경로만 검증 — **rack_place() 제품 코드는 남음**(pick() 과 같이)'),
 'V-14':    dict(note_add=S1450 + ': 정식 반복·빈 구역 시험은 pick() 코드 뒤'),
 'V-06':    dict(note_add=S1450 + ': 팔레트 반복·걸림 시험은 rack_place() 코드 뒤'),
 'UT-F1':   dict(note_add=S1450 + ': pick()·rack_place() 구현 뒤 진행'),
 'V-19':    dict(note_add=S1450 + '(한석형이 "V-19·V-22 정식 결과 기록 남음" 이라 적음): V-22 는 황인재 PR #52 로 완료 · V-19 는 황인재 0.8(팔레트 컵 칸 2곳 — 이번 PR #69 로 컵 칸 좌표가 확정됐으니 rack_place 실기 때 같이 닫는다)'),
}
for _tid, _e in P1450.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY102 = ['v15.2', '보고 반영', 'CELL-04, F1-02, F1-04, V-14, V-06, UT-F1, V-19', '한석형 9/22 14:50: CELL-04 완료 확인(컵 동선 좌표 · PR #69) · 경로만 검증했고 pick()·rack_place() 제품 코드 · V-14 · V-06 · UT-F1 은 남음 → 다음 작업 = handling.py 반영 + 단위시험', '황인재 9/22 14:50', 'S']


# ---------------------------------------------------------------- 9/22 15:00 PR #70 merge(민범진) — FLOW-05 · 물 털기 직선 왕복 · V-02 값
M70 = '✅ 9/22 PR #70 merge(민범진)'
P1500 = {
 'FLOW-05': dict(status='완료', prog='1.0', note_add=M70 + ': `flow.weigh_kinds: [BOWL]` — 목록에 없는 종류는 WEIGH 두 단계를 뺀다(컵 = PICK → SEAT). 자동 시험 3건(컵 plan 에서 두 함수 0회 · step 에 WEIGH 없음 · 그릇 그대로) · 병합본 388 통과. 🟡 실기 확인은 FLOW-04 · INT-3b. 🔔 주석에 "임시 건너뛰기" 라 적혀 있으나 E25 는 시나리오 결정 — 문구 수정은 다음 PR'),
 'F2-02':   dict(prog='0.85', note_add=M70 + ': **물 털기 = BASE X 축 직선 왕복 ±20 mm · 주기 0.5 s**(관절 회전 → 직선 · 상한 max_amp_mm 60 · tilt 불가). 🟡 실기 전 — amp 20 은 시작값, rig_jog 로 수조 벽 폭 재고 저속부터(V-07 물 털기 그릇·컵)'),
 'V-07':    dict(note_add=M70 + ': 물 털기가 새 동작(BASE X 직선)이 됨 → V-07 물 털기(그릇·컵)는 이 동작으로 · 저속부터'),
 'V-02':    dict(note_add=M70 + '(F4 1차 반영 · 민범진 결정): weigh_samples 10 → 30(창 21 s — 흔들림 주기 ≤ 20 s 보다 길게) · min_net_g −30 → −60 · 임계 50 은 **보류**(INT-12a 에서 같은 경로로 빈 그릇·대용품 재서 결정 · 후보 70). 기준값 BOWL 은 아직 임시 180 → F4 PR 로'),
 'F2-01':   dict(note_add=M70 + ': 무게 1회 ≈ 5 + 21 s · 잔반이면 최대 3회 ≈ 80 s(정확도 우선 · 시연 그릇 2개 감수)'),
 'INT-4c':  dict(note_add='🔔 9/22 PR #70: 무게 표본 창 21 s 로 그릇 1개 사이클이 +25~75 s 늘어난다(무게 1~3회) — 사이클 타임 측정 때 감안'),
 'INT-3b':  dict(note_add=M70 + ': 컵은 flow 에서 WEIGH 를 건너뛴다(weigh_kinds) — 여기서 실기 확인'),
}
for _tid, _e in P1500.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY103 = ['v15.3', '진척', 'FLOW-05, F2-02, V-07, V-02, F2-01, INT-4c, INT-3b', 'PR #70 merge(민범진 9/22 15:00): FLOW-05 완료(flow.weigh_kinds · 컵은 무게 단계 건너뜀 · 🟡 FLOW-04/INT-3b 실기) · 물 털기 = BASE X 직선 왕복(🟡 V-07) · 무게 표본 창 21 s · min_net_g −60 · 임계 50 보류(INT-12a 에서 결정). 사이클 +25~75 s', '황인재 9/22 15:00', 'M,H']


# ---------------------------------------------------------------- 9/22 15:15 F4 자세별 하중 흔들림(참고)
EDIT.setdefault('V-02', {}).update(dict(note_add='📈 9/22 F4 자세별 흔들림(빈손 · 14:19~14:25 · 자세마다 63 s · −Fz): HOME −153.5(폭 39) · WEIGH.BOWL z158 −65.5(**폭 25 · 가장 안정**) · z235 +14(폭 68 · +230 튐 1회) · HOME 끝 −154.7. 어느 자세도 ±10 g 는 안 됨 · 2 h 사이 z158 빈손 −34 → −65.5(센서의 느린 흐름) → **WEIGH.BOWL z158 유지 권고**(황인재 확인 대기) · 표본 30 이면 주기 흔들림은 덮이고 남는 것은 방문 사이·시간 흐름 → INT-12a 에서 같은 경로로 기준값(④)이 핵심. 다음: 그릇 쥔 채 결정 시험(황인재 동의 뒤) → V-02 기록·PR(BOWL 기준값 한 줄) · F4 브랜치에 main #70 병합 완료(0b216ab)'))
HISTORY104 = ['v15.4', '실기 결과', 'V-02', 'F4 자세별 하중 흔들림(9/22 14:20 · 참고): z158 이 가장 안정(폭 25 g) · HOME 은 ±20 g 출렁 · 2 h 사이 −31 g 흐름 → WEIGH.BOWL z158 유지 권고 · 기준값은 INT-12a 에서 같은 경로로. F4 브랜치 main #70 병합 완료', '황인재 9/22 15:15', 'H']


# ---------------------------------------------------------------- 9/22 15:25 박진용 답 — 11:10 rig_v03 실행(툴·TCP 풀림 구간 안) · 재검증 다시 · moved=False 갈래 확인
P1525 = {
 'F3-02':  dict(note_add='📥 9/22 15:25 박진용: 그릇 닦기 재검증은 **11:10 실행**(툴·TCP 풀림 구간 10:54~11:17 안) — 공중 Fz 1.77 N · 접촉 5.6 N · 평균 1.4 N 전부 그리퍼 무게 미반영이라 **다시 잰다**. 복구 뒤 12:18 · 12:54 두 번 돌림(결과 미보고). "실패해도 곧게 올라와 HOME" 그대로 · **moved=False(MotionHalted·MoveIncomplete) 갈래는 wipe_bowl·wipe_cup·soap 전부 남아 있음**(finally 가 moved 확인 뒤 안 움직임) — PR 검토 때 대조'),
 'ENV-05': dict(note_add='🔎 9/22 15:25 원인 단서(박진용): 10:54~11:17 사이 펜던트는 안 만짐 · **11:10 에 rig_v03 계열(닦기 시나리오)을 돌림** — 그때 찍힌 툴·TCP 이름은 로그에 없음(다음부터 확인). rig_v03 은 툴 이름을 확인·되돌리는 코드가 있어 F4 가 그 호출(set 계열 서비스)이 선택을 지울 수 있는지 확인'),
 'SAFE-01': dict(note_add='📥 9/22 박진용: 실측 줄은 복구 뒤 재검증(12:18 · 12:54) 값으로 채운다 — 11:10 값은 무효'),
}
for _tid, _e in P1525.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY105 = ['v15.5', '보고 반영', 'F3-02, ENV-05, SAFE-01', '박진용 9/22 15:25: 그릇 닦기 재검증 11:10 실행은 툴·TCP 풀림 구간 → 다시 잰다(복구 뒤 12:18·12:54 결과 대기) · moved=False 갈래 3함수 모두 남아 있음 · 펜던트 안 만짐 · 11:10 rig_v03 실행이 풀림 원인 단서(F4 확인)', '황인재 9/22 15:25', 'P,H']


# ---------------------------------------------------------------- 9/22 15:45 F4 — 무게 흔들림 원인 = 그리퍼 케이블 장력 · 툴·TCP 풀림 시점 분석
C1545 = '🔑 9/22 15:45 F4(황인재 관찰): **무게 오르내림의 원인 = 그리퍼 케이블 장력·흔들림** — 전선을 늘려 주니 ±10 g 안팎(숫자는 결정 시험으로 기록)'
P1545 = {
 'V-02':    dict(note_add=C1545 + '. 오후 자세별 결과(HOME −153 출렁 · z235 +230 튐)도 케이블로 설명될 가능성 → 케이블 느슨하게 고정한 뒤 그릇 쥔 채 결정 시험 → V-02 기록·PR'),
 'INT-12a': dict(note_add='🔗 9/22 전제 추가: **그리퍼 케이블 상태(느슨하게 · 자세마다 당기지 않게)를 먼저 맞춘다** — 무게 흔들림의 원인(케이블 장력)이 시험 중 바뀌면 기준값이 흔들린다'),
 'F3-02':   dict(note_add='🔗 9/22 15:45 F4 분석: 11:10 실행은 툴·TCP 가 **정상**이었다(공중 Fz 1.77 N — 풀렸으면 약 14 N 이라 rig_v03 이 거부했을 것) → 11:10 값이 무효가 아닐 수 있음. 다만 공중 1.77 N(≈180 g)은 케이블 장력일 수 있다 → 케이블 정리 뒤 재실행이 맞다'),
 'ENV-05':  dict(note_add='🔎 9/22 15:45 F4 분석: rig_v03 은 이름이 다를 때만 MANUAL 로 바꿔 set_tool/set_tcp 하고 AUTONOMOUS 로 되돌린다 · 11:10 실행은 정상이었다 → **풀린 시점 = 11:10 실행 뒤 ~ 11:17**. 12시 ROS set 실패는 AUTONOMOUS 모드라 거부된 것(펜던트가 필요했던 이유). rig_v03 주석 "브링업을 새로 켜면 툴·TCP 가 비어 있다(9/19)" → 그 사이 브링업 재시작(killdrcf 포함) 여부·9/19 관찰 조건을 박진용에게 확인. F4 의견: 시험 도구가 ROS 로 set 하고 모드를 오가는 것은 위험 → "확인만 · 다르면 거부 + 펜던트 안내" 로(황인재 결정 · 박진용 파일)'),
}
for _tid, _e in P1545.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY106 = ['v15.6', '원인·분석', 'V-02, INT-12a, F3-02, ENV-05', '황인재 9/22 15:45(F4 전달): 무게 흔들림 원인 = 그리퍼 케이블 장력(늘리니 ±10 g) → INT-12a 전제로 케이블 상태 고정 · 리마인드 §6. 툴·TCP 풀림 시점은 11:10 실행 뒤~11:17(11:10 은 정상) → 브링업 재시작 여부를 박진용에게. 시험 도구의 ROS set·모드 전환을 "확인만" 으로 바꿀지는 황인재 결정', '황인재 9/22 15:45', 'H,P,M']


# ---------------------------------------------------------------- 9/22 15:55 결정 E26 — 툴·TCP 는 확인만(ROS set · 모드 전환 금지) · 케이블 여유 길이로 해결
NEW_RULES.append(('🚨 실기 시작', '툴·TCP 이름 확인', '로봇을 움직이기 전에 get_current_tcp → GripperDA_v1 · get_current_tool → Tool Weight 를 확인한다. 비어 있거나 다르면 움직이지 말고 브링업을 끈 뒤 펜던트에서 다시 고른다. 🚨 E26(9/22): 프로그램·시험 도구도 **확인만** — ROS 로 set_tool/set_tcp 하거나 MANUAL↔AUTONOMOUS 를 오가지 않는다(다르면 종료 + 펜던트 안내). 9/22 오전 선택이 풀려 posx 이동이 손끝 208 mm 아래로 갔다'))
NEW_RULES.append(('🔗 케이블', '그리퍼 전선 느슨하게', '그리퍼 케이블이 팽팽하면 힘·무게 값이 ±25 g 이상 흔들린다(9/22 황인재 — 여유 길이를 늘려 해결 · ±10 g 안팎). 실기 전 케이블을 느슨하게 두고 자세마다(잔반통 J6 180° 회전 · HOME) 당기지 않는지 본다. 무게·힘 실기는 케이블 상태부터'))
P1555 = {
 'F3-02':  dict(note_add='🔴 9/22 결정 E26(황인재): rig_v03 · rig_v10 의 **set_tool/set_tcp · MANUAL↔AUTONOMOUS 전환 줄을 뺀다** — 확인만 하고 다르면 종료 + 펜던트 안내(민범진 preflight 와 같은 방식). 박진용에게 요청(오후 묶음 ③-3) · 작은 PR'),
 'ENV-05': dict(note_add='✅ 9/22 15:55 결정 E26: 툴·TCP 는 확인만(ROS set · 모드 전환 금지) — 규칙 시트 · 리마인드 §6. F4 init 이름 확인 PR 도 같은 원칙'),
 'V-02':   dict(note_add='🔗 9/22 15:55 황인재: 케이블은 **여유 길이를 늘려서 해결**. 그릇 쥔 채 결정 시험(--revisit · 물건 100 g) 진행 중 → 결과로 V-02 기록·PR'),
}
for _tid, _e in P1555.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY107 = ['v15.7', '결정 E26·규칙', 'F3-02, ENV-05, V-02, 규칙 시트', '황인재 9/22 15:45~55(F4 전달): E26 — 툴·TCP 는 확인만, 다르면 거부 + 펜던트(ROS set·모드 전환 금지) → 박진용 rig_v03·rig_v10 set 줄 제거 요청 · F4 init PR 같은 원칙 · 규칙 시트 갱신. 케이블은 여유 길이로 해결(규칙 🔗) · 그릇 결정 시험 진행 중', '황인재 9/22 15:55', 'P,H,M']


# ---------------------------------------------------------------- 9/22 16:30 PR #71 merge(민범진) — 물 털기 종류별 · 튜닝 시험대 · RINSE 값 인계 요청
M71 = '✅ 9/22 PR #71 merge(민범진)'
P1630 = {
 'F2-02':  dict(prog='0.9', note_add=M71 + ': 물 털기 = **J5 관절 왕복으로 되돌림 · 그릇·컵 종류별**(`f2.shake.RINSE.BOWL` ±10° 0.5 s · `.CUP` ±6° 0.6 s — 🟡 시작값) · `shake_params()` 종류별 묶음(한쪽만 있으면 KeyError) · 직선 왕복은 옵션(acc_mm_s2 추가) · 키보드 튜닝 시험대 `rig_shake_tune.py`(스페이스 = 진짜 shake · v = 30↔100 %) · 인계 절차서 `docs/test_logs/20260922_RINSE_물털기_튜닝_인계_민범진.md`. 병합본 390 통과'),
 'V-07':   dict(note_add=M71 + ': 🟡 물 털기 값(그릇·컵)은 실기로 정해야 함 — **민범진이 "PM(황인재) 인계" 요청**(그릇 10분 · 컵 10분 · 시험대·절차서 준비됨). 황인재 11:40 분담(무게만 F4)과 달라 **황인재 확인 대기** — 확정 전 담당은 민범진 그대로. 처음은 PREWASH_VEL_SCALE=0.3'),
 'UT-F2':  dict(note_add=M71 + ': rig_f2 shake 에 --amp/--period/--acc/--tilt(이번 실행만) 추가'),
}
for _tid, _e in P1630.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY108 = ['v15.8', '진척', 'F2-02, V-07, UT-F2', 'PR #71 merge(민범진 9/22 16:30): 물 털기 J5 왕복 · 그릇·컵 종류별(🟡 시작값) · 튜닝 시험대 · 인계 절차서. 민범진이 RINSE 값 정하기를 PM(황인재)에게 인계 요청 → 황인재 확인 대기(11:40 분담은 무게만)', '황인재 9/22 16:30', 'M,H']


# ---------------------------------------------------------------- 9/22 16:50 황인재 — ① 물 털기 값 = F4 ② GitHub 대조 ③ 뼈대 통합 계획(INT-F2 · INT-F3 · INT-ALL · NEW-01)
NEW.append(
 ('INT-F2', 'INT-12a', 'INT-12a', '통합', '민범진 F2 기능(무게·잔반 버리기·헹굼·물 털기)을 한석형 뼈대 코드(그릇 한 바퀴 시나리오)에 통합 — 실기로 한 바퀴',
  'M(S)', '시작 전', S('9/22 저녁'), '뼈대 + F2 통합본(브랜치 · PR) · 실기 기록(한 바퀴 몇 회 · 막힌 곳)',
  '한석형 뼈대(집기 → … → 적재)에 F2 함수(leftover_loop · dip · shake)가 진짜로 들어가 그릇 1개가 실기로 끝까지 돈다(F3 구간은 손·가짜) · INT-12a·12b(5회)는 이 안에서 같이 센다',
  '황인재 9/22 16:50 통합 방식: 민범진·박진용이 각자 자기 기능을 한석형 뼈대에 넣는다 → 둘 다 끝나면 한 사람이 두 통합본을 합쳐 전체 통합 코드 → 한석형 + 나머지 1명은 새 기능 구현. 🟡 뼈대 = `rig_bowl_scenario_real.py`(한석형 9/21~22 실기 완주본)으로 이해 — 확인 필요'))
NEW.append(
 ('INT-F3', 'INT-13', 'INT-13', '통합', '박진용 F3 기능(세제·닦기 + 안착 놓기)을 한석형 뼈대 코드에 통합 — 실기로 한 바퀴',
  'P(S)', '시작 전', S('9/22 저녁'), '뼈대 + F3 통합본(브랜치 · PR) · 실기 기록',
  '한석형 뼈대에 F3 함수(soap · wipe_bowl · wipe_cup)와 안착 놓기(F1-05)가 진짜로 들어가 그릇 1개가 실기로 끝까지 돈다(F2 구간은 손·가짜) · INT-13(5회)은 이 안에서 같이 센다',
  '황인재 9/22 16:50 통합 방식(INT-F2 와 같음). 박진용은 9/21 밤 이미 "한석형 경로 + 9/20 닦기" 로 한 바퀴 1회 성공 — 그 판을 main 코드(wipe.py)로 바꿔 잇는다'))
NEW.append(
 ('INT-ALL', 'SAFE-01', 'INT-3a', '통합', '전체 통합 코드 — INT-F2 통합본 + INT-F3 통합본을 한 사람이 합친다(뼈대 1개 · 기능 3개 · 그릇 한 바퀴 실기)',
  '🟡 M 또는 P (황인재 지정)', '시작 전', S('9/23 오전'), '전체 통합본(브랜치 · PR) · 실기 기록(그릇 한 바퀴 · 컵 한 바퀴)',
  '두 통합본을 합친 코드로 그릇 1개가 실기로 끝까지 돈다(손·가짜 없음) · 컵도 같은 코드로(E25: 무게 없음) · 🟡 flow_node·HMI 와의 관계는 황인재 확인',
  '황인재 9/22 16:50: INT-F2·INT-F3 가 둘 다 끝나면 한 사람이 합친다. 🟡 누가 합칠지 미정 · 🟡 이 전체 통합 코드가 flow_node(제품 메인 프로그램 · HMI 연결)를 대신하는지, flow_node 안으로 넣는 것인지 확인 필요 — L3(INT-3a·3b · flow + HMI)와 시연 구성이 달라진다'))
NEW.append(
 ('NEW-01', 'INT-ALL', 'INT-3a', '개발', '새 기능 구현 — 한석형 + 나머지 1명 (내용 🟡 황인재 지정)',
  '🟡 S + (M 또는 P)', '시작 전', S('9/23 오전', '9/23 오후'), '🟡 황인재 지정',
  '🟡 황인재 지정 — INT-ALL 을 맡지 않는 사람이 한석형과 함께 한다. 9/23 저녁 동결 전에 끝나는 범위로',
  '황인재 9/22 16:50: 통합을 한 사람에게 맡기고 한석형 + 나머지 1명은 새 기능을 만든다. 내용·담당은 황인재가 정한다(후보: 실패 주입 대응 · 컵 팔레트 2번째 칸 · HMI 연동 등 — PM 추정 아님, 미정)'))
EASY['INT-F2'] = '민범진이 자기가 만든 무게·털기·헹굼 함수를 한석형이 만든 "그릇 한 바퀴" 뼈대 프로그램에 끼워 넣고, 실제 로봇으로 한 바퀴 돌려 본다'
EASY['INT-F3'] = '박진용이 자기가 만든 세제·닦기·안착 함수를 한석형 뼈대 프로그램에 끼워 넣고, 실제 로봇으로 한 바퀴 돌려 본다'
EASY['INT-ALL'] = '민범진 통합본과 박진용 통합본을 한 사람이 하나로 합쳐 "전체가 다 들어간" 프로그램을 만들고 실기로 확인한다'
EASY['NEW-01'] = '통합을 맡지 않은 사람이 한석형과 함께 새 기능을 만든다(무엇을 만들지는 황인재가 정한다)'
H1650 = '🔄 9/22 16:50 황인재'
P1650 = {
 'V-07':    dict(owner='H(M)', note_add=H1650 + ': **물 털기 값 정하기(그릇·컵)는 F4(황인재)가 맡는다** — 민범진 인계 수락. 시험대 rig_shake_tune · 절차서(main `docs/test_logs/20260922_RINSE_물털기_튜닝_인계_민범진.md` · 🔔 15:34 개정판은 브랜치 `beomjin/20260922-F2-02-rinse-per-kind` 에만) · 처음 PREWASH_VEL_SCALE=0.3. 잔반 버리기(그릇)는 민범진이 이미 🟢'),
 'INT-12a': dict(note_add=H1650 + ': 통합 방식 변경 — 시험대(rig_int12) 대신 **INT-F2(한석형 뼈대에 F2 통합)** 안에서 5회를 센다. 이 행은 기록용'),
 'INT-12b': dict(note_add=H1650 + ': **INT-F2** 안에서 같이(재파지 → 헹굼 → 물 털기 → 적재)'),
 'INT-13':  dict(note_add=H1650 + ': **INT-F3** 안에서 같이(안착 → 툴 → 세제 → 닦기 → 반납)'),
 'FLOW-04': dict(note_add=H1650 + ': 🟡 통합 방식이 "한석형 뼈대에 기능 통합 → 전체 통합 코드" 로 바뀜 — flow_node 첫 실기를 언제·어떻게 할지는 INT-ALL 과 flow_node 의 관계가 정해진 뒤(황인재)'),
 'F1-02':   dict(note_add=H1650 + ': 저녁 통합(INT-F2·F3)이 한석형 뼈대(시나리오 스크립트)를 쓰므로 **pick() 제품 코드가 저녁 전제에서 빠짐** — 그래도 L3·flow_node 에는 필요'),
}
for _tid, _e in P1650.items():
    EDIT.setdefault(_tid, {}).update(_e)
SLOT['9/22 화']['D'] = ('🔄 16:50 통합 방식 변경(황인재): **① 민범진 INT-F2 — F2 기능을 한석형 뼈대에 통합해 그릇 한 바퀴(M·S · 60분)** → **② 박진용 INT-F3 — F3 기능 + 안착을 한석형 뼈대에 통합해 그릇 한 바퀴(P·S · 60분)** · '
                        'INT-12a·12b·13 의 5회는 이 안에서 센다 · 로봇 불필요: 황인재 물 털기 값(V-07)은 로봇 빌 때 20분 · UT-FLOW(M) · NOTE-02 gif(H)')
SLOT['9/23 수']['B'] = ('🔄 통합 계획(황인재 9/22): **INT-ALL — 두 통합본을 한 사람이 합쳐 전체 통합 코드(🟡 담당 미정 · 그릇·컵 한 바퀴 실기)** · **NEW-01 새 기능 — 한석형 + 나머지 1명(🟡 내용 미정)** · '
                        'UT-F4·F4-05(H) — G3(L2) · 🛡 L1 잔여가 있으면 여기서 닫는다')
HISTORY109 = ['v15.9', '분담·통합 계획', 'V-07, INT-F2(신규), INT-F3(신규), INT-ALL(신규), NEW-01(신규), INT-12a·12b·13, FLOW-04, F1-02, 9/22 저녁·9/23 오전 로봇 슬롯',
              '황인재 9/22 16:50: ① 물 털기 값 정하기(V-07)는 F4(황인재) — 민범진 인계 수락 ② GitHub 대조(PR #65~#71 전부 반영 · 누락 없음 · 민범진 15:34 인계 문서 개정판은 브랜치에만) ③ 통합 방식: 민범진·박진용이 각자 기능을 한석형 뼈대에 통합(INT-F2·INT-F3 · 9/22 저녁) → 한 사람이 합쳐 전체 통합 코드(INT-ALL · 9/23 오전 · 🟡 담당 미정) → 한석형 + 1명 새 기능(NEW-01 · 🟡 내용 미정). 🟡 전체 통합 코드와 flow_node·HMI 의 관계 확인 필요',
              '황인재 9/22 16:50', 'S,M,P,H']


# ---------------------------------------------------------------- 9/22 17:00 민범진 인계 메시지 — 헹굼·털기 실기값 3가지(범위 확인 대기) · V-16 닫기 제안
MI = '📥 9/22 17:00 민범진 인계(→ 황인재 F4)'
P1700 = {
 'V-07':  dict(note_add=MI + ': 넘기는 것 **셋** — ① 헹굼 담금(dip) 컵 🟡 한 번도 안 함(🚨 담금 하강은 힘 감시 없음 → 컵 첫 시도 저속 · RINSE.CUP 자세 처음) ② 잔반 버리기(WASTE) ✅ 되는 것까지(추 107 g 털림) · 🟡 시연용 임팩트 미조정 ③ 물 털기(RINSE) 🟡 값 미정(그릇·컵 둘 다 채워야 시작). 한 세션 35분 · 절차서 `docs/test_logs/20260922_헹굼_털기_실기값_인계_민범진.md`(브랜치 · main 에 없음). 🟡 **황인재 결정 대기: 셋 다 F4 가 받을지, 물 털기만 받고 ①②는 민범진이 할지**'),
 'F2-02': dict(note_add=MI + ': 헹굼 담금 그릇 ✅ 9/22 실기 3/3(깊이 60 mm · 바닥 접촉 없음) · 컵 🟡 미실기'),
 'V-16':  dict(status='완료', prog='1.0', note_add=MI + ': **그릇 35 N 으로 털기·물 털기 낙하 0 → "35 N 유지" 로 닫는다**(민범진 제안 · PM 수용). 컵은 E19 로 HOLD 자체가 없음(NORMAL 5 N 으로 버팀 — 놓침은 V-07 물 털기에서 눈으로)'),
 'INT-F2': dict(note_add='🔔 9/22 17:00: 민범진은 아직 "저녁 INT-12a·12b(시험대) · FLOW-04" 로 알고 있음 — 18:20 공지(⓪-3)로 INT-F2(한석형 뼈대 통합) 방식을 알린다'),
}
for _tid, _e in P1700.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY110 = ['v16.0', '인계·완료', 'V-07, F2-02, V-16, INT-F2', '민범진 인계 메시지(9/22 17:00): 헹굼 담금 컵 · 잔반 버리기 임팩트 · 물 털기 값 셋을 황인재(F4)에게 — 범위는 황인재 결정 대기(결정은 물 털기만이었음). V-16 은 35 N 낙하 0 으로 완료. 민범진은 저녁을 아직 시험대 방식으로 알고 있어 18:20 공지로 INT-F2 안내', '황인재 9/22 17:00', 'M,H']


# ---------------------------------------------------------------- 9/22 17:20 황인재 — V-07 셋 다 민범진 · INT-ALL/NEW-01 추후 · 뼈대 함수화는 F4(SKEL-01)
NEW.append(
 ('SKEL-01', 'F1-01', 'F1-01', '개발', '뼈대 코드 정리 — 한석형 그릇 한 바퀴 시나리오 스크립트(rig_bowl_scenario_real.py)를 함수화·코드화해 통합 뼈대로 만든다',
  'H(S)', '시작 전', S('9/22 저녁'), '함수화된 뼈대(브랜치 · PR) — 단계별 함수 + 한 바퀴 실행 진입점 · 실기 1회 완주 기록',
  '한석형 스크립트가 실기로 완주한 경로·좌표를 그대로 지키면서 단계(집기 → 저울 → 잔반통 → 홈 → 툴 → 헹굼 → 팔레트)가 함수로 나뉜다 · 민범진(F2)·박진용(F3)이 자기 함수를 끼울 자리가 분명하다 · 실기 그릇 1회 완주(경로 바뀌지 않음 확인)',
  '황인재 9/22 17:20: 뼈대 = 한석형 시나리오 스크립트가 맞는데 함수화·코드화가 안 돼 있어 **F4(황인재)가 맡는다**. INT-F2·INT-F3 의 전제. 🟡 함수화 결과를 handling.py(pick·rack_place)로 넣으면 F1-02·F1-04 제품 코드가 되는데 그 파일은 한석형 담당 — 어디에 둘지 황인재 확인'))
EASY['SKEL-01'] = '한석형이 실기로 완주시킨 "그릇 한 바퀴" 시험 스크립트를 단계별 함수로 나눠, 민범진·박진용이 자기 기능을 끼워 넣을 수 있는 뼈대 프로그램으로 만든다'
H1720 = '🔄 9/22 17:20 황인재'
P1720 = {
 'V-07':   dict(owner='M', note_add=H1720 + ': **셋 다 민범진이 그대로 담당**(어느 정도 구현돼 있어서) — 헹굼 담금 컵 · 잔반 버리기 임팩트 · 물 털기 값. F4 인계 취소'),
 'INT-F2': dict(note_add=H1720 + ': 전제 = **SKEL-01**(F4 뼈대 함수화) — 뼈대가 함수로 나뉜 뒤 F2 함수를 끼운다'),
 'INT-F3': dict(note_add=H1720 + ': 전제 = **SKEL-01**(F4 뼈대 함수화)'),
 'INT-ALL': dict(note_add=H1720 + ': 담당은 **추후** 정한다'),
 'NEW-01': dict(note_add=H1720 + ': 내용은 **구상한 뒤** 넣는다'),
 'F1-02':  dict(note_add=H1720 + ': 뼈대 함수화(SKEL-01)는 F4 가 맡음 — 🟡 그 결과가 pick() 제품 코드를 대신하는지(파일은 한석형 담당) 확인 필요'),
 'F1-04':  dict(note_add=H1720 + ': 🟡 rack_place 도 같은 확인(SKEL-01)'),
}
for _tid, _e in P1720.items():
    EDIT.setdefault(_tid, {}).update(_e)
_o = '🔄 16:50 통합 방식 변경(황인재): **① 민범진 INT-F2'
assert _o in SLOT['9/22 화']['D']
SLOT['9/22 화']['D'] = SLOT['9/22 화']['D'].replace(_o, '🔄 17:20: **⓪ 황인재 SKEL-01 — 한석형 시나리오 스크립트 함수화(로봇 불필요 · 끝나면 실기 1회 완주 15분)** → **① 민범진 INT-F2')
SLOT['9/22 화']['D'] = SLOT['9/22 화']['D'].replace('로봇 불필요: 황인재 물 털기 값(V-07)은 로봇 빌 때 20분 · ', '민범진 V-07(헹굼 담금 컵 · 잔반 임팩트 · 물 털기 값 35분)은 INT-F2 앞뒤 로봇 빌 때 · ')
HISTORY111 = ['v16.1', '분담', 'V-07, SKEL-01(신규), INT-F2, INT-F3, INT-ALL, NEW-01, F1-02, F1-04, 9/22 저녁 로봇 슬롯',
              '황인재 9/22 17:20: ① 헹굼 담금 컵·잔반 임팩트·물 털기 값(V-07)은 민범진이 그대로(F4 인계 취소) ② INT-ALL 담당 추후 ③ 새 기능은 구상 뒤 ④ 뼈대 = 한석형 시나리오 스크립트, 함수화·코드화는 F4(SKEL-01 · 9/22 저녁 · INT-F2·F3 전제). 🟡 함수화 결과와 handling.py pick/rack_place(한석형 파일)의 관계 확인 필요',
              '황인재 9/22 17:20', 'H,M,S,P']


# ---------------------------------------------------------------- 9/22 17:45 PR #72 merge(박진용) — soap 속도 · 나선 재시도 · 실기 1차 통합 성공
M72 = '✅ 9/22 PR #72 merge(박진용)'
P1745 = {
 'F3-02':  dict(prog='0.95', note_add=M72 + ': wipe_bowl = rig_v03 순서 그대로(빠른 하강 140 · 공중 |Fz| > 3 N 중단 · 바닥 3 N · 40 s · 순응 유지 · 나선 최대 3회 재시도 · 힘제어 1.5 N · 벽면 · 120 s 상한 유지) · 🟢 실기 1차 통합(soap → 닦기 → 반납) 성공 1회(🟡 시각 확인 요청 — 툴·TCP 풀림 구간 여부). 병합본 386 통과. 남은 것: 재검증 3회 기록(UT-F3)'),
 'F3-03':  dict(prog='0.95', note_add=M72 + ': **soap 동작 변경** — SOAP 자리로 안 가고 툴 집은 자리에서 J6 ±20° 비틀기 3회 → Z ±5 mm 왕복 2회 → HOME(그릇·컵 공용 · count 무시 · 60 s 상한 · vel_scale 예외). 🟡 E18(홀더 컵에서 담금)과 다름 — F1-03 tool(PICK) 이 툴을 빼낸 뒤 부르면 세제가 안 묻을 수 있어 INT-F3 에서 F1-03(황인재)과 맞춘다. SDD §5.4 · IRD 갱신'),
 'UT-F3':  dict(note_add=M72 + ': 제품 코드로 soap → wipe_bowl 1회 성공 → TC-06 연속 3회 기록만 남음'),
 'INT-F3': dict(note_add=M72 + ': 박진용 뼈대 통합본 `src/f3_wipe/test/rig_bowl_scenario_wipe.py`(한석형 스크립트 + F3 삽입 · 수세미 목표 폭 22 mm 실측 · 반납은 집은 깊이 그대로)가 main 에 — SKEL-01 함수화의 참고. 🟡 soap 높이(컵 안/위)와 F1-03 툴 빼내기 순서 확인'),
 'F1-03':  dict(note_add='🔔 9/22 PR #72(박진용): 반납은 집을 때 잰 posx 를 z 포함 그대로 써서 release 해도 된다(실기로 안 눌림 확인 · +10 mm 여유 불필요) · soap 이 "툴 집은 자리에서 비틀기" 로 바뀌어 tool(PICK) 이 툴을 빼내는 높이와 맞춰야 한다'),
 'INF-02b': dict(note_add=M72 + ': force.py 에 move_pose · move_joints · move_line_rel · wait_done 추가(닦기 전용 · motion.py 와 역할 겹침 — 동결 뒤 정리 후보) · contact_down(timeout_s, keep_compliance) 인자'),
 'CELL-04': dict(note_add=M72 + ': cell.yaml stations.HOME 에 posx_z_mm 215.11 추가(박진용 · soap 상승 계산용) — HOME posj 파생값이라 HOME 이 바뀌면 같이(E17 로 안 바꿈)'),
}
for _tid, _e in P1745.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY112 = ['v16.2', '진척', 'F3-02, F3-03, UT-F3, INT-F3, F1-03, INF-02b, CELL-04', 'PR #72 merge(박진용 9/22 17:45): 실기 1차 통합(soap → 닦기 → 반납) 성공 · wipe_bowl rig_v03 그대로(120 s 유지 · 나선 재시도) · soap 동작 변경(집은 자리에서 비틀기·왕복 · 🟡 E18 과 다름 → INT-F3 에서 F1-03 과 맞춤) · HOME posx_z_mm 키 추가', '황인재 9/22 17:45', 'P,H']


# ---------------------------------------------------------------- 9/22 17:50 황인재 E27·E28 · F4 V-02 끝
H1750 = '🔄 9/22 17:50 황인재'
P1750 = {
 'SKEL-01': dict(note_add=H1750 + ' E27: 함수화한 코드는 **`f1_handling/handling.py` 에 넣는다**(pick · rack_place · 일반 place · move_to) — 한석형 파일이지만 예외 · 한석형은 같은 시간에 handling.py 를 고치지 않는다(18:20 공지). 좌표 정본 = cell.yaml(스크립트 리터럴과 다르면 cell.yaml 고치고 보고). 참고: 박진용 통합본 rig_bowl_scenario_wipe.py 도 main 에'),
 'F1-02':   dict(owner='H(S)', note_add=H1750 + ' E27: pick() 제품 코드는 **SKEL-01(F4)** 이 handling.py 에 넣는다 — 한석형은 참여(경로·좌표 확인)'),
 'F1-04':   dict(owner='H(S)', note_add=H1750 + ' E27: rack_place() 도 SKEL-01(F4) 로'),
 'INT-ALL': dict(crit='🔄 E28: **예외 처리 없이 정상 흐름대로 전체(그릇 2 · 컵 2)를 한 번 끝까지 시연** — 실패 정책·격리·재시도는 목표에서 제외. 합친 코드로 그릇 1개 → 컵 1개 → 4개 연속. 🟡 flow_node·HMI 와의 관계 · INT-4b 범위는 황인재 확인',
                 note_add=H1750 + ' E28: 목표 = 정상 상황 플로우 전체 1회 시연(예외 제외). 담당은 추후'),
 'INT-4b':  dict(note_add='🟡 9/22 E28: 시연 목표가 "예외 처리 제외 · 정상 흐름" 이라 실패 주입 4종을 시연 범위에서 뺄지 황인재 확인(SDD §9.9 범위 방어)'),
 'V-02':    dict(prog='0.9', note_add='✅ 9/22 F4 V-02 끝(실기 · 케이블 정리 뒤 · 15:22~15:52): 빈 그릇 z158 기준값 **−12 g**(63 s 창 3개 −10/−15/−7) · 그릇+96 g 창 3개 +95/+80/+88 → 100 g 물건 오차 +3 g ✅ · 21 s 창 흔들림 ±12~17 g · HOME 다녀온 뒤 −5~−16 g → 한 번 재는 값 불확실성 약 ±20 g. '
                          '황인재: **잔반 임계 50 g 유지**(후보 70 대신 · 최종은 INT-12a 같은 경로 재측정 뒤). params `f2.empty_weight_g.BOWL: -12` + 기록 `docs/test_logs/20260922_V-02_무게기준값_황인재.md` → 브랜치 injae/20260922-V-02-weigh-baseline(3643607) · PR 은 황인재 확인 뒤. 🟡 민범진 판단 요청: **min_net_g −60 은 그릇 놓침을 못 잡는다**(빈손 z158 −57 → 순무게 −45 > −60) → 놓침은 폭(pick 판정·slip_tol)으로, 또는 −35(빈 그릇과 여유 15 g)'),
 'F2-01':   dict(note_add='🔔 9/22 F4 V-02: 임계 50 유지(황인재) · min_net_g −60 으로는 그릇 놓침이 안 잡힘(−45) → 민범진 판단(−35 또는 폭으로) — 18:20 묶음'),
}
for _tid, _e in P1750.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY113 = ['v16.3', '결정 E27·E28 · V-02', 'SKEL-01, F1-02, F1-04, INT-ALL, INT-4b, V-02, F2-01', '황인재 9/22 17:50: E27 뼈대 함수화는 handling.py 에(F4 · pick/rack_place 가 이걸로 · 한석형 동시 수정 금지 · 좌표 정본 cell.yaml) · E28 시연 = 예외 처리 없이 정상 흐름 전체 1회(🟡 INT-4b·HMI 관계 확인). F4 V-02 끝: 기준값 −12 g · 100 g 오차 +3 g · 불확실성 ±20 g → 임계 50 유지 · min_net_g 는 민범진 판단', '황인재 9/22 17:50', 'H,S,M']


# ---------------------------------------------------------------- 9/22 18:05 PR #73 merge(V-02 끝) · F4 실기 잔여 → 저녁 틈/9/23 오전 · SKEL-01 한석형 동의 뒤 PR
P1805 = {
 'V-02':    dict(status='완료', prog='1.0', note_add='✅ 9/22 PR #73 merge — `f2.empty_weight_g.BOWL: −12`(황인재 실기 · 민범진 멘션) · 기록 `docs/test_logs/20260922_V-02_무게기준값_황인재.md` · rig_weigh_poses 옵션. 🟡 케이블 정리 뒤 재현성 1회 → INT-12a(같은 경로)에서 재확인 · 시연 날 아침 `rig_f2.py empty --kind BOWL -n 10` 재측정(REH-02 점검표)'),
 'REH-02':  dict(note_add='📋 9/22: 시연 날 아침 점검 — 케이블 여유 · 툴·TCP 이름 · 빈 그릇 기준값 재측정 `rig_f2.py empty --kind BOWL -n 10`(3.5 분 · 케이블·툴 무게·TCP·좌표가 바뀌었으면 필수)'),
 'SKEL-01': dict(note_add='🔄 9/22 18:00 황인재: **한석형 동의를 받고** handling.py 에 넣는다(18:20 묶음 ① 동의 요청) — 동의 전에는 F4 브랜치에서만 · PR 은 동의 뒤. 좌표는 cell.yaml 키로 읽고 스크립트 리터럴과 다른 곳은 PR 표로'),
 'V-24':    dict(slots=S('9/20 오후', '9/21 오전', '9/22 저녁', '9/23 오전'), note_add='🔄 9/22 18:00 F4: 오전 로봇이 없어 ②③④(그릇 2·3회차)는 미완 — 오늘 저녁은 INT-F2·F3 가 로봇을 쓰므로 SKEL-01 실기 완주(15분) 뒤 남는 틈 또는 **9/23 오전**'),
 'V-25':    dict(slots=S('9/21 저녁', '9/22 저녁', '9/23 오전'), note_add='🔄 9/22 18:00 F4: 미완 → 저녁 틈 또는 9/23 오전'),
 'V-08':    dict(slots=S('9/22 저녁', '9/23 오전'), note_add='🔄 9/22 18:00 F4: 오늘 오후 못 함 → 저녁 틈 또는 **9/23 오전**(툴 프리셋 측정 → 10회 → F1-03 PR). 오늘 저녁 INT-F3 는 박진용 통합본 스크립트의 툴 집기로 돈다'),
 'F1-03':   dict(slots=S('9/22 저녁', '9/23 오전'), note_add='🔄 9/22 18:00 F4: **오후 마감 못 지킴** — V-08 뒤 PR 은 9/23 오전. 오늘 저녁 INT-F3 는 뼈대 스크립트 방식이라 막히지 않음 · INT-ALL·L3(제품 tool()) 전제. 🔔 PR #72 로 soap 이 "집은 자리에서 비틀기" 가 됨 → tool(PICK) 끝 높이를 박진용 답에 맞춘다'),
}
for _tid, _e in P1805.items():
    EDIT.setdefault(_tid, {}).update(_e)
SLOT['9/22 화']['D'] = SLOT['9/22 화']['D'].replace('민범진 V-07(헹굼 담금 컵 · 잔반 임팩트 · 물 털기 값 35분)은 INT-F2 앞뒤 로봇 빌 때 · ',
                                                    '민범진 V-07(헹굼 담금 컵 · 잔반 임팩트 · 물 털기 값 35분)은 INT-F2 앞뒤 로봇 빌 때 · 황인재 V-24 ②③④ · V-25 · V-08 은 **로봇이 비면**(아니면 9/23 오전) · ')
SLOT['9/23 수']['B'] = SLOT['9/23 수']['B'].replace('UT-F4·F4-05(H) — G3(L2)', '**황인재 V-08 → F1-03 PR · V-24 ②③④ · V-25(오전 첫 로봇 40분)** · UT-F4·F4-05(H) — G3(L2)')
HISTORY114 = ['v16.4', '완료·재배치', 'V-02, REH-02, SKEL-01, V-24, V-25, V-08, F1-03, 9/22 저녁·9/23 오전 로봇 슬롯', 'PR #73 merge(9/22 18:05): V-02 완료 — 빈 그릇 기준값 −12 g. F4 실기 잔여(V-24 ②③④ · V-25 · V-08 → F1-03 PR)는 오늘 로봇이 없어 저녁 틈 또는 9/23 오전 첫 로봇 40분으로(F1-03 오후 마감 못 지킴 · 저녁 INT-F3 는 뼈대 스크립트라 막히지 않음). SKEL-01 은 한석형 동의 뒤 PR', '황인재 9/22 18:05', 'H,S']


# ---------------------------------------------------------------- 9/22 18:30 민범진 PR #74(pick·rack_place 이식) — 코드 통과 · merge 는 황인재 결정 대기(E27 겹침)
P74 = '🟡 9/22 18:30 PR #74(민범진 · 대기)'
P1830 = {
 'F1-02':   dict(prog='0.8', note_add=P74 + ': 한석형 대본을 pick() 으로 이식(좌표는 cell.yaml · 그릇 폭 판정 E16 · 컵 E19 · 재파지 빈손 = GRIP_FAIL) · 자동 시험 404 통과 · 가상 12a 2/2 · 🔴 실기 미확인(V-14 · INT-12a 0.3). **handling.py 는 한석형 파일 — "PM 승인" 은 없었고 E27(F4 SKEL-01)과 겹침 → merge 는 황인재 결정 + 한석형 동의 뒤**'),
 'F1-04':   dict(prog='0.8', note_add=P74 + ': rack_place() 이식 — RINSE 위 → 경유점(RACK_B_VIA · RACK_B1_VIA J6 +180 · RACK_C_VIA) → 칸 위 → 마지막 30 mm 삽입력 감시(15 N) → RACK_JAM/FORCE_LIMIT/TIMEOUT 후퇴 → exit. 가상 12b 그릇 2/2 · 컵 1/1 · 🔴 실기 미확인(V-06 · INT-12b). cell.yaml RACK_B1 C +180 · RET_B 접근점 변경 — 한석형 확인 대기'),
 'SKEL-01': dict(note_add=P74 + ': 🚨 민범진이 같은 일(대본 → handling.py 함수)을 먼저 해서 PR #74 로 올림 — **F4 는 멈춤**(PM 18:25 통보). 황인재 결정: ① #74 를 뼈대로 받고 F4 는 tool()·컵·검토로 / ② F4 가 E27 대로 다시. 결정 전까지 handling.py 손대지 않음'),
 'INT-F2':  dict(note_add=P74 + ': #74 가 merge 되면 저녁 통합을 "뼈대 스크립트" 대신 **제품 함수(pick·rack_place) + rig_int12/flow** 로 갈 수 있다 — 방식은 황인재 결정'),
}
for _tid, _e in P1830.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY115 = ['v16.5', 'PR 대기', 'F1-02, F1-04, SKEL-01, INT-F2', '민범진 PR #74(9/22 18:30): 한석형 대본을 handling.py pick()/rack_place() 로 이식(가상 12a·12b 통과 · 404 통과) — 코드는 통과했으나 한석형 파일이고 "PM 승인" 이 없었으며 E27(F4 SKEL-01)과 겹쳐 **merge 보류 · 황인재 결정 + 한석형 동의 대기**. F4 SKEL-01 멈춤', '황인재 9/22 18:30', 'M,S,H']


# ---------------------------------------------------------------- 9/22 18:40 F4 — V-08 1단계(툴 프리셋) · F1-03 브랜치도 handling.py · 순서 결정 요청
F1840 = '📈 9/22 18:40 F4'
P1840 = {
 'V-08':    dict(prog='0.5', status='진행', note_add=F1840 + ': 1단계 툴 프리셋 실측(E23) — 수세미 25.10 mm(영점 뺀 14.52 · 흔들림 0.20 · 40 N) · 솔 19.30(8.72 · 0.10 · 30 N) → cell.presets.SPONGE/BRUSH 채움(폭 판정 가능 · 빈손과 1.2 mm 차 · tol 0.6). 2단계 홀더 집기 → 반납 CYCLE ×10 실기 중(F1-03 브랜치) — 9/10 이상이면 황인재 승인 뒤 F1-03 PR'),
 'F1-03':   dict(note_add=F1840 + ': 브랜치가 handling.py 를 바꾼다(tool() +100/−7 · _TOOL_STATION) — **민범진 PR #74(pick·rack_place)와 같은 파일** → merge 순서 결정 필요(먼저 merge 되는 쪽에 다른 쪽이 rebase). PM 권고: #74 먼저(크고 이미 가상 검증) → F1-03 rebase(충돌 범위 작음)'),
 'SKEL-01': dict(note_add=F1840 + ': F4 는 handling.py 에 한 줄도 안 넣음(스크립트 읽기만) → 멈춤. F4 의견: #74 를 뼈대로 받고 F4 는 실기 1회 완주 검증 + place·move_to 정리 + F2/F3 끼울 자리 명시로(리터럴 좌표 없어야 · E14)'),
}
for _tid, _e in P1840.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY116 = ['v16.6', '진척', 'V-08, F1-03, SKEL-01', 'F4 9/22 18:40: V-08 1단계 툴 프리셋 실측(수세미 25.10 · 솔 19.30 → cell.presets) · 2단계 CYCLE ×10 실기 중. F1-03 브랜치도 handling.py 를 바꿔 PR #74 와 순서 결정 필요(PM 권고 #74 먼저). SKEL-01 은 시작 전 멈춤 — #74 를 뼈대로 받는 안', '황인재 9/22 18:40', 'H,M']


# ---------------------------------------------------------------- 9/22 18:50 황인재 결정(E27 갱신) — PR #74 merge · 뼈대 = 민범진 이식 · F4 손 뗌
M74 = '✅ 9/22 PR #74 merge(민범진 · 황인재 결정 E27 갱신)'
P1850 = {
 'F1-02':   dict(owner='S', prog='0.85', note_add=M74 + ': pick() 제품 코드 main 에(대본 이식 · 좌표 cell.yaml · 가상 12a 2/2). 🔴 실기 미확인 → 오늘 저녁 INT-12a 첫 실기 0.3(V-14 겸). 이후 수정은 한석형. 한석형 확인 2건: RACK_B1 C +180 · HOME J6 0(케이블)'),
 'F1-04':   dict(owner='S', prog='0.85', note_add=M74 + ': rack_place() main 에(경유점 3개 · 삽입력 감시 15 N · RACK_JAM/FORCE_LIMIT/TIMEOUT). 🔴 실기 미확인 → INT-12b(V-06 겸)'),
 'SKEL-01': dict(status='완료', prog='1.0', note_add='✅ 9/22 18:2x 황인재: **뼈대 = 민범진 PR #74** — F4 는 손 뗌(E27 갱신). 이 행은 #74 로 갈음'),
 'INT-F2':  dict(note_add='🔄 9/22 18:50: #74 merge → 저녁 통합은 **제품 함수(pick·rack_place·F2) + rig_int12(또는 flow)** 로 — 뼈대 스크립트 대신. 첫 실기 0.3 · 한석형 참여'),
 'INT-F3':  dict(note_add='🔄 9/22 18:50: F1-03 tool() 은 아직 브랜치(V-08 2단계 뒤 PR · #74 위 rebase) → 박진용 통합은 오늘 밤엔 통합본 스크립트(rig_bowl_scenario_wipe.py) 방식 유지, tool() merge 뒤 제품 함수로'),
 'F1-03':   dict(note_add='🔄 9/22 18:50: 순서 확정 — **#74 먼저 merge 됨 → F1-03 은 그 위에 rebase**(F4 동의)'),
 'V-25':    dict(note_add='9/22 18:50 F4 순서: V-08 2단계 → F1-03 PR → V-25 → V-24 → HMI E25 · init 툴/TCP 확인 PR'),
}
for _tid, _e in P1850.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY117 = ['v16.7', '결정 E27 갱신·merge', 'F1-02, F1-04, SKEL-01, INT-F2, INT-F3, F1-03, V-25', '황인재 9/22 18:2x(F4 전달): 민범진 PR #74(대본 → pick·rack_place 이식)를 뼈대로 받는다 → merge · SKEL-01 완료(갈음) · F4 는 V-08 → F1-03 PR(#74 위 rebase) → V-25 → V-24. 저녁 INT-F2 는 제품 함수 + rig_int12/flow 로 · 🔴 pick/rack_place 실기 미확인(첫 실기 0.3)', '황인재 9/22 18:50', 'M,S,H']


# ---------------------------------------------------------------- 9/22 19:00 PR #74 추가 커밋(rig_flow_once) 사후 검토 — INT-F2 = FLOW-04 도구
P1900 = {
 'INT-F2':  dict(note_add='🔧 9/22 PR #74 추가 커밋(15c6570 · PM 사후 검토 OK): `src/f2_sense_flow/test/rig_flow_once.py` — flow.process_one 을 용기 1개에 실기로(HMI 없이 · PAUSED 면 사람이 Enter/a/q · 문지기 통과 뒤 · `--mock f3` 기본). 민범진: "뼈대는 따로 만들지 않는다 — 제품 경로(flow.py)가 뼈대" → 오늘 저녁 INT-F2 = 이 도구로 그릇 1개(진짜 f1·f2 · F3 가짜) = **FLOW-04 와 같은 것**'),
 'FLOW-04': dict(note_add='🔄 9/22 19:00: rig_flow_once(#74)로 오늘 저녁 INT-F2 에서 사실상 수행 — process_one 을 진짜 f1·f2 로(F3 가짜). flow_node + HMI 로 같은 것을 다시 돌리면 L3(INT-3a)'),
}
for _tid, _e in P1900.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY118 = ['v16.8', '도구', 'INT-F2, FLOW-04', 'PR #74 에 merge 직전 올라온 rig_flow_once.py(시험 도구 · PM 사후 검토 OK · 404 통과): flow.process_one 을 용기 1개에 실기로 — 오늘 저녁 INT-F2 가 이 도구로 진행되며 FLOW-04 를 겸한다', '황인재 9/22 19:00', 'M']


# ---------------------------------------------------------------- 9/22 19:40 PR #75 merge(민범진) — 케이블 장력 경고
P1940 = {
 'F2-01':   dict(note_add='✅ 9/22 PR #75 merge(민범진): 🔗 **케이블 장력 경고** — weigh() 표본 30개의 10~90 % 폭 > `f2.limits.max_weigh_spread_g`(50) 이면 경고(추가 시간 0 s) · 시작 전 문지기 뒤 HOME 정지 Fz 8회 폭 > `flow.preflight.cable.max_spread_g`(60) 이면 경고(약 5 s · samples 0 이면 끔). 경고만 · 멈추지 않음 · Virtual 건너뜀. 🟡 기준값 2개는 임시 → 저녁 INT-F2 로그의 "퍼짐 NN g" 로 조정(params 한 줄 PR)'),
 'INF-02c': dict(note_add='✅ 9/22 PR #75: weigh() 에 퍼짐 계산·경고 · `weigh_last()`(기록용 요약)'),
 'F4-03':   dict(note_add='🔔 9/22 PR #75: 케이블 경고는 지금 flow_node 로그(PC-A 터미널)에만 — HMI 표시는 F4 몫(합의 뒤 · /flow/state.message 에 섞지 않기로)'),
}
for _tid, _e in P1940.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY119 = ['v16.9', '진척', 'F2-01, INF-02c, F4-03', 'PR #75 merge(민범진 9/22 19:40): 케이블 장력 경고 — 무게 잴 때 표본 퍼짐(0 s) + 시작 전 정지 흔들림(5 s) · 경고만 · 기준값 임시(저녁 실기로 조정) · 410 통과. HMI 표시는 F4 몫', '황인재 9/22 19:40', 'M,H']


# ---------------------------------------------------------------- 9/22 20:00 PR #76 merge(F4 F1-03) — V-08 완료 · f1 세 함수 전부 main
M76 = '✅ 9/22 PR #76 merge(황인재 F4)'
P2000 = {
 'F1-03':  dict(status='완료', prog='1.0', note_add=M76 + ': tool(PICK/RETURN) 제품 코드 main 에 — PICK 폭 판정(E16) → 100 mm 빼냄 · RETURN contact_down 8 N · 깊이 ≤ 20 mm · 바닥 못 찾으면 놓지 않음 · 후퇴. 🟢 V-08 실기 10/10 · 10/10. 🟡 tool(PICK) 끝 높이 ↔ soap(#72) 는 INT-F3 에서(박진용 답 뒤)'),
 'V-08':   dict(status='완료', prog='1.0', note_add=M76 + ': 실기(18:08~18:35 · vel 0.3) 수세미 10/10(폭 25.60) · 솔 1차 8/10 → 기준값 8.72 → 8.3 뒤 2차 10/10(18.6~19.1) · 손목 −220° 풀림·툴 밀림·반납 바닥 찾기 이상 없음. 프리셋 SPONGE 15.0·40 N / BRUSH 8.3·30 N(E23). 기록 `docs/test_logs/20260922_V-08_툴집기반납_황인재.md`'),
 'INT-13': dict(note_add=M76 + ': 전제였던 f1.tool 이 main 에 — 이제 제품 함수(tool → soap → wipe → tool RETURN)로 돌릴 수 있다. 🟡 soap 높이(#72) ↔ tool(PICK) 끝 높이 확인이 먼저'),
 'INT-F3': dict(note_add=M76 + ': f1 세 함수 전부 main → 박진용 통합도 뼈대 스크립트 대신 **제품 함수 + rig_flow_once(--mock 없이)** 로 갈 수 있다 — 단 soap ↔ tool(PICK) 높이 먼저 맞춘다'),
 'FLOW-04': dict(note_add=M76 + ': pick · rack_place · tool 전부 main → rig_flow_once 를 `--mock` 없이(진짜 f1·f2·f3) 돌릴 수 있는 상태. 🟡 soap ↔ tool 높이 확인 뒤'),
 'F1-02':  dict(note_add=M76 + ': handling.py 머리(import · _TOOL_STATION · _retreat) 합침 · pick/rack_place 는 #74 그대로'),
}
for _tid, _e in P2000.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY120 = ['v17.0', '완료', 'F1-03, V-08, INT-13, INT-F3, FLOW-04, F1-02', 'PR #76 merge(황인재 F4 9/22 20:00): F1-03 tool() 완료 · V-08 완료(수세미·솔 각 10/10 · 프리셋 확정) → **f1 세 함수(pick · rack_place · tool) 전부 main** — 저녁 INT-F3·INT-13·flow_node 실기 전제 해소. 🟡 soap(#72) ↔ tool(PICK) 끝 높이는 INT-F3 에서 박진용 답 뒤', '황인재 9/22 20:00', 'H,P,M']


# ---------------------------------------------------------------- 9/22 20:30 황인재 — 저녁 진행 상황(한석형 새 기능 · 민범진·박진용 뼈대 통합 중)
H2030 = '🔄 9/22 20:30 황인재'
P2030 = {
 'NEW-01': dict(status='진행 중', prog='0.1', owner='S', slots=S('9/22 저녁', '9/23 오전', '9/23 오후'), note_add=H2030 + ': **한석형이 새 기능을 구상하면서 구현 중**(오늘 저녁부터). 내용은 정해지는 대로 이 행에 적는다 · 9/23 저녁 동결 전 범위로'),
 'INT-F2': dict(status='진행 중', prog='0.2', note_add=H2030 + ': **민범진 — 한석형 뼈대 코드와 통합 시도 중**(오늘 저녁). 도구: rig_flow_once(제품 함수 pick·rack_place·F2 · F3 가짜) 또는 뼈대 스크립트 — 결과·막힌 곳은 저녁 보고로'),
 'INT-F3': dict(status='진행 중', prog='0.2', note_add=H2030 + ': **박진용 — 한석형 뼈대 코드와 통합 시도 중**(오늘 저녁). soap ↔ tool(PICK) 높이 정합이 먼저(PR #76 코멘트 답)'),
}
for _tid, _e in P2030.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY121 = ['v17.1', '진척', 'NEW-01, INT-F2, INT-F3', '황인재 9/22 20:30: 한석형은 새 기능 구상·구현 중(NEW-01 진행 · 내용 미정) · 민범진(INT-F2)·박진용(INT-F3)은 한석형 뼈대 코드와 통합 시도 중', '황인재 9/22 20:30', 'S,M,P']



# ---------------------------------------------------------------- 9/22 17:20 시각 정정 — v15.1~v17.1 의 시각을 추정으로 적었던 것을 커밋 시각으로 바로잡는다
FIX_TIMES = {'v15.1': '14:09', 'v15.2': '14:29', 'v15.3': '14:33', 'v15.4': '14:35', 'v15.5': '14:49', 'v15.6': '14:53', 'v15.7': '14:59', 'v15.8': '15:22',
             'v15.9': '15:38', 'v16.0': '15:40', 'v16.1': '15:59', 'v16.2': '16:05', 'v16.3': '16:05', 'v16.4': '16:09', 'v16.5': '16:25', 'v16.6': '16:26',
             'v16.7': '16:30', 'v16.8': '16:31', 'v16.9': '16:52', 'v17.0': '16:57', 'v17.1': '17:15'}
HISTORY122 = ['v17.2', '시각 정정', '변경이력 v15.1~v17.1 · 비고', 'PM 정정(9/22 17:20): v15.1~v17.1 의 변경이력 시각과 비고 안의 "15:00~20:30" 표기는 PM 이 시계를 보지 않고 추정한 값이었다(실제보다 20~200분 뒤). 변경이력 시각은 커밋 시각으로 고쳤다 — 비고 안의 시각은 이 표로 읽는다: '
              + ' · '.join(f'{k}={v}' for k, v in FIX_TIMES.items()) + '. 순서·내용은 그대로', '황인재 9/22 17:20', 'H']



# ---------------------------------------------------------------- 9/22 17:40 GitHub 대조(변화 없음) · README 정리
EDIT.setdefault('DOC-05', {}).update(dict(prog='0.2', status='진행 중', note_add='📝 9/22 17:40 README 정리(PM): 강사가 보고 이해하게 — 시나리오 · 구조 · 지금까지 된 것(검증 수준 표) · 직접 확인하는 명령(로봇 없이/가상/실기) · 문서 지도. as-built 갱신은 동결 뒤'))
HISTORY123 = ['v17.3', '최신화', 'DOC-05', 'GitHub 대조(9/22 17:20~17:40): 열린 PR 없음 · 17:15 이후 merge·push 없음 → 진척 변화 없음. README 를 강사용으로 정리(지금까지 된 것 + 확인 명령만)', '황인재 9/22 17:40', 'H']


# ---------------------------------------------------------------- 9/22 17:55 F4 V-25 컵 실기 — 컵 안 잡혔는데 ok=True (E19 판정 없음 · 그리퍼 힘 계단 가설)
F1755 = '🚨 9/22 17:55 F4(V-25 컵 실기 17:31)'
P1755 = {
 'V-25':    dict(prog='0.6', status='진행', note_add=F1755 + ': 그릇 pick(#74) 첫 실기 OK(17:11 · 폭 2.32 · 홈 B 놓기 OK — 안전 정지 2회는 손으로 잘못 물린 그릇 탓, 로봇 집기로 바꾼 뒤 재발 없음). **컵 1차: grip 목표 76 · 5 N → 실제 107.8 mm(거의 열림) 인데 PickResult ok=True** — E19(컵 폭 판정 없음)라 성공으로 넘어감 · 컵은 안 잡힘. 2차(25 s 뒤) 76.2 정상. 기록은 V-24 결과까지 모아 문서 PR'),
 'F1-02':   dict(note_add=F1755 + ': 🔴 컵 pick 이 **"안 닫힘"을 못 잡는다**(실제 107.8 인데 ok) → 제안 ① 컵도 최소 판정: 실제 폭 > 목표 + 10 mm 면 GRIP_FAIL(빈손 구분은 못 해도 "손가락이 안 닫힘"은 잡는다) — 민범진 판단(#74 pick · gripper.py) · 저녁 INT-12b 컵 1회차 폭 확인'),
 'INF-02d': dict(note_add=F1755 + ': 가설 — gripper.py `_set_force` 가 "마지막으로 읽은 힘"에서 2.5 N 계단 수로 맞추는데, 직전 그릇 집기(20 N 목표 → 27.5 N "정확히 못 맞춤")로 기억값과 실제가 어긋난 채 5 N 로 내리면 실제 힘이 유효 범위(3~40 N) 아래로 떨어져 **손가락이 안 움직인다**(오전 rig_tool_width 솔 3회차 "그리퍼가 전혀 움직이지 않았다" 경고도 같은 계통 의심). 제안 ② set 뒤 읽은 힘이 목표와 2.5 N 넘게 다르면 다시 맞추거나 grip 전에 오류 — 민범진 판단 · TS 기록 후보'),
 'INT-12b': dict(note_add=F1755 + ': 🔴 **컵 1회차 집기 폭을 꼭 확인**(76 근처인지 · 107 이면 안 잡힌 것) — E25 로 컵은 무게도 안 재니 안 잡힌 채 끝까지 갈 수 있다'),
}
for _tid, _e in P1755.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY124 = ['v17.4', '🚨 발견', 'V-25, F1-02, INF-02d, INT-12b', 'F4 V-25 컵 실기(9/22 17:31): 컵 pick 이 실제 폭 107.8(거의 열림)인데 ok=True — E19 로 폭 판정이 없어 안 잡힌 채 성공 처리. 가설 = gripper.py 힘 계단(_set_force)이 기억값과 어긋나 손가락이 안 움직임. 제안: 컵도 "안 닫힘" 최소 판정(목표 +10 mm 초과 → GRIP_FAIL) · 힘 set 확인 — 민범진 판단(18:20 묶음 맨 앞). 그릇 pick 첫 실기는 OK', '황인재 9/22 17:55', 'H,M']


# ---------------------------------------------------------------- 9/22 17:35 F4 정정 — 컵 107.8 은 배치 문제(힘 가설 철회) · 홈 C 놓기 좌표 의심
FIX_TIMES['v17.4'] = '17:34'
F1735 = '🔄 9/22 17:35 F4 정정'
P1735 = {
 'V-25':    dict(note_add=F1735 + ': 컵 1차 107.8 mm 는 **컵이 집는 자리에 딱 붙어 배치돼 손가락이 못 닫힌 것**(황인재 확인) — 힘 계단 가설 철회. "안 닫혀도 ok=True" 맹점은 그대로 → 민범진 판단 요청 유지. 🆕 **홈 C 놓기(place SPONGE_BED_C) 좌표가 안 맞는다**(17:33 관찰 · PlaceResult 는 OK 인데 컵이 홈에 제대로 안 앉음) — 방향·양 재실행 확인 중, 재현되면 F4 가 cell.yaml 고쳐 PR(E14)'),
 'INF-02d': dict(note_add=F1735 + ': 힘 계단(_set_force) 가설은 **철회**(컵 배치 문제였음) — ② 제안은 참고만'),
 'CELL-04': dict(note_add=F1735 + ': 🟡 `beds.SPONGE_BED_C.place`(#69 한석형: 접근 z 300 → 삽입 z 110 → +140) 로 놓으면 컵이 홈에 제대로 안 앉는다(황인재 17:33) — F4 재실행 확인 → 재현되면 좌표 수정 PR'),
 'INT-12b': dict(note_add=F1735 + ': 🟡 홈 C 놓기 좌표 의심 — 컵 재파지(regrip) 전 홈에 앉은 상태를 눈으로 확인 · F4 수정 PR 이 오면 그 좌표로'),
}
for _tid, _e in P1735.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY125 = ['v17.5', '정정·발견', 'V-25, INF-02d, CELL-04, INT-12b', 'F4 정정(9/22 17:35): 컵 1차 107.8 mm 는 컵이 집는 자리에 딱 붙어 배치된 탓(힘 가설 철회) · "안 닫혀도 ok" 맹점은 유지(민범진 판단). 🆕 홈 C 놓기 좌표(beds.SPONGE_BED_C.place)가 안 맞는 의심 — F4 확인 중 · 저녁 INT-12b 컵 주의. (v17.4 비고의 17:55 표기는 17:34)', '황인재 9/22 17:35', 'H,M']


# ---------------------------------------------------------------- 9/22 17:44 F4 — 🚨 툴·TCP 선택 두 번째 풀림(17:37~17:39 · 프로그램 안 돌던 틈) → 외부 요인 의심
T1744 = '🚨 9/22 17:44 F4'
P1744 = {
 'ENV-05':  dict(note_add=T1744 + ': **툴·TCP 선택이 오늘 두 번째로 풀렸다**(17:3x 확인 · get_current_tool/tcp 빈 값). 창 17:37:49(홈 C 놓기 posx 정상 완료 = TCP 살아 있음) ~ 17:39:07(다음 pick 부터 전혀 다른 좌표 · 17:40:39 move_stop 응답 없음). 그 사이 우리 프로그램은 안 돌았다 — 아침(11:10~11:17)도 rig_v03 종료 뒤 빈 틈 → **외부 요인(펜던트 조작 · 다른 PC 브링업/접속 · 컨트롤러) 의심**. 조치: 황인재가 펜던트에서 다시 선택(브링업 끄고 → 선택 → Dart 닫고 → 브링업 → 이름 확인) · 복구 전 로봇 이동 금지 · rig_f1 에 문지기 없어 못 막음 → F4 가 넣는다. 팀 질문: 17:37~17:40 펜던트·다른 PC 브링업/접속 여부(전원 · 즉시)'),
 'INT-F2':  dict(note_add=T1744 + ': 🚨 시작 전 **툴·TCP 두 이름 확인 필수**(17:3x 두 번째 풀림 · 복구 뒤) · 저녁 통합 준비로 다른 PC 에서 브링업·접속했는지 확인'),
 'INT-F3':  dict(note_add=T1744 + ': 🚨 시작 전 툴·TCP 두 이름 확인 필수 · rig_v03·rig_v10 은 아직 set/모드 전환 코드가 남아 있음(E26 수정 PR 전) — 실행 전 이름부터'),
 'V-25':    dict(note_add=T1744 + ': 상태 — 이동 3 · 빈손 놓기 · 그릇 pick→place 1(+손 1) · 컵 pick→홈 C 놓기 2회(좌표 어긋남 관찰 — 🟡 TCP 풀림 시각과의 관계 확인 필요: 17:33 관찰은 풀림(17:38) 전) · V-24 미실행 → 로봇을 통합 팀에 넘기면 V-24 는 9/23 아침'),
 'CELL-04': dict(note_add=T1744 + ': 홈 C 놓기 좌표 의심(17:33)은 TCP 풀림(17:37~) **전** 관찰이라 별개일 가능성 — F4 재실행으로 가린다'),
}
for _tid, _e in P1744.items():
    EDIT.setdefault(_tid, {}).update(_e)
HISTORY126 = ['v17.6', '🚨 사고 2', 'ENV-05, INT-F2, INT-F3, V-25, CELL-04', 'F4 9/22 17:44: 툴·TCP 선택이 두 번째로 풀림(17:37~17:39 · 우리 프로그램 안 돌던 틈 · 아침과 같은 양상) → 외부 요인 의심 · 황인재 펜던트 재선택 · 복구 전 이동 금지 · 저녁 통합 시작 전 두 이름 확인 필수 · 전원에게 "17:37~17:40 펜던트·다른 PC 브링업/접속 여부" 즉시 질문 · rig_f1 문지기 추가(F4)', '황인재 9/22 17:44', '전원']



# ---------------------------------------------------------------- 9/22 17:46 F4 — TCP 풀림 확정 · 15:19 브링업 재시작 때는 이름 유지 · 재현 계획
EDIT.setdefault('ENV-05', {}).update(dict(note_add='🔎 9/22 17:46 F4: **TCP 풀림 확정** — HOME posj 인데 posx z 422.98(플랜지) · robot_state 1 · 알람 기록 없음. 참고: 15:19 브링업 껐다 켰을 때는 이름이 살아 있었음(rig_f2 문지기 통과) → "브링업 재시작이 항상 비운다" 는 아님. 두 창 공통점 = 우리 프로그램이 안 도는 빈 틈 → 외부 조작·다른 PC 의심. 복구 뒤 ① ros2 node list(낯선 노드) ② 브링업만 껐다 켜기 재현 ③ 두 이름 확인 → 결과 대기'))
HISTORY127 = ['v17.7', '확인', 'ENV-05', 'F4 9/22 17:46: TCP 풀림 확정(HOME z 422.98 = 플랜지 · 알람 없음) · 15:19 브링업 재시작 때는 이름 유지 → 외부 요인 쪽 · 복구 뒤 재현 3단계 · 로봇은 복구·확인 뒤 통합 팀에 · V-24 는 9/23 아침', '황인재 9/22 17:46', 'H']



# ---------------------------------------------------------------- 9/22 17:55 🚨 실기 충돌(TS-08) · PR #77 merge
EDIT.setdefault('INT-F2', {}).update(dict(note_add='🚨 9/22 17:27 실기 충돌(민범진 세션 · 30 %): rig_f2 dip 3회 뒤 rig_shake_tune 시작 → 수조 안 자세(z −13.6)에서 HOME 관절 이동이 테이블을 가로질러 그리퍼가 상판을 쓸고 비상정지 · 툴 전원 끊겨 그리퍼 드라이버 종료(sendCommand 안 보임) · 피해 없음 · 슬롯 ~15분. → PR #77 merge(17:55): f2 시험대 6곳 + flow.abort_container 가 HOME 앞에 곧게 위로(safe_retreat · 새 설정 없음) · TS-08 문서. 🟡 실기 재확인 = 오늘 저녁 헹굼→물털기 순서 · 그 전에 툴·TCP 두 이름 확인(비상정지 뒤)'))
EDIT.setdefault('ENV-05', {}).update(dict(note_add='🔎 17:55 실마리: 민범진 세션이 17:27 충돌 전후 실기 사용(dip 3회 → 충돌 → 복구·브링업 재시작) → 17:37~39 TCP 풀림 창과 재시작 시각 대조 — 민범진 PC 의 sodreal 브링업 시각을 확인(다른 PC 연결이 이름을 비우는지)'))
EDIT.setdefault('CELL-04', {}).update(dict(note_add='🟡 17:55 황인재 결정 대기: rig_f1·rig_f3·rig_weigh_* 도 시작 때 "낮으면 곧게 위로" 보호 필요(직전 프로세스가 수조 안에서 끝날 수 있음) → go_home_safely 를 cobot_common.motion 으로 올릴지'))
HISTORY128 = ['v17.8', '🚨사고', 'INT-F2', '9/22 17:27 실기 충돌(TS-08): 수조 안에서 HOME 관절 이동 → 그리퍼가 테이블 쓸고 비상정지 · 피해 없음 · PR #77(민범진) 승인·merge 17:55 — f2 시험대·abort 가 HOME 앞에 곧게 위로 · 자동 시험 444 · 실기 재확인 🟡 저녁', '황인재 9/22 17:55', 'H']



# ---------------------------------------------------------------- 9/22 17:58 F4 원인 분석 — 두 PC 동시 접속
EDIT.setdefault('ENV-05', {}).update(dict(note_add='🎯 17:58 F4 분석(원인 거의 확정): 황인재 V-25 16:57~17:45 실기 중에 민범진이 17:3x 다른 PC 에서 sodreal 접속 → ① 17:37~39 툴·TCP 빔 ② 17:39 황인재 명령에 로봇이 엉뚱한 좌표로(다른 PC 명령 실행) ③ 17:40:39 move_stop 무응답. 아침 11:1x = 박진용 rig_v03 다른 PC 접속과 겹침. 가설 "다른 PC 에서 sodreal 을 켜면 현재 툴·TCP 선택이 빈다" → 민범진 sodreal 시각으로 확정 대기. 🟡 규칙 제안 3개(선언 뒤 사용·접속 PC 1대 / 새 브링업은 두 이름 확인 / 펜던트 재선택 황인재) → 황인재 결정'))
EDIT.setdefault('V-25', {}).update(dict(note_add='⚠ 17:58: 17:33~17:38 컵 홈 C 놓기 어긋남 관찰은 민범진 접속과 겹친 시각일 수 있음 → cell.yaml 수정 보류 · 재확인은 9/23 아침 V-24 와 함께(로봇 확실히 빈 때)'))
EDIT.setdefault('CELL-04', {}).update(dict(note_add='17:58: F4 소유 시험대(rig_weigh_poses 등)에 go_home_safely 보호는 9/23 F4 가 넣음'))
HISTORY129 = ['v17.9', '원인', 'ENV-05', 'F4 9/22 17:58: 툴·TCP 풀림 2건 원인 = 다른 PC 의 sodreal 동시 접속(17:3x 민범진 · 11:1x 박진용)이 유력 — 접속이 넘어가며 선택이 비고 남의 명령이 실행됨 · 규칙 3개 제안(황인재 결정) · V-25 컵 홈 C 관찰 보류', '황인재 9/22 17:58', 'H']



# ---------------------------------------------------------------- 9/22 18:02 🔴 F4 시각 정정(로그 epoch→date) — 위 9/22 오후 F4 블록의 16:xx 는 전부 +47분으로 고쳐 넣었다
EDIT.setdefault('ENV-05', {}).update(dict(note_add='🔴 18:02 시각 정정(F4 로그 date 값 · 앞 기록의 16:xx 는 환산 오류라 고침): 황인재 V-25 **16:57~17:45** · 17:03:47·17:08:43 황인재 쪽 SAFE_STOP 2회(HOME 이동 거부) — 민범진 충돌 17:27 과 겹침 → **17:07:5x 황인재 리셋(set_robot_control 2 ×2)이 남의 비상정지를 푼 것일 수 있음(매우 위험)** · 17:37:49 놓기 정상(TCP 살아 있음) → **풀린 창 17:37:49~17:39:07**(민범진 복구 뒤 브링업 재시작 시각과 대조) → 17:39:07 엉뚱한 좌표 → Ctrl+C · 17:40:39 move_stop 무응답 · 17:45:31 --where z 422.98. 민범진에게 date 기준 ①sodreal ②dip 3회 ③충돌 ④재시작 시각 요청. 규칙 제안 ㉣ 비상정지 해제·리셋은 자기 세션 것만 추가(황인재 결정)'))
EDIT.setdefault('V-25', {}).update(dict(note_add='🔴 18:02 시각 정정: 컵 pick·홈 C 놓기 17:31~17:38(3회 OK · 폭 76.2/76.9/76.7) · 안전 정지 2회(17:03:47 · 17:08:43)는 "손으로 잘못 물린 그릇 탓" 으로 봤으나 민범진 충돌 17:27 과 겹쳐 재해석 필요 · 표는 F4 가 test_logs V-25 기록에 넣음'))
EDIT.setdefault('INT-F2', {}).update(dict(note_add='⚠ 18:02: 충돌 17:27 시각에 황인재 V-25 세션도 같은 컨트롤러 접속 중(두 PC 명령 섞임) → TS-08 원인("수조 안→HOME")은 민범진 date 시각으로 재확인 · PR #77 보호는 그대로 유효'))
HISTORY130 = ['v18.0', '🔴 정정', 'ENV-05, V-25, INT-F2', 'F4 9/22 18:02: 오후 시각 전부 정정(+47분) — 황인재 V-25 16:57~17:45 가 민범진 실기(17:27 충돌)와 겹침 · 황인재 SAFE_STOP 17:03·17:08 · 17:07:5x 리셋이 남의 비상정지 푼 셈일 수 있음 · TCP 풀린 창 17:37:49~17:39:07 · 규칙 ㉣ 제안', '황인재 9/22 18:02', 'H']



# ---------------------------------------------------------------- 9/22 20:03 🔴 민범진 PR #78 — 충돌 시각 17:07→17:27 정정 · 18:11 무게 영점 이동 · 폭 판정
EDIT.setdefault('INT-F2', {}).update(dict(note_add='🔴 20:03 정정(민범진 PR #78 · 로그 epoch): 충돌은 **17:27:10~17:27:18**(리모컨 시작→HOME 도착 8초) · 그리퍼 드라이버 사망 17:27:51 — 앞의 17:07 은 변환 착오. 황인재 세션이 쉬던 17:12~17:31 틈이라 명령이 섞인 건 아니고 원인은 "수조 안→HOME 관절 이동" 확정. 🚨 18:11 무게 −117.5 g(15:22 기준값 −12 → 105 g 영점 이동) → GRIP_FAIL 로 통합 막힘 → PR #78: 하한 미달이면 **그리퍼 폭으로 파지 재확인**(빈손만 GRIP_FAIL · 쥐고 있으면 경고+통과) + weigh 흐름/떨림 분리(📉 max_weigh_drift_g 20 🟡). PR #78 은 #77 브랜치 재사용으로 main 과 충돌 4파일 → 재푸시 대기'))
EDIT.setdefault('ENV-05', {}).update(dict(note_add='🔴 20:03 재해석(충돌 17:27 정정): 황인재 SAFE_STOP 17:03·17:08·리셋 17:07:5x 는 **자기 세션 것** — "남의 비상정지 푼 셈" 철회. 풀린 창 17:37:49~17:39:07 은 충돌 **10분 뒤** = 민범진 복구(비상정지 해제·서보 온·브링업 재시작) 직후로 보임. 17:31~17:37 황인재 컵 작업은 TCP 살아 있었음 → 민범진 첫 접속(17:2x)은 안 비웠고 **복구 절차 또는 재시작 접속**이 비운 것. 가설 2개: ⓐ 다른 PC 새 브링업 접속 ⓑ 비상정지 복구 절차 → 민범진 시각(①sodreal ②비상정지 해제·서보 온 ③재시작)으로 가른다'))
EDIT.setdefault('V-02', {}).update(dict(note_add='🚨 20:03: 18:11 실기(민범진) 빈 그릇 자리 −117.5 g — 15:22 기준값 −12 대비 **105 g 영점 이동**(툴·TCP 재선택 17:4x 가 사이에 있음 · 재는 21 s 안에도 −26 g 흐름). 🟡 황인재 결정: 자동 영점(실행 시작 때 빈손으로 저울 1회 · 40 s) vs 시연 아침 사람이 다시 재기. F4: 펜던트 재선택 뒤 툴 무게 값(1.440 kg) 확인'))
HISTORY131 = ['v18.1', '🔴 정정', 'INT-F2, ENV-05, V-02', '민범진 PR #78 9/22 20:03: 충돌 17:07→17:27 정정(황인재 리셋과 무관) · 풀린 창은 충돌 10분 뒤(복구 절차·재시작 의심) · 18:11 영점 105 g 이동 → 폭으로 파지 재확인·흐름/떨림 분리 · PR 은 충돌 4파일로 재푸시 요청 · 🟡 자동 영점 결정', '황인재 9/22 20:03', 'H']



# ---------------------------------------------------------------- 9/22 20:13 황인재 — 펜던트 Tool Weight·무게 값 그대로
EDIT.setdefault('V-02', {}).update(dict(note_add='✅ 20:13 황인재: 펜던트 재선택 뒤에도 Tool Weight 와 등록 무게 값(1.440 kg) 그대로 → 18:11 의 105 g 영점 이동은 **툴 등록 탓이 아님** → 힘센서 영점 자체의 흐름(시간·자세·케이블·비상정지 복구) 쪽. 자동 영점 결정 ④ 근거 강화'))
HISTORY132 = ['v18.2', '확인', 'V-02', '황인재 9/22 20:13: Tool Weight·무게 값 그대로 확인 — 105 g 영점 이동은 툴 등록 탓 아님(힘센서 영점 흐름)', '황인재 9/22 20:13', 'H']



# ---------------------------------------------------------------- 9/22 20:19 황인재 결정 E29·E30 — PR #79 merge(컵 벽 집기 · 컵도 무게 · 새 좌표 · rig_f1 문지기)
NEW.append(
 ('CELL-05', 'CELL-04', 'CELL-04', '티칭', '컵 좌표 재티칭 + 컵 벽 집기(그릇 방식 · E29) + E25 되돌림(컵도 무게·잔반 · E30) + rig_f1 문지기',
  'H', '진행', S('9/22 저녁'), 'cell.yaml(RET_C 파지점 · 홈 C 삽입점 · WEIGH.CUP · presets.CUP) · params flow.weigh_kinds [BOWL, CUP] · handling._grip_close 키 방식 · rig_f1 E26 문지기 — ✅ PR #79 merge 20:19',
  '새 컵 좌표로 pick → 홈 C place 실기 OK · presets.CUP 폭을 첫 pick 실측으로 교정 · WEIGH.CUP·WASTE.CUP·재파지·헹굼·팔레트 C 실기(INT-12b / V-24)',
  '황인재 9/22 19:0x 결정: ① 컵 옆면 고정 폭(E19)을 끄고 그릇처럼 테두리 벽을 위에서 집기(폭 판정 · 20 N) ② E25 되돌림 — 컵도 무게 측정·잔반 버리기. 🟡 실기: 9/22 저녁 첫 pick(0.3) 결과는 PR #79 코멘트 → 후속은 main 에서 새 브랜치로 PR. 남의 파일(handling.py 한석형 · flow 절 민범진) PR 멘션으로 알림'))
EASY['CELL-05'] = '컵을 옆에서 정해진 폭으로 잡던 방식을 버리고, 그릇처럼 컵 테두리 벽을 위에서 집어 "잡았는지" 를 폭으로 확인한다. 그래서 컵 집는 자리·홈에 넣는 자리를 새로 찍었고, 컵도 무게를 재고 잔반을 버리는 흐름으로 돌아간다'
H2018 = '황인재 9/22 20:19'
EDIT.setdefault('FLOW-05', {}).update(dict(note_add=H2018 + ': 🔄 **E30(E25 되돌림)** — flow.weigh_kinds [BOWL, CUP](PR #79 · 황인재가 민범진 절 수정 · 멘션). 컵 기준값은 V-02 컵 재측정 뒤 유효'))
EDIT.setdefault('V-02', {}).update(dict(note_add=H2018 + ': 🔄 E30 으로 **컵 기준값 재측정 필요**(WEIGH.CUP 새 자세 = 파지점 +100 · f2.empty_weight_g.CUP 🟡 120 임시) → 9/23 아침'))
EDIT.setdefault('V-07', {}).update(dict(note_add=H2018 + ': 🔄 E30 — 컵도 잔반 버리기(WASTE.CUP = 그릇 잔반통 자리 · J6 0 · 한쪽에 매달리면 180) 실기 확인 필요'))
EDIT.setdefault('INT-12b', {}).update(dict(note_add=H2018 + ': 🔄 E29·E30 — 컵 통합은 PR #79(main a037abb) 뒤 새 방식으로(벽 집기 · 무게 포함). 오늘 밤 민범진 컵 통합 전에 황인재 첫 pick 실기 결과 확인'))
EDIT.setdefault('CELL-04', {}).update(dict(note_add=H2018 + ': 홈 C 놓기 어긋남(17:33~17:38 관찰)은 CELL-05 새 삽입점 티칭으로 대체 — 🟡 실기 확인 중'))
EDIT.setdefault('F1-02', {}).update(dict(note_add=H2018 + ': handling._grip_close 가 종류가 아니라 프리셋 키(grip_target_mm)로 고정 폭/폭 판정을 고른다(PR #79 · 황인재 수정 · 한석형 확인 요청)'))
HISTORY133 = ['v18.3', '🔄 결정', 'CELL-05, FLOW-05, V-02, V-07, INT-12b, CELL-04, F1-02', '황인재 9/22 19:0x E29(컵 벽 집기 · E19 끔) · E30(E25 되돌림 · 컵도 무게) → PR #79 merge 20:19(444 passed · 실기 🟡 첫 pick 진행 중) · 결정기록·IRD·SDD·BR-SR·리마인드·AGENTS 반영', '황인재 9/22 20:19', 'H']



# ---------------------------------------------------------------- 9/22 20:23 PR #78 merge(재푸시 · 충돌 해소)
EDIT.setdefault('INT-F2', {}).update(dict(note_add='✅ 20:23 PR #78 merge(민범진 · 충돌 해소 뒤): sense.weigh — 잔반 하한 미달이면 **그리퍼 폭으로 파지 재확인**(빈손만 GRIP_FAIL · 쥐고 있으면 "기준값 낡음" 경고+통과 · 컵은 E19 키 없으면 폭 판정) · weigh 흐름/떨림 분리(🔗 케이블 = 떨림 · 📉 흐름 > max_weigh_drift_g 20 경고) · TS-08 17:27 정정. 448 passed · 실기 🟡 INT-12b. 🟡 남음: preflight 케이블 확인도 떨림 기준으로 · + 방향 영점 · 세 시각'))
HISTORY134 = ['v18.4', 'PR', 'INT-F2', 'PR #78(민범진) 승인·merge 20:23: 폭으로 파지 재확인 · 무게 흐름/떨림 분리 · TS-08 17:27 정정 — 448 passed · 실기 🟡 INT-12b', '황인재 9/22 20:23', 'H']



# ---------------------------------------------------------------- 9/22 20:26 PR #81 merge · 황인재 결정(F4 창 20:3x): 자동 영점 채택(E31) · 규칙 ①~④ 미채택(E32)
NEW.append(
 ('ZERO-01', 'F2-01', 'F2-01', '개발', '자동 영점 — 실행 시작 때 빈손으로 WEIGH 자세 1회 → 그날의 힘센서 0 (E31)',
  'M', '시작 전', S('9/23 오전'), 'f2(sense/flow) 시작 단계 + 단위 시험 · PR', '시작 때 빈손 영점 1회(약 40 s) · 그 뒤 잔반 판정이 그날 영점 기준 · 단위 시험 통과 · 🟡 실기 1회(9/23)',
  '황인재 9/22 20:3x 채택(F4 창) · PM 창 20:28 확인(민범진 제안 · 무게 측정에서 중요하면 한다). 근거: 18:11 빈 그릇 자리 −117.5 g(기준값 −12 → 105 g 이동) · Tool Weight 그대로 → 영점 흐름. 동결 9/23 저녁 안에'))
EASY['ZERO-01'] = '주방 저울의 0 맞춤처럼, 한 바퀴를 시작할 때마다 로봇이 빈손으로 저울 자세에 한 번 들러 그날의 0 을 스스로 잡는다 — 오후에 맞춘 0 이 저녁에 밀려 잔반 판정이 틀리는 것을 막는다'
H2030 = '황인재 9/22 20:26'
EDIT.setdefault('CELL-05', {}).update(dict(prog='0.8', note_add=H2030 + ': ✅ 첫 벽 집기 실기 20:18 — 집기(벽 1.82 mm)·홈 C 삽입 정확히 맞음 → PR #81 merge(폭 1.8 · WASTE.CUP J6 180). 진행 중: rig_f2 empty CUP(새 WEIGH.CUP 기준값) → 96 g 넣고 loop CUP · V-25 기록 PR 은 그 뒤'))
EDIT.setdefault('V-02', {}).update(dict(note_add=H2030 + ': 컵 기준값 재측정 **진행 중**(황인재 · WEIGH.CUP 새 자세)'))
EDIT.setdefault('V-07', {}).update(dict(note_add=H2030 + ': 컵 잔반 버리기 loop(96 g) 실기 진행 중(황인재) · WASTE.CUP J6 180 첫 확인'))
EDIT.setdefault('ENV-05', {}).update(dict(note_add=H2030 + ': 규칙 제안 ①~④ **채택 안 함**(황인재 · F4 창 · E32) — 기존 🚨 실기 시작 두 이름 확인(E26) · 🔌 실기 끝 그대로. 황인재 PM 창 20:28: 두 PC 동시 접속 문제는 **팀 회의로 함께 전파함**'))
HISTORY135 = ['v18.5', '결정·PR', 'ZERO-01, CELL-05, V-02, V-07, ENV-05', '황인재 9/22 20:3x: 자동 영점 채택(E31 · 민범진 · 9/23) · 규칙 ①~④ 미채택(E32) · PR #81 merge 20:26(컵 벽 폭 1.8 · WASTE.CUP 180 · 실기 정확히 맞음)', '황인재 9/22 20:26', 'H']



# ---------------------------------------------------------------- 9/22 20:37 F4 — 컵 E30 흐름 실기(20:31~20:35) 결과
F2035 = 'F4 9/22 20:37(실기 20:31~20:35 · date 값)'
EDIT.setdefault('V-07', {}).update(dict(note_add=F2035 + ': ✅ **컵 잔반 버리기 실기 통과** — rig_f2 loop CUP(96 g · 0.3 · max-rounds 2) 3회: 1회차 98.7 g − 기준 −20 → 잔반 118.7 ≥ 50 → HOLD(12.4→12.0) → WASTE(J6 180) 기울기 −90° · 4회 → 재측정 24.1 → 잔반 44.1 → 1회 만에 통과 · 2회차 16.8 · 3회차 −3.8 통과. 자세(뒤쪽 이동·기울임·복귀) 문제없음(황인재). 🟡 민범진 참고: ① 털고 온 직후 재측정 44 g 은 가라앉는 중 값(임계 50 과 6 g 차) → 불필요한 2차 털기 가능 · 털기 뒤 settle 늘리거나 자동 영점(E31)과 같이 ② HOLD 35 N 컵 벽 폭 12.4→12.0→11.5(0.9 mm) — slip_tol 1.0 과 0.1 차 · 눌림/미끄러짐 확인 ③ WASTE.CUP J6 180 입 방향·떨어짐 확인 중'))
EDIT.setdefault('V-02', {}).update(dict(note_add=F2035 + ': 빈 컵 기준값 **−20 g**(3회 · 폭 20.2 · 3회차 위로 흐름) → 브랜치 injae/20260922-V-02-cup-baseline 으로 PR 예정. 📉 도착 직후 21 s 창 −38 g 흐름 경고(#78) 정상 작동'))
EDIT.setdefault('CELL-05', {}).update(dict(prog='0.9', note_add=F2035 + ': WEIGH.CUP·WASTE.CUP(J6 180) 실기 OK — 컵 벽 집기 흐름(집기→무게→잔반 버리기→재측정) 1바퀴 통과. 남은 것: 재파지·헹굼·팔레트 C(INT-12b) · V-25 기록 PR'))
EDIT.setdefault('INT-12b', {}).update(dict(note_add=F2035 + ': 컵 무게·잔반 버리기까지 실기 OK(황인재) → 민범진 컵 통합은 이제 가능(main #78·#79·#81 · 기준값 PR 곧). 🟡 slip_tol 여유 0.1 · 재측정 settle 참고'))
HISTORY136 = ['v18.6', '✅ 실기', 'V-07, V-02, CELL-05, INT-12b', 'F4 9/22 20:37: 컵 E30 흐름 실기 3회 통과(잔반 118.7 → 털기 → 44.1 · 자세 OK) · 빈 컵 기준값 −20(PR 예정) · 🟡 민범진 참고 3(settle · slip_tol · 입 방향)', '황인재 9/22 20:37', 'H']



# ---------------------------------------------------------------- 9/22 20:40 PR #82 merge — 빈 컵 기준값 −20
EDIT.setdefault('V-02', {}).update(dict(note_add='✅ 20:40 PR #82 merge(황인재): f2.empty_weight_g.CUP 120(임시) → **−20**(20:26~20:28 3회 · 중앙값 · 민범진 절 멘션). 🟡 9/23 아침 V-02 컵 10회·추 재확인'))
HISTORY137 = ['v18.7', 'PR', 'V-02', 'PR #82 merge 20:40: 빈 컵 기준값 −20(실측 3회) · presets.CUP 주석 시각 20:18 — 448 passed · 🟡 9/23 10회 재확인', '황인재 9/22 20:40', 'H']



# ---------------------------------------------------------------- 9/22 20:57 황인재 결정 E33 — 재분담: 민범진 에이전트 토큰 소진 → F4 총괄 통합 · 한석형·박진용 새 기능
H2055 = '황인재 9/22 20:57(E33)'
NEW.append(
 ('NEW-01a', 'NEW-01', 'NEW-01', '개발', '새 기능 ① 격리 이송 — 잔반 과다·실패 용기를 격리 구역으로 옮기는 동작(그릇·컵) + 격리 구역 좌표',
  'S', '시작 전', S('9/23 오전', '9/23 오후'), 'cell.yaml 격리 구역 좌표 · f1 격리 놓기 함수 · rig 실기 3회 · PR',
  '격리 구역 좌표 티칭 · 그릇·컵 각 3회 놓기 실기 OK · flow 실패 정책(잔반 초과 지속 → 격리 · IRD)에서 부르는 자리 확인 · 🚨 9/23 저녁 동결 전 PR',
  H2055 + ': 한석형 새 기능 ①. 격리는 IRD 실패 정책에 이미 있는 단계 — 좌표·동작을 구현한다. flow 연결은 F4(총괄 통합)와 맞춘다'))
NEW.append(
 ('NEW-01b', 'NEW-01a', 'NEW-01', '개발', '새 기능 ② 거품 펌프 — 솔·수세미 근처에 펌프를 두고 일정 사용 횟수마다 펌프질 동작(소모품 카운트 연동)',
  'S', '시작 전', S('9/23 오전', '9/23 오후'), '펌프 위치 cell.yaml · 펌프질 동작 함수 · 사용 횟수 카운트 → 펌프질 · 실기 3회 · PR',
  '펌프질 동작 실기 3회 · 횟수 카운트가 params flow.consumables(soap_max_dips 등)와 연동 · 동결 전 PR',
  H2055 + ': 한석형 새 기능 ②. 🟡 카운트를 어디서 세는지(flow vs f3 soap) F4 와 맞춘다'))
NEW.append(
 ('NEW-02a', 'NEW-01b', 'NEW-01', '개발', '새 기능 ③ 넛지 재개 ① — 툴(수세미·솔) 파지 실패 → "툴 없음" 판단 → 사람 호출 → 사람이 채우고 로봇을 툭 치면(힘센서 넛지) 재개',
  'P', '시작 전', S('9/23 오전', '9/23 오후'), 'cobot_common force 넛지 감지 함수 · f1.tool TOOL_FAIL → 대기 → 넛지 → 재개 흐름 · 실기 3회 · PR',
  '넛지 임계(힘 · 지속 시간) params · 오검출 0/3 · 대기 중 로봇 정지 상태 유지 · 동결 전 PR',
  H2055 + ': 박진용 새 기능 ①. 🚨 접촉 감지는 힘 상한·타임아웃 규칙(AGENTS §3-2) · 대기 상태와 flow 정책(PAUSED/재개)의 관계는 F4 와 맞춘다'))
NEW.append(
 ('NEW-02b', 'NEW-02a', 'NEW-01', '개발', '새 기능 ④ 넛지 재개 ② — 케이블 꼬임·장력으로 무게 떨림이 커지면 사람 호출 → 케이블 풀고 툭 치면 재측정·재개',
  'P', '시작 전', S('9/23 오전', '9/23 오후'), '떨림(🔗 jitter) 경고 → 대기 → 넛지 → 재측정 흐름 · 실기 · PR',
  'weigh 의 🔗 떨림 경고(f2.limits.max_weigh_spread_g)를 신호로 · 넛지 뒤 재측정 정상 · 오검출 없음',
  H2055 + ': 박진용 새 기능 ②. PR #78 의 흐름/떨림 분리 결과(케이블 = 떨림)를 신호로 쓴다 · 넛지 감지 함수는 ①과 공용'))
EASY['NEW-01a'] = '잔반이 계속 남거나 실패한 그릇·컵을 따로 모아 두는 격리 자리로 로봇이 옮겨 놓는 동작을 만든다'
EASY['NEW-01b'] = '솔·수세미 옆에 거품 펌프를 두고, 몇 번 쓸 때마다 로봇이 펌프를 눌러 거품을 보충하는 동작을 만든다'
EASY['NEW-02a'] = '수세미·솔을 집으려다 못 집으면 "없다" 고 보고 사람을 부른 뒤, 사람이 채워 놓고 로봇을 톡 치면 힘센서가 그것을 알아채 이어서 일한다'
EASY['NEW-02b'] = '케이블이 꼬여 무게가 심하게 떨리면 사람을 불러 풀게 하고, 톡 치면 다시 재서 이어서 일한다'
EDIT.update({
 'NEW-01':  dict(owner='S', status='진행 중', prog='0.2', note_add=H2055 + ': 내용 확정 — NEW-01a 격리 이송 · NEW-01b 거품 펌프(한석형) + 발표용 영상(DOC-03). 나머지 1명 = 박진용(NEW-02a/b 넛지)'),
 'INT-F2':  dict(owner='H(M)', note_add=H2055 + ': **F4(황인재) 총괄 통합으로 이관** — 민범진 에이전트 토큰 소진. 민범진은 코드 없이 실기 실행·기록 보조(🟡). 그릇 한 바퀴 실기는 9/23 아침 첫 순서'),
 'INT-F3':  dict(owner='H(P)', note_add=H2055 + ': 박진용은 새 기능(NEW-02a/b)으로 → 남은 통합은 F4 총괄. 박진용은 F3 함수 질문 대응'),
 'INT-ALL': dict(owner='H', status='시작 전', note_add=H2055 + ': 주인 확정 = **황인재(F4 총괄 통합)**'),
 'INT-3a':  dict(owner='H(전원)', note_add=H2055 + ': 주도 M → H(총괄 통합)'),
 'INT-3b':  dict(owner='H(전원)', note_add=H2055 + ': 주도 M → H'),
 'INT-4a':  dict(owner='H(전원)', note_add=H2055 + ': 주도 M → H'),
 'INT-4b':  dict(task='INT-4b 새 기능 시연 시나리오 — 툴 없음→사람 호출→넛지 재개(NEW-02a) · 케이블 장력→넛지 재개(NEW-02b) · 잔반 과다→격리(NEW-01a) · 거품 펌프(NEW-01b) 각 1회 실기', owner='S,P(H)', note_add=H2055 + ': "실패 주입 4종" 을 새 기능 시연으로 재정의(E28 정상 흐름 + 새 기능 4개). 팔레트 걸림·빈 구역 주입은 뺀다'),
 'FLOW-04': dict(owner='H(S)', note_add=H2055 + ': M → H(총괄 통합)'),
 'REH-02':  dict(owner='전원(H 실행)', note_add=H2055 + ': 실행 M → H'),
 'ZERO-01': dict(owner='H', note_add=H2055 + ': 구현 M → **H(F4)** — f2·flow·weigh 파일 임시 주인 = 황인재'),
 'INT-12a': dict(task='INT-12a F1+F2 — 집기→무게→잔반 버리기 5회 · 그릇·컵(🔄 E30) · 시험대 rig_int12(flow_node 없이)', owner='H(M)', prog='0.3', note_add=H2055 + ': 주도 M → H · 컵은 20:31 3회 통과(V-07) · 그릇 5회 남음'),
 'INT-12b': dict(owner='H(M)', note_add=H2055 + ': 주도 M → H · 컵은 새 방식(E29·E30)'),
 'UT-F2':   dict(status='완료', prog='1.0', note_add=H2055 + ': 9/22 실기 rig_f2 dip·shake·loop 각 3회 이상(V-07 · 20:31 컵 · TS-08 세션)으로 갈음 — 정리'),
 'F2-01':   dict(status='완료', prog='1.0', note_add=H2055 + ': 잔여 0.1 은 문서 — 9/22 실기 통과(그릇 12:20 · 컵 20:31)로 마감. 이후 수정은 F4(임시 주인)'),
 'F2-02':   dict(status='완료', prog='1.0', note_add=H2055 + ': 잔여 0.1 은 문서 — 9/22 dip 3회·RINSE 실기(#71)로 마감'),
 'INF-02c': dict(status='완료', prog='1.0', note_add=H2055 + ': weigh.py 는 #68·#73·#78 로 완성 — 마감'),
 'V-07':    dict(owner='H(M)', prog='0.8', note_add=H2055 + ': 컵 잔반 버리기 3회 통과(20:31) · 그릇 12:20 저속 1회 → 남은 것 = 그릇 통상 속도·물 털기 그릇/컵 3회 — INT-12b 에서 같이'),
 'CELL-03': dict(status='완료', prog='1.0', note_add=H2055 + ': 잔반통·수조 배치는 실기가 도는 상태 · 잔반 대용품 96 g 사용 중 — 마감'),
 'V-24':    dict(owner='H(P)'),
 'INT-4':   dict(owner='H'),
 'DOC-03':  dict(owner='S(H)', status='진행 중', prog='0.2', note_add=H2055 + ': 발표용 영상 제작 = **한석형**(진행 중) · 편집 최종 확인 H'),
})
HISTORY138 = ['v18.8', '🔄 재분담', 'NEW-01a/b, NEW-02a/b, INT-F2, INT-F3, INT-ALL, INT-3a/3b/4a/4b, FLOW-04, REH-02, ZERO-01, INT-12a/b, UT-F2, F2-01/02, INF-02c, V-07, CELL-03, V-24, INT-4, DOC-03', '황인재 9/22 20:57 E33: 민범진 에이전트 토큰 소진 → F4 총괄 통합(f2·flow 임시 주인) · 한석형 새 기능 격리 이송·거품 펌프 + 영상 · 박진용 넛지 재개 2종 · INT-4b 를 새 기능 시연으로 재정의 · 0.9 행 4개·CELL-03 마감', '황인재 9/22 20:57', 'H']



# ---------------------------------------------------------------- 9/22 21:04 황인재 결정 E34 — 9/23 통합 축소(혼자 · 필수 검증만) · HMI 는 추석
H2110 = '황인재 9/22 21:04(E34 통합 축소)'
NEW.append(
 ('INT-ONE-B', 'INT-ALL', 'INT-ALL', '통합', 'INT-ONE-B 그릇 1개 한 바퀴 — rig_flow_once(실제 f1/f2/f3 · mock 없음 · 0.3): 빈 그릇 1회 완주 → 잔반 96 g 넣고 1회(잔반 버리기 포함)',
  'H', '시작 전', S('9/23 오전'), '완주 기록(단계별 시간·코드) · 막힌 단계 수정 PR', '2회 완주(빈 그릇 · 잔반) · 실패 정책 없이 정상 흐름만(E28)',
  H2110 + ': INT-F2·INT-F3·INT-ALL·INT-12a/b 를 이 한 줄로 갈음 — 09:30~11:30 로봇'))
NEW.append(
 ('INT-ONE-C', 'INT-ONE-B', 'INT-ALL', '통합', 'INT-ONE-C 컵 1개 한 바퀴 — rig_flow_once(실제 f1/f2/f3 · 0.3 · E29 벽 집기 · E30 무게): 빈 컵 1회 → 잔반 1회',
  'H', '시작 전', S('9/23 오후'), '완주 기록 · 수정 PR', '2회 완주',
  H2110 + ': INT-3b 대체 — 13:30~15:00 로봇'))
EASY['INT-ONE-B'] = '그릇 하나를 집어서 무게 재고 잔반 버리고 닦고 헹궈서 팔레트에 넣기까지, 진짜 기능 함수로 처음부터 끝까지 두 번 돌려 본다'
EASY['INT-ONE-C'] = '컵 하나로 같은 한 바퀴를 두 번 돌려 본다'
for _t in ('INT-F2', 'INT-F3', 'INT-ALL', 'INT-12a', 'INT-12b', 'INT-3a', 'INT-3b', 'FLOW-04'):
    EDIT.setdefault(_t, {}).update(dict(status='취소', note_add=H2110 + ': **대체** — INT-ONE-B/C(한 바퀴 실기) + INT-4a(시연 실행)로 갈음. 별도 검증 안 함'))
EDIT.update({
 'INT-4a':  dict(task='INT-4a 시연 실행 — flow_node(PC-A) 시작 1회 → 그릇 2·컵 2 연속(E28 정상 흐름) · 시작은 서비스 호출(HMI 는 추석) · 녹화(영상 원본) · 사이클 타임 1회', owner='H(S 촬영)', note_add=H2110 + ': 15:00~17:00 로봇 · 이 1회 완주 + 녹화가 9/23 의 통과선. FLOW-04·INT-3a/3b·INT-4c 를 여기서 한 번에'),
 'INT-4c':  dict(task='INT-4c 사이클 타임 1회 — INT-4a 녹화에서 읽는다(성공률·잔반 검출률 표는 1회 값)', owner='H', note_add=H2110 + ': ×3 → 1회'),
 'INT-4d':  dict(owner='H(S 촬영)', note_add=H2110 + ': INT-4a 와 같은 시간에 원본 녹화 · 저녁 v1.0-demo 태그 · 동결'),
 'INT-4':   dict(status='보류', note_add=H2110 + ': **HMI 는 추석(9/24~28) 집에서** — 9/29 아침 REH-02 에서 실기 연결(시작 버튼 = /flow/start 서비스 그대로)'),
 'V-24':    dict(status='보류', note_add=H2110 + ': 시간 남으면 9/23 17시 예비 슬롯 · 아니면 추석 후(시연은 정상 흐름만 · 정지는 Ctrl+C V-26 5/5 · 펜던트)'),
 'ZERO-01': dict(note_add=H2110 + ': 🟡 조건부 — 9/23 17시 예비 슬롯에 시간 남으면. 못 하면 **대안 = 시연 아침(REH-02) 수동 영점**(빈 그릇·컵 기준값 재측정) 체크리스트 · #78 폭 재확인이 놓침 오판은 막는다'),
 'REH-02':  dict(note_add=H2110 + ': 체크리스트 — ① 두 이름 확인 ② 빈 그릇·컵 기준값 재측정(수동 영점 · ZERO-01 못 했으면 필수) ③ HMI 시작 버튼 → /flow/start 연결 확인 ④ 시연 1회 완주'),
 'NEW-01a': dict(note_add=H2110 + ': 로봇 슬롯 9/23 11:30~12:30(NEW-01b 와 같이)'),
 'NEW-01b': dict(note_add=H2110 + ': 로봇 슬롯 9/23 11:30~12:30'),
 'NEW-02a': dict(note_add=H2110 + ': 로봇 슬롯 9/23 12:30~13:30(NEW-02b 와 같이)'),
 'NEW-02b': dict(note_add=H2110 + ': 로봇 슬롯 9/23 12:30~13:30'),
 'V-07':    dict(status='완료', prog='1.0', note_add=H2110 + ': 남은 3회는 INT-ONE-B/C 완주에 포함 — 마감'),
})
HISTORY139 = ['v18.9', '🔄 축소', 'INT-ONE-B/C, INT-4a/4c/4d, INT-F2/F3/ALL, INT-12a/b, INT-3a/3b, FLOW-04, INT-4, V-24, ZERO-01, REH-02, NEW-01a/b, NEW-02a/b, V-07', '황인재 9/22 21:04 E34: 9/23 은 혼자 통합 → 필수 검증만 — 그릇 1개 한 바퀴 2회 · 컵 1개 한 바퀴 2회 · flow_node 시작 1회로 그릇2·컵2 연속 1회+녹화. 8행 취소(대체) · HMI 추석 · V-24 보류 · ZERO-01 조건부(대안 수동 영점) · 새 기능 로봇 슬롯 11:30~13:30', '황인재 9/22 21:04', 'H']



# ---------------------------------------------------------------- 9/22 21:07 황인재 — 보류 없이 9/23 에 되는 것은 전부 일정표에(우선순위 순)
H2110b = '황인재 9/22 21:07'
for _t in ('INT-F2', 'INT-F3', 'INT-ALL', 'INT-12a', 'INT-12b', 'INT-3a', 'INT-3b', 'FLOW-04'):
    EDIT.setdefault(_t, {}).update(dict(status='대체'))
EDIT.update({
 'ZERO-01': dict(status='시작 전', slots=S('9/23 오전', '9/23 오후'), note_add=H2110b + ': 보류 아님 — **9/23 4순위**. 코드는 11:30~13:30(로봇이 한석형·박진용에게 있는 동안 F4 에이전트) · 실기 17:00~ 예비 슬롯. 못 끝내면 REH-02 수동 영점'),
 'V-24':    dict(status='진행 중', slots=S('9/23 오후'), note_add=H2110b + ': 보류 아님 — **9/23 5순위**. 코드는 11:30~13:30 · 실기(②③④) 17:30~ 예비 슬롯'),
 'INT-4':   dict(status='진행 중', slots=S('9/23 저녁'), note_add=H2110b + ': 보류 아님 — **9/23 6순위(저녁)**: 시작·일시 정지·재개·중단을 HMI 로 1회. 시간 안 되면 추석에 이어서 → 9/29 아침 REH-02 연결'),
 'INT-4a':  dict(note_add=H2110b + ': 9/23 우선순위 — ① INT-ONE-B ② INT-ONE-C ③ INT-4a(시연 실행·녹화) ④ ZERO-01 ⑤ V-24 ⑥ INT-4(HMI) ⑦ 새 기능 flow 연결 실기(17:00 예비의 첫 순서는 ⑦ · 그 뒤 ④⑤⑥)'),
})
HISTORY140 = ['v19.0', '🔄 순서', 'ZERO-01, V-24, INT-4, INT-4a, 대체 8행', '황인재 9/22 21:07: 보류 없이 9/23 에 되는 것은 전부 — 우선순위 ①그릇 한 바퀴 ②컵 한 바퀴 ③시연 실행·녹화 ⑦새 기능 flow 연결 ④자동 영점 ⑤V-24 ⑥HMI(저녁 · 못 하면 추석) · 대체 8행은 취소 → 대체 표기', '황인재 9/22 21:07', 'H']



# ---------------------------------------------------------------- 9/22 21:09 황인재 — 한석형·박진용은 9/23 오후까지 개발 · 저녁은 구현된 동작까지 통합
H2113 = '황인재 9/22 21:09'
EDIT.update({
 'INT-4b':  dict(slots=S('9/23 저녁'), owner='S,P(H)', status='시작 전', note_add=H2113 + ': **9/23 저녁** — 한석형·박진용은 오후까지만 개발하고 저녁에 **구현된 동작까지만** 시연 흐름에 통합(황인재 총괄과 같이). 못 끝낸 기능은 넣지 않는다(동결)'),
 'NEW-01a': dict(note_add=H2113 + ': 개발은 9/23 오후까지 · 저녁 = 통합(INT-4b)'),
 'NEW-01b': dict(note_add=H2113 + ': 개발은 9/23 오후까지 · 저녁 = 통합(INT-4b)'),
 'NEW-02a': dict(note_add=H2113 + ': 개발은 9/23 오후까지 · 저녁 = 통합(INT-4b)'),
 'NEW-02b': dict(note_add=H2113 + ': 개발은 9/23 오후까지 · 저녁 = 통합(INT-4b)'),
 'INT-4a':  dict(note_add=H2113 + ': 17시 예비의 ⑦(새 기능 flow 연결)은 **저녁 INT-4b** 로 — 한석형·박진용이 직접 · 황인재는 17시에 ④ZERO-01 ⑤V-24 부터'),
})
HISTORY141 = ['v19.1', '일정', 'INT-4b, NEW-01a/b, NEW-02a/b, INT-4a', '황인재 9/22 21:09: 한석형·박진용 새 기능 개발은 9/23 오후까지 · 저녁 = 구현된 동작까지만 통합(INT-4b · 황인재 총괄) · 17시 예비는 ZERO-01·V-24 부터', '황인재 9/22 21:09', 'H']



# ---------------------------------------------------------------- 9/22 21:14 PR #83 merge(박진용 F3) — soap 위치 판정 · rig 가 F1 제품 함수 호출 · 실기 재검증
P2120 = 'PR #83 9/22 21:14'
EDIT.update({
 'INT-F3':   dict(note_add=P2120 + ': ✅ 박진용 실기 — 그릇 pick→place→soap→wipe_bowl(나선)→tool RETURN→재파지 성공 · 컵 pick→place→soap→wipe_cup 성공. soap 은 잡은 위치(X)로 수세미/솔 판정 · wipe 는 호출 자리에서 바로 하강. F3 rig 가 f1_handling 제품 함수를 직접 부름(E29·E30 뒤 F1 변경에 자동 추종). ⚠ rack_place(RACK_B1) TIMEOUT 28.5/30 mm'),
 'INT-ONE-B': dict(note_add=P2120 + ': 🟡 **첫 확인 항목** — 박진용 실기에서 rack_place(RACK_B1) 이 삽입 28.5/30 mm 에서 10 s TIMEOUT(거의 다 들어감) → insert_approach_mm/타임아웃 튜닝(F4)'),
 'F1-03':    dict(note_add=P2120 + ': 🟡 황인재 결정 2건(박진용 요청) — ① tool(PICK) 이 잡자마자 tool_clear_mm 100 상승 → soap 은 잡은 자리에서 비틀기 원함(지금은 공중에서 비틀고 성공은 함 · NEW-01b 거품 펌프와 함께 볼 것) ② tool(RETURN) 고정 return 자세+contact_down 방식 vs 갔던 길 역순 — 지금 방식 V-08 10/10 이라 바꿀 이유가 약함'),
 'F1-04':    dict(note_add=P2120 + ': ⚠ rack_place(RACK_B1) TIMEOUT(28.5/30 mm · 10 s) — 9/23 INT-ONE-B 에서 F4 가 튜닝'),
 'CELL-04':  dict(note_add=P2120 + ': cell.yaml HOME 에 posx_x_mm 367.48 · posx_y_mm 8.09 키 추가(박진용 · 값 변경 없음 · E17 유지)'),
})
HISTORY142 = ['v19.2', 'PR', 'INT-F3, INT-ONE-B, F1-03, F1-04, CELL-04', 'PR #83(박진용) 승인·merge 21:14: soap 수세미/솔 위치 판정 · wipe 호출 자리에서 바로 · F3 rig 가 F1 제품 함수 호출 · 실기 그릇·컵 soap→wipe 통과 · ⚠ rack_place TIMEOUT → 9/23 첫 확인 · 🟡 회전 속도 검사 삭제(되살리기 요청) · F1 요청 2건 황인재 결정', '황인재 9/22 21:14', 'H']



# ---------------------------------------------------------------- 9/22 21:18 PR #84 merge — V-25 기록
EDIT.update({
 'V-25':    dict(status='완료', prog='1.0', note_add='✅ 21:18 PR #84 merge: V-25 기록(16:57~21:3x · date 값) — move_to 3/3 · place · 그릇 pick 2.32 · 컵 E29/E30 pick 1.82~1.92 · 홈 C +5 · 재파지 1.42 · 기준값 −20 · 잔반 버리기 통과 · 동시 사용 사고 시간표. 🟡 남은 것 → INT-ONE-C 전: RACK_C_VIA·C1/C2 재티칭(옆 파지 기준) · RINSE.CUP z 60 첫 확인'),
 'INT-ONE-C': dict(note_add='21:18(V-25 기록): 시작 전에 **RACK_C_VIA·RACK_C1/C2 재티칭**(벽 집기 손목 자세) · RINSE.CUP 깊이 z 60(계산값) 첫 확인 · 홈 C z +5(117.47)·재파지 기준 1.7 이 main 에 없으면 PR'),
})
HISTORY143 = ['v19.3', 'PR', 'V-25, INT-ONE-C', 'PR #84 merge 21:18: V-25 실기 기록(컵 E29/E30 포함) — V-25 완료 · 컵 한 바퀴 전 RACK_C 재티칭·RINSE.CUP z 60 확인', '황인재 9/22 21:18', 'H']



# ---------------------------------------------------------------- 9/22 21:24 황인재 — 일정표 정리: 안 해도 되는 행 삭제 · 끝난 행 완료 처리
H2125 = '황인재 9/22 21:24(정리)'
DELETE = ['INT-ALL', 'INT-3a', 'INT-3b', 'INT-12a', 'INT-12b', 'INT-F2', 'INT-F3', 'FLOW-04',   # E34 로 INT-ONE-B/C·INT-4a 가 대신함
          'NEW-01',                                                                            # 자리표시 행 — NEW-01a/b·NEW-02a/b 로 구체화됨
          'INT-13', 'V-14', 'V-06',                                                             # 한 바퀴 실기(INT-ONE)·#83 실기로 갈음
          'V-04', 'F1-05',                                                                      # 안착 탐색(예외 처리) — E28 시연 범위 밖
          'F4-04', 'F4-05', 'CR-01']                                                            # 시연에 불필요(기록 API · KPI 스크립트 · 코드리뷰 회의)
EDIT.update({
 'F1-01': dict(status='완료', prog='1.0', note_add=H2125 + ': V-25(#84) move_to 3/3 · place 실기 OK — 완료'),
 'F1-02': dict(status='완료', prog='1.0', note_add=H2125 + ': pick 실기 — 그릇 2.32(#74 · V-25) · 컵 벽 집기 1.82~1.92(#79 · #81) — 완료. 이후 수정은 F4'),
 'F1-04': dict(status='진행', prog='0.9', owner='H(S)', note_add=H2125 + ': rack_place 실기 동작함 · ⚠ RACK_B1 TIMEOUT(28.5/30 mm · #83) 튜닝 + RACK_C 재티칭이 남음 → 9/23 INT-ONE-B/C'),
 'F3-02': dict(status='완료', prog='1.0', note_add=H2125 + ': #83 실기 soap→wipe_bowl(나선) 통과 — 완료'),
 'F3-03': dict(status='완료', prog='1.0', note_add=H2125 + ': #83 실기 soap→wipe_cup 통과 — 완료(🟡 회전 속도 검사 되살리기는 작은 PR)'),
 'V-19':  dict(status='완료', prog='1.0', note_add=H2125 + ': 오늘 실기에서 모든 자리(RET·WEIGH·WASTE·홈·툴·RINSE·RACK)에 티칭 경로대로 도달 — 완료'),
 'V-15':  dict(status='완료', prog='1.0', note_add=H2125 + ': 재파지 폭 실기 — 컵 1.42(V-25) · 그릇 재파지(#83) — 완료'),
 'UT-F1': dict(status='완료', prog='1.0', note_add=H2125 + ': rig_f1 실기 반복(pick·place·tool·rack_place 각 3회 이상 · V-08 10/10 · V-25)로 갈음'),
 'UT-F3': dict(status='완료', prog='1.0', note_add=H2125 + ': #72·#83 실기 반복으로 갈음'),
 'UT-F4': dict(note_add=H2125 + ': HMI 는 추석 — TC-11 도 그때'),
 'NOTE-02': dict(note_add=H2125 + ': HMI 화면 캡처는 지금 있는 운영 화면(#66)으로 제출 가능 · 추석에 갱신'),
})
HISTORY144 = ['v19.4', '🧹 정리', 'DELETE 17행 · F1-01/02, F3-02/03, V-19, V-15, UT-F1/F3 완료 · F1-04', '황인재 9/22 21:24: 안 해도 되는 행 17개 삭제(대체 8 · NEW-01 · INT-13 · V-14 · V-06 · V-04 · F1-05 · F4-04 · F4-05 · CR-01) · 실기로 끝난 행 8개 완료 처리 · F1-04 는 TIMEOUT 튜닝만 남음', '황인재 9/22 21:24', 'H']



# ---------------------------------------------------------------- 9/22 21:32 PR #85 merge — 컵 벽 집기 후속(재파지·+5·1.7·RINSE z 60) · 툴 PICK/RETURN 방식(E35) · insert_approach 20
P2130 = 'PR #85 9/22 21:32(E35)'
EDIT.update({
 'CELL-05':  dict(prog='0.95', note_add=P2130 + ': 홈 C z 117.47 · CUP 폭 1.7 · RINSE.CUP z 60(dip 1회 ✅) · 재파지 place 자리 방식(1.42 ✅) main 반영. 남은 것 = **RACK_C_VIA·C1/C2 재티칭**(그 전 컵 rack_place 금지) → 9/23 13:30 전'),
 'F1-03':    dict(note_add=P2130 + ': 황인재 결정 — ① tool(PICK) 은 홀더 안에서 끝(안 빼냄 · soap 이 그 자리에서) ② RETURN 은 같은 프로그램이 집었으면 역순(집은 자리 +100 → 곧게 내려 놓기). 🟡 역순 반납 **힘 감시 없음**(PM 권고: 마지막 10~20 mm contact_down) · 🟡 실기 9/23 INT-ONE-B 첫 확인'),
 'F1-04':    dict(note_add=P2130 + ': insert_approach_mm 30 → 20(감시 하강 줄여 타임아웃 회피 · 자유 하강 +10 mm) — 🟡 9/23 INT-ONE-B 실기 · 대안 timeout_s 15'),
 'INT-ONE-B': dict(note_add=P2130 + ': 첫 확인 3가지 — ① rack_place(insert_approach 20) ② tool RETURN 역순(힘 감시 없음 · 0.3 · E-Stop 손에) ③ tool PICK 뒤 안 빼내고 soap'),
 'INT-ONE-C': dict(note_add=P2130 + ': 컵 값 main 반영(폭 1.7 · 홈 C +5 · RINSE z 60 · 재파지) — 시작 전 RACK_C 재티칭만 남음'),
})
HISTORY145 = ['v19.5', 'PR·결정', 'CELL-05, F1-03, F1-04, INT-ONE-B/C', 'PR #85 merge 21:32: 컵 후속 값(폭 1.7 · 홈 C +5 · RINSE z 60 · 재파지 키 방식) + E35 툴 PICK 홀더 안에서 끝·RETURN 역순 + insert_approach 20 — 449 passed · 🟡 역순 반납 힘 감시·자유 하강 +10 은 9/23 첫 실기', '황인재 9/22 21:32', 'H']



# ---------------------------------------------------------------- 9/22 21:41 PR #86 merge — rack_place 타임아웃 배속 반영·재시도 제자리·순응 해제 + 역순 반납 힘 감시 · 오늘 밤 그릇 한 바퀴 거의 완주
P2145 = 'PR #86 9/22 21:41'
EDIT.update({
 'INT-ONE-B': dict(prog='0.5', status='진행', note_add=P2145 + ': 🎯 **오늘 밤 황인재 실기(0.3)에서 그릇 한 바퀴가 rack_place 직전까지 통과** — 집기 2.32 → 무게(영점 −100 밀림 · 폭으로 쥠 확인 → 통과 · #78 작동) → 안착 → 수세미 집기(홀더 안에서 끝) → 세제 → 닦기(바닥 6.1 mm · 5.9 N · 나선 13.7) → 역순 반납 → 재파지 2.32 → 헹굼 2회 → 물 털기 3회 → rack_place TIMEOUT(19.9/20 mm · 10 s) → 재시도가 수조로 되돌아감 → 순응 −1. → #86 으로 셋 다 고침. 🟡 시각 "22:53~23:00" 표기는 date 값 재확인. 9/23 첫 회차 = rack_place(33 s)·재시도 제자리·역순 반납 힘 감시 확인'),
 'F1-04':    dict(note_add=P2145 + ': 접촉 타임아웃 = timeout_s/vel_scale(0.3 → 33 s) · 실패 뒤 순응 끄고 접근점 위로 · 재시도는 칸 150 mm 안이면 수조·경유점 생략 — 🟡 9/23 실기'),
 'F1-03':    dict(note_add=P2145 + ': 역순 반납 마지막 20 mm 는 contact_down(8 N) 힘 감시 — PM 지적 반영 ✅ · 실기 1회(역순 반납 OK · 힘 감시 전 코드)'),
 'V-02':     dict(note_add=P2145 + ': 오늘 밤 그릇 무게에서 영점 −100 g 밀림 관찰 — 폭 재확인(#78)으로 통과 · 자동 영점(ZERO-01) 필요성 재확인'),
})
HISTORY146 = ['v19.6', 'PR·🎯', 'INT-ONE-B, F1-04, F1-03, V-02', 'PR #86 merge 21:41: rack_place 타임아웃 배속 반영(33 s)·실패 뒤 순응 해제·재시도 제자리 + 역순 반납 마지막 20 mm 힘 감시 — 451 passed · 오늘 밤 그릇 한 바퀴가 rack_place 직전까지 실기 통과(INT-ONE-B 0.5)', '황인재 9/22 21:41', 'H']



# ---------------------------------------------------------------- 9/22 21:43 황인재 — 9/23 실기 검증 체크리스트 행(VER-0923) · F4 전달
NEW.append(
 ('VER-0923', 'INT-ONE-B', 'INT-ONE-B', '검증', '9/23 실기 검증 체크리스트 — 9/22 PR·실기에서 나온 🟡 22개(A 아침 → B 그릇 한 바퀴 → C 컵 한 바퀴 → D 남은 것) · 결과는 기록 PR',
  'H', '시작 전', S('9/23 오전', '9/23 오후'), '체크리스트 결과(✅/✗ · date 시각) — docs/test_logs 9/23 기록 PR · ✗ 는 F4 수정 PR',
  '22개 전부 ✅/✗ 판정 · ✗ 는 원인·조치 한 줄 · 시연 경로(그릇 2·컵 2)에 걸리는 ✗ 는 동결 전 해결',
  '황인재 9/22 21:43: 검증 항목을 한 줄로 모음 — A 아침 준비 — ① 툴·TCP 두 이름 확인 ② 빈 그릇·컵 기준값 각 3회(WEIGH 자세) ③ 시험대 시작 전 로봇이 낮으면 먼저 곧게 위로(rig_f1·rig_f3 는 보호 없음) | B 그릇 한 바퀴(INT-ONE-B) 첫 회차 — ④ rack_place 감시 하강 20 mm · 타임아웃 33 s(#85·#86) ⑤ 실패 뒤 순응 해제·접근점 위 → 재시도 제자리(150 mm 안이면 수조·경유점 생략) ⑥ tool RETURN 역순 + 마지막 20 mm 힘 감시 8 N ⑦ tool PICK 뒤 안 빼내고 soap 이 홀더 안에서 비틀기 → 스스로 작업 위치(E35·#83) ⑧ 자유 하강이 10 mm 깊어진 만큼 칸 위 접근 여유 ⑨ 무게 📉 흐름 경고·폭 재확인(#78) 동작 ⑩ soap 에 movej 가 없어 6번 관절이 누적되는지(#83) | C 컵 한 바퀴(INT-ONE-C) 전·중 — ⑪ RACK_C_VIA·RACK_C1/C2 재티칭(벽 집기 손목 자세 · 그 전 컵 rack_place 금지) ⑫ RINSE.CUP z 60 담금 2회 + 물 털기 ⑬ WASTE.CUP J6 180 컵 입 방향·떨어짐 ⑭ HOLD 35 N 벽 폭 변화 0.9 mm vs slip_tol 1.0 ⑮ 재파지 기준 1.7(관찰 1.42) ⑯ 홈 C +5 | D 남은 🟡 — ⑰ wipe_cup 회전 속도 검사 삭제(#83) → 박진용 되살리기 PR ⑱ preflight 케이블 확인을 떨림 기준으로(#78) ⑲ 털기 뒤 재측정 settle(44 g vs 임계 50) ⑳ ZERO-01 자동 영점 실기 ㉑ V-24 ②③④ ㉒ HMI 시작 버튼 → /flow/start'))
EASY['VER-0923'] = '오늘 코드를 많이 바꿔서 내일 로봇으로 하나씩 확인해야 하는 것들을 한 줄에 모았다. 아침 준비 → 그릇 한 바퀴 → 컵 한 바퀴 → 남은 것 순서로 보고, 결과를 기록에 남긴다'
HISTORY147 = ['v19.7', '검증', 'VER-0923', '황인재 9/22 21:43: 9/23 실기 검증 체크리스트 22개(A 아침 3 · B 그릇 7 · C 컵 6 · D 남은 6)를 한 행으로 · F4 전달', '황인재 9/22 21:43', 'H']



# ---------------------------------------------------------------- 9/22 21:44 F4 시각 정정(epoch→date)
EDIT.update({
 'INT-ONE-B': dict(note_add='🔴 21:44 시각 정정(F4 · epoch→date): 그릇 한 바퀴 3차 **21:26:55~21:32:14**(rack TIMEOUT 21:30:59 · 재시도 −1 21:32:03) · 2차 21:23:22~21:26:07 · 1차 21:18:28(중복 실행). "22:53~23:00" 은 암산 오류'),
 'CELL-05':   dict(note_add='🔴 21:44 시각 정정(F4): 컵 재파지 1.42 = 21:03:56 · RINSE.CUP z 60 dip = 21:11:51 · release 21:18:14 · loop 20:31:41~20:35:03 — cell.yaml 주석(22:0x·21:3x)·V-25 컵 줄은 9/23 문서 PR 에서 정정'),
})
HISTORY148 = ['v19.8', '🔴 정정', 'INT-ONE-B, CELL-05', 'F4 9/22 21:44: 오늘 밤 실기 시각 정정 — 그릇 한 바퀴 21:26:55~21:32:14 · 컵 재파지 21:03:56 · dip z60 21:11:51 (앞 22:xx·21:24 는 암산 오류 · 앞으로 Python 변환값만)', '황인재 9/22 21:44', 'H']



# ---------------------------------------------------------------- 9/22 21:54 황인재 결정 E36 — 헹굼(dip·shake RINSE) 재설계 · F4 가 통합하면서 새로 만든다
H2150 = '황인재 9/22 21:54(E36)'
NEW.append(
 ('RINSE-02', 'INT-ONE-B', 'INT-ONE-B', '개발', '헹굼 재설계 — 지금 f2.dip·shake(RINSE) 는 팀 논의와 다르게 만들어져 **새로 만든다**(F4 · 통합과 동시에): 수조 진입·담금 깊이·물 털기 동작을 팀이 정한 시나리오대로',
  'H', '시작 전', S('9/23 오전', '9/23 오후'), 'f2 dip·shake(RINSE) 새 구현(같은 함수 이름·Result · IRD 서명 유지) + params f2.dip/shake.RINSE 값 + 단위 시험 · 실기 그릇·컵 각 2회 · PR',
  '팀이 정한 헹굼 동작(황인재 지시)대로 · 수조 안에서 끝나면 TS-08 보호(#77 go_home_safely) 유지 · 힘 상한·타임아웃 · 그릇·컵 한 바퀴 실기에서 통과 · 동결 전 PR',
  H2150 + ': 황인재 — "민범진의 헹굼이 다같이 논의한 느낌이 아니라 아예 새로 만든다 · F4 가 통합하면서 동시에". 코드는 11:30~13:30(로봇 없는 동안) · 실기는 컵 한 바퀴(13:30~)·시연 실행(15:00~)에서. 🟡 목표 동작 사양(팀 논의본)은 황인재가 F4 에 지시 — 결정기록 E36 에 채운다'))
EASY['RINSE-02'] = '헹굼(물에 담갔다 빼고 물을 터는 동작)을 팀이 함께 정한 방식대로 F4 가 내일 통합하면서 새로 만든다'
EDIT.update({
 'INT-ONE-B': dict(note_add=H2150 + ': 헹굼 단계는 **새 구현(RINSE-02)** 으로 — 첫 회차는 지금 코드로 돌려 rack_place 까지 보고, 새 헹굼이 되면 2회차부터'),
 'INT-ONE-C': dict(note_add=H2150 + ': 헹굼 = 새 구현(RINSE-02) · RINSE.CUP z 60 은 새 설계에 맞춰 다시'),
 'VER-0923':  dict(note_add=H2150 + ': ⑫ 는 "새 헹굼(RINSE-02) 그릇·컵 각 2회" 로 바꿈'),
})
HISTORY149 = ['v19.9', '🔄 결정', 'RINSE-02, INT-ONE-B/C, VER-0923', '황인재 9/22 21:54 E36: 헹굼(dip·shake RINSE) 재설계 — F4 가 9/23 통합과 동시에 새로 만든다(코드 11:30~13:30 · 실기 컵 한 바퀴·시연 실행) · 🟡 사양은 황인재가 F4 에 지시', '황인재 9/22 21:54', 'H']



# ---------------------------------------------------------------- 9/23 06:04 아침 — 어젯밤 F4 마감 보고 · PR #87·#88 merge
M0923 = 'PM 9/23 06:04'
EDIT.update({
 'F1-04':    dict(note_add=M0923 + ': ✅ rack_place 단독 실기 OK 9/22 21:49:11(감시 20 mm · 33 s 안 · #86) · 🚨 21:48 그릇 들고 수조 쪽으로 가다 **솔 홀더에 걸림**(적재는 OK) → PR #87 merge(RINSE 접근점 z 150→235 · rack_place 는 safe_retreat 뒤 이동) — 🟡 오늘 첫 회차 확인'),
 'V-24':     dict(prog='0.8', note_add=M0923 + ': ✅ 빈손 ①②③④ 통과 9/22 21:49:45~21:50:37(F4) · 그릇 든 2회 미실행 → 오늘 5순위에서'),
 'INT-ONE-B': dict(note_add=M0923 + ': PR #87 merge 됨 — 09:00 준비 때 main pull(9177149 이후). 첫 회차 확인에 "수조 진입 z 235 · 홀더 걸림 없음" 추가'),
 'F3-03':    dict(note_add=M0923 + ': PR #88 merge(주석 정리 · 죽은 코드 3개 제거 · 동작 변화 없음) — F3 기능 완료 체크포인트'),
 'NEW-02a':  dict(note_add=M0923 + ': 박진용 제안(#88) — cobot_api 에 **TOOL_LOST** 코드 추가 + F3 가 폭 재확인으로 툴 놓침 감지 → flow 정지·사람 확인·재개(tool PICK 재호출). IRD 변경(4명 확인) · 🟡 황인재 결정 — NEW-02a 와 같은 흐름이라 묶는 안'),
})
HISTORY150 = ['v20.0', 'PR·실기', 'F1-04, V-24, INT-ONE-B, F3-03, NEW-02a', '9/23 06:04: 어젯밤 마감(rack_place OK 21:49:11 · V-24 빈손 ①②③④ · 🚨 21:48 솔 홀더 걸림 사고 3) · PR #87(수조 접근 235 · safe_retreat) · #88(F3 주석 정리) merge · TOOL_LOST 제안은 황인재 결정', '황인재 9/23 06:04', 'H']



# ---------------------------------------------------------------- 9/23 06:10 황인재 승인 E37 — TOOL_LOST(툴 놓침) 채택 · NEW-02a 와 묶음
EDIT.update({
 'NEW-02a': dict(task='새 기능 ③ 넛지 재개 ① + 툴 놓침(TOOL_LOST · E37) — 툴 파지 실패 또는 닦는 중 놓침(폭 재확인) → "툴 없음" → 사람 호출 → 사람이 채우고 로봇을 툭 치면(힘센서 넛지) tool PICK 재호출 → 재개', note_add='황인재 9/23 06:10 승인(E37 · 9/22 회의 합의): #88 제안 채택 — cobot_api 에 TOOL_LOST 코드 추가는 박진용 PR 에 포함(정본 담당 황인재 승인 · 본문 멘션) · flow 분기(정지→사람→재개→PICK 재호출)는 F4 와 맞춘 뒤 · slip_tol 재사용 OK · IRD §2 코드 표에 추가함'),
})
HISTORY151 = ['v20.1', '✅ 결정', 'NEW-02a', '황인재 9/23 06:10 E37: 박진용 TOOL_LOST 제안 승인(9/22 회의 합의 · IRD 코드 추가) — NEW-02a 와 한 흐름으로 · 상수는 박진용 PR · flow 분기는 F4 와', '황인재 9/23 06:10', 'H']



# ---------------------------------------------------------------- 9/23 06:14 황인재 — E36 헹굼 사양 확정
EDIT.update({
 'RINSE-02': dict(task='헹굼 재설계(E36 · F4) — 담금 2회(dip 유지) → 위로 곧게 빼서(z 235) → 좌우 3회 털기(수조 위 공중 · 새 shake) · 지금 J5 왕복 털기는 버림', note_add='황인재 9/23 06:14 사양 확정: 담금 2회(수조 안으로 곧게 내려갔다 올라오기 · 지금 dip 유지) → **위로 곧게 빼서**(수조 밖 접근 높이 z 235) → **좌우로 3회 털기**(수조 위 공중에서 · 새 동작 · F4 구현). 지금의 J5 왕복 물 털기(#71)는 동작이 마음에 안 들어 버린다 — 좌우(옆 방향) 흔들기로 새로 만든다. 코드 11:30~13:30(로봇 없는 동안) · 실기 컵 한 바퀴(13:30~)·시연 실행(15:00~) 그릇·컵 각 2회 · 값 params f2.shake.RINSE 종류별 · 털기가 수조 위에서 끝나 헹굼 뒤 높은 자세(TS-08 위험 감소)'),
 'VER-0923': dict(note_add='9/23 06:14: ⑫ = 새 헹굼(담금 2회 → 곧게 위로 → 좌우 3회 털기) 그릇·컵 각 2회 · 물 흘림·용기 미끄러짐(HOLD 폭) 관찰'),
})
HISTORY152 = ['v20.2', '✅ 결정', 'RINSE-02, VER-0923', '황인재 9/23 06:14 E36 사양: 담금 2회 → 위로 곧게 빼서 → 좌우 3회 털기(새 동작 · F4) · J5 왕복 털기 폐기', '황인재 9/23 06:14', 'H']



# ---------------------------------------------------------------- 9/23 06:18 F4 — VER-0923 A 결과 · 아침 기준값(켠 직후 드리프트)
F0655 = 'F4 9/23 06:18(date 값)'
EDIT.update({
 'VER-0923': dict(status='진행', prog='0.15', note_add=F0655 + ': **A ✅** — A1 LOCALHOST · A3 두 이름 OK · A4 HOME z 215.55 · 그릇 pick 2.32 · 컵 pick 1.82. 기준값 그릇 **−58**(06:26~27 · −66.9/−32.6/−58.2 · 폭 34 · 흐름 경고) · 컵 **−17**(06:49~50 · −22.7/+15.5/−16.6 · 폭 38 · 매 회차 흐름 경고) → 임시(🟡) · 그릇 1회차 뒤 재측정 → 2회차(96 g) 전 갱신 · 컵 13:30 전 재측정. B 시작'),
 'V-02':     dict(note_add=F0655 + ': 🔎 아침 기준값이 어젯밤(그릇 −12 · 컵 −20)과 크게 다름(−58 / −17 · 폭 34~38) = **켠 직후 힘 센서 드리프트** → ZERO-01(자동 영점) 근거 추가 · 🟡 시연 아침(REH-02)은 브링업 뒤 워밍업 시간을 두고 기준값'),
 'ZERO-01':  dict(note_add=F0655 + ': 근거 추가 — 켠 직후(06:2x) 기준값이 밤 값과 40~50 g 차이 · 실행 시작 때 빈손 영점이 있어야 아침 첫 바퀴가 맞는다'),
 'REH-02':   dict(note_add='PM 9/23 06:18: 🟡 체크리스트 ② 보완 — 브링업 뒤 **워밍업 시간(🟡 F4 가 오늘 드리프트 안정 시간 측정)** 지나서 기준값 재측정(켠 직후는 40~50 g 어긋남)'),
})
HISTORY153 = ['v20.3', '✅ 실기', 'VER-0923, V-02, ZERO-01, REH-02', 'F4 9/23 06:18: 체크리스트 A 통과 · 아침 기준값 그릇 −58 · 컵 −17(켠 직후 드리프트 · 임시) → 재측정 계획 · ZERO-01 근거 · REH-02 워밍업', '황인재 9/23 06:18', 'H']



# ---------------------------------------------------------------- 9/23 06:23 황인재 — 영점은 "켠 뒤 안정되면 1회 검증" 이 기본
EDIT.update({
 'REH-02':   dict(note_add='황인재 9/23 06:23: 체크리스트 ② 확정 — **브링업 → 힘센서 안정(워밍업 · 🟡 분)** → 빈 그릇·컵 기준값 각 1회 재서 직전 값 ±15 g 안이면 OK(넘으면 갱신) → 시연 시작 때 자동 영점(ZERO-01). 용기마다 재는 건 기본 아님'),
 'ZERO-01':  dict(note_add='황인재 9/23 06:23: 기본 = 실행 시작 1회. 한 바퀴 안 흐름이 20 g 넘으면 "집기 직전 빈손 2초 읽기" 추가 설계(오늘 F4 측정 뒤 결정)'),
 'VER-0923': dict(note_add='9/23 06:23: A2 보완 — 켠 뒤 안정 시간 측정 + 한 바퀴 안 영점 흐름(20 g 기준) 기록'),
})
HISTORY154 = ['v20.4', '결정', 'REH-02, ZERO-01, VER-0923', '황인재 9/23 06:23: 영점은 켠 뒤 안정되면 1회 검증 + 실행 시작 자동 영점이 기본 · 용기마다는 오늘 흐름 측정(20 g) 뒤 결정', '황인재 9/23 06:23', 'H']



# ---------------------------------------------------------------- 9/23 06:28 F4 시각 정정(epoch→date) + 오늘 영점 측정 순서
EDIT.update({
 'VER-0923': dict(note_add='🔴 06:28 시각 정정(F4): 컵 pick 06:15:15 · 컵 기준값 06:16:30~06:17:11(−22.7/+15.5/−16.6 → −17 · 회차 폭 38 · 21초 흐름 +24/+35/−51 = 🚨 불안정) · 그릇 기준값(−58)은 06:1x 이전(탭 닫혀 epoch 없음). 앞 "06:26/06:49" 는 오류. 오늘 순서: ① 06:3x 그릇 기준값 1회(흐름 <20 g 이면 안정 · 켠 시각부터 분 기록 · −58 ±15 안이면 유지) ② 그릇 1회차(빈 그릇)에서 바퀴 안 영점 이동 관찰 ③ 1회차 뒤 기준값 1회 → 2회차 96 g ④ 컵 기준값은 13:30 전'),
 'V-02':     dict(note_add='🔴 06:28 시각 정정: 컵 기준값 06:16:30~06:17:11(불안정 · 21초 안 ±24~51 g) · 그릇 06:1x 이전'),
})
HISTORY155 = ['v20.5', '🔴 정정', 'VER-0923, V-02', 'F4 9/23 06:28: 아침 기준값 시각 정정(컵 06:16~06:17 · 불안정) · 오늘 영점 측정 순서 4단계', '황인재 9/23 06:28', 'H']



# ---------------------------------------------------------------- 9/23 07:18 F4 — 그릇 한 바퀴 2회 완주 · 무게 경로 의존 발견 · 영점 절차 답
F0730 = 'F4 9/23 07:18(date 값)'
EDIT.update({
 'INT-ONE-B': dict(status='완료', prog='1.0', note_add=F0730 + ': ✅ **그릇 한 바퀴 2회 완주** — 1회차(빈 그릇) 06:35:13~06:40:05 · 283 s · 0.3 · f1·f2·f3 전부 진짜 · RACK_B1 OK / 2회차(96 g) 07:06:58~07:13:42 · 395 s · 잔반 111.2 감지 → HOLD·J5 −90°·털기 4회(물건 떨어짐) → 재측정 −20.7 통과 → 닦기·헹굼·적재 OK(황인재: "버리는 모션까지 완벽"). 체크 ④⑥⑦⑧⑨⑩ ✅ · ⑤ 미발생'),
 'VER-0923':  dict(prog='0.5', note_add=F0730 + ': B ④⑥⑦⑧⑨⑩ ✅(⑤ 미발생) · 1회차 첫 무게 −122.8(기준 −58) 은 폭 재확인으로 통과(⑨ 작동)'),
 'V-02':      dict(note_add=F0730 + ': 🔎 **무게가 오는 길에 따라 두 무리**(같은 그릇·같은 WEIGH 자세): 집은 자리에서 바로 재면 중앙 −121 · HOME 을 거쳐 내려오면 −23~−67 · 1분 간격 직접 비교 90 g 차(관절 토크 기반 힘 추정의 마지막 이동 이력 추정). 흐름의 첫 측정만 "집은 자리" 길이라 96 g 넣어도 ~30 g 으로 놓칠 뻔 → 조치: sense.weigh 가 항상 HOME 경유 → WEIGH(용기당 +10 s) · leftover_loop 중복 HOME 제거 · 기준값 BOWL **−23**(06:55:17 HOME 경유) · 브랜치 injae/20260923-VER-0923-record(황인재 승인 뒤 PR)'),
 'ZERO-01':   dict(note_add=F0730 + ': 영점 절차 답 — ① 켠 뒤 안정: 06:04:57 브링업 → 정지 흐름 06:07 −32 · 06:16 ±51 · 06:32 +25 · 06:55 −6 → **약 50분 뒤 20 g 아래** ② 워밍업 중 빈 그릇 값 −58 → −65 → −23(40분에 +35 g) → F4 제안 "실행 직전 1회(rig_f2 empty · HOME 경유)" 로 대체 ③ 한 바퀴 안: 잔반통→HOME 직후 재측정 흐름 +47(5 s 대기 짧음) → weigh_settle_s 5 → 8~10 검토 ④ ZERO-01 코드는 가능하나 오늘은 ②로 대체 제안 → 🟡 황인재 결정'),
 'REH-02':    dict(note_add=F0730 + ': 🚨 워밍업 **약 50분** — 시연 14:00 이면 13:00 전 브링업 · 리허설 뒤 시연 직전 빈 그릇·컵 기준값 1회(HOME 경유)'),
 'CELL-05':   dict(note_add=F0730 + ': 🟡 황인재 결정 — 컵 팔레트 "뒤집어 놓기" 는 벽 집기(E29)로 물리적 불가(컵이 손가락 아래 매달림) → ㉠ 벽 집기 그대로 입 위로 적재(RACK_C 3자세 재티칭) vs ㉡ 홈 C 에서 옆면 재파지(원안 · 프리셋·헹굼·팔레트 자세 되살림). 결정 뒤 컵 기준값(HOME 경유 1회) → 컵 한 바퀴'),
})
HISTORY156 = ['v20.6', '🎯 완주', 'INT-ONE-B, VER-0923, V-02, ZERO-01, REH-02, CELL-05', 'F4 9/23 07:18: 그릇 한 바퀴 2회 완주(빈 그릇 · 96 g 잔반 감지·털기·재측정 통과) · 무게 경로 의존 발견(HOME 경유 필수 · 기준값 −23) · 워밍업 50분 · 영점 절차 제안 · 🟡 컵 적재 방향 결정', '황인재 9/23 07:18', 'H']



# ---------------------------------------------------------------- 9/23 07:39 PM — RINSE-02 코드·시험 완료(브랜치) · 실기 대기
EDIT.update({
 'RINSE-02': dict(status='진행', prog='0.6', owner='H(PM)', note_add='PM 9/23 07:39: 황인재 관찰(07:4x 옛 헹굼 실기)로 사양 구체화 — 담금 2회 뒤 HOME 을 거치지 않고 **곧게 위로(접근 높이 235)** 빼서 그 높이에서 **J4 좌우 3회 · 빠르게**. 구현 = PM 에이전트(F4 는 통합 검증 · 역할 분리 통보): sense.shake at: approach · fast(vel_scale 예외 · motion.move_joint_rel scale=False · 상한 100 °/s) · params RINSE BOWL J4 ±20° 0.8 s · CUP ±15° 0.6 s · 시험 456 통과 · 브랜치 injae/20260923-RINSE-02-shake(push) · 작업 폴더 rokey_pjt01_ws_pm 빌드. 🟡 실기 = 황인재가 직접(rig_f2 dip → shake RINSE) → 승인 뒤 PR'),
})
HISTORY157 = ['v20.7', '개발', 'RINSE-02', 'PM 9/23 07:39: 헹굼 재설계 코드·시험 완료(브랜치 · 456 passed · at approach · J4 fast) — 실기·승인 대기 · 구현 주체 PM(F4 통합 검증과 분리)', '황인재 9/23 07:39', 'H']



# ---------------------------------------------------------------- 9/23 07:48 황인재 결정 E38 — 컵 적재 ㉡(옆면 재파지 · 뒤집기) · F4 변경
EDIT.update({
 'CELL-05':  dict(note_add='황인재 9/23 07:48(E38 · F4 창): 컵 적재 = **㉡ 옆면 재파지 → 손목 돌려 뒤집어 팔레트**(식기세척기 요구). F4: regrip 다시 켬 + CUP_SIDE(76 · 5 N · hold 5) · gripper.set_grip_preset · RINSE.CUP z −13.6 복귀(🟡 옆면 자세 첫 실기 전). 실기 순서(F4): 홈 C 컵 → rig_f1 pick SPONGE_BED_C CUP(옆면 76·5 N·z 250) → rack_place RACK_C1'),
 'INT-ONE-C': dict(note_add='9/23 07:48(E38): 컵 한 바퀴 = 벽 집기(집기·무게·버리기·홈 C) + 옆면 재파지 + 뒤집어 적재 · 컵 담금·털기는 옆면 컵이 가로로 눕는 기하라 좌표 F4 수정 뒤 PM 헹굼 실기에 포함'),
 'RINSE-02': dict(note_add='9/23 07:48(E38 참고): 재파지 뒤 컵은 5 N 고정 폭이라 HOLD 불가 → f2.shake.RINSE.CUP 은 그릇보다 약하게(지금 J4 ±15° 0.6 s · 🟡 컵 실기로 더 낮출 수 있음) · 컵 dip/shake 실기는 F4 가 RINSE.CUP 좌표 고친 뒤'),
})
HISTORY158 = ['v20.8', '✅ 결정', 'CELL-05, INT-ONE-C, RINSE-02', '황인재 9/23 07:48 E38: 컵 적재 ㉡(홈 C 옆면 재파지 → 뒤집어 팔레트) · F4 브랜치에 regrip/CUP_SIDE/set_grip_preset/RINSE.CUP −13.6 · 컵 물 털기는 약하게', '황인재 9/23 07:48', 'H']



# ---------------------------------------------------------------- 9/23 08:03 F4 — 옆면 재파지 실패 → 컵 적재 ㉠′ · PM 헹굼 2차(RINSE_SHAKE·smooth)
EDIT.update({
 'CELL-05':  dict(note_add='F4 9/23 08:03: 🔄 **E38 정정 ㉠′** — 옆면 재파지 실기 07:55:05 실패(관절 이동 9.4° 만에 SAFE_STOP · 그리퍼 안 열림 · 재파지 자세가 낮 place 기준) → 벽 집기 그대로 컵을 옆으로 눕혀 칸에. 황인재가 RACK_C1·C2·RACK_C_VIA 를 컵 쥔 채 재티칭 중 → cell.yaml 갱신 → rack_place 컵 0.3 실기. RINSE.CUP z 60 복구(1cdc461)'),
 'RINSE-02': dict(prog='0.8', note_add='PM 9/23 08:03: 2차 — 황인재 티칭 털기 자세 RINSE_SHAKE(z 600 · J4 −93°)에서 J4 ±30°(컵 ±25°) · 3차 — "3단계로 보인다" → **관절 스플라인 한 번(smooth · amovesj · move_joints_via)** 으로 정지 없이. 컵 실기 07:5x OK(RINSE_SHAKE · ±25° · 폭 유지) · 시험 461 · 브랜치 push. 🟡 스플라인 판 실기 대기 · 컵은 벽 집기(20 N·HOLD 35) 기준'),
})
HISTORY159 = ['v20.9', '🔄 정정·개발', 'CELL-05, RINSE-02', 'F4 9/23 08:03: 옆면 재파지 SAFE_STOP → 컵 적재 ㉠′(벽 집기 · 옆으로 눕혀 · RACK_C 재티칭) · PM 헹굼 2·3차(털기 자세 RINSE_SHAKE · 스플라인 한 번) 브랜치 461 passed', '황인재 9/23 08:03', 'H']



# ---------------------------------------------------------------- 9/23 08:15 황인재 최종 — 컵 적재 ㉡ 유지(㉠′ 철회) · 재파지 접근점 방식 · PM 헹굼 스플라인 posj 수정
EDIT.update({
 'CELL-05':  dict(note_add='황인재 9/23 08:15 최종: **㉡ 유지**(뒤집어 적재 · ㉠′ 철회). 07:55 실패 = 가는 길(HOME 관절 이동 → 열린 그리퍼가 컵에 걸림) → F4: 재파지에 접근점(+100 · 위에서 맞추고 Z 만) 방식 · rig_fkin(posj→posx) · 다음 = 황인재 fkin 값 → cell.yaml 접근점 → rack 전까지 실기. 🟡 한석형 "새 재파지 좌표" 존재 여부 PM 조사(저장소엔 −29.24… 뿐)'),
 'RINSE-02': dict(note_add='PM 9/23 08:15: 스플라인 첫 실기(08:1x) 실패 — 두산 movesj 는 점이 posj 형이어야(list → DR_Error 1000) → move_joints_via 가 posj 로 감싸도록 수정(c040ad2 · 461 passed) · 재실기 대기. 컵 최종은 옆면 5 N 기준이라 CUP 진폭·속도 낮출 것(🟡)'),
})
HISTORY160 = ['v21.0', '🔄 확정·수정', 'CELL-05, RINSE-02', '황인재 9/23 08:15: 컵 적재 ㉡ 유지(㉠′ 철회 · 재파지 접근점 방식) · PM 헹굼 스플라인 posj 형 수정 뒤 재실기 대기', '황인재 9/23 08:15', 'H']



# ---------------------------------------------------------------- 9/23 08:47 RINSE-02 실기 승인 · PR #89
EDIT.update({
 'RINSE-02': dict(prog='0.9', note_add='황인재 9/23 08:47: **실기 승인**("잘 구현됨") — 최종 = 담금 2회 → 곧게 위로 → 털기 자세(RINSE_SHAKE) → J4 ±30°(컵 ±25°) 스플라인 3회 · 143 °/s · 가속 600 · 3회 5 s · 폭 유지. 빈손 가드·grip_level 탐색 보강 포함. **PR #89**(PM · 466 passed · 충돌 0) — merge 는 황인재 승인 뒤 · F4 브랜치와 순서 조율(gripper·cell·params 겹침 → 뒤쪽 rebase). 🟡 그릇은 최종 판 미실기 → 시연 실행에서 · 옆면 컵(5 N) 값 낮추기'),
 'VER-0923': dict(note_add='9/23 08:47: ⑫ 새 헹굼 컵 실기 ✅(벽 집기) · 그릇은 오늘 시연 실행에서'),
})
HISTORY161 = ['v21.1', '✅ 실기', 'RINSE-02, VER-0923', '황인재 9/23 08:47: 새 헹굼 실기 승인 → PR #89(PM) 열림 · merge 승인·F4 순서 대기', '황인재 9/23 08:47', 'H']



# ---------------------------------------------------------------- 9/23 09:02 일정표 최신화 — 로봇 슬롯 9/23 실제 계획 · 아침 진행 반영
SLOT['9/23 수'] = {
 'B': ('🔄 09:02 실제(E33·E34·E36·E38): ✅ **06:35~07:14 그릇 한 바퀴 2회 완주(INT-ONE-B · 96 g 잔반 감지→털기→통과)** · ✅ 08:4x 새 헹굼(담금 2회 → 곧게 위로 → 털기 자세 J4 스플라인 3회 · 빠르게) 실기 승인 → PR #89 · '
       '~11:30 황인재: 컵 옆면 재파지·팔레트 적재 실기(E38 · F4 코드) → **컵 한 바퀴(INT-ONE-C)** · 11:30~12:30 한석형 NEW-01a 격리 이송·NEW-01b 거품 펌프 단위 실기 · '
       '로봇 불필요: F4 PR(무게 HOME 경유·기준값·컵 재파지) → PM 검토·merge → #89 rebase·merge(황인재 승인)'),
 'C': ('12:30~13:30 박진용 NEW-02a 툴 없음 넛지·NEW-02b 케이블 넛지 단위 실기(TOOL_LOST E37 포함) · 13:30~15:00 황인재 컵 나머지·시연 준비 · '
       '**15:00~17:00 INT-4a 시연 실행 — flow_node 시작 1회(/flow/start) → 그릇 2·컵 2 연속(E28) + 녹화(한석형 촬영 · 영상 원본)** · INT-4c 사이클 타임 1회 · 새 헹굼 그릇 판 첫 실기(VER-0923 ⑫)'),
 'D': ('17:00~ 예비(순서대로 전부): ④ ZERO-01 자동 영점 실기 → ⑤ V-24 ②③④(그릇 든 2회) → 저녁: 한석형·박진용이 오후까지 구현한 동작만 시연 흐름에 통합(INT-4b · 황인재와) → ⑥ INT-4 HMI 시작·정지·재개·중단 1회(시간 되면 · 아니면 추석) → '
       '🚨 **동결 · v1.0-demo 태그(INT-4d)** · 시연 아침 체크리스트(REH-02): 브링업 뒤 워밍업 ~50분 → 기준값 1회 검증(±15 g)'),
}
EDIT.update({
 'VER-0923':  dict(prog='0.6', note_add='PM 9/23 09:02: A ✅ · B ④⑥⑦⑧⑨⑩ ✅(⑤ 미발생) · ⑫ 새 헹굼 컵 ✅(그릇은 15:00 시연 실행에서) · C ⑪⑬⑭⑮⑯ 은 컵 재파지·적재 실기(진행 중) 뒤 · D ⑰⑱ 박진용 PR 대기 · ⑳㉑ 17:00 예비 · ㉒ 저녁'),
 'INT-ONE-C': dict(note_add='PM 9/23 09:02: 그릇이 아침에 끝나 **오전으로 당김** — F4 컵 옆면 재파지·RACK_C1 적재 실기(08:47~) 통과 뒤 바로 · 헹굼 컵(옆면 5 N 값) 실기 포함'),
 'CELL-05':   dict(note_add='PM 9/23 09:02: 08:47~ 황인재가 F4 코드로 컵 rack_place RACK_C1 빈손 경로 시험(08:41 RACK_C_VIA 관절 이동 30 s 초과 → 이동 상한 vel_scale 반영 수정 cf32e25 뒤 재시험) — 결과 대기'),
 'BRF':       dict(note_add='9/23 09:02: 09:30 묶음은 내용이 적어 황인재가 **구두 전파**(파일 `_upload/0923_0930_아침묶음.md` 참고용)'),
})
HISTORY162 = ['v21.2', '📅 최신화', '로봇 슬롯 9/23, VER-0923, INT-ONE-C, CELL-05, BRF', 'PM 9/23 09:02: 로봇 슬롯 9/23 을 실제 계획으로(아침 그릇 2회 완주·새 헹굼 승인 반영 · 오전 컵 · 11:30/12:30 새 기능 · 15:00 시연 실행·녹화 · 저녁 통합·동결) · 체크리스트 0.6 · 09:30 구두 전파', '황인재 9/23 09:02', 'H']



# ---------------------------------------------------------------- 9/23 10:09 F4 — 컵 옆면 재파지·팔레트 적재 C1·C2 OK
F1010 = 'F4 9/23 10:09(date 값)'
EDIT.update({
 'CELL-05':  dict(status='완료', prog='1.0', note_add=F1010 + ': ✅ **컵 옆면 재파지 → 팔레트 적재 C1·C2 OK** — 재파지 = 접근점(fkin +100) → 40 자유 → 60 힘 감시 → CUP_SIDE 목표 폭 70·10 N(08:54 76·5 N 은 손가락이 위치에서 멈춰 실제 힘 ≤5 N → 이송 중 컵이 돌아 변경 · 실기 폭 70.3~73.8 · 10.0 N · 안 돌음) · 적재 C1 09:57:57~09:59:29 OK · C2 10:02:34~10:03:58 OK(자세 재티칭 09:2x · 접근 z 350 · 빠져나오기 Z 350 → Y 350) · RACK_C_VIA 관절 이동 30 s 초과 → 이동 상한 ÷ vel_scale(cf32e25). 🚨 사고 참고 09:38: 컵 칸(z 249)에서 --home 이 235 보다 높다고 안 올라가고 관절 이동 → 팔레트에 걸림(도구 문제 · 수정 cde8218 · 상태 1 복구)'),
 'INT-ONE-C': dict(status='진행', prog='0.3', note_add=F1010 + ': 집기→홈 C→옆면 재파지→팔레트 적재까지 실기 OK. 남은 것 = **컵 헹굼(옆면 컵 · RINSE.CUP 접근 235 · z −13.6 · 컵이 가로로 눕는 기하)** — F4 PR merge → #89 rebase·merge 뒤(HOLD 힘이 옆면 프리셋을 따라야 함) PM 헹굼 실기 → 컵 기준값 1회(HOME 경유) → rig_flow_once --kind CUP'),
 'RINSE-02': dict(note_add='PM 9/23 10:09: 컵 값을 옆면 재파지 기준(70 mm·10 N)으로 낮춤 — J4 ±15° 0.8 s 가속 400(#89 갱신). 컵 헹굼 실기는 F4 PR merge + #89 rebase 뒤(그 전엔 grip_level HOLD 가 벽 집기 35 N 을 써 옆면 컵을 눌러 버림)'),
 'VER-0923': dict(note_add=F1010 + ': ⑪ RACK_C 재티칭 ✅ · ⑬⑭ 벽 집기 컵에서 확인(옆면은 컵 헹굼 때) · ⑮ 옆면 재파지 70 mm·10 N ✅ · ⑯ ✅'),
})
HISTORY163 = ['v21.3', '🎯 실기', 'CELL-05, INT-ONE-C, RINSE-02, VER-0923', 'F4 9/23 10:09: 컵 옆면 재파지(70 mm·10 N)→팔레트 C1·C2 적재 OK · CELL-05 완료 · 컵 헹굼은 F4 PR merge→#89 rebase 뒤 PM 실기(컵 값 낮춤 ±15°)', '황인재 9/23 10:09', 'H']



# ---------------------------------------------------------------- 9/23 10:25 PR 3개 merge(#90 #91 #92) · #89 main 합침
P1025 = 'PM 9/23 10:25(date 값)'
EDIT.update({
 'NEW-01a': dict(prog='0.7', note_add=P1025 + ': ✅ **PR #90 merge**(한석형) — 그릇 격리 = HOME 형상에서 J1 만 −210° → Z −50 → 놓기 → Z +50 → J1 0°(`f1.place(ISOLATE, BOWL)` · `f1.isolate_drop_mm 50`) · 한석형 단독 실기 ✅(시각 미기록) · 컵은 옛 경로 그대로. 🟡 흐름 안(중단 → 격리)은 저녁 INT-4b 에서 첫 실기 · 진입 조건 = J2~J6 HOME ±3°(flow.abort_container 는 HOME 먼저 가므로 맞음). 참고 지적: HOME 형상·허용값 하드코딩 → 다음 PR'),
 'NEW-01b': dict(prog='0.5', note_add=P1025 + ': ✅ **PR #91 merge**(한석형) — 세제 펌프 **rig 만**(`cobot_common/test/rig_soap_sponge_real.py` · 단계마다 Enter · 순응 + ΔFz 10 N 상한 · 최대 30 mm) · SPONGE 갈래 실기 ✅ · BRUSH 갈래 🟡 미실기 · 임시 미스트 용기 값. **남은 것: f1 제품 함수 + 값 YAML 분리 + 흐름 연결(어느 단계에서 · F4 와)** — 시연에 넣을지는 황인재 판단(저녁 INT-4b)'),
 'NEW-01':  dict(prog='0.6', note_add=P1025 + ': 한석형 단위 PR 2개 merge(#90 격리 · #91 펌프 rig) · 11:30 로봇 슬롯은 남은 확인(컵 격리 · BRUSH 펌프)에'),
 'VER-0923': dict(prog='0.7', note_add=P1025 + ': ✅ **F4 PR #92 merge**(main 288fc4a · 458 통과) — weigh 항상 HOME 경유 · 기준값 BOWL −23/CUP −17 · 컵 옆면 재파지 접근점(60 mm 힘 감시) · CUP_SIDE 70/10 N · RACK_C1/C2 재티칭 · 이동 상한 ÷ vel_scale · 검증 기록 `docs/test_logs/20260923_VER-0923_검증기록_황인재.md`. 🟡 남음: 컵 기준값 실행 직전 재측정 · ⑫ 새 헹굼 그릇 판(15:00) · ⑰⑱ 박진용 · ⑳㉑㉒'),
 'RINSE-02': dict(note_add=P1025 + ': #89 에 새 main 을 합침(a3aa4fc · 충돌 gripper.grip_level 1곳 = F4 쥔 프리셋 + PM 열린 그리퍼 거부 둘 다 · 473 통과 · MERGEABLE) → **황인재 "merge 해" 대기** → merge 뒤 컵 헹굼 실기(옆면 70 mm·10 N · J4 ±15°)'),
 'INT-ONE-C': dict(note_add=P1025 + ': F4 코드 main 반영(#92). 컵 헹굼 실기는 #89 merge 직후 PM 명령(3명령 → dip → shake RINSE CUP) → 컵 기준값 1회 → rig_flow_once --kind CUP'),
})
HISTORY164 = ['v21.4', '✅ merge', 'NEW-01a, NEW-01b, NEW-01, VER-0923, RINSE-02, INT-ONE-C', 'PM 9/23 10:25: PR #90(그릇 격리 J1 경로)·#91(세제 펌프 rig)·#92(F4 VER-0923: weigh HOME 경유·컵 옆면 재파지·RACK_C 재티칭) merge · #89 는 main 합쳐 merge 대기(황인재 승인)', '황인재 9/23 10:25', 'H']



# ---------------------------------------------------------------- 9/23 10:36 #89 merge(황인재 승인) → 컵 한 바퀴 통합 시험으로
P1036 = 'PM 9/23 10:36(date 값)'
EDIT.update({
 'RINSE-02': dict(status='완료', prog='1.0', note_add=P1036 + ': ✅ **PR #89 merge**(황인재 "merge하고, 통합 테스트 하면되나" · main 9beaf2b · 473 통과). 🟡 옆면 컵(70 mm·10 N · ±15°) 헹굼은 첫 실기 전 · 흐름 안 그릇 판은 15:00 INT-4a'),
 'INT-ONE-C': dict(prog='0.5', note_add=P1036 + ': main 에 새 헹굼까지 들어감 → F4 main 받기 → 컵 기준값 1회(HOME 경유) → **rig_flow_once --kind CUP**. PM 권고: 한 바퀴 전에 옆면 컵 헹굼 5분 단독 확인(3명령 → dip → shake) — 황인재 결정'),
 'VER-0923': dict(prog='0.75', note_add=P1036 + ': ⑫ 컵(옆면) 헹굼은 통합 시험에서 · #89 merge 로 코드 동결 대상 확정(남은 PR = 박진용 NEW-02a/b)'),
})
HISTORY165 = ['v21.5', '✅ merge', 'RINSE-02, INT-ONE-C, VER-0923', 'PM 9/23 10:36: #89(새 헹굼) 황인재 승인 merge → 컵 한 바퀴 통합 시험으로(F4 main 받기 · 컵 기준값 · rig_flow_once CUP)', '황인재 9/23 10:36', 'H']



# ---------------------------------------------------------------- 9/23 10:5x 컵 한 바퀴 1회차 DONE(F4) · 옆면 컵 단독 확인 결과
F1055 = 'F4 9/23 10:5x(로그 환산값)'
EDIT.update({
 'INT-ONE-C': dict(status='완료', prog='1.0', note_add=F1055 + ': ✅ **컵 한 바퀴 1회차 DONE**(rig_flow_once CUP · mock 없음 · 0.3 배속 · 358 s · main 9beaf2b) — 집기 1.92 → 무게 HOME 경유 → 홈 C → 솔 → 세제 → **컵 닦기 흐름 안 첫 실기 OK** → 반납 → 옆면 재파지 70.6·10 N → 담금 2회(HOLD 가 CUP_SIDE 10 N) → **새 물털기(J4 ±15°) 폭 70.6 유지** → 팔레트 C1 → HOME. 🟡 컵 자세·물털기 모양은 황인재 눈 확인. PM 단독 확인(10:4x): 재파지·담금 OK · 털기는 단계별 rig 한계(프로세스마다 그리퍼 프리셋·힘이 안 이어짐)로 흐름에서 봄'),
 'VER-0923': dict(prog='0.85', note_add=F1055 + ': ⑫ 새 헹굼 컵(옆면) ✅ 흐름 안 · ⑬⑭ ✅ · C 항목 완료. 🚨 무게 드리프트: 컵 기준값 10:46 +30 → 10:52 −15.6(6분 −46 g) → 96 g 대용품이면 잔반 ≈50 = 임계 50 과 겹칠 수 있음 → **황인재 결정 필요: 시연 대용품 2개(≈190 g · 코드 변경 없음 · PM 권고) / 임계 조정** · 컵 2회차(96 g)로 확인'),
 'REH-02':   dict(note_add='PM 9/23 10:5x: 시연 아침 체크리스트에 "기준값은 실행 직전(≤5분) 1회" 추가 근거 — 6분 사이 −46 g 이동(F4 10:46→10:52)'),
})
HISTORY166 = ['v21.6', '🎯 실기', 'INT-ONE-C, VER-0923, REH-02', 'F4 9/23 10:5x: 컵 한 바퀴 1회차 DONE(닦기·옆면 재파지·새 물털기 흐름 안 첫 실기 OK) · INT-ONE-C 완료 · 무게 드리프트 −46 g/6분 → 시연 대용품 2개 결정 요청', '황인재 9/23 10:5x', 'H']



# ---------------------------------------------------------------- 9/23 11:13 컵 한 바퀴 2회차 DONE · PR #93(민범진 케이블 넛지) 보류
F1113 = 'F4 9/23 11:13(로그 환산값)'
EDIT.update({
 'INT-ONE-C': dict(note_add=F1113 + ': ✅ **컵 2회차 DONE**(11:06:59~11:13:07 · 361 s · 기준값 30 · 털기 자세 CUP J6 0 = 컵 뒤집힌 자세) — 옆면 재파지 70.3·10 N → 담금(HOLD CUP_SIDE 10 N) → **새 물털기 폭 70.3 유지 · 황인재 눈 확인 OK** → C1 → HOME. 황인재: "컵 세척 한 플로우 완벽". 🟡 읽음 9.4 = 빈 컵 값 — 96 g 을 넣었는지 확인(넣었으면 놓침 사례 · E39 근거)'),
 'RINSE-02':  dict(note_add=F1113 + ': 컵 털기 자세 `RINSE_SHAKE.CUP` J6 −84 → **0**(컵 입 아래 · F4 cup-flow 브랜치 · 그릇 그대로) · 흐름 안 실기 2회 OK'),
 'VER-0923':  dict(prog='0.9', note_add=F1113 + ': ⑪~⑯ 컵 몫 ✅ · 남은 것 ⑫ 그릇 판(15:00) · ⑰⑱ 박진용 · ⑳㉑㉒ · E39(대용품 2개) 결정'),
 'NEW-02b':   dict(status='검토', prog='0.6', note_add='PM 9/23 11:13: **PR #93 민범진**(케이블 떨림 > 50 g → 후퇴 없이 PAUSED → 톡톡 5 N/HMI 재개 → 10표본 재검증 → 그 단계부터 재개) — 기술 검토 통과(480 통과 · 실기 없음 🟡) · **merge 보류 → 황인재 결정**(E33 에서 박진용 몫 · 동결일 PAUSED 조건 추가 · 오늘 떨림 최대 31 g). PM·F4 권고: 15:00 시연 뒤 merge + 저녁 INT-4b 실기 / 지금이면 상한 80'),
})
HISTORY167 = ['v21.7', '🎯 실기', 'INT-ONE-C, RINSE-02, VER-0923, NEW-02b', 'F4 9/23 11:13: 컵 한 바퀴 2회차 DONE(새 물털기 컵 뒤집힌 자세 눈 확인 OK) · PR #93 민범진 케이블 넛지 기술 검토 통과·merge 보류(황인재 결정)', '황인재 9/23 11:13', 'H']



# ---------------------------------------------------------------- 9/23 11:23 PR #94(F4 cup-flow) merge → 컵 96 g 3회차
P1123 = 'PM 9/23 11:23(date 값)'
EDIT.update({
 'VER-0923':  dict(note_add=P1123 + ': ✅ **PR #94 merge**(main 1da799d · 474 통과) — 컵 기준값 30 · 재파지 접촉 타임아웃 거리 비례(`f1.contact_timeout_ref_mm` 20) · `RINSE_SHAKE.CUP` J6 0 · rig_goto · 기록 §11~13. 황인재: "통합한 거 PR 한 다음 테스트" → **컵 96 g 3회차**(잔반 루프 흐름 안 첫 실기 · E39 근거) → 15:00 시연 준비'),
 'INT-ONE-C': dict(note_add=P1123 + ': 2회차는 96 g 안 넣음(황인재 확인 · 9.4 = 빈 컵 값 정상). 3회차(96 g)로 컵 잔반 루프 흐름 안 첫 실기 + 읽은 값으로 대용품 1개/2개 결정(E39)'),
})
HISTORY168 = ['v21.8', '✅ merge', 'VER-0923, INT-ONE-C', 'PM 9/23 11:23: PR #94(F4 · 컵 기준값 30 · 타임아웃 거리 비례 · 컵 털기 자세 J6 0 · rig_goto) merge → 컵 96 g 3회차로', '황인재 9/23 11:23', 'H']



# ---------------------------------------------------------------- 9/23 11:3x 통합 인수인계(PM → F4) · 남은 순서 확정 · 시연 준비 3개 추가
P1135 = 'PM·F4 9/23 11:3x(date 값)'
SLOT['9/23 수']['C'] = ('12:30~13:30 박진용 NEW-02a 툴 없음 넛지(TOOL_LOST E37) 단위 실기 · **로봇 슬롯은 시작·끝을 채팅으로(한 번에 한 프로세스)** · '
                      '13:30~15:00 시연 준비(F4): (a) **flow_node 경로 첫 실기** — launch vel_scale 0.3 → /flow/start 그릇 1개(오늘 전부 rig_flow_once 였음) · (b) **그릇 2개 연속 리허설**(RACK_B2 첫 흐름 실기) · '
                      '(c) 컵 2개 연속(C1→C2)은 시연에서 처음 — 🟡 황인재 허용 여부 · 성한 컵 · 대용품(E39) · 기준값 2종 실행 직전 · 녹화 준비(한석형) · '
                      '**15:00~17:00 INT-4a 시연 실행 — flow_node 1회 시작 → 그릇 2·컵 2 연속(E28) + 녹화 + INT-4c 사이클 타임 1회** · 새 헹굼 그릇 판 첫 실기(VER-0923 ⑫) · 🟡 시연 배속 결정(0.3 유지 권고 · 0.5 는 오늘 실기 0회)')
SLOT['9/23 수']['D'] = ('17:00~ 예비(순서대로): ④ ZERO-01 → **코드 없이 절차로 대체 확정**(브링업 → 50분 → rig_f2 empty 그릇·컵 각 1회 → params 갱신 → 시작) → ⑤ V-24 ②③④ → '
                      '저녁 INT-4b 새 기능 시연(구현된 것만: 격리 #90 · 펌프 rig #91 · 넛지 · #93 케이블 넛지는 merge 뒤) → ⑥ INT-4 HMI 1회(시간 되면) → 🚨 **동결 · v1.0-demo 태그(PM)** · 시연 아침 체크리스트(REH-02)')
EDIT.update({
 'INT-ALL':  dict(owner='H', note_add=P1135 + ': 황인재 "기능 구현 끝 → 통합 테스트는 F4" — PM 인수인계(끝난 것 4 · 남은 순서 ①~⑥) · F4 확정. PM = 일정표·결정기록·PR·VER-0923 갱신 · F4 = 실기·조정·코드(브랜치 injae/20260923-demo · PR 로)'),
 'INT-4a':   dict(note_add=P1135 + ': 시연 준비에 flow_node 경로 첫 실기 · 그릇 2개 연속 리허설(RACK_B2) 추가 · 컵 2개 연속·배속은 황인재 결정'),
 'ZERO-01':  dict(status='완료', prog='1.0', note_add=P1135 + ': **코드 없이 절차로 대체 확정** — 브링업 → 워밍업 50분 → `rig_f2 empty` 그릇·컵 각 1회(HOME 경유) → params 갱신 → 실행 시작(REH-02 체크리스트에). 오늘 근거: 켠 직후 −58 → 40분 뒤 −23 · 컵 −17 → +30'),
 'REH-02':   dict(note_add=P1135 + ': ZERO-01 절차 편입 · 기준값 2종 실행 직전(≤5분) · 성한 컵 · 대용품 E39 · 배속'),
})
HISTORY169 = ['v21.9', '🔄 인수인계', 'INT-ALL, INT-4a, ZERO-01, REH-02, 로봇 슬롯 9/23', 'PM·F4 9/23 11:3x: 통합 시험 F4 담당(황인재) · 남은 순서 확정 · 시연 준비에 flow_node 첫 실기·그릇 2개 연속 리허설 추가 · ZERO-01 절차 대체 · 미결(대용품·#93·settle 8·배속·컵 2개 연속) 황인재', '황인재 9/23 11:3x', 'H']



# ---------------------------------------------------------------- 9/23 11:35 황인재 결정 E40(시연 배속 0.5 · settle 8 · #93 시연 뒤 · 컵 2개 연속 필수) · E39 보류
P1145 = '황인재 9/23 11:35(E40)'
SLOT['9/23 수']['C'] = SLOT['9/23 수']['C'].replace('(c) 컵 2개 연속(C1→C2)은 시연에서 처음 — 🟡 황인재 허용 여부',
                                                   '(c) **컵 2개 연속(C1→C2) 리허설 필수**(E40 ④ · 성한 컵 2개) · (d) **배속 0.5 리허설 필수**(E40 ① · 오늘 0.5 실기 0회 · 문제면 0.3) · (e) weigh_settle_s 8 PR(E40 ②) 먼저')
SLOT['9/23 수']['C'] = SLOT['9/23 수']['C'].replace('🟡 시연 배속 결정(0.3 유지 권고 · 0.5 는 오늘 실기 0회)', '**시연 배속 0.5**(E40 ① · 리허설 통과 조건)')
EDIT.update({
 'INT-4a':  dict(note_add=P1145 + ': **시연 배속 0.5** — 13:30 준비에서 0.5 리허설(flow_node · 그릇 1 → 컵 1 이상) 통과가 조건 · 컵 2개 연속 리허설 필수 · 대용품은 3회차 값 뒤(E39)'),
 'REH-02':  dict(note_add=P1145 + ': settle 8 · 배속 0.5 · 컵 2개 · 대용품(E39) 체크리스트 반영'),
 'NEW-02b': dict(status='대기', note_add=P1145 + ': **#93 은 시연 실행 뒤 merge**(황인재 결정) · NEW-02b = 민범진 구현으로 · 저녁 INT-4b 에서 실기'),
 'F2-01':   dict(note_add=P1145 + ': weigh_settle_s 5 → **8**(F4 PR · 리허설 전)'),
})
HISTORY170 = ['v22.0', '결정', 'INT-4a, REH-02, NEW-02b, F2-01, 로봇 슬롯 9/23', '황인재 9/23 11:35 E40: 시연 배속 0.5(0.5 리허설 필수) · weigh_settle_s 8 · #93 시연 뒤 merge · 컵 2개 연속 리허설 필수 · E39 대용품은 3회차 뒤', '황인재 9/23 11:35', 'H']



# ---------------------------------------------------------------- 9/23 11:56 컵 98 g 3회차 DONE(잔반 루프 흐름 안 첫 실기) · PR #96 수정 요청 · E39 권고
F1150 = 'F4 9/23 11:48(로그 환산값)'
EDIT.update({
 'INT-ONE-C': dict(note_add=F1150 + ': ✅ **컵 98 g 3회차 DONE**(11:39:26~11:48:12 · 509.7 s · settle 8 첫 실기) — 잔반 60.8 g 감지 → 잔반통 털기(HOLD 35 N · 4회) → 재측정 −7.3 통과 → 옆면 재파지 → 담금 → 물털기 → C1. **컵 잔반 루프 흐름 안 첫 실기 ✅**. 🚨 털기 뒤 컵 테두리 눌림 1.00 mm 가 미끄러짐 허용 1.0 에 걸려 PAUSED 1회(Enter 재개) → PR #96(컵 허용 1.5 · HOLD 25)'),
 'VER-0923':  dict(prog='0.95', note_add='PM 9/23 11:56: 컵 잔반 루프 ✅ · 98 g 이 60.8 g 으로 읽힘(−37) → **E39 대용품 2개(≈190 g) 권고 → 황인재 확정 대기** · 남은 것 ⑫ 그릇 판(15:00) · ⑰⑱ 박진용 · 리허설(0.5 · 컵 2개 · flow_node)'),
 'F2-01':     dict(note_add='PM 9/23 11:56: **PR #96**(F4 · f2.slip_tol_mm 종류별 {BOWL 1.0, CUP 1.5} · CUP HOLD 35 → 25) — 합친 트리 시험 1 실패(경계값 시험) → 수정 요청 · 값은 황인재 확인 뒤 merge(리허설 전)'),
})
HISTORY171 = ['v22.1', '🎯 실기', 'INT-ONE-C, VER-0923, F2-01', 'F4 9/23 11:48: 컵 98 g 3회차 DONE(잔반 루프 흐름 안 첫 실기 · 60.8 g 감지 → 털기 → 통과) · 테두리 눌림 PAUSED 1회 → PR #96(컵 허용 1.5 · HOLD 25) 수정 요청 · E39 대용품 2개 권고', '황인재 9/23 11:56', 'H']



# ---------------------------------------------------------------- 9/23 12:13 PR #96 merge(컵 값 실기 검증 통과) · 컵 98 g 재시험 · E39 자료
P1213 = 'PM 9/23 12:13(로그 환산값)'
EDIT.update({
 'F2-01':     dict(note_add=P1213 + ': ✅ **PR #96 merge**(main 8b7aec4) — 검증: 컵 98 g 재시험 12:09:37~12:12:12 HOLD 25 N 폭 11.9→11.5 → 잔반통 털기 4회 → NORMAL 11.5(변화 0.4 < 1.5 · PAUSED 없음) · 잔반 91.4 g 감지 → 재측정 −29.8 통과. main = 컵 HOLD 25 · 허용 {BOWL 1.0, CUP 1.5} · 슬롯 2 · 기준값 −47/15 · settle 8'),
 'INT-ONE-C': dict(note_add=P1213 + ': 컵 98 g **4회차**(재시험 · 12:09~) 잔반 루프 OK(91.4 감지 → 털기 → −29.8 통과) · 나머지 진행 중'),
 'VER-0923':  dict(note_add=P1213 + ': E39 자료 — 98 g 읽힘 11:40 **60.8** / 12:10 **91.4**(기준값 재측정 직후) → 편차 30 g · F4·PM 권고 대용품 2개 유지 · **황인재 결정**. 다음 = F4 main 받아 0.5 리허설(그릇 1 → 컵 1) → 그릇1→그릇2→컵1→컵2'),
})
HISTORY172 = ['v22.2', '✅ merge', 'F2-01, INT-ONE-C, VER-0923', 'PM 9/23 12:13: #96 merge(컵 HOLD 25·허용 1.5·슬롯 2·기준값 — 컵 98 g 재시험으로 검증) · 잔반 91.4 g 읽힘 · E39 황인재 결정 대기 · 다음 0.5 리허설', '황인재 9/23 12:13', 'H']



# ---------------------------------------------------------------- 9/23 12:58 시연 경로 리허설 완료(flow_node 0.5 · 4개 연속) · 결정 3건 요청
F1258 = 'F4 9/23 12:58(로그 환산값)'
EDIT.update({
 'INT-4a':   dict(prog='0.7', note_add=F1258 + ': ✅ **리허설 완료 — flow_node 0.5 · /flow/start 1회 · 그릇 2 → 컵 2 · 12:38:29~12:58:03(19분 34초) · 격리 0** — 그릇1 잔반 27.3 → B1 · 그릇2 슬롯 2 → 잔반 8.1 → **B2 첫 실기 OK** · 컵1 툴 반납 TIMEOUT 1회 → 정책 자동 재시도 성공 → C1 · 컵2 슬롯 2 → 잔반 50.1 → 털기(HOLD 25 · 변화 0.5) → 재측정 −30.2 → **C2 첫 실기 OK**. flow_node 경로·이벤트 첫 실기 ✅ · 슬롯 2 흐름 안 ✅. 🟡 결정: 솔 반납 TIMEOUT 대책(timeout_s 10→15 + 0.5 재확인 / 배속 0.3) · 대용품 2개 · 성한 컵'),
 'INT-4c':   dict(note_add=F1258 + ': 리허설 사이클 타임 — 그릇 4분 10초 · 3분 57초 · 컵 4분 51초(재시도 포함) · 6분 00초(잔반 루프 포함) · 4개 19분 34초(0.5)'),
 'VER-0923': dict(prog='0.97', note_add=F1258 + ': ⑫ 그릇 판 헹굼 흐름 안 ✅(그릇 1·2) · 슬롯 2 · B2·C2 ✅ · E39 자료 98 g → 60.8 / 91.4 / **50.1**(임계 50 과 0.1 차) → **대용품 2개 강력 권고** · 남은 것 ⑰⑱ 박진용 · 저녁 INT-4b · 동결'),
 'REH-02':   dict(note_add=F1258 + ': 성한 컵(컵 1 집기 폭 1.12 = 하한) · 대용품 2개 · 기준값 직전 · 배속 결정 반영'),
})
HISTORY173 = ['v22.3', '🎯 실기', 'INT-4a, INT-4c, VER-0923, REH-02', 'F4 9/23 12:58: 시연 경로 리허설 완료(flow_node 0.5 · 그릇 2·컵 2 · 19분 34초 · 격리 0 · B2·C2 첫 실기) · 결정 3건(툴 반납 TIMEOUT 대책 · 대용품 2개 · 성한 컵) 황인재', '황인재 9/23 12:58', 'H']



# ---------------------------------------------------------------- 9/23 13:56 리허설 2회차 완료 · 툴 반납 TIMEOUT 원인 확정 · 시연 준비 막바지
F1356 = 'F4 9/23 13:56(로그 환산값)'
EDIT.update({
 'INT-4a':   dict(prog='0.8', note_add=F1356 + ': ✅ **리허설 2회차 완료**(flow_node 0.5 · 13:36:10~13:55:49 · 19분 39초 · 격리 0) — 그릇1 20.2 → B1 · 그릇2 슬롯 2 12.2 → **B2 손목 +180 적재**(방향 눈 확인) · 컵1 −4.1 · 컵2 56.4(98 g) → 털기 → −46.1 → **C2 x+3**(정렬 확인). 🔎 **툴 반납 TIMEOUT 원인 확정**: 순응 하강 한 걸음(3 mm) ≈3 s(배속 무관) → 20 mm ≈21 s > 상한 20 s(0.5) → 0.5 이상에서 항상 실패 · retry 정책이 두 번 다 살림 → 수정 `f1.contact_timeout_min_s: 30`(F4 · 컵 1개 0.5 확인 뒤 PR). 다음 = PR → 14:4x 기준값 2종 → 15:00 시연(0.5 · 대용품 2개 · 새 컵)'),
 'F1-03':    dict(note_add=F1356 + ': 툴 반납 TIMEOUT 원인 = 접촉 걸음 ≈3 s × 7 = 21 s > 상한 20 s(0.5 배속) → `f1.contact_timeout_min_s` 30 최소값(정상 동작 무변화 · 실패 대기만 김) · 🟡 걸음 시간(재파지 0.8 vs 반납 3 s) 분리는 시연 뒤'),
 'VER-0923': dict(note_add=F1356 + ': E39 자료 추가 98 g → **56.4**(컵2 · 2회차) — 오늘 4회 50.1~91.4 → 대용품 2개 · 컵1 떨림 45(#93 상한 50 근접 → merge 시 80 검토)'),
})
HISTORY174 = ['v22.4', '🎯 실기', 'INT-4a, F1-03, VER-0923', 'F4 9/23 13:56: 리허설 2회차 완료(0.5 · 19분 39초 · B2 손목 반전 · C2 x+3) · 툴 반납 TIMEOUT 원인 확정(걸음 3 s · 상한 20 s) → 최소 30 s 수정 PR 예정 · 15:00 시연 준비', '황인재 9/23 13:56', 'H']



# ---------------------------------------------------------------- 9/23 14:00 PR #97 merge — 시연 판 후보 main 50b7245
P1400 = 'PM 9/23 14:00(date 값)'
EDIT.update({
 'INT-4a':   dict(prog='0.85', note_add=P1400 + ': ✅ **PR #97 merge**(main 50b7245) — B2 손목 +180 · C2 x+3 · 접촉 타임아웃 최소 30 s(🟡 실기 0회 · 시연 컵 2 가 첫 실기) · 사유 로그. main = 시연 판 후보. 14:4x 기준값 2종 → **15:00 시연 실행**(flow_node 0.5 · 그릇 2 → 컵 2 · 녹화) · 볼 것: 솔 반납 TIMEOUT 없음 · 잔반 감지 · B2 방향 · C2 정렬'),
 'F1-03':    dict(note_add=P1400 + ': 최소 30 s 바닥값 main 반영(#97) · 시연에서 첫 실기'),
 'CELL-05':  dict(note_add=P1400 + ': RACK_B2 손목 +180(via RACK_B1_VIA · C −174) · RACK_C2 x+3 main 반영(#97 · 실기 ✅ 13:19/13:33 단독 · 13:44/13:55 흐름)'),
 'NEW-01':   dict(note_add=P1400 + ': 한석형 격리·펌프 단위 확인 로봇 슬롯(11:30)은 통합 리허설에 밀려 **저녁 INT-4b 로**(황인재 확인 대기) · 불필요 동작·속도 다듬기는 한석형이 통합 때'),
 'NEW-02a':  dict(note_add=P1400 + ': 박진용 넛지 단위 확인 슬롯(12:30)도 **저녁 INT-4b 로**(황인재 확인 대기)'),
})
HISTORY175 = ['v22.5', '✅ merge', 'INT-4a, F1-03, CELL-05, NEW-01, NEW-02a', 'PM 9/23 14:00: #97 merge(B2 손목 반전 · C2 x+3 · 접촉 타임아웃 최소 30 s) → main 50b7245 = 시연 판 후보 · 15:00 시연 준비 · 한석형·박진용 단위 확인은 저녁으로', '황인재 9/23 14:00', 'H']



# ---------------------------------------------------------------- 9/23 14:06 황인재 결정 — 대용품은 F4 시험 · #93 저녁 실기 민범진 · 한석형·박진용은 저녁 통합과 같이
P1405 = '황인재 9/23 14:06'
SLOT['9/23 수']['D'] = SLOT['9/23 수']['D'].replace('저녁 INT-4b 새 기능 시연(구현된 것만: 격리 #90 · 펌프 rig #91 · 넛지 · #93 케이블 넛지는 merge 뒤)',
    '저녁 INT-4b 새 기능 시연 — **한석형 격리·펌프 · 박진용 넛지 단위 확인을 통합과 같이**(낮 슬롯은 리허설에 밀림) · **#93 케이블 넛지 실기는 민범진 직접**(비프음 분리 뒤 · 시나리오 B·C·D · 통과 시 PM merge → 태그 전)')
EDIT.update({
 'VER-0923': dict(note_add=P1405 + ': E39 = **F4 가 대용품 2개(≈190 g)로 시험**(15:00 시연 실행/직전) → 읽은 값으로 확정'),
 'NEW-02b':  dict(note_add=P1405 + ': #93 저녁 실기 담당 **민범진 직접**(비프음 커밋 4개 별도 PR 로 분리 뒤 · 케이블 당김 → PAUSED → 톡톡 → 재검증 → 재개) · 로봇 슬롯은 F4 와'),
 'NEW-01':   dict(note_add=P1405 + ': 한석형 격리·펌프 단위 확인 = 저녁 통합(INT-4b)과 같이 · 지금은 개발 계속'),
 'NEW-02a':  dict(note_add=P1405 + ': 박진용 넛지 단위 확인 = 저녁 통합(INT-4b)과 같이 · 지금은 개발 계속'),
})
HISTORY176 = ['v22.6', '결정', 'VER-0923, NEW-02b, NEW-01, NEW-02a, 로봇 슬롯 9/23', '황인재 9/23 14:06: 대용품은 F4 가 2개로 시험해 확정 · #93 저녁 실기는 민범진 직접 · 한석형·박진용 단위 확인은 저녁 통합과 같이', '황인재 9/23 14:06', 'H']



# ---------------------------------------------------------------- 9/23 14:07 저녁 슬롯 확정(F4 안 · PM 동의) — 시연 뒤 새 기능 단위 확인 + #93 실기 + 동결
P1410 = 'PM·F4 9/23 14:07'
SLOT['9/23 수']['D'] = ('15:30~ 시연 결과 정리(F4·PM) → **16:00 한석형 40분** 격리(abort 흐름 · PAUSED 에서 /flow/abort) · 펌프 rig → **16:40 박진용 40분** 넛지(TOOL_LOST) → '
                      '**17:20 민범진 40분** #93 케이블 넛지 실기(pr-93 · 시나리오 B·C·D · 통과 시 PM merge) → **18:00 정리** · ZERO-01 은 절차 대체(REH-02) · V-24 ②③④ 는 시간 되면 · '
                      'INT-4 HMI 는 시간 되면(황인재) → 🚨 **동결 · v1.0-demo 태그(PM)**. 각 슬롯 시작·끝은 채팅으로 · 한 번에 한 프로세스')
EDIT.update({
 'INT-4b':  dict(note_add=P1410 + ': 저녁 슬롯 확정 — 16:00 한석형(격리·펌프) · 16:40 박진용(넛지) · 17:20 민범진(#93 실기) · 18:00 정리 · 시작·끝 채팅'),
 'INT-4d':  dict(note_add=P1410 + ': 동결·v1.0-demo 태그는 18:00 정리 뒤(#93 통과 여부 반영) · PM 이 태그'),
})
HISTORY177 = ['v22.7', '📅 슬롯', 'INT-4b, INT-4d, 로봇 슬롯 9/23', 'PM·F4 9/23 14:07: 저녁 슬롯 16:00 한석형 · 16:40 박진용 · 17:20 민범진(#93) · 18:00 정리 → 동결·태그', '황인재 9/23 14:07', 'H']



# ---------------------------------------------------------------- 9/23 15:18 #93 merge(황인재 수락) · 저장소 정리 · README 실행 방법 · 아키텍처 Archify
P1518 = 'PM 9/23 15:18(date 값)'
EDIT.update({
 'NEW-02b':  dict(status='완료', prog='0.9', note_add=P1518 + ': ✅ **PR #93 merge**(황인재 수락 · 분리 없이 케이블 넛지 + 그리퍼 안전 스위치 원격 해제(흐름 미연결 · 운영자 도구) + HMI 비프음 · 494 통과) · 🟡 실기 0회 → 17:20 민범진 실기(케이블 당김 → PAUSED → 톡톡 → 재개) · 🟡 떨림 상한 50 vs 오늘 최대 45 → 80 검토(황인재)'),
 'DOC-03': dict(note_add=P1518 + ': 강사 확인용 저장소 정리(옛 일정표 패치 3 · 프롬프트/아키텍처 생성기 2 · 옛 그림 3 · 해결된 요청 문서 4 삭제 · 316 파일) · README §4 "실행 방법" · 리마인드·SDD 브리핑용 갱신 · **시스템 아키텍처를 Archify 대화형 HTML 로 다시 그림**(docs/images/system_architecture_pc.html · 명세 .archify.json · 캡처 .png · 보기 3개 · 자동 검사 9항목 통과)'),
})
HISTORY178 = ['v22.8', '✅ merge', 'NEW-02b, DOC-03', 'PM 9/23 15:18: #93 merge(황인재 수락 · 실기 17:20) · 저장소 정리 · README 실행 방법 · 아키텍처 Archify 갱신', '황인재 9/23 15:18', 'H']



# ---------------------------------------------------------------- 9/23 15:50 최종 시연 9/29(화) 14:00 확정(황인재) — DEMO-01 · REH-02
P1545 = '황인재 9/23 15:50'
EDIT.update({
 'DEMO-01': dict(task='DEMO-01 최종 시연 — **9/29(화) 14:00** 강사 입회 · 그릇 2 → 컵 2 정상 흐름(E28 · E41 전부 배치 · 배속 0.5) + 새 기능 시연(구현·검증된 것만) + PPT 토의',
                 owner='전원(H 실행 · S 촬영)', slots=S('9/29 오후'),
                 note_add=P1545 + ': **최종 시연 일시 확정 — 9/29(화) 14:00**. 준비 순서(당일): 13:00 전 브링업 → 워밍업 ~50분 → REH-02 리허설 1회 → 시연 직전 빈 그릇·컵 기준값 각 1회(HOME 경유 · ±15 g 안이면 OK) → 대용품 2개(E39) · 새 컵 · 시연 판 = 9/23 저녁 동결 v1.0-demo'),
 'REH-02':  dict(slots=S('9/29 오전'), note_add=P1545 + ': 9/29(화) 오전 리허설 → 14:00 최종 시연(DEMO-01) 앞 절차로 확정'),
})
HISTORY179 = ['v22.9', '📅 일정', 'DEMO-01, REH-02', '황인재 9/23 15:50: 최종 시연 9/29(화) 14:00 확정 — DEMO-01 이름·슬롯·당일 준비 순서 · REH-02 오전 리허설', '황인재 9/23 15:50', 'H']



# ---------------------------------------------------------------- 9/23 16:09 15:00 시연 실행 → 통합 코드 튜닝으로 변경(황인재) · 저녁 순서 재조정
F1555 = 'F4 9/23 15:5x'
SLOT['9/23 수']['C'] = SLOT['9/23 수']['C'].replace('**15:00~17:00 INT-4a 시연 실행 — flow_node 1회 시작 → 그릇 2·컵 2 연속(E28) + 녹화 + INT-4c 사이클 타임 1회**',
    '🔄 15:5x 황인재: 15:00 시연 실행 대신 **통합 코드 튜닝(TUNE)** — rig_flow_once --step 으로 그릇 한 바퀴 단계별 관찰 → 불필요 동작 삭제·속도 조정 9건(WEIGH 이동 단계 제거 · 툴 반납 곧게 · 삽입 감시 5 mm · 재파지 감시 20 mm · 수세미 홀더 J6 등가 자세) → 그릇·컵 단계별 재확인 → PR → **INT-4a 시연 실행 + 녹화 시각은 그 뒤 재결정**')
SLOT['9/23 수']['D'] = SLOT['9/23 수']['D'].replace('15:30~ 시연 결과 정리(F4·PM)', '튜닝 PR merge 뒤 INT-4a 시연 실행·녹화(시각 재결정) → 결과 정리')
EDIT.update({
 'INT-4a':  dict(prog='0.8', note_add=F1555 + ': **15:00 시연 실행은 통합 코드 튜닝으로 대체**(황인재) — 단계별 실행 도구로 그릇 한 바퀴 관찰 → 9건 수정(브랜치 injae/20260923-tune · 484 통과 · 실기 확인 뒤 PR). 시연 실행·녹화 시각은 튜닝 뒤 재결정. 🟡 PM 확인 요청: 재파지 힘 감시 60 → 20 mm 는 컵 테두리 통과 구간(잡는 높이 +45)을 못 덮음 · 툴 반납 접촉 감시 제거(depth 0) — 실기 근거를 PR 표에'),
 'INT-4b':  dict(note_add=F1555 + ': 저녁 슬롯(한석형 격리·#98 · 박진용 넛지 · 민범진 #93 실기)은 **튜닝 뒤로 밀림** — 시각은 황인재가 다시 잡음'),
 'INT-4c':  dict(note_add=F1555 + ': 튜닝 목표 = 불필요 동작 삭제·속도 → 사이클 타임 단축(리허설 19분 30초 기준) · 값은 시연 실행에서'),
})
HISTORY180 = ['v23.0', '🔄 계획', 'INT-4a, INT-4b, INT-4c, 로봇 슬롯 9/23', 'F4 9/23 15:5x: 15:00 시연 실행 → 통합 코드 튜닝(9건 · 브랜치 tune)으로 변경(황인재) · 시연 실행·녹화·저녁 슬롯 시각 재조정', '황인재 9/23 15:5x', 'H']



# ---------------------------------------------------------------- 9/23 16:52 PR #99 박진용 TOOL_LOST + 넛지 재개(E37) merge
P1652 = 'PM 9/23 16:52(date 값)'
EDIT.update({
 'NEW-02a':  dict(status='완료', prog='0.9', note_add=P1652 + ': ✅ **PR #99 merge**(박진용 · 507 통과) — 닦는 도중 툴 놓침(폭 이탈) → 그 자리 정지 TOOL_LOST → 사람이 홀더에 넣고 넛지(15 N · 0.15 s) 또는 HMI 재개 → STANDBY 확인 → f1.tool 재PICK(집은 자리로 직선) → 놓친 단계부터 다시. 실기: 그릇 시나리오 rig ✅ · 🟡 컵 · flow_node 경로 · 넛지 값 튜닝'),
 'VER-0923': dict(note_add=P1652 + ': ⑰⑱ 박진용 PR 도착·merge(#99) · 남은 🟡 = flow_node 경로 TOOL_LOST 1회(저녁) · #98 실기 · 튜닝 PR'),
})
HISTORY181 = ['v23.1', '✅ merge', 'NEW-02a, VER-0923', 'PM 9/23 16:52: #99 박진용 TOOL_LOST+넛지 재개 merge(그릇 시나리오 실기 ✅ · flow_node 경로 🟡)', '황인재 9/23 16:52', 'H']



# ---------------------------------------------------------------- 9/23 17:40 #98(한석형 직접 merge) · #100 세제 펌프 제품 통합 merge(꺼짐 기본)
P1740 = 'PM 9/23 17:40(date 값)'
EDIT.update({
 'NEW-01a':  dict(status='완료', prog='0.9', note_add=P1740 + ': #98(빈 반납 구역 → HOME 복귀 · HOME 실패 시 재개 대기) — PM 승인 뒤 **한석형이 17:26 직접 merge**(실기 확인 전 · 규칙은 PM 이 squash merge) → 🟡 EMPTY_ZONE→HOME 실기 미확인 · 시연 시나리오에는 안 걸림'),
 'NEW-01b':  dict(status='완료', prog='0.8', note_add=P1740 + ': ✅ **PR #100 merge** — 세제 펌프를 제품 함수로(`handling.tool(PICK)` 앞 `_soap_pump_and_pick` · 값은 `f1.soap_pump`·`cell.stations.SOAP_PUMP`) · **기본 꺼짐**(`enabled: false`) · 508 통과 · 🟡 제품 경로 실기 0회 → 시연 포함은 황인재 결정 뒤 흐름 안 실기'),
 'REH-02':   dict(note_add=P1740 + ': 체크리스트 추가 — **드라이버 브링업 먼저 → flow_node**(17:16·17:19 launch 실패 원인) · HMI 확인용 `fake_state_pub` 은 시연 전 반드시 종료(/flow/start 를 가로챔)'),
})
HISTORY182 = ['v23.2', '✅ merge', 'NEW-01a, NEW-01b, REH-02', 'PM 9/23 17:40: #98 한석형 직접 merge(실기 전) · #100 세제 펌프 제품 통합 merge(기본 꺼짐) · 체크리스트에 브링업 순서·fake_state_pub 종료', '황인재 9/23 17:40', 'H']




# ---------------------------------------------------------------- 9/23 18:33 E42 LEFTOVER_REMAIN pause · E43 #102 민범진 안 채택 · #103 변경 요청
P1830 = 'PM 9/23 18:33(date 값)'
EDIT.update({
 'NEW-01a':  dict(note_add=P1830 + ': 🔁 **PR #103(WEIGH→ISOLATE 관절 직행) 변경 요청** — main flow 는 격리 놓기를 abort 정리(HOME 먼저)에서만 부르고, HOME 출발이면 #90 의 J1-only 와 같은 움직임이라 가드만 잃음 · WEIGH→ISOLATE 직행은 오른쪽 홀더·수조 위 z 158~215 미검증(9/22 "z 150 솔 홀더 걸림") · 권고 (b) f1 안에서 HOME 자가 복귀 뒤 J1-only. 🚨 검토 중 발견: 정책 isolate 갈래(LEFTOVER_REMAIN·SEAT_FAIL·retry 소진)는 **로봇을 옮기지 않고 기록만** → 다음 PICK 의 release 가 든 용기를 떨어뜨림 → E42'),
 'INT-4b':   dict(note_add=P1830 + ': ✅ **E42(황인재 18:29)** — 시연용 `flow.policy.LEFTOVER_REMAIN: pause`(main f4734e7 · 510 통과) → 잔반 과다 시나리오 = **멈춤 → 사람이 재개(다시 잰다) / 중단(HOME → 격리 #90 경로 → 다음 용기)** · 정책 격리의 물리 이송(B)은 동결 뒤 민범진 flow.py'),
 'NEW-02b':  dict(note_add=P1830 + ': ✅ **E43(황인재 18:29) — PR #102(넛지 재개 뒤 SAFE_STOP 자동 복구) 민범진 안 그대로 채택** · merge 조건 = wipe.py 충돌 해소(#101 `_tool_tol_mm` 유지 · `_tool_slip_tol` 삭제 · PR 코멘트로 요청) → PM 검토·merge · 실기 🟡 저녁 민범진'),
 'VER-0923': dict(note_add=P1830 + ': 정책 격리 빈틈 발견 → E42 pause · #102 충돌 해소 대기(E43 채택) · #103 변경 요청 · 남은 🟡 = flow_node TOOL_LOST 1회 · #98 실기 · 튜닝 PR'),
})
HISTORY183 = ['v23.3', '✅ 결정', 'NEW-01a, NEW-02b, INT-4b, VER-0923', 'PM 9/23 18:33: E42 LEFTOVER_REMAIN isolate→pause(정책 격리 갈래 이송 없음 발견) · E43 #102 민범진 안 채택(충돌 해소 뒤 merge) · #103 한석형 변경 요청', '황인재 9/23 18:29', 'H']




# ---------------------------------------------------------------- 9/23 18:39 PR #103 한석형 merge — flow LEFTOVER_REMAIN 물리 격리 갈래(HOME 경유) · E42 라 시연 미사용
P1839 = 'PM 9/23 18:39(date 값)'
EDIT.update({
 'NEW-01a':  dict(note_add=P1839 + ': ✅ **PR #103 merge(ceccf45)** — 한석형이 PM 제안 (a) 로 수정: handling.py 는 main 그대로(J1-only 검증 경로) · flow.py 에 LEFTOVER_REMAIN → **HOME(들고) → 격리 → HOME** 갈래 추가(510 통과). E42 로 main 정책은 pause 라 **시연에서는 이 갈래를 타지 않음** · 정책을 isolate 로 되돌릴 때(동결 뒤 B) 살아남 · 흐름 전체 🟡 INT-4b(조각은 실기 있음: WEIGH→HOME 잔반 버리기 · HOME→J1-only #90) · 참고 6건(결과 무시 로그 · 상수 · 시험 1개 · SEAT_FAIL 갈래 · 컵 🟡 · 민범진 절)'),
 'VER-0923': dict(note_add=P1839 + ': #103 merge(시연 경로 무관) · 열린 PR = #102 뿐(충돌 해소 대기)'),
})
HISTORY184 = ['v23.4', '✅ merge', 'NEW-01a, VER-0923', 'PM 9/23 18:39: #103 한석형 merge — flow LEFTOVER_REMAIN HOME 경유 격리 갈래(E42 pause 라 시연 미사용 · 🟡 INT-4b)', '황인재 9/23 18:29', 'H']




# ---------------------------------------------------------------- 9/23 18:49 PR #102 민범진 merge — 넛지 재개 뒤 SAFE_STOP 자동 복구(E43)
P1848 = 'PM 9/23 18:49(date 값)'
EDIT.update({
 'NEW-02b':  dict(status='완료', prog='0.95', note_add=P1848 + ': ✅ **PR #102 merge(924ee79)** — E43(황인재 18:29) 민범진 안 그대로: (상태별 set_robot_control → STANDBY 대기) + flow 케이블 이상 재개 두 자리·TOOL_LOST 넛지 경로 · 충돌은 wipe.py 변경 제거(#101 유지)로 해소 · 512 통과 · 실기 ✅ 1회(그릇 → weigh 케이블 이상 → 넛지 → 자동 복구 → soap 진입) · 🟡 TOOL_LOST 넛지 경로 0회(INT-4b) · 참고: 상태 9/10 복구 코드 미확인 · client 재사용'),
 'VER-0923': dict(note_add=P1848 + ': #102 merge → **열린 PR 0** · 남은 🟡 = flow_node TOOL_LOST 1회 · #98 실기 · 튜닝 PR(F4 · main #102/#103/E42 합친 뒤)'),
})
HISTORY185 = ['v23.5', '✅ merge', 'NEW-02b, VER-0923', 'PM 9/23 18:49: #102 민범진 merge — 넛지 재개 뒤 SAFE_STOP 자동 복구(E43 · 실기 1회 ✅ · TOOL_LOST 경로 🟡) · 열린 PR 0', '황인재 9/23 18:29', 'H']




# ---------------------------------------------------------------- 9/23 19:46 PR #104 박진용 merge — 그릇 세척 속도 튜닝 · 컵 회전 사전검사(⑰) · wipe.py 정리
P1950 = 'PM 9/23 19:46(date 값)'
EDIT.update({
 'INT-4c':   dict(note_add=P1950 + ': ✅ **PR #104 merge(bb14f43)** — 박진용 probe 실기로 f3.wipe_bowl `rot_vel_deg_s` 400→1600 · `twist_deg` 18→10 · `spiral_time_s` 3.0→2.0(1.7 은 알람 1209) · turns/wall_arc/lin_vel 은 시도 뒤 원복 · 510 통과 · 🟡 **회전 속도는 공용 함수가 상한으로 안 자르므로 시연 배속 0.5 면 800°/s 명령 — 실기는 0.3 추정(배속 미기재 · PR 에 확인 요청) → REH-02 에서 그릇 1개 0.5 확인 · 알람이면 400/18/3.0 복귀**'),
 'VER-0923': dict(note_add=P1950 + ': ⑰ wipe_cup 회전 속도 사전검사 되살림(#104 · 컵 probe 에서 326.5°/s 초과가 안 걸리던 구멍 실측) ✅ · #104 merge · 열린 PR 0'),
 'REH-02':   dict(note_add=P1950 + ': 체크리스트 추가 — **그릇 1개 0.5 배속으로 닦기(wipe_bowl) 경고음·알람 확인**(#104 새 속도값 · 0.5 실기 없음) → 있으면 params f3.wipe_bowl 세 값 400/18/3.0 복귀'),
})
HISTORY186 = ['v23.6', '✅ merge', 'INT-4c, VER-0923, REH-02', 'PM 9/23 19:46: #104 박진용 merge — 그릇 닦기 속도 튜닝(1600/10/2.0 · probe 실기) · 컵 회전 사전검사 ⑰ · force_check 삭제 · 🟡 0.5 배속은 REH-02 확인', '황인재 9/23 18:29', 'H']




# ---------------------------------------------------------------- 9/23 20:22 F4 통합 실기 0.5 완주(17:39) — #104 0.5 통과 · 튜닝 3차 통과
F2015 = 'F4 9/23 20:15 · PM 20:22'
EDIT.update({
 'INT-4a':   dict(prog='0.95', note_add=F2015 + ': ✅ **통합 실기 0.5(flow_node · 그릇 2 → 컵 2) plan 완료 · 무정지 · 17분 39초**(19:57:08~20:14:47 · tune 0a7455e = main #104 까지 + 튜닝 1~3차) · ros bag `_bags/0923_full_0.5`(20분 12초) · 알람 1209·3210 없음(3205/3206 특이점 알림만 · 적재 경로) · 튜닝 3차 첫 실기 통과(감시 0 곧게 놓기 8회 · 잔반 털기 스플라인 1회 · 솔 반납 4회) · **튜닝 PR 은 황인재 "열어" 대기** · 다음 튜닝 후보: 기본 배속 0.3 · 홈 B 179.7 · 컵 RINSE 84 s(재파지 45 mm 감시)'),
 'INT-4c':   dict(prog='0.9', note_add=F2015 + ': ✅ 사이클 타임 **리허설 19:39 → 17:39**(0.5 · 그릇 2 컵 2) · 단계별(그릇 1) PICK 10.5 · WEIGH 35 · SEAT 14.5 · SOAP 15.5 · WIPE 30 · RINSE 56 · RACK 43 s · 그릇 2 잔반 루프(72.6→23.2 g) 118 s · 컵 274/283 s · **#104 새 닦기 값 0.5 첫 실기 통과**(힘 |Fz| 그릇 평균 2.64/2.06 · 최대 6.91/6.34 N · 컵 1.82/3.39 N) → 🟡 해소'),
 'REH-02':   dict(note_add=F2015 + ': ✅ "그릇 1개 0.5 닦기 경고음·알람 확인" 항목 **오늘 통합 실기에서 완료** — 9/29 오전에는 재확인만'),
 'VER-0923': dict(note_add=F2015 + ': #104 🟡(0.5 배속) 해소 · 통합 실기 0.5 완주 · 남은 🟡 = flow_node TOOL_LOST 1회 · #98 EMPTY_ZONE→HOME · 튜닝 PR 검토'),
})
HISTORY187 = ['v23.7', '✅ 실기', 'INT-4a, INT-4c, REH-02, VER-0923', 'F4 9/23 20:15: 통합 실기 0.5 완주 17:39(무정지 · bag) · #104 닦기 값 0.5 통과 · 튜닝 3차 통과 · 튜닝 PR "열어" 대기', '황인재 9/23 20:15', 'H']




# ---------------------------------------------------------------- 9/23 20:33 PR #105 튜닝 1~3차 merge(F4 · 황인재) — E44 감시 0 + 완충
P2033 = 'PM 9/23 20:33(date 값)'
EDIT.update({
 'INT-4a':   dict(status='완료', prog='1.0', note_add=P2033 + ': ✅ **PR #105 merge(8874dfc)** — 튜닝 1~3차 15 파일(WEIGH 이동 단계 제거 · 수세미 J6 동치각 j6_symmetric · RINSE.BOWL A 122.7 · 감시 0 곧게 놓기 + 15 mm 완충(E44) · WASTE 스플라인 · regrip_watch 45 · watch_step 5 · rig --step) · 532 통과 · 실기 = 0.5 통합 17:39 완주 · 🟡 1.0 재확인 · **main 8874dfc = 시연 코드 후보** · 튜닝 브랜치 삭제(다음은 새 브랜치)'),
 'VER-0923': dict(note_add=P2033 + ': 튜닝 PR #105 merge · 열린 PR 0 · 남은 🟡 = 1.0 배속(시연 무관) · flow_node TOOL_LOST 1회 · #98 EMPTY_ZONE→HOME · 결정 대기: 동결·v1.0-demo 태그 시각 · 기본 배속 0.3 · 홈 B 179.7 · 컵 RINSE 84 s'),
 'INT-4b':   dict(note_add=P2033 + ': E44(감시 0)로 RACK_JAM·홀더 밀림 판정은 시연 코드에서 발생하지 않음 — 실패 시나리오 목록에서 제외(충돌 감지 SAFE_STOP 이 마지막 보호)'),
})
HISTORY188 = ['v23.8', '✅ merge', 'INT-4a, INT-4b, VER-0923', 'PM 9/23 20:33: #105 튜닝 1~3차 merge(0.5 통합 17:39 완주 · E44 감시 0+완충) · main 8874dfc 시연 코드 후보 · 열린 PR 0', '황인재 9/23 20:2x', 'H']




# ---------------------------------------------------------------- 9/23 20:39 황인재: 9/29(화) 오전에 나머지 예외 시나리오 실기 — 오늘은 정상 흐름의 잔반 루프 1개만 봤다
H2040 = '황인재 9/23 20:39'
EDIT.update({
 'INT-4b':   dict(slots=S('9/29 오전'), owner='H(S,P,M)', status='시작 전',
                  task='INT-4b 예외 시나리오 실기(시연 코드 main 8874dfc · 0.5) — ① 잔반 과다 → 멈춤(E42) → 재개(다시 잼) / 중단(HOME → J1-only 격리 → 다음 용기) 그릇·컵 ② 빈 구역(EMPTY_ZONE → SKIPPED · HOME 복귀 #98) ③ 툴 놓침(TOOL_LOST → PAUSED → 넛지·HMI 재개 → 재PICK · flow_node 경로) ④ 케이블 장력 → 넛지 재개 → SAFE_STOP 자동 복구(#93·#102) ⑤ 정지·재개·중단 버튼(HMI · 중단 정리 = HOME → 툴 반납 → 격리 → HOME) ⑥ (선택) 그리퍼 놓침 GRIP_FAIL → 멈춤 ⑦ (결정 시) 세제 펌프. 제외: RACK_JAM(E44 판정 없음)',
                  note_add=H2040 + ': **9/29(화) 오전으로 이동** — 오늘 통합 실기(0.5 · 17:39)에서 예외는 "정상 흐름 중 잔반 남음 → 털기 → 재측정" 1개만 봤다. 나머지 예외 시나리오 ①~⑤(⑥⑦ 선택)를 화요일 오전 리허설(REH-02) 뒤·14:00 시연 전에 실기. 대본(넣는 법 · 볼 것 · 통과 기준 · 복구 방법)은 F4 가 추석 중 준비(원격) · 기능 담당이 옆에서(①③ 한석형·박진용 · ④ 민범진 · ⑤ 황인재 HMI) · 실기 순서는 위험 낮은 것부터(⑤ → ② → ① → ③ → ④) · 각 1회 · 실패하면 시연에서는 그 시나리오를 빼고 정상 흐름만(E28)'),
 'REH-02':   dict(note_add=H2040 + ': 9/29 오전 순서 — 브링업 → 좌표 재현 10분 → **정상 흐름 리허설 1회(0.5 · #104 닦기 값 재확인 포함)** → **INT-4b 예외 시나리오 ①~⑤** → 시연 직전 기준값 2종. 예외 실기가 길어지면 시연 대본에 넣을 것만 남기고 나머지는 시연 뒤'),
 'DEMO-01':  dict(note_add=H2040 + ': 새 기능 시연 = 오전 INT-4b 에서 **통과한 시나리오만** 넣는다(실패한 것은 정상 흐름만 · E28)'),
})
HISTORY189 = ['v23.9', '📅 일정', 'INT-4b, REH-02, DEMO-01', '황인재 9/23 20:39: 예외 시나리오 실기(잔반 과다 멈춤·재개/중단 격리 · 빈 구역 · 툴 놓침 넛지 · 케이블 넛지 · 정지/재개/중단 버튼)를 9/29(화) 오전 REH-02 뒤로 — 오늘은 정상 흐름 잔반 루프 1개만 확인', '황인재 9/23 20:39', 'H']




# ---------------------------------------------------------------- 9/24 17:54 동결(E45 · v1.0-demo = 8874dfc) · 기본 배속 0.5(E46) · ③④ 는 9/29 오전 실기 · INT-4b 대본 준비됨
P0924 = 'PM 9/24 17:54(date 값)'
EDIT.update({
 'INT-4a':   dict(note_add=P0924 + ': ✅ **동결(E45 · 황인재 9/23 밤) — 태그 `v1.0-demo` = main 8874dfc**(PM 9/24). 이후 기능 추가 금지 · 동결 뒤 코드는 시연 경로 무영향 안전장치·문서만 · 9/29 오전 실기 확인 뒤 반영 · main 이 달라지면 리허설 통과 뒤 `v1.0-demo.1`'),
 'INT-4b':   dict(note_add=P0924 + ': ✅ 대본 준비됨(F4 · 브랜치 injae/20260929-INT-4b-script · docs/test_logs/20260929_INT-4b_예외시나리오_대본.md · PR 은 "열어" 뒤) — 순서 ⑤→②→①→③→④ · ⑥ GRIP_FAIL 제외 권고 · 예상 1시간 · 화요일 추가 항목: **홈 B 방향 179.7 · 컵 재파지 걸음 3 → 5 mm**(황인재 9/23 밤 · 실기로 결정 · 준비 코드 f1.regrip_step_mm 기본 3 = 동작 불변) · 케이블 떨림 상한 50→80 은 결정 대기(오늘 45 g 오탐 여지)'),
 'VER-0923': dict(status='완료', prog='1.0', note_add=P0924 + ': 9/23 검증 마감 — 동결 v1.0-demo · 남은 🟡(1.0 배속 · flow_node TOOL_LOST · #98 EMPTY_ZONE→HOME)은 9/29 오전 INT-4b/REH-02 로 이관 · **E46 기본 배속 0.5**(F4 tune2 · PR 대기)'),
})
HISTORY190 = ['v24.0', '🔒 동결', 'INT-4a, INT-4b, VER-0923', 'PM 9/24 17:54: E45 동결 태그 v1.0-demo(main 8874dfc) · E46 기본 배속 0.5(tune2 PR 대기) · 홈 B 179.7·재파지 걸음 5 는 9/29 오전 실기 · INT-4b 대본 준비됨', '황인재 9/23 밤', 'H']




# ---------------------------------------------------------------- 9/24 19:23 황인재: 떨림 상한·넛지 힘은 화요일 실기로(민범진·박진용) · 세제 펌프는 화요일 구매 뒤 확인(한석형)
H0924 = '황인재 9/24 19:23'
EDIT.update({
 'INT-4b':   dict(note_add=H0924 + ': ④ 케이블 항목에서 **두 값을 실기로 정한다** — (1) 떨림 상한 `f2.limits.max_weigh_spread_g`(50 · 정상 무게 재기의 떨림 8~45 g 기록 vs 케이블을 실제로 당겼을 때 값 사이) (2) 넛지 힘 `f2.nudge`(케이블 · ≈5 N) · `cell.limits.nudge_force_n`(툴 놓침 · 15 N) — 얼마나 세게 쳐야 재개되는지. 담당 민범진(케이블) · 박진용(툴) · 값 변경은 E45(b) 절차'),
 'NEW-01b':  dict(slots=S('9/29 오전'), status='진행 중', note_add=H0924 + ': **9/29 오전 펌프 구매 → 단독 확인(한석형) → 시연 포함 결정** — 켜려면 `f1.soap_pump.enabled: true`(동결 뒤 설정 변경 · 리허설 통과 뒤 · E45(b)) · 대본 ⑦ 은 "결정 시"'),
})
HISTORY191 = ['v24.1', '📅 일정', 'INT-4b, NEW-01b', '황인재 9/24 19:23: 케이블 떨림 상한·넛지 힘은 9/29 오전 실기로 결정(민범진·박진용) · 세제 펌프는 9/29 오전 구매 뒤 단독 확인(한석형)', '황인재 9/24 19:23', 'H']




# ---------------------------------------------------------------- 9/24 19:57 황인재 결정 3: 떨림 상한 80(E47) · 넛지 15 N·2번 통일(E48) · 대용품 94 g 1개 + 화요일 무게 확인(E39 종결)
H0924b = '황인재 9/24 19:57'
EDIT.update({
 'INT-4b':   dict(note_add=H0924b + ': **E47** 떨림 상한 50 → 80(main 반영 · ④ 에서 확인) · **E48** 넛지 힘·횟수 통일 15 N·2번(힘은 설정 · 2번 치기는 코드 = F4 tune2 · ③④ 실기 · 실패 시 태그 v1.0-demo 옛 동작) · **⓪ 대용품 무게 확인 추가**: 94 g 을 그릇·컵에 넣고 각 3회 읽어 모두 ≥ 65 g 이면 그대로, 하나라도 60 g 아래면 2개로(또는 기준 조정) — 리허설 앞에 10분'),
 'DEMO-01':  dict(note_add=H0924b + ': **E39 종결 — 대용품 94 g 1개를 그릇 2·컵 2 중 임의 용기에**(판정 기준 50 g 유지 · 오전 ⓪ 무게 확인 통과가 조건) · 시연 직전 빈 용기 기준값 2종 필수'),
})
HISTORY192 = ['v24.2', '✅ 결정', 'INT-4b, DEMO-01', '황인재 9/24 19:57: E47 떨림 상한 80 · E48 넛지 15 N·2번 통일(코드 F4 · 9/29 실기) · E39 종결 대용품 94 g 1개 임의 용기 + 오전 무게 확인 ⓪', '황인재 9/24 19:57', 'H']




# ---------------------------------------------------------------- 9/24 21:08 황인재 결정(F4 창): 홈 B 변경 안 함(E49) · 기본 배속은 9/29 1.0 뒤(E46 보류) · 컵 재파지 순응 하강 제거(E50) · E48 코드 tune2
H0924c = '황인재 9/24 21:08'
EDIT.update({
 'INT-4b':   dict(note_add=H0924c + ': **E49** 홈 B 179.7 변경 안 함(스펀지 절단으로 해결) · **E46 보류** 배속 기본값은 화요일 **⑧ 1.0 배속 통합 1바퀴** 뒤 결정 · **E50** 컵 재파지 순응 하강 제거(`regrip_watch_mm 0` · 곧게 + 15 mm 완충 · RINSE 84 → ≈45 s · 🟡 컵 실기 · 실패 시 45) · **E48 2번 치기 코드 완료**(tune2 a293b17 · 공용 감지기 taps/window · 530 통과) → 화요일 ③④ 는 **tune2 코드로 실기**(F4 작업 폴더) → 통과하면 PR(실기 결과) → merge → v1.0-demo.1 · 대본 갱신됨(⓪ 94 g · ③④ 2번 · ④ 80 g · §3-2 재파지 곧게 · ⑧ 1.0)'),
 'DEMO-01':  dict(note_add=H0924c + ': 시연 코드 = 화요일 오전 실기 통과분(tune2 merge 시 `v1.0-demo.1`) · 통과 못 하면 `v1.0-demo`(8874dfc)'),
})
HISTORY193 = ['v24.3', '✅ 결정', 'INT-4b, DEMO-01', '황인재 9/24 21:08(F4 창): E49 홈 B 변경 안 함 · E46 기본 배속 보류(9/29 1.0 1바퀴 뒤) · E50 컵 재파지 순응 하강 제거(🟡 9/29) · E48 2번 치기 코드 tune2 완료 → 화요일 tune2 코드로 실기', '황인재 9/24 21:08', 'H']




# ---------------------------------------------------------------- 9/24 23:11 황인재(PM 창): 배속 장치는 내 설계 아님 — 화요일 1.0 검증 통과면 시연도 1.0(E40 갱신)
H0924d = '황인재 9/24 23:11'
EDIT.update({
 'DEMO-01':  dict(note_add=H0924d + ': **시연 배속 = 화요일 ⑧ 1.0 통합 1바퀴 통과 시 1.0**(E40 의 0.5 갱신 · 배속 장치는 코드만 두고 시연에서 안 씀) · 실패하면 0.5 · 대용품 94 g 1개'),
 'INT-4b':   dict(note_add=H0924d + ': ⑧ 1.0 통합 1바퀴 = **시연 배속 결정 시험**(통과 → 1.0 · 실패 → 0.5) — 18:07 솔 반납 SAFE_STOP(완충 전) 재현 여부 · 툴 반납·적재 곧게 놓기 충격 · 컵 재파지 곧게(E50) 를 1.0 에서 본다 · 순서는 0.3 → 0.5 → 1.0'),
})
HISTORY194 = ['v24.4', '✅ 결정', 'DEMO-01, INT-4b', '황인재 9/24 23:11: 화요일 1.0 통합 1바퀴 통과면 시연 배속 1.0(E40 갱신 · 배속 장치는 두되 안 씀) · 실패면 0.5', '황인재 9/24 23:11', 'H']




# ---------------------------------------------------------------- 9/24 23:40 황인재 21:5x 확정(F4 창): 화요일 검증 = 전체 흐름 2번 · 1.0 · tune2 코드 (E51)
H0924e = '황인재 9/24 21:5x · PM 23:40'
EDIT.update({
 'INT-4b':   dict(owner='H(전원)', task='INT-4b 9/29 오전 검증 — 단독 rig 없이 **전체 흐름 2번**(코드 tune2 = main + E48 넛지 2번 + E50 컵 재파지 곧게 · 배속 1.0 · 로봇 ≈30분 + 준비 10분): ① 기본 흐름 1회(그릇 2·컵 2·94 g 1개 · 손 안 댐 · 동결 확인 · E50 첫 실기) ② 예외 6개 1회(그릇 2 · 컵 구역 비움 · 그릇 2 에 94 g 테이프 고정): 케이블 흔들기→톡톡 2번 · 세제에서 정지→재개 · 나선에서 수세미 빼기→TOOL_LOST→2번 톡톡→재PICK · 그릇 2 잔반 남음 멈춤→대용품 제거→재개 · 세제(수세미 든 채) 정지→중단(HOME→반납→격리→HOME) · 컵 구역 빈손→SKIPPED→HOME',
                  note_add=H0924e + ': **E51 확정** — 준비 10분(브링업 · bag · 기준값 2종 · 94 g 그릇·컵 각 1회 ≥ 65 g → 1개 확정) → 1회 기본(≈14분 · 통과 = 무정지 완주 + 알람 없음 + 파지 폭 정상 · 1.0 완주 E46 · E44 · #104 · E50 · 잔반 루프 · 떨림 80) → 2회 예외 6개(≈12분). 뺀 것: 컵 잔반 중단 · GRIP_FAIL · 세제 펌프 · 0.3/0.5 바퀴 · 단독 rig. 실패 대응: E50→45 · E48→1번 · 1.0→0.5 · 나머지는 시연 배치로 회피. 담당: 버튼 황인재 · 케이블 민범진 · 수세미 빼기 박진용 · 대용품 한석형 · E-Stop 1명 · 기록 PM. 대본 §1-2 갱신됨(PR "열어" 대기). 통과 → PR(실기 결과) → merge → v1.0-demo.1'),
 'REH-02':   dict(note_add=H0924e + ': 9/29 오전 = **INT-4b 의 1회 기본 흐름이 리허설을 겸한다**(별도 0.3/0.5 바퀴 없음 · 1.0) · 좌표 재현 10분은 준비 10분에 포함(브링업 · bag · 기준값 2종 · 94 g 읽기)'),
 'DEMO-01':  dict(note_add=H0924e + ': **시연 배속 1.0 확정**(화요일 통과 시 그대로 동결 · 배속 장치는 시연 뒤 삭제) · 시연 코드 = 화요일 통과분 v1.0-demo.1(실패 항목은 되돌린 설정으로)'),
 'NEW-01b':  dict(note_add=H0924e + ': 세제 펌프는 화요일 검증 2번에서 **제외**(황인재 21:5x) — 구매 뒤 단독 확인만 · 시연 포함은 별도 결정'),
})
HISTORY195 = ['v24.5', '✅ 결정', 'INT-4b, REH-02, DEMO-01, NEW-01b', '황인재 9/24 21:5x(F4 창): E51 화요일 검증 = 전체 흐름 2번(기본 1회 + 예외 6개 1회) · 1.0 · tune2 코드 · 준비 10분 · 시연 배속 1.0 확정 · 펌프는 검증에서 제외', '황인재 9/24 21:5x', 'H']




# ---------------------------------------------------------------- 9/24 23:48 황인재 22:1x(F4 창): 넛지는 1번만(2번 치기 철회 · 15 N 유지)
H0924f = '황인재 9/24 22:1x · PM 23:48'
EDIT.update({
 'INT-4b':   dict(note_add=H0924f + ': **E48 변경 — 넛지 횟수 1번**(2번 치기 철회 · 힘 15 N 통일 유지 · tune2 `nudge_taps 1` d306742 · 530 통과 · taps 코드는 남김). 예외 ①③ 은 톡톡 1번으로 · 실패 대응 목록에서 "E48→1번" 제거'),
})
HISTORY196 = ['v24.6', '✅ 결정', 'INT-4b', '황인재 9/24 22:1x(F4 창): 넛지는 1번만 쳐도 재개(2번 철회 · 15 N 유지) — tune2 설정 1 · 대본 갱신', '황인재 9/24 22:1x', 'H']




# ---------------------------------------------------------------- 09/25 13:48 황인재: 추석 순서 = ① HMI 완성(F4) → ② 문서·아키텍처 최신화(PM) → ③ PPT · 끝난 행 닫기
H0925 = '황인재 09/25 13:48'
EDIT.update({
 'INT-4':    dict(slots=S('9/24~28 오전', '9/24~28 오후'), status='진행 중', note_add=H0925 + ': **추석 1순위 — HMI 완성(F4)**: 시작·일시 정지·재개·중단 버튼 · 단계 카드 · "일시 정지됨 — 단계" 문구(케이블·툴 놓침·잔반 멈춤 안내) · 용기별 이력 · 넛지 비프 · 끊김 표시 (되면 팔레트 그림·소모품 바) · 확인 = bag `_bags/0923_full_0.5` 재생 + fake_state_pub · 실제 flow_node 연결은 9/29 준비 10분 · 완료 뒤 PM 이 문서·아키텍처 최신화 시작'),
 'UT-F4':    dict(slots=S('9/24~28 저녁'), note_add=H0925 + ': INT-4 와 함께(TC-11 · bag 재생으로)'),
 'DOC-05':   dict(note_add=H0925 + ': 순서 ② — **HMI 완성 뒤** as-built·결과표·아키텍처(HMI 화면 포함) 최신화(PM) · 최종 수치는 9/29 저녁'),
 'DOC-02':   dict(note_add=H0925 + ': 순서 ③ — 문서 최신화 뒤 PPT(강사 5장 양식 · 원문 양식은 황인재가 _upload 에)'),
 'ARCH-01':  dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ 9/23 Archify 로 다시 그림(동결 판 · 카드 4개 · 9/24 예외 처리 카드) — 남은 것은 DOC-05 에서 HMI 화면 반영'),
 'INT-4c':   dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ 0.5 기준 17분 39초(9/23 20:14 · 단계별 표) · 1.0 값은 9/29 INT-4b 기본 흐름에서'),
 'INT-4d':   dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ 원본 영상 17분(9/23 · 황인재 촬영 · 노션은 드라이브 링크로) · v1.0-demo 태그(9/24) · 동결(E45)'),
 'FIX-01':   dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ 9/23 튜닝 1~3차(PR #105) + hotfix #101 로 마감'),
 'V-24':     dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ 즉시 정지·재개는 9/23 통합 실기·리허설에서 확인(정지 버튼 · 넛지 재개) · 남은 건 HMI 버튼 연결(INT-4)'),
 'F1-04':    dict(status='완료', prog='1.0', note_add=H0925 + ': ✅ rack_place 4칸 실기(9/23 리허설 3회) · E44 로 순응 삽입·RACK_JAM 판정은 제거'),
 'SAFE-01':  dict(note_add=H0925 + ': 노션 안전표 값 확인(박진용) — E44·E47·E48·E50 반영본으로 갱신 필요(SDD §7·§8 · 추석)'),
})
HISTORY197 = ['v24.7', '📅 일정', 'INT-4, UT-F4, DOC-05, DOC-02, ARCH-01, INT-4c, INT-4d, FIX-01, V-24, F1-04, SAFE-01', '황인재 09/25 13:48: 추석 순서 ① HMI 완성(F4) → ② 문서·아키텍처(PM) → ③ PPT · 끝난 행 6개 완료 처리', '황인재 09/25 13:48', 'H']


def main(out):
    gen_todo.EASY.update(EASY)
    for _t in DELETE: EDIT.pop(_t, None); MOVE.pop(_t, None)
    NEW[:] = [_n for _n in NEW if _n[0] not in DELETE]                 # 지운 행은 새 행 목록에서도 뺀다(다시 만들지 않게)
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    # 1) 새 행
    for tid, after, like, cat, task, owner, status, slots, deliv, crit, note in NEW:
        if has(tl, ID, tid): continue
        n = new_timeline_row(tl, tl.rows[tl.find(ID, like)], slots, A=None, B=cat, C=task, D=owner, E='0.0', F=status, **{ID: tid})
        tl.insert(tl.find(ID, after) + 1, n)
        q = d.rows[d.find('A', like)].clone()
        for c, v in zip('ACDEFG', [tid, task, owner, deliv, crit, note]): q.set(c, v)
        d.insert(d.find('A', after) + 1, q)
    # 2) 셀 고치기
    for tid, e in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if 'task' in e: r.set('C', e['task'])
        if 'owner' in e: r.set('D', e['owner'])
        if 'status' in e and tl.text(r, 'F').strip() != '완료':   # 시트에서 이미 완료인 행은 되돌리지 않는다(황인재가 직접 완료 처리한 것 보호)
            r.set('F', e['status'])
        if 'prog' in e and tl.text(r, 'F').strip() != '완료': r.set('E', e['prog'])
        if 'slots' in e:
            try: set_slots(r, e['slots'])
            except ValueError:                           # 색 칸이 하나도 없는 행(이미 비운 행 · 보류였던 행)
                if e['slots']: _paint_like_neighbor(tl, r, e['slots'])
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, k in (('C', 'task'), ('D', 'owner'), ('E', 'deliv'), ('F', 'crit'), ('G', 'note')):
                if k in e: q.set(c, e[k])
            if 'note_add' in e and e['note_add'] not in d.text(q, 'G'):     # 진척 메모는 앞에 덧붙인다(여러 번 돌려도 한 번만)
                q.set('G', e['note_add'] + ' · ' + d.text(q, 'G'))
    # 2-1) 행 삭제 (황인재 9/22: 안 해도 되는 작업은 지운다) — Time Line 과 상세 둘 다 · 구역 이름표(A)는 다음 행에 넘긴다
    for tid in DELETE:
        for sh, col in ((tl, ID), (d, 'A')):
            try: i = sh.find(col, tid)
            except KeyError: continue
            row = sh.rows[i]
            if sh is tl and sh.text(row, 'A').strip() and i + 1 < len(sh.rows) and row.cells.get('A'):
                sh.rows[i + 1].cells['A'] = list(row.cells['A'])
            sh.merges = [mm for mm in sh.merges if mm[1] is not row and mm[3] is not row]
            sh.rows.pop(i)
    # 3) 완료 행은 진행 1.0 + **간트 칸을 회색으로**(황인재 9/20: G6 칸처럼 — 완료한 일은 회색). PM 이 시트에서 완료로 바꾼 행 포함
    gray = tl.rows[tl.find(ID, 'DOC-01a')].style('G')          # G6 = 회색 칸의 서식(내보낼 때마다 번호가 달라져서 매번 찾는다)
    ocols = open_gantt_cols()                                  # 닫힌 칸(주말 저녁 열 배경)은 건드리지 않는다
    for r in tl.rows:
        if tl.text(r, 'F').strip() == '완료' and tl.text(r, ID).strip():
            r.set('E', '1.0')
            styles = [r.style(c) for c in ocols if r.style(c) is not None]
            if not styles: continue
            blank = max(set(styles), key=styles.count)
            for c in ocols:
                if r.style(c) not in (None, blank, gray): r.set(c, style=gray)
    # 4) 팀(구역) 이동
    def team_of(i):
        while i >= 0 and not tl.text(tl.rows[i], 'A').strip(): i -= 1
        return tl.text(tl.rows[i], 'A').strip() if i >= 0 else ''
    for tid, (team, after) in MOVE.items():
        src = tl.find(ID, tid); dst = tl.find(ID, after)
        if team_of(src) != team and src != dst + 1:
            if tl.text(tl.rows[src], 'A').strip():           # 구역 첫 행이면 이름표를 다음 행에 넘긴다
                tl.rows[src + 1].cells['A'] = list(tl.rows[src].cells['A'])
            tl.move(src, dst + 1)
            up = tl.rows[tl.find(ID, after)]
            a_style = up.style('A') if not tl.text(up, 'A').strip() else tl.rows[tl.find(ID, after) + 2].style('A')
            tl.rows[tl.find(ID, tid)].set('A', None, style=a_style)
            qs = d.find('A', tid); qd = d.find('A', after)
            if qs != qd + 1: d.move(qs, qd + 1)
        d.rows[d.find('A', tid)].set('B', team)
    # 5) 마일스톤·로봇 슬롯
    m = b.sheet('마일스톤·로봇 슬롯')
    k_mile = m.find('A', '마일스톤'); k_slot = m.find('A', '로봇 슬롯', prefix=True)
    for i, r in enumerate(m.rows):
        key = m.text(r, 'A').strip()
        if i < k_mile and key in LECTURE:
            r.set('B', LECTURE[key][0]); r.set('C', LECTURE[key][1])
        elif k_mile < i < k_slot and key in GATE:
            for c, v in GATE[key].items(): r.set(c, v)
        elif i > k_slot and key in SLOT:
            for c, v in SLOT[key].items(): r.set(c, v)
    # 6) 규칙
    ru = b.sheet('규칙')
    for r in ru.rows:
        key = (ru.text(r, 'A').strip(), ru.text(r, 'B').strip())
        if key in RULES: r.set('B', RULES[key][0]); r.set('C', RULES[key][1])
    ru.rows[0].set('A', f'운영 규칙 (PreWash-Cell 일정표 {VERSION})')
    for rule in NEW_RULES:
        if has(ru, 'A', rule[0]):
            r_ = ru.rows[ru.find('A', rule[0])]; r_.set('B', rule[1]); r_.set('C', rule[2])
        else:
            k = ru.first_empty(); n = ru.rows[k - 1].clone()
            for c, v in zip('ABC', rule): n.set(c, v)
            ru.rows[k] = n
    # 7) 변경이력
    h = b.sheet('변경이력')
    for hist in (HISTORY, HISTORY2, HISTORY3, HISTORY4, HISTORY5, HISTORY6, HISTORY7, HISTORY8, HISTORY9, HISTORY10, HISTORY11, HISTORY12, HISTORY13, HISTORY14, HISTORY15, HISTORY16, HISTORY17, HISTORY18, HISTORY19, HISTORY20, HISTORY21, HISTORY22, HISTORY23, HISTORY24, HISTORY25, HISTORY26, HISTORY27, HISTORY28, HISTORY29, HISTORY30, HISTORY31, HISTORY32, HISTORY33, HISTORY34, HISTORY35, HISTORY36, HISTORY37, HISTORY38, HISTORY39, HISTORY40, HISTORY41, HISTORY42, HISTORY43, HISTORY44, HISTORY45, HISTORY46, HISTORY47, HISTORY48, HISTORY49, HISTORY50, HISTORY51, HISTORY52, HISTORY53, HISTORY54, HISTORY55, HISTORY56, HISTORY57, HISTORY58, HISTORY59, HISTORY60, HISTORY61, HISTORY62, HISTORY63, HISTORY64, HISTORY65, HISTORY66, HISTORY67, HISTORY68, HISTORY69, HISTORY70, HISTORY71, HISTORY72, HISTORY73, HISTORY74, HISTORY75, HISTORY76, HISTORY77, HISTORY78, HISTORY79, HISTORY80, HISTORY81, HISTORY82, HISTORY83, HISTORY84, HISTORY85, HISTORY86, HISTORY87, HISTORY88, HISTORY89, HISTORY90, HISTORY91, HISTORY92, HISTORY93, HISTORY94, HISTORY95, HISTORY96, HISTORY97, HISTORY98, HISTORY99, HISTORY100, HISTORY101, HISTORY102, HISTORY103, HISTORY104, HISTORY105, HISTORY106, HISTORY107, HISTORY108, HISTORY109, HISTORY110, HISTORY111, HISTORY112, HISTORY113, HISTORY114, HISTORY115, HISTORY116, HISTORY117, HISTORY118, HISTORY119, HISTORY120, HISTORY121, HISTORY122, HISTORY123, HISTORY124, HISTORY125, HISTORY126, HISTORY127, HISTORY128, HISTORY129, HISTORY130, HISTORY131, HISTORY132, HISTORY133, HISTORY134, HISTORY135, HISTORY136, HISTORY137, HISTORY138, HISTORY139, HISTORY140, HISTORY141, HISTORY142, HISTORY143, HISTORY144, HISTORY145, HISTORY146, HISTORY147, HISTORY148, HISTORY149, HISTORY150, HISTORY151, HISTORY152, HISTORY153, HISTORY154, HISTORY155, HISTORY156, HISTORY157, HISTORY158, HISTORY159, HISTORY160, HISTORY161, HISTORY162, HISTORY163, HISTORY164, HISTORY165, HISTORY166, HISTORY167, HISTORY168, HISTORY169, HISTORY170, HISTORY171, HISTORY172, HISTORY173, HISTORY174, HISTORY175, HISTORY176, HISTORY177, HISTORY178, HISTORY179, HISTORY180, HISTORY181, HISTORY182, HISTORY183, HISTORY184, HISTORY185, HISTORY186, HISTORY187, HISTORY188, HISTORY189, HISTORY190, HISTORY191, HISTORY192, HISTORY193, HISTORY194, HISTORY195, HISTORY196, HISTORY197):
        if not has(h, 'A', hist[0]):
            k = h.first_empty(); n = h.rows[k - 1].clone()
            for c, v in zip('ABCDEF', hist): n.set(c, v)
            h.rows[k] = n
    # 7-1) 변경이력 시각 정정 (9/22 17:20 — 추정으로 적은 시각을 커밋 시각으로)
    for r in h.rows:
        v = h.text(r, 'A').strip()
        if v in FIX_TIMES:
            r.set('E', f'황인재 9/22 {FIX_TIMES[v]}')
    # 8) 고친 Time Line 을 다시 읽어 완료 목록·할일 시트를 채운다
    tmp = os.path.join(tempfile.mkdtemp(), 'stage.xlsx'); b.save(tmp)
    rows, det = timeline(load(tmp))
    done = b.sheet('완료 목록'); txt, ctr = d.rows[1].style('C'), d.rows[1].style('A'); n_old = len(done.rows)
    done.rows = done.rows[:1]
    for r in rows:
        if r['status'] != '완료' or not r['slots']: continue
        n = Row('', {})
        vals = [r['id'] or '—', r['task'], r['owner'], det.get(r['id'], {}).get('deliv', ''), ' '.join(r['slots'][0]), ' '.join(r['slots'][-1])]
        for c, v, st in zip('ABCDEF', vals, [ctr, txt, ctr, txt, ctr, ctr]): n.set(c, v, style=st)
        done.rows.append(n)
    while len(done.rows) < n_old: done.rows.append(Row('', {}))
    people = [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]
    rebuild_todo(b, lambda L: gen_todo.person_entries(rows, det, L), people)
    for name, _ in people:
        if name in b.paths: b.sheet(name).rows[0].set('A', TITLES[name])
    b.save(out); print('->', out)
    report(rows)
    return rows


def _paint_like_neighbor(tl, row, slots):
    """색 칸이 하나도 없는 행(보류였던 행 등)에 칸을 칠한다 — 색은 가까운 이웃 행의 작업 칸 색을 빌린다(회색 = 완료 색은 빼고)."""
    ocols = open_gantt_cols()
    styles = [row.style(c) for c in ocols if row.style(c) is not None]
    blank = max(set(styles), key=styles.count)
    gray = tl.rows[tl.find(ID, 'DOC-01a')].style('G')
    i = tl.rows.index(row)
    near = [j for d in range(1, 20) for j in (i - d, i + d) if 0 <= j < len(tl.rows)]
    donor = next((tl.rows[j].style(c) for j in near for c in ocols
                  if tl.rows[j].style(c) not in (None, blank, gray)), None)
    if donor is None:
        raise ValueError('이웃 행에도 색 칸이 없다')
    for d, p in slots:
        row.set(gantt_col(d, p), style=donor)


def report(rows):
    """사람별·칸별 부하(주도 + (참여)) — 브리핑·PM-01 제외, 5건 이상 ⚠. 주말 저녁에 남은 작업이 있으면 🚫 로 알린다."""
    load_ = collections.defaultdict(list); bad = []
    for r in rows:
        if r['status'] in ('완료', '보류') or r['id'] in ('BRF', 'PM-01'): continue
        lead = re.sub(r'\(.*?\)', '', r['owner']); part = ''.join(re.findall(r'\((.*?)\)', r['owner']))
        L = set('SMPH') if '전원' in lead else set(c for c in lead if c in 'SMPH')
        P = (set('SMPH') if '전원' in part else set(c for c in part if c in 'SMPH')) - L
        for dday, p in r['slots']:
            if '~' in dday or int(dday.split('/')[1]) > 23: continue
            if dday in ('9/19', '9/20') and p == '저녁': bad.append(r['id'])
            for w in L: load_[(dday, p, w)].append(r['id'])
            for w in P: load_[(dday, p, w)].append('(' + r['id'] + ')')
    order = {'오전': 0, '오후': 1, '저녁': 2}
    for w in 'SMPH':
        print('==', w)
        for k in sorted([k for k in load_ if k[2] == w and k[0] != '9/18'], key=lambda k: (int(k[0].split('/')[1]), order[k[1]])):
            print(f"  {k[0]} {k[1]} [{len(load_[k])}]{' ⚠' if len(load_[k]) >= 5 else ''} {' '.join(load_[k])}")
    print('🚫 주말 저녁에 남은 작업:', bad or '없음')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else OUT)
