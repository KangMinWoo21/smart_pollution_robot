# TurtleBot3 공기정화 로봇 시스템

ROS2 Humble 기반 TurtleBot3 Waffle을 이용한 공기정화 로봇 프로젝트입니다. 미세먼지 센서값을 기준으로 팬 릴레이를 제어하고, 웹 UI에서 수동/자동 모드를 전환하며, SLAM/Nav2 기반 주행 시나리오를 실험할 수 있도록 구성되어 있습니다.

## 프로젝트 개요

이 프로젝트는 다음 기능을 목표로 합니다.

- TurtleBot3 Waffle 원격 bringup
- PMS7003 미세먼지 센서 기반 오염 감지
- 릴레이를 통한 공기정화 팬 ON/OFF 제어
- iPad/브라우저 웹 UI 기반 수동 조종 및 자동 모드 전환
- Cartographer SLAM 및 RViz 맵 시각화
- 가상 오염원 기반 Nav2 자동 정화 시나리오 실험
- 라이다 근거리 노이즈 마스킹

## 현재 저장소 구조

```text
pollution_robot/
├── README.md
├── run_demo.sh                  # 시연용 통합 실행 스크립트
├── stop_demo.sh                 # 시연 프로세스 종료 스크립트
├── real_cleaner.py              # 실전 센서 기반 공기정화 제어 노드
├── virtual_cleaner.py           # 가상 오염원 기반 Nav2 자동 정화 노드
├── scan_masker.py               # /scan 근거리 데이터 제거 후 /scan_filtered 발행
├── my_cartographer.launch.py    # /scan_filtered를 사용하는 Cartographer launch 초안
├── linetrace_map.yaml           # 저장된 맵 메타데이터
├── linetrace_map.pgm            # 저장된 맵 이미지
├── docs/
│   └── project_spec.md          # 지금까지 진행한 통합 명세/인수인계 기록
└── web_ui/
    └── index.html               # rosbridge 기반 웹 관제 UI
```

현재 저장소는 `package.xml`, `setup.py`, `CMakeLists.txt`가 없는 스크립트 중심 구조입니다. 즉, 아직 정식 ROS2 패키지로 빌드되는 형태는 아니며, 각 Python 파일을 직접 실행하거나 기존 TurtleBot3 패키지와 함께 사용하는 방식입니다.

`docs/project_spec.md`에는 이전 진행 과정에서 작성한 최종 통합 명세가 들어 있습니다. 다만 Python 문자열 생성 로그와 중복 본문이 섞여 있으므로, 제출용 문서로 쓰기 전에는 별도 정리가 필요합니다.

## 하드웨어 구성

### TurtleBot3 본체

- 플랫폼: TurtleBot3 Waffle
- 메인 보드: Raspberry Pi 4
- 라이다: LDS-02
- ROS2 배포판: Humble

### PMS7003 미세먼지 센서

- 연결 인터페이스: Raspberry Pi GPIO UART
- 포트: `/dev/ttyAMA0`
- Baudrate: `9600`
- 발행 토픽: `/pms7003/pm25` (`std_msgs/Int32`)
- 진행 기록 기준 구현 방식:
  - ROS2 타이머 콜백 대신 백그라운드 스레드에서 시리얼 바이트 스트림을 추적
  - PMS7003 프레임 헤더 `0x42 0x4d`를 직접 확인
  - PM2.5 값을 파싱해 `/pms7003/pm25`로 발행

### 릴레이 및 블로우팬

- 제어 대상: 블로우팬 전원 릴레이
- Raspberry Pi GPIO 모드: `GPIO.BOARD`
- 제어 핀: 물리 핀 `12`
- 제어 토픽: `/hardware/relay` (`std_msgs/Bool`)
- 전원 구성:
  - 팬은 Raspberry Pi 5V/3.3V에서 직접 전원을 공급하지 않음
  - 외부 12V 배터리를 릴레이 COM-NO 단자를 통해 팬에 공급
  - Raspberry Pi는 릴레이 제어 신호만 담당

진행 기록에는 Raspberry Pi에서 실행하는 `pms_ros_node.py`, `relay_control_node.py` 코드가 포함되어 있지만, 현재 저장소 루트에는 아직 해당 파일이 없습니다. 정식 패키지화 시 이 두 노드를 함께 포함하는 것이 좋습니다.

## 주요 구성요소

### `real_cleaner.py`

실제 센서 기반 공기정화 제어 노드입니다.

- 노드명: `autonomous_purifier`
- 구독 토픽:
  - `/pms7003/pm25` (`std_msgs/Int32`): PM2.5 센서값
  - `/robot_mode` (`std_msgs/String`): `manual` 또는 `auto`
- 발행 토픽:
  - `/cmd_vel` (`geometry_msgs/Twist`): 자동 모드 회전 탐색 및 정지 명령
  - `/hardware/relay` (`std_msgs/Bool`): 팬 릴레이 제어
- 동작:
  - PM2.5 값이 `100` 이상이면 팬 ON 및 로봇 정지
  - PM2.5 값이 `45` 이하로 내려가면 팬 OFF
  - 자동 모드에서는 제자리 회전으로 탐색
  - 수동 모드 전환 시 즉시 정지 명령 발행

### `virtual_cleaner.py`

가상 오염원을 생성하고 Nav2 목표점으로 이동해 정화 시나리오를 수행하는 실험용 노드입니다.

- 노드명: `virtual_cleaner`
- Action client:
  - `navigate_to_pose` (`nav2_msgs/action/NavigateToPose`)
- 구독 토픽:
  - `/robot_mode` (`std_msgs/String`)
- 발행 토픽:
  - `/hardware/relay` (`std_msgs/Bool`)
  - `/pollution_markers` (`visualization_msgs/MarkerArray`)
- 동작:
  - 맵 범위 안에 가상 오염원 3개 생성
  - `auto` 명령 수신 시 오염원 위치로 순차 이동
  - 도착 후 팬을 5초간 가동
  - 모든 구역 정화 완료 후 오염원을 재배치

### `scan_masker.py`

TurtleBot3 상판, 기둥, 장착물 등 라이다 주변의 매우 가까운 장애물 데이터를 제거하는 필터 노드입니다.

- 노드명: `scan_masker`
- 구독 토픽:
  - `/scan` (`sensor_msgs/LaserScan`)
- 발행 토픽:
  - `/scan_filtered` (`sensor_msgs/LaserScan`)
- 기본 필터 기준:
  - 라이다 기준 `0.20m` 이내 유효 거리값을 `0.0`으로 변경

### `my_cartographer.launch.py`

Cartographer가 원본 `/scan` 대신 `scan_masker.py`에서 발행한 `/scan_filtered`를 사용하도록 구성한 launch 파일 초안입니다.

주의: 현재 파일은 루트에 독립적으로 놓여 있어 `ros2 launch`로 바로 실행하려면 ROS2 패키지 내부 launch 디렉터리로 이동하거나 별도 패키지화가 필요합니다.

### `web_ui/index.html`

브라우저 또는 iPad에서 접속하는 관제 UI입니다.

- rosbridge websocket 연결: `ws://<현재 접속 호스트>:9090`
- 기능:
  - ROS 연결 상태 표시
  - `/map` 표시
  - `manual` / `auto` 모드 전환
  - 조이스틱 기반 `/cmd_vel` 발행
- 필요 노드:
  - `rosbridge_server`
  - `/map` 발행 노드
  - `/cmd_vel`, `/robot_mode`를 사용하는 로봇 제어 노드

## 시스템 구성 예시

```text
iPad / Browser
    │
    │ WebSocket :9090
    ▼
rosbridge_server (노트북)
    │
    ├── /robot_mode ───────────────┐
    ├── /cmd_vel ──────────────────┼── TurtleBot3
    └── /map ◀─────────────────────┘

TurtleBot3
    ├── /scan
    ├── /pms7003/pm25
    └── /hardware/relay

scan_masker.py
    /scan ──▶ /scan_filtered

Cartographer / Nav2
    /scan_filtered, /map, navigate_to_pose
```

## 실행 전 요구사항

### 공통

- Ubuntu 22.04
- ROS2 Humble
- TurtleBot3 ROS2 패키지
- TurtleBot3 모델: `waffle`
- ROS Domain ID: `30`

### 노트북

- `turtlebot3_cartographer`
- `turtlebot3_teleop`
- `rosbridge_server`
- RViz2
- Python3 ROS2 환경

### TurtleBot3

- `turtlebot3_bringup`
- PMS7003 센서 발행 스크립트 또는 노드
- 릴레이 제어 노드 또는 스크립트
- SSH 접속 가능 상태

현재 `run_demo.sh`는 TurtleBot3 접속 정보를 다음처럼 가정합니다.

```text
user: a
host: 172.20.10.2
```

환경에 맞게 `run_demo.sh`, `stop_demo.sh`의 SSH 계정과 IP를 수정해야 합니다.

진행 기록 기준 시연 네트워크는 다음 값을 사용했습니다.

```text
네트워크: iPhone 개인 핫스팟
대역: 172.20.10.x / 255.255.255.240
노트북 IP: 172.20.10.5
TurtleBot3 IP: 172.20.10.2
iPad 접속 주소: http://172.20.10.5:8000
```

Docker 가상 네트워크가 켜져 있으면 FastDDS가 `/map` 같은 대용량 토픽을 잘못된 인터페이스로 내보내 웹 UI 지도 표시가 깨질 수 있습니다. 진행 기록에서는 시연 전 다음 명령으로 `docker0`를 내렸습니다.

```bash
sudo ip link set dev docker0 down
```

## 환경 변수

시연 스크립트는 다음 환경 변수를 사용합니다.

```bash
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=waffle
export LDS_MODEL=LDS-02
```

수동으로 실행할 때도 노트북과 TurtleBot3 양쪽에서 같은 `ROS_DOMAIN_ID`를 사용해야 합니다.

## 실행 방법

### 1. 통합 시연 실행

```bash
chmod +x run_demo.sh stop_demo.sh
./run_demo.sh
```

`run_demo.sh`는 다음 순서로 터미널을 엽니다.

1. TurtleBot3 원격 bringup
2. TurtleBot3 원격 미세먼지 센서 및 팬 제어 스크립트 실행
3. 노트북에서 Cartographer SLAM 실행
4. 노트북에서 키보드 teleop 실행

현재 `run_demo.sh`는 초기 시연용 스크립트에 가깝습니다. `docs/project_spec.md`의 최종 진행 기록은 Cartographer SLAM보다 기존 저장 맵을 불러온 Nav2 주행 시연 흐름을 기준으로 작성되어 있습니다.

### 2. 통합 시연 종료

```bash
./stop_demo.sh
```

주의: `stop_demo.sh`는 로컬 및 원격의 `ros2`, `python3` 관련 프로세스를 종료합니다. 다른 ROS2 작업을 동시에 실행 중이면 함께 종료될 수 있습니다.

### 3. 웹 UI 실행

노트북에서 rosbridge를 실행합니다.

```bash
export ROS_DOMAIN_ID=30
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

그 다음 브라우저에서 다음 파일을 엽니다.

```text
web_ui/index.html
```

iPad에서 접속하려면 노트북과 같은 네트워크에 연결한 뒤, 노트북 IP를 기준으로 정적 파일 서버를 열어 접속하는 방식을 권장합니다.

```bash
cd web_ui
python3 -m http.server 8000
```

브라우저 접속:

```text
http://<노트북_IP>:8000
```

진행 기록 기준 iPad 접속 주소는 다음과 같습니다.

```text
http://172.20.10.5:8000
```

### 4. 실전 공기정화 노드 직접 실행

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=30
python3 real_cleaner.py
```

### 5. 가상 오염원 자동 정화 노드 직접 실행

Nav2가 실행 중이고 `navigate_to_pose` action server가 준비된 상태에서 실행합니다.

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=30
python3 virtual_cleaner.py
```

웹 UI에서 `자동` 버튼을 누르면 `/robot_mode`에 `auto`가 발행되고 자동 정화 시퀀스가 시작됩니다.

### 6. 라이다 마스킹 노드 실행

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=30
python3 scan_masker.py
```

Cartographer 또는 SLAM 쪽에서 `/scan_filtered`를 사용하도록 remapping해야 합니다.

## 최종 시연 워크플로우

`docs/project_spec.md`에 정리된 최종 시연 순서는 다음 흐름입니다.

### 1. Raspberry Pi / TurtleBot3

터미널 1: TurtleBot3 bringup

```bash
export ROS_DOMAIN_ID=30
ros2 launch turtlebot3_bringup robot.launch.py
```

터미널 2: PMS7003 센서 노드

```bash
export ROS_DOMAIN_ID=30
python3 pms_ros_node.py
```

터미널 3: 릴레이 제어 노드

```bash
export ROS_DOMAIN_ID=30
python3 relay_control_node.py
```

### 2. 노트북

시작 전 네트워크 충돌 방지:

```bash
sudo ip link set dev docker0 down
```

터미널 1: 저장 맵 기반 Navigation2

```bash
export ROS_DOMAIN_ID=30
ros2 launch turtlebot3_navigation2 navigation2.launch.py map:=/home/kang/pollution_robot/linetrace_map.yaml
```

RViz가 열리면 `2D Pose Estimate`로 실제 로봇 위치와 맵 위치를 맞춥니다.

터미널 2: rosbridge websocket

```bash
export ROS_DOMAIN_ID=30
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

터미널 3: 웹 UI 서버

```bash
cd /home/kang/pollution_robot/web_ui
python3 -m http.server 8000
```

터미널 4: 공기정화 FSM 노드

```bash
export ROS_DOMAIN_ID=30
cd /home/kang/pollution_robot
python3 real_cleaner.py
```

### 3. iPad 시연

1. Safari에서 `http://172.20.10.5:8000` 접속
2. 연결 상태가 초록색으로 바뀌고 `/map`이 표시되는지 확인
3. `자동` 모드 선택
4. 로봇이 제자리 회전 탐색을 시작하는지 확인
5. PMS7003 센서 근처에 가습기 연기 등 오염원을 투입
6. PM2.5 값이 `100` 이상이면 팬 ON 및 로봇 정지 확인
7. PM2.5 값이 `45` 이하로 내려가면 팬 OFF 및 탐색 재개 확인

## 주요 토픽 정리

| 토픽 | 타입 | 방향 | 설명 |
| --- | --- | --- | --- |
| `/robot_mode` | `std_msgs/String` | UI → 노드 | `manual`, `auto` 모드 전환 |
| `/cmd_vel` | `geometry_msgs/Twist` | UI/노드 → 로봇 | 수동 조종 또는 자동 탐색 속도 명령 |
| `/pms7003/pm25` | `std_msgs/Int32` | 센서 → 노드 | PM2.5 측정값 |
| `/hardware/relay` | `std_msgs/Bool` | 노드 → 하드웨어 | 팬 릴레이 ON/OFF |
| `/scan` | `sensor_msgs/LaserScan` | 라이다 → 필터 | 원본 라이다 스캔 |
| `/scan_filtered` | `sensor_msgs/LaserScan` | 필터 → SLAM | 근거리 데이터 제거 스캔 |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM → UI | 웹 UI 맵 표시 |
| `/pollution_markers` | `visualization_msgs/MarkerArray` | 가상 노드 → RViz | 가상 오염원 표시 |
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | 노드 → Nav2 | 목표 지점 주행 |

## ROS2 패키지화 권장 구조

현재 구조를 ROS2 워크스페이스 기준으로 정리하면 다음 형태를 권장합니다.

```text
pollution_robot_ws/
└── src/
    └── pollution_robot/
        ├── package.xml
        ├── setup.py
        ├── resource/
        │   └── pollution_robot
        ├── pollution_robot/
        │   ├── __init__.py
        │   ├── real_cleaner.py
        │   ├── virtual_cleaner.py
        │   ├── scan_masker.py
        │   ├── pms_ros_node.py
        │   └── relay_control_node.py
        ├── launch/
        │   └── my_cartographer.launch.py
        ├── maps/
        │   ├── linetrace_map.yaml
        │   └── linetrace_map.pgm
        ├── web_ui/
        │   └── index.html
        └── scripts/
            ├── run_demo.sh
            └── stop_demo.sh
```

패키지화 후에는 다음처럼 실행할 수 있도록 구성하는 것이 좋습니다.

```bash
colcon build --symlink-install
source install/setup.bash
ros2 run pollution_robot real_cleaner
ros2 run pollution_robot virtual_cleaner
ros2 run pollution_robot scan_masker
ros2 launch pollution_robot my_cartographer.launch.py
```

## 현재 주의사항

- `my_cartographer.launch.py`는 현재 루트에 있어 패키지 launch 파일처럼 바로 사용할 수 없습니다.
- `run_demo.sh`의 로봇 IP, 계정, 원격 경로는 환경 의존적입니다.
- `real_cleaner.py`는 `/pms7003/pm25`와 `/hardware/relay` 토픽을 제공하는 별도 센서/하드웨어 계층이 필요합니다.
- `virtual_cleaner.py`는 Nav2 action server가 준비되어 있어야 동작합니다.
- 웹 UI는 외부 CDN을 사용하므로 인터넷이 없으면 JS 라이브러리를 불러오지 못할 수 있습니다.
- `stop_demo.sh`는 `pkill` 범위가 넓으므로 개발 중인 다른 ROS2 프로세스가 있으면 주의해야 합니다.

## 다음 작업 후보

- 정식 ROS2 Python 패키지로 변환
- `docs/project_spec.md`에서 `pms_ros_node.py`, `relay_control_node.py`를 분리해 실제 소스 파일로 추가
- 중복 로그가 섞인 `docs/project_spec.md`를 제출용 문서로 정리
- launch 파일 정리 및 통합 bringup launch 작성
- 하드웨어 설정값을 YAML 파라미터로 분리
- PM2.5 임계값, 팬 동작 시간, 탐색 속도 파라미터화
- 웹 UI 정적 파일 로컬 번들링
- `run_demo.sh`의 IP, 계정, 도메인 ID를 환경 변수 또는 설정 파일로 분리
