# 개발 환경 설정 (env)

| 파일 | 내용 |
|---|---|
| [M0609_환경설정.md](M0609_환경설정.md) | Doosan M0609 + OnRobot RG2 개발 환경 설정. Ubuntu 24.04 LTS + ROS 2 Jazzy, GPU 유무 공통. 처음부터 하면 2~4시간 |

두산 드라이버 워크스페이스(`ws_dsr`) 위에 이 저장소 워크스페이스(`rokey_pjt01_ws`)를 겹쳐 쓴다. 시연은 GPU PC(로봇 제어 · 브링업 · `flow_node`)와 화면 PC(`hmi_bridge` · 브라우저 · 기록 DB) 2대로 했다.

## 목차

| 절 | 내용 |
|---|---|
| 먼저 읽어야 할 7가지 함정 | `DR_init` · `DSR_ROBOT2` import 실패, 포트 12345 점유, 티치펜던트와 ROS 동시 연결, venv 안 colcon, 지난 프로젝트 Fast DDS XML, `ROS_DOMAIN_ID` 중복, Secure Boot · MOK |
| 1. 시스템 기본 정보 확인 | OS · Python 버전과 ROS 2 설치 여부 확인 |
| 2. 패키지 목록 업데이트 | apt 업데이트 |
| 3. 그래픽 드라이버 | NVIDIA GPU PC 는 드라이버 설치 · MOK 등록 · PRIME 확인, 내장 그래픽 PC 는 RViz 경량화 |
| 4. Locale 설정 | UTF-8 로케일 |
| 5. ROS 2 Jazzy 설치 | 저장소 등록 · 데스크톱 · colcon 등 개발 도구(시스템에 설치) |
| 6. 개발 도구 설치 | 기본 도구 · VS Code |
| 7. Git 설정 · 저장소 클론 | 저장소를 `rokey_pjt01_ws` 로 받고 `PREWASH_WS` 로 가리킨다 |
| 8. 프로젝트 디렉터리 + M0609 · RG2 실행 환경 | 디렉터리 구조(`~/ws_cobot_pjt`) · 두산 드라이버 소스 · rosdep · 의존성 · 에뮬레이터(DRCF) · 빌드 · PYTHONPATH · 워크스페이스 겹치기 |
| 9. `.bashrc` 구성 | 백업 · 기존 설정 진단 · 팀 도메인 · 기본 격리 · 브링업과 점검 별칭 · source 순서 |
| 10. Virtual 모드 동작 확인 | 브링업 · 노드와 토픽 확인 · 예제 모션 · 실기 접속 점검 · PC 2대 통신(Discovery Server 또는 같은 유선 스위치) · 종료 |
| 11. 우리 워크스페이스 빌드 | 패키지 8개 빌드 · 화면 PC 도 같은 방법 |
| 12. 좌표 티칭 준비 | 좌표 · 힘 · 횟수를 두는 `cell.yaml` · `params.yaml` 양식 |
| 13. (선택) HMI 용 venv | 화면 PC 의 웹 서버 부품과 웹 화면 빌드용 Node.js |
| 최종 완료 체크리스트 · 자주 겪는 문제 · 작업 전 확인 | 점검표와 증상별 빠른 참조 |
