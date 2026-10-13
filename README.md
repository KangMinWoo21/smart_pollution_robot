# 자율주행 공기청정 로봇

TurtleBot3가 실내를 순찰하며 미세먼지를 측정하고, 오염이 감지된 곳에서 팬을 작동시키는 프로젝트입니다. 웹 화면에서 공기질과 로봇 위치를 확인하고 주행 모드와 팬을 제어할 수 있습니다.

## 주요 기능

- Nav2 기반 실내 자율주행과 장애물 회피
- PMS7003 센서로 PM2.5 측정 및 오염 구역 탐색
- 릴레이를 통한 팬 자동·수동 제어
- 웹에서 지도, 로봇 위치, 실내외 공기질 확인
- 외부 미세먼지와 시간대에 따른 구역별 순찰 추천

## 실행 환경

TurtleBot3 Waffle, Raspberry Pi, PMS7003 센서, 릴레이와 팬을 사용합니다. 노트북과 Raspberry Pi에는 ROS 2 Jazzy와 TurtleBot3 패키지가 필요하며, 노트북에는 Nav2와 rosbridge, 양쪽에는 Zenoh 통신 패키지가 설치되어 있어야 합니다. 센서와 릴레이 노드는 pyserial과 RPi.GPIO를 사용합니다.

두 기기를 같은 네트워크에 연결하고 Raspberry Pi에 SSH 접속이 가능하도록 설정합니다. 기본 `ROS_DOMAIN_ID`는 `30`입니다.

## 실행 방법

`run_demo.sh`의 SSH 주소, Raspberry Pi 프로젝트 경로, 노트북 IP를 사용하는 환경에 맞게 수정합니다. 지도와 순찰 좌표는 `start_laptop.sh`에서 설정합니다.

노트북에서 실행합니다.

```bash
./run_demo.sh
```

웹 화면은 `http://localhost:8000`에서 접속합니다. RViz의 **2D Pose Estimate**로 초기 위치를 지정한 뒤 웹에서 자동 모드를 선택합니다.

종료할 때는 다음 명령을 사용합니다. `stop_demo.sh`의 `PI_SSH`도 실제 접속 주소에 맞게 설정해야 합니다.

```bash
./stop_demo.sh
```

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `real_cleaner.py`, `cleaning_logic.py` | 자동 주행, 오염 탐색, 정화 제어 |
| `pms_ros_node.py`, `relay_control_node.py` | 미세먼지 센서와 팬 제어 |
| `outdoor_air_quality_node.py` | 외부 미세먼지 조회 |
| `web_ui/`, `*_web_publisher.py` | 웹 화면과 지도·위치 전달 |
| `run_demo.sh`, `start_*.sh`, `stop_demo.sh` | 실행과 종료 |
| `linetrace_map.*`, `demo_nav2_params.yaml` | 지도와 주행 설정 |

외부 미세먼지 API 설정은 `start_laptop.sh`에서 확인할 수 있습니다. 실제 조회에는 공공데이터 API 인증키가 필요합니다.
