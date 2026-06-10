# 소프트웨어 시스템

PPT 제작 시 `소프트웨어 시스템`, `시스템 구성 설명`, `ROS 통신 구조` 슬라이드에 사용하기 좋은 내용입니다.

## 전체 구조

소프트웨어는 노트북과 TurtleBot3 Raspberry Pi로 역할을 나누어 실행합니다.

- 노트북: Nav2, 자동 정화 알고리즘, rosbridge, Web UI, 지도/위치 웹 발행, 외부 미세먼지 API 노드
- Raspberry Pi: TurtleBot3 bringup, LiDAR와 odometry, PMS7003 센서 노드, 릴레이 팬 제어 노드

두 장치는 `ROS_DOMAIN_ID=30`과 Zenoh RMW를 사용해 ROS 2 토픽을 주고받습니다.

## 주요 기술 스택

| 구분 | 기술 | 역할 |
| --- | --- | --- |
| OS / Middleware | Ubuntu 24.04, ROS 2 Jazzy | 전체 ROS 실행 환경 |
| 자율주행 | Nav2 | 목표 위치 이동, 경로 계획, 장애물 회피 |
| 지도/위치 | SLAM 지도, AMCL, odometry | 실내 지도 기반 위치 추정 |
| 통신 | Zenoh RMW | 노트북과 Pi 사이 ROS 2 통신 안정화 |
| 웹 연동 | rosbridge, roslibjs | 브라우저와 ROS 토픽 연결 |
| 센서 | PMS7003 노드 | PM2.5 토픽 발행 |
| 팬 제어 | relay_control_node.py | `/hardware/relay` 명령을 GPIO로 변환 |
| 자동 정화 | real_cleaner.py, cleaning_logic.py | 오염 후보 탐색, 판단, 정화 제어 |

## 주요 ROS 토픽

| 토픽 | 타입 | 방향 | 역할 |
| --- | --- | --- | --- |
| `/pms7003/pm25` | `std_msgs/Int32` | Pi → Laptop/Web | 실내 PM2.5 값 |
| `/hardware/relay` | `std_msgs/Bool` | Web/자동정화 → Pi | 팬 ON/OFF |
| `/robot_mode` | `std_msgs/String` | Web → 자동정화 | 수동/자동 모드 전환 |
| `/target_zone` | `std_msgs/String` | Web → 자동정화 | 전체/주방 집중 구역 선택 |
| `/scan` | `sensor_msgs/LaserScan` | Pi → Laptop | LiDAR 데이터 |
| `/odom` | `nav_msgs/Odometry` | Pi → Laptop | 로봇 odometry |
| `/robot_pose_web` | `geometry_msgs/PoseStamped` | Laptop → Web | 웹 표시용 로봇 위치 |
| `/map_web` | `nav_msgs/OccupancyGrid` | Laptop → Web | 웹 표시용 지도 |
| `/air_quality/outdoor_pm25` | `std_msgs/Int32` | Laptop → Web/자동정화 | 외부 PM2.5 |
| `/air_quality/adaptive_threshold` | `std_msgs/Int32` | 자동정화 → Web | 외부 공기질 반영 기준값 |
| `/purifier_status` | `std_msgs/String` | 자동정화 → Web | 정화 완료, 복귀 중 등 상태 |

## Web UI

웹 UI는 브라우저에서 `http://172.20.10.5:8000`으로 접속합니다.

주요 기능:

- ROS 연결 상태 표시
- 실내 PM2.5와 외부 PM2.5 표시
- 지도와 로봇 위치 표시
- 수동/자동 모드 전환
- 수동 모드에서 조이스틱 주행과 팬 ON/OFF
- 자동 모드에서 전체 또는 주방 집중 선택
- 정화 완료, 복귀 중, 출발지 복귀 완료 상태 표시

발표 문장:

> Web UI는 단순 모니터링 화면이 아니라, 로봇 모드 전환, 집중 정화 구역 선택, 수동 팬 제어를 ROS 토픽으로 직접 발행하는 관제 인터페이스입니다.

## Zenoh 통신

기존 DDS 통신은 네트워크 인터페이스나 핫스팟 환경에 따라 토픽 발견이 불안정할 수 있습니다. 이를 줄이기 위해 Zenoh RMW를 사용합니다.

- 노트북은 Zenoh router를 실행합니다.
- Raspberry Pi는 노트북 router endpoint에 client mode로 연결합니다.
- 양쪽 모두 `RMW_IMPLEMENTATION=rmw_zenoh_cpp`를 사용합니다.

발표 문장:

> 시연 환경에서는 노트북과 TurtleBot3가 개인 핫스팟을 통해 통신하므로, ROS 2 토픽 발견 안정성을 위해 Zenoh 기반 통신 구조를 적용했습니다.

## 외부 미세먼지 API

`outdoor_air_quality_node.py`는 외부 PM2.5 값을 가져와 `/air_quality/outdoor_pm25`로 발행합니다. 자동 정화 알고리즘은 이 값을 이용해 실내 오염 판단 기준을 조정합니다.

- 외부 공기질이 양호하면 기본 기준값 50을 사용합니다.
- 외부 공기질이 나쁘면 기준값을 48 또는 45로 낮춥니다.
- API 실패 시 mock 값을 fallback으로 사용할 수 있습니다.

## 소프트웨어 발표 핵심

- Web UI, ROS 토픽, Nav2, 센서, 릴레이가 하나의 통합 흐름으로 연결됩니다.
- 자동 정화 판단은 `cleaning_logic.py`와 `real_cleaner.py`에서 수행합니다.
- 실제 하드웨어 제어는 Raspberry Pi의 PMS 센서 노드와 릴레이 노드가 담당합니다.
