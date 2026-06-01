# TurtleBot3 Air Purifier Robot

ROS 2 Jazzy 기반 TurtleBot3 Waffle 공기정화 로봇 프로젝트입니다. PMS7003 미세먼지 센서로 PM2.5 값을 측정하고, 오염 감지 시 로봇을 정지시킨 뒤 릴레이로 블로우팬을 구동합니다. iPad 또는 브라우저 웹 대시보드에서 수동 조종, 자동 모드 전환, 실시간 맵 확인을 수행할 수 있습니다.

## 주요 기능

- TurtleBot3 Waffle 기반 ROS 2 주행
- PMS7003 PM2.5 센서 데이터 수집
- 릴레이 기반 블로우팬 ON/OFF 제어
- 웹 UI 기반 수동 조종 및 자동 모드 전환
- rosbridge websocket 기반 브라우저-ROS 연동
- Navigation2 저장 맵 기반 위치 추정 및 주행
- 자동 모드 중 오염 감지 시 정지, 정화, 탐색 재개 FSM
- 가상 오염원 기반 Nav2 자동 정화 실험 노드
- 라이다 근거리 노이즈 제거용 `/scan_filtered` 발행

## 프로젝트 구조

```text
pollution_robot/
├── README.md
├── real_cleaner.py              # 실전 공기정화 FSM 노드
├── map_web_publisher.py         # 웹 UI용 /map_web 주기 발행 노드
├── robot_pose_web_publisher.py  # 웹 UI용 /robot_pose_web 주기 발행 노드
├── virtual_cleaner.py           # 가상 오염원 기반 Nav2 자동 정화 노드
├── scan_masker.py               # /scan 근거리 노이즈 제거 필터
├── my_cartographer.launch.py    # /scan_filtered 기반 Cartographer launch 초안
├── start_raspberry_pi.sh        # Raspberry Pi/TurtleBot3 실행 자동화
├── start_laptop.sh              # 노트북 실행 자동화
├── run_demo.sh                  # 초기 시연용 통합 실행 스크립트
├── stop_demo.sh                 # 시연 프로세스 종료 스크립트
├── linetrace_map.yaml           # 저장 맵 메타데이터
├── linetrace_map.pgm            # 저장 맵 이미지
├── web_ui/
│   └── index.html               # iPad/브라우저 관제 UI
└── docs/
    └── project_spec.md          # 진행 기록 및 상세 명세 원본
```

현재 저장소는 ROS 2 패키지 형태가 아닌 Python 스크립트 중심 구조입니다. 따라서 `colcon build` 없이 각 노드를 직접 실행하는 방식을 기준으로 설명합니다.

## 하드웨어 구성

| 구성품 | 설정 |
| --- | --- |
| 로봇 플랫폼 | TurtleBot3 Waffle |
| 메인 보드 | Raspberry Pi 4 |
| ROS 2 | Jazzy |
| 라이다 | LDS-02 |
| 미세먼지 센서 | PMS7003 |
| 센서 포트 | `/dev/ttyAMA0` |
| 센서 baudrate | `9600` |
| 릴레이 GPIO 모드 | `GPIO.BOARD` |
| 릴레이 제어 핀 | 물리 핀 12 |
| 팬 전원 | 외부 12V 배터리, 릴레이 COM-NO 경유 |

PMS7003 센서 노드는 시리얼 프레임 헤더 `0x42 0x4d`를 백그라운드 스레드에서 추적해 PM2.5 값을 안정적으로 파싱하는 구조로 설계했습니다. 팬은 Raspberry Pi 전원 핀에서 직접 구동하지 않고, Raspberry Pi는 릴레이 신호 제어만 담당합니다.

## 설치 방법

### 1. ROS 2 및 TurtleBot3 패키지

노트북과 TurtleBot3 양쪽에 ROS 2 Jazzy 환경이 필요합니다.

```bash
source /opt/ros/jazzy/setup.bash
```

노트북에는 다음 패키지가 필요합니다.

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-turtlebot3 \
  ros-jazzy-turtlebot3-navigation2 \
  ros-jazzy-turtlebot3-cartographer \
  ros-jazzy-turtlebot3-teleop \
  ros-jazzy-rosbridge-server
```

TurtleBot3에는 bringup 패키지가 필요합니다.

```bash
sudo apt install -y ros-jazzy-turtlebot3-bringup
```

### 2. 저장소 받기

```bash
git clone <repository-url> pollution_robot
cd pollution_robot
chmod +x run_demo.sh stop_demo.sh start_laptop.sh start_raspberry_pi.sh
```

### 3. Raspberry Pi Python 의존성

PMS7003와 릴레이 제어 노드를 사용하는 Raspberry Pi 환경에는 다음 Python 패키지가 필요합니다.

```bash
pip3 install pyserial RPi.GPIO
```

Raspberry Pi에서 실행하는 하드웨어 노드는 저장소 루트의 `pms_ros_node.py`, `relay_control_node.py`로 분리되어 있습니다. 기본 실행은 `start_raspberry_pi.sh`가 담당하며, 필요하면 `PMS_NODE`, `RELAY_NODE`, `PMS_PORT` 환경 변수로 경로와 포트를 덮어쓸 수 있습니다.

## 네트워크 설정

모든 장치는 같은 네트워크에 있어야 하며, 동일한 ROS domain을 사용해야 합니다.

```bash
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=waffle
export LDS_MODEL=LDS-02
```

시연 기준 네트워크 설정은 다음과 같습니다.

| 장치 | 주소 |
| --- | --- |
| 네트워크 | iPhone 개인 핫스팟 |
| 대역 | `172.20.10.x / 255.255.255.240` |
| 노트북 | `172.20.10.5` |
| TurtleBot3 | `172.20.10.2` |
| iPad UI | `http://172.20.10.5:8000` |
| rosbridge | `ws://172.20.10.5:9090` |

Docker 가상 네트워크가 활성화되어 있으면 FastDDS가 `/map` 같은 대용량 토픽을 잘못된 네트워크 인터페이스로 송신해 웹 UI 지도 표시가 실패할 수 있습니다. 시연 전 노트북에서 `docker0` 인터페이스를 내립니다.

```bash
sudo ip link set dev docker0 down
```

`run_demo.sh`, `stop_demo.sh`에는 TurtleBot3 접속 정보가 하드코딩되어 있습니다.

```text
user: a
host: 172.20.10.2
```

다른 환경에서는 SSH 계정과 IP를 수정해야 합니다.

## 실행 순서

장치별 실행 절차는 자동화 스크립트로도 실행할 수 있습니다.

Raspberry Pi / TurtleBot3에서:

```bash
cd /home/kang/pollution_robot
./start_raspberry_pi.sh
```

노트북에서:

```bash
cd /home/kang/pollution_robot
./start_laptop.sh
```

스크립트는 실행 로그를 `logs/` 디렉터리에 저장합니다. `Ctrl+C`를 누르면 해당 스크립트가 실행한 프로세스를 종료합니다.

주요 환경 변수는 다음처럼 실행 시 덮어쓸 수 있습니다.

```bash
ROS_DOMAIN_ID=30 MAP_FILE=/path/to/map.yaml ./start_laptop.sh
OUTDOOR_AIR_MODE=mock OUTDOOR_PM25_MOCK=62 ./start_laptop.sh
OUTDOOR_AIR_MODE=api OUTDOOR_AIR_API_URL='https://example.com/air.json' OUTDOOR_AIR_API_JSON_PATH='pm25' ./start_laptop.sh
PMS_NODE=/path/to/pms_ros_node.py RELAY_NODE=/path/to/relay_control_node.py ./start_raspberry_pi.sh
```

### 1. TurtleBot3 / Raspberry Pi

터미널 1: TurtleBot3 bringup

```bash
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=waffle
export LDS_MODEL=LDS-02
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

네트워크 충돌 방지:

```bash
sudo ip link set dev docker0 down
```

터미널 1: 저장 맵 기반 Navigation2 실행

```bash
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=waffle
ros2 launch turtlebot3_navigation2 navigation2.launch.py map:=/home/kang/pollution_robot/linetrace_map.yaml
```

RViz가 열리면 `2D Pose Estimate`로 실제 로봇 위치와 지도상의 위치를 맞춥니다.

터미널 2: rosbridge websocket 실행

```bash
export ROS_DOMAIN_ID=30
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

터미널 3: 웹 UI 서버 실행

```bash
cd /home/kang/pollution_robot/web_ui
python3 -m http.server 8000
```

터미널 4: 공기정화 FSM 노드 실행

```bash
cd /home/kang/pollution_robot
export ROS_DOMAIN_ID=30
python3 real_cleaner.py
```

### 3. iPad / 브라우저

브라우저에서 다음 주소로 접속합니다.

```text
http://172.20.10.5:8000
```

접속 후 확인 순서:

1. 상태 표시가 연결됨으로 바뀌는지 확인
2. `/map`이 웹 UI에 표시되는지 확인
3. `수동` 모드에서 조이스틱으로 로봇이 움직이는지 확인
4. `자동` 모드로 전환해 로봇이 제자리 회전 탐색을 수행하는지 확인
5. PMS7003 센서 근처에 오염원을 투입
6. PM2.5 값이 임계치 이상일 때 팬 ON 및 로봇 정지 확인
7. 정화 기준 이하로 내려가면 팬 OFF 및 탐색 재개 확인

## 토픽 구조

| 토픽 / Action | 타입 | 발행 | 구독 | 설명 |
| --- | --- | --- | --- | --- |
| `/pms7003/pm25` | `std_msgs/Int32` | PMS7003 센서 노드 | `real_cleaner.py` | PM2.5 측정값 |
| `/robot_mode` | `std_msgs/String` | 웹 UI | `real_cleaner.py`, `virtual_cleaner.py` | `manual` / `auto` 모드 전환 |
| `/cmd_vel` | `geometry_msgs/TwistStamped` | 웹 UI, `real_cleaner.py` | TurtleBot3 | 수동 조종 및 자동 탐색 속도 |
| `/hardware/relay` | `std_msgs/Bool` | `real_cleaner.py`, `virtual_cleaner.py` | 릴레이 제어 노드 | 팬 ON/OFF |
| `/air_quality/outdoor_pm25` | `std_msgs/Int32` | `outdoor_air_quality_node.py` | `real_cleaner.py`, 웹 UI | 외부 PM2.5 |
| `/air_quality/adaptive_threshold` | `std_msgs/Int32` | `real_cleaner.py` | 웹 UI | 현재 팬 ON 기준 |
| `/scan` | `sensor_msgs/LaserScan` | TurtleBot3 LiDAR | `scan_masker.py`, SLAM/Nav2 | 원본 라이다 스캔 |
| `/scan_filtered` | `sensor_msgs/LaserScan` | `scan_masker.py` | Cartographer/Nav2 | 근거리 노이즈 제거 스캔 |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM/Nav2 | 웹 UI, RViz | 지도 데이터 |
| `/map_web` | `nav_msgs/OccupancyGrid` | `map_web_publisher.py` | 웹 UI | rosbridge 표시용 주기 발행 지도 |
| `/robot_pose_web` | `geometry_msgs/PoseStamped` | `robot_pose_web_publisher.py` | 웹 UI | 로봇 위치 표시용 주기 발행 pose |
| `/pollution_markers` | `visualization_msgs/MarkerArray` | `virtual_cleaner.py` | RViz | 가상 오염원 표시 |
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | `virtual_cleaner.py` | Nav2 | 목표 지점 주행 요청 |

## FSM 동작 설명

실전 제어 노드 `real_cleaner.py`는 `AutonomousPurifier` 클래스로 구현된 간단한 FSM입니다.

### 상태 변수

| 변수 | 의미 |
| --- | --- |
| `current_mode` | 현재 주행 모드. 기본값은 `manual` |
| `current_pm` | 최근 PM2.5 센서값 |
| `outdoor_pm25` | 최근 외부 PM2.5 값 |
| `is_purifying` | 정화 동작 진행 여부 |
| `POLLUTION_THRESHOLD` | 오염 감지 기준. 외부 PM2.5에 따라 `100`, `85`, `70`으로 조정 |
| `CLEAN_THRESHOLD` | 정화 완료 기준. 기본값 `45` |

### 상태 전이

```text
manual
  ├─ /robot_mode == auto ─────────────▶ auto_explore
  └─ joystick /cmd_vel ───────────────▶ manual

auto_explore
  ├─ PM2.5 >= adaptive threshold ────▶ purifying
  ├─ /robot_mode == manual ──────────▶ manual + stop_robot()
  └─ timer loop ─────────────────────▶ rotate in place

purifying
  ├─ PM2.5 <= 45 ────────────────────▶ previous mode behavior
  └─ timer loop ─────────────────────▶ stop_robot() + fan ON
```

### 제어 우선순위

1. 정화 중이면 모드와 관계없이 로봇을 정지합니다.
2. 오염 감지 시 `/hardware/relay=True`를 발행해 팬을 켭니다.
3. 공기질이 정화 기준 이하로 내려가면 `/hardware/relay=False`를 발행해 팬을 끕니다.
4. 자동 모드에서는 0.5초마다 `angular.z = 0.3` 회전 명령을 발행합니다.
5. 수동 모드에서는 웹 UI 조이스틱이 `/cmd_vel` 제어권을 갖습니다.
6. 자동 모드에서 수동 모드로 바뀌는 순간 `stop_robot()`을 한 번 호출해 잔여 속도 명령을 제거합니다.


외부 PM2.5 값이 들어오면 팬 ON 기준은 적응형으로 바뀝니다. 외부 데이터가 없거나 정상 수준이면 기준은 `100`이고, 외부 PM2.5가 `36-75`이면 `85`, `76` 이상이면 `70`으로 낮아집니다. 외부 대기질만으로 팬을 켜지는 않고, 실내 PMS7003 값이 현재 기준 이상일 때만 정화를 시작합니다.

## 주요 노드

### `real_cleaner.py`

센서 기반 실전 정화 FSM 노드입니다.

```bash
python3 real_cleaner.py
```

### `outdoor_air_quality_node.py`

외부 PM2.5를 `/air_quality/outdoor_pm25`로 발행하는 선택 노드입니다. 기본값은 API 키 없이 동작하는 mock 모드입니다.

```bash
OUTDOOR_AIR_MODE=mock OUTDOOR_PM25_MOCK=62 python3 outdoor_air_quality_node.py
```

### `virtual_cleaner.py`

가상 오염원을 생성하고 Nav2 `navigate_to_pose` action으로 순차 이동하는 실험용 노드입니다.

```bash
python3 virtual_cleaner.py
```

웹 UI에서 `자동` 모드를 누르면 `/robot_mode=auto`를 받아 자동 정화 시퀀스를 시작합니다.

### `scan_masker.py`

라이다 기준 `0.20m` 이내의 유효 거리값을 `0.0`으로 바꿔 `/scan_filtered`로 발행합니다.

```bash
python3 scan_masker.py
```

## 시연 종료

시연용 프로세스를 종료하려면 다음 스크립트를 사용할 수 있습니다.

```bash
./stop_demo.sh
```

주의: 이 스크립트는 `pkill`을 사용해 로컬과 원격의 ROS/Python 프로세스를 종료합니다. 다른 ROS 2 작업을 동시에 실행 중이면 함께 종료될 수 있습니다.

## 향후 개선 사항

- ROS 2 Python 패키지 구조로 변환
- `pms_ros_node.py`, `relay_control_node.py`를 실제 소스 파일로 분리
- launch 파일 통합 및 파라미터 YAML 분리
- PM2.5 임계값, 회전 속도, 팬 동작 정책 파라미터화
- 웹 UI 외부 CDN 의존성 로컬 번들링
- DDS 인터페이스 설정을 XML profile로 고정
