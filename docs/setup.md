# 실행 방법 — PreWash-Cell

> 전체 실행 절차다. 요약은 [README](../README.md#-설치--실행)에 있다.

**1~4 는 로봇 없이 Ubuntu 24.04(데스크톱) PC 한 대에서 그대로 따라 하면 된다.** 인터넷만 있으면 되고, 위에서 아래로 명령을 복사해 실행한다. 저장소는 2 의 `git clone` 이 `~/rokey_pjt01_ws` 에 받는다.

## 1. ROS 2 Jazzy 설치

이미 `/opt/ros/jazzy` 가 있으면 건너뛴다. [ROS 2 공식 설치 안내](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)와 같은 방법이다.

```bash
sudo apt update && sudo apt install -y software-properties-common curl
sudo add-apt-repository -y universe
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}')
curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update && sudo apt install -y ros-jazzy-ros-base ros-dev-tools
```

| 확인 | 통과 기준 |
|---|---|
| `ls /opt/ros/jazzy/setup.bash` | 파일이 있다 |

## 2. 받기 · 빌드 · 자동 시험

```bash
sudo apt install -y git python3-colcon-common-extensions python3-pytest python3-venv python3-pymodbus
cd ~ && git clone https://github.com/rokey9-d2/rokey_9_pjt1_D2.git rokey_pjt01_ws
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
python3 -m pytest -q src
```

| 확인 | 통과 기준 |
|---|---|
| 빌드 마지막 줄 | `Summary: 8 packages finished` |
| 시험 마지막 줄 | `616 passed, 9 skipped, 1 xfailed` · `failed` 없음 (건너뛴 9개는 3 의 화면 부품이 있어야 도는 시험) |

## 3. 운영 화면 부품

화면 서버용 가상환경과 웹 화면을 만든다.

```bash
sudo apt install -y nodejs npm
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install -r ~/rokey_pjt01_ws/requirements.txt
cd ~/rokey_pjt01_ws/src/f4_hmi/web && npm install && npm run build && cd ~/rokey_pjt01_ws
```

| 확인 | 통과 기준 |
|---|---|
| `npm run build` 끝 | `(Static)  prerendered as static content` · `src/f4_hmi/web/out/index.html` 이 생긴다 |

(선택) 화면 쪽 시험 — 2 와 같은 터미널(새 터미널이면 `cd ~/rokey_pjt01_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash` 먼저)에서:

```bash
~/venvs/hmi/bin/python3 -m pytest -q src/f4_hmi
cd src/f4_hmi/web && node --test test/*.test.mjs && cd ~/rokey_pjt01_ws
```

통과 기준은 `51 passed` 와 `pass 15` · `fail 0`.

## 4. 로봇 없이 실행

로봇과 드라이버 없이 메인 프로그램과 운영 화면을 띄운다. 기능은 가짜로 돈다.

```bash
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch prewash_bringup prewash_mock.launch.py
```

| 확인 | 통과 기준 |
|---|---|
| 터미널 | `IDLE — /flow/start 를 기다린다` 와 `HMI 서버를 연다 → http://localhost:8000` |
| 브라우저 <http://localhost:8000> | 화면이 뜨고 연결 점이 초록이다 |
| 화면의 **시작** 버튼 | 곧바로 그릇 2 · 컵 2 완료(기능이 가짜라 로봇 동작 시간이 없다) |

- `setup_io 를 건너뛴다` 경고 두 줄은 두산 드라이버가 없을 때 나오는 정상 안내다. 끌 때는 Ctrl+C.
- 브라우저 없이 확인하려면 새 터미널에서 `source /opt/ros/jazzy/setup.bash && export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST && ros2 service call /flow/start std_srvs/srv/Trigger` → `success=True`. 같은 방법으로 `stop` · `resume` · `abort` 도 부른다.

<details>
<summary><b>멈춤 화면 골라 보기 (가짜 상태 발행기)</b></summary>

4 의 launch 대신 터미널 2개로 돌린다. 두 터미널 모두 4 의 첫 세 줄(`cd` · `source` · `export`)을 먼저 실행한다. launch 와 같은 포트를 쓰므로 한 번에 하나만 켠다.

```bash
ros2 run f4_hmi hmi_bridge
```

```bash
ros2 run f4_hmi fake_state_pub tool_lost
```

`tool_lost` 자리에 넣을 수 있는 이름: `normal` · `paused` · `isolate` · `error` · `empty_zone` · `tool_lost` · `leftover_remain` · `cable` · `tool_fail`. 기록 DB 조회는 `ros2 run f4_hmi hmi_db kpi`.

</details>

## 5. 실제 로봇

두산 M0609 + RG2 와 우리 워크셀이 있을 때만 한다. 1~3 을 마친 PC 에서 이어서 한다.

<details>
<summary><b>5-1. 두산 드라이버 설치 (처음 한 번)</b></summary>

드라이버는 이 저장소에 없다. 교육 과정 배포본(`doosan-robot2` · 그리퍼 드라이버 `onrobot_rg_control` · `m0609_rg2_bringup`)을 `~/ws_cobot_pjt/ws_dsr` 에 받아 빌드한다. 절차는 [환경 설정 문서 §8](env/M0609_환경설정.md)에 있다. RViz 가 필요하므로 데스크톱 패키지도 설치하고, 빌드가 끝나면 확인한다.

```bash
sudo apt install -y ros-jazzy-desktop
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
ros2 pkg prefix m0609_rg2_bringup && python3 -c "import DR_init; print('DR_init OK')"
```

통과 기준은 설치 경로 한 줄과 `DR_init OK`. `DR_init` 을 못 찾으면 아래 줄을 `~/.bashrc` 맨 아래에 넣고 터미널을 새로 연다.

```bash
export PYTHONPATH=$PYTHONPATH:~/ws_cobot_pjt/ws_dsr/install/dsr_common2/lib/dsr_common2/imp
```

**터미널 준비(로봇용)** — 5-2 와 5-3 의 모든 터미널에서 먼저 실행한다.

```bash
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
```

</details>

<details>
<summary><b>5-2. 가상 로봇 (RViz)</b></summary>

**터미널 1 — 가상 브링업**

```bash
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=virtual host:=127.0.0.1 port:=12345 model:=m0609
```

**터미널 2 — 좌표 순회**

```bash
python3 src/cobot_common/test/rig_coords.py --from 1
```

RViz 에 로봇이 뜨고 셀 좌표를 차례로 돈다. 통과 기준은 마지막 줄 `결과: 통과 — OK n · FAIL 0`. 가상 로봇에는 힘 · 무게 · 접촉이 없다.

</details>

<details>
<summary><b>5-3. 실제 로봇 — PC 1대</b></summary>

> **주의**
> - `cell.yaml` 의 좌표는 우리 워크셀 배치 기준이다. 배치가 다른 셀에서는 좌표를 다시 티칭한 뒤에 돌린다.
> - 처음 켜는 셀과 다시 티칭한 뒤의 첫 실행은 `vel_scale:=0.3` 을 붙여 천천히 돌린다.
> - 급할 때는 Ctrl+C 가 아니라 **E-Stop**.

| 전제 | 값 |
|---|---|
| PC 유선 주소 | `192.168.1.x/24` 로 고정 |
| 로봇 제어기 · 그리퍼 | `192.168.1.100` · `192.168.1.1` |
| 티치 펜던트 | 툴 `Tool Weight`(1.440 kg)와 TCP `GripperDA_v1`(Z 208 mm) 등록 — 이름이 다르면 프로그램이 시작을 거부한다 |

**① 터미널 1 — 브링업**

```bash
ping -c 3 192.168.1.100
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

**② 터미널 2 — 툴 · TCP 확인**

```bash
ros2 service call /dsr01/dsr_controller2/tool/get_current_tool dsr_msgs2/srv/GetCurrentTool
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp dsr_msgs2/srv/GetCurrentTcp
```

통과 기준은 `Tool Weight` 와 `GripperDA_v1`.

**③ 터미널 2 — 빈 용기 기준값** (실행 직전에 한 번 · 무게 값이 시간에 따라 흐르므로)

그리퍼가 빈 상태에서 아래 첫 줄을 실행한다. 그리퍼가 열리고 `▶ BOWL 을(를) 그리퍼 사이에 대 주세요 — 준비되면 Enter` 가 뜨면 빈 그릇을 대고 Enter 를 누른다. 다음 줄은 로봇이 HOME 을 거쳐 무게 재는 자세로 움직여 잰다(약 1분 30초). 마지막 줄은 그릇을 **손으로 받친 채** 실행한다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py grip --kind BOWL
PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL -n 3
python3 src/f2_sense_flow/test/rig_f2.py release
```

출력의 `중앙값 X g (폭 Y g)` 에서 폭이 20 g 이하면, 중앙값을 `src/cobot_common/config/params.yaml` 의 `f2.empty_weight_g.BOWL` 에 넣는다. 컵도 같은 순서로 재서 `f2.empty_weight_g.CUP` 에 넣는다.

```bash
python3 src/f2_sense_flow/test/rig_f2.py grip --kind CUP
PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind CUP -n 3
python3 src/f2_sense_flow/test/rig_f2.py release
```

**④ 터미널 2 — 메인 프로그램과 화면**

팔레트와 격리 구역을 비우고, 반납 구역에 그릇 2개와 컵 2개를 놓는다.

```bash
ros2 launch prewash_bringup prewash.launch.py hmi:=true
```

| 확인 | 통과 기준 |
|---|---|
| 터미널 | 시작부에 `[prewash] use_mock=없음(전부 실제) · vel_scale=1 · hmi=True` → 문지기 통과 → 케이블 확인 → `IDLE` |
| 브라우저 <http://localhost:8000> | 연결 점이 초록이다 |
| **시작** 버튼 | 그릇 2 → 컵 2 를 처리하고 `IDLE` 로 돌아온다 |

**⑤ 끝낼 때** — 로봇이 멈춘 뒤 터미널 2 → 터미널 1 순서로 Ctrl+C.

</details>

<details>
<summary><b>5-4. 실제 로봇 — PC 2대 (로봇 PC + 웹 PC)</b></summary>

PC 두 대가 같은 망에 있을 때 쓴다. 로봇 PC 는 1 · 2 와 5-1, 웹 PC 는 1 · 2 · 3 을 마쳐 둔다. 5-3 의 주의와 전제는 그대로 적용하고, 5-3 의 ① · ④ 는 실행하지 않는다. 무선망이 ROS 2 기본 탐색(멀티캐스트)을 막으므로 로봇 PC 에 Fast DDS Discovery Server 를 띄우고 두 PC 가 거기에 붙는다. 작업 당시 결정 · 시험 기록에는 로봇 PC 를 'GPU PC', 웹 PC 를 '화면 PC'라고 적었다.

**① 로봇 PC 의 주소 확인** — `hostname -I` 로 무선 쪽 주소를 적어 둔다(예: `172.18.0.101`). 아래 명령의 `ROBOT_PC_IP=172.18.0.101` 을 **이 값으로 바꿔서** 실행한다. `ping -c 3 192.168.1.100`(로봇 PC → 로봇)과 `ping -c 3 <ROBOT_PC_IP>`(웹 PC → 로봇 PC)가 되어야 한다.

**② 로봇 PC 터미널 A — Discovery Server** (끝까지 켜 둔다)

```bash
export ROBOT_PC_IP=172.18.0.101
source /opt/ros/jazzy/setup.bash
fastdds discovery --server-id 0 --udp-address $ROBOT_PC_IP --udp-port 11811
```

**③ 로봇 PC 터미널 B — 브링업**

```bash
export ROBOT_PC_IP=172.18.0.101
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$ROBOT_PC_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 launch m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345 model:=m0609
```

**④ 로봇 PC 터미널 C — 준비 · 툴/TCP 확인 · 빈 용기 기준값**

```bash
export ROBOT_PC_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$ROBOT_PC_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
```

이 터미널에서 5-3 의 ②(툴 · TCP 확인)와 ③(빈 용기 기준값)을 그대로 한다.

**⑤ 로봇 PC 터미널 C — 메인 프로그램** (④와 같은 터미널 · `hmi:=true` 는 붙이지 않는다 — 붙이면 화면 서버와 기록 DB 가 두 곳에 생긴다)

```bash
ros2 launch prewash_bringup prewash.launch.py
```

통과 기준: 시작부에 `[prewash] use_mock=없음(전부 실제) · vel_scale=1 · hmi=False` → 문지기 통과 → 케이블 확인 → `IDLE`.

**⑥ 웹 PC 터미널 — 화면 서버** (로봇 PC 의 A · B · C 가 모두 켜진 뒤 · 두산 드라이버는 필요 없다)

```bash
export ROBOT_PC_IP=172.18.0.101
cd ~/rokey_pjt01_ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp ROS_DISCOVERY_SERVER=$ROBOT_PC_IP:11811 ROS_SUPER_CLIENT=TRUE ROS_DOMAIN_ID=60 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET && unset ROS_STATIC_PEERS
ros2 daemon stop && ros2 daemon start
ros2 run f4_hmi hmi_bridge
```

**⑦ 연결 확인** — 웹 PC 에서 새 터미널을 열고 ⑥의 처음 네 줄(`export ROBOT_PC_IP` · `cd` · `source` · `export`)을 먼저 실행한 뒤:

```bash
ros2 node list | grep -E 'flow_node|dsr_controller2'
ros2 topic hz /flow/state
```

통과 기준: `/flow_node` · `/dsr01/flow_node_dsr` · `/dsr01/dsr_controller2` 가 보이고 `/flow/state` 가 약 2 Hz, 브라우저 <http://localhost:8000> 의 연결 점이 초록이다.

**⑧ 끝낼 때** — 화면 서버 → 로봇 PC 의 C(로봇이 멈춘 뒤) → B → A 순서로 Ctrl+C.

</details>

<details>
<summary><b>문제가 생기면</b></summary>

| 언제 | 증상 | 원인 | 대처 |
|---|---|---|---|
| 설치 · 실행 | `ros2: command not found` | 그 터미널에서 `source` 줄을 실행하지 않았다 | 그 단계의 첫 줄(`cd` · `source`)부터 다시 |
| 설치 · 실행 | `colcon: command not found` | colcon 을 설치하지 않았다 | 2 의 apt 설치를 다시 |
| 설치 · 실행 | `Package 'prewash_bringup' not found` | `source install/setup.bash` 를 빼먹었거나 빌드 전이다 | 2 의 빌드와 `source` 를 다시 |
| 설치 · 실행 | 화면 주소에 시험 페이지만 나온다 | 화면을 빌드하지 않았다 | 3 의 `npm install && npm run build` |
| 설치 · 실행 | 8000 포트가 이미 쓰이고 있다 | 먼저 켠 화면 서버가 남아 있다 | 남은 `hmi_bridge` 를 끄고 다시 켠다 |
| 실제 로봇 | 브링업이 곧 꺼지거나 먼저 켠 브링업이 멈춘다 | 브링업 · 에뮬레이터가 이미 켜져 있다 | `ss -tlnp \| grep 12345` 로 확인하고, 켜져 있으면 새로 켜지 말고 그것을 쓴다 |
| 실제 로봇 | 프로그램이 시작하자마자 거부한다(문지기) | 펜던트의 툴 · TCP 이름이 `Tool Weight` · `GripperDA_v1` 이 아니다 | 펜던트에서 툴 · TCP 를 고르고 5-3 ② 로 확인 |
| PC 1대 | 화면이 "연결 끊김"이다 | 5-4 의 환경변수 줄을 넣은 터미널에서 화면 서버를 켰다 | 화면 서버를 끄고, 새 터미널에서 5-1 의 터미널 준비 줄만 실행한 뒤 다시 켠다 |
| PC 2대 | 화면이 "연결 끊김"인데 토픽은 보인다 | 화면 서버를 환경변수 없는 새 터미널에서 켰다 | 환경변수 줄을 넣은 터미널에서 다시 켠다 |
| PC 2대 | `ros2 topic list` 가 비어 있다 | 옛 ros2 데몬이 옛 설정으로 남아 있다 | `ros2 daemon stop && ros2 daemon start` |
| PC 2대 | PC 끼리 `ping` 이 안 된다 | 기기 사이 통신을 막는 망(손님용 무선 등)에 붙어 있다 | 두 PC 를 서로 통신이 되는 같은 망에 붙인다 |
| PC 2대 | 두산 드라이버나 새로 켠 노드가 안 보인다 | 터미널 B · C 에 환경변수 줄이 빠졌거나 서버(A)가 꺼졌다 | 서버 → 브링업 → 메인 프로그램 순서로 다시 켠다 |
| PC 2대 | 화면만 끊기고 로봇은 계속 돈다 | 무선이 끊겼다 | 멈춰야 하면 E-Stop |

두 PC 가 같은 유선 스위치에 있으면 Discovery Server 없이도 된다. 방법은 [환경 설정 문서 10-5](env/M0609_환경설정.md)에 있다.

</details>
