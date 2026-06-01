# TurtleBot3 Air Purifier Robot - Current Status

최종 업데이트: 2026-06-01

## 1. 현재 시스템 구성

### 노트북
- OS: Ubuntu 24.04
- Shell: zsh
- ROS: ROS 2 Jazzy
- IP: 172.20.10.5
- 역할: Navigation2, rosbridge websocket, Web UI 서버, RViz, 공기정화 FSM 실행

### TurtleBot3 Raspberry Pi
- OS: Ubuntu Server 24.04
- ROS: ROS 2 Jazzy
- Hostname: turtlebot
- User: a
- IP: 172.20.10.2
- 역할: turtlebot3_bringup, PMS7003 센서 노드, 릴레이 제어 노드, OpenCR

### 네트워크
- iPhone Personal Hotspot
- 대역: 172.20.10.x
- ROS domain: 30
- iPad UI: http://172.20.10.5:8000
- rosbridge: ws://172.20.10.5:9090

## 2. 완료된 작업

- Raspberry Pi Ubuntu 24.04 재설치 및 SSH 접속 설정
- ROS 2 Jazzy 기준 실행 절차 정리
- PMS7003 센서 노드 분리: `pms_ros_node.py`
- 릴레이 제어 노드 분리: `relay_control_node.py`
- 실전 공기정화 FSM 정리: `real_cleaner.py`
- 웹 UI 지도/로봇 위치 표시 보조 노드 추가: `map_web_publisher.py`, `robot_pose_web_publisher.py`
- 라이다 근거리 노이즈 제거 노드 추가: `scan_masker.py`
- 장치별 실행 자동화 스크립트 추가: `start_raspberry_pi.sh`, `start_laptop.sh`
- 웹 UI 예측 공기질 모듈 및 단위 테스트 추가: `web_ui/predictive_air_quality.js`, `web_ui/predictive_air_quality.test.js`
- 외부 PM2.5 기반 적응형 팬 기준 설계 및 구현
- 선제 대응 UI 패널 추가
- 외부 대기질 mock/API 노드 추가: `outdoor_air_quality_node.py`

## 3. 실행 순서

### Raspberry Pi / TurtleBot3

```bash
cd /home/a/pollution_robot
./start_raspberry_pi.sh
```

필요 시 다음 환경 변수를 덮어쓸 수 있습니다.

```bash
ROS_DOMAIN_ID=30 PMS_PORT=/dev/serial0 ./start_raspberry_pi.sh
```

### 노트북

```bash
cd /home/kang/pollution_robot
./start_laptop.sh
```

스크립트는 Navigation2, rosbridge, 웹 서버, `/map_web`, `/robot_pose_web`, `outdoor_air_quality_node.py`, `real_cleaner.py`를 실행하고 로그를 `logs/`에 저장합니다.

### iPad / 브라우저

```text
http://172.20.10.5:8000
```

확인 순서:

1. 상태 표시가 연결됨으로 바뀌는지 확인
2. 지도가 표시되는지 확인
3. 수동 모드에서 조이스틱 주행 확인
4. 자동 모드에서 제자리 회전 탐색 확인
5. PM2.5 임계치 이상에서 로봇 정지 및 팬 ON 확인
6. 정화 기준 이하에서 팬 OFF 및 탐색 재개 확인

## 4. 검증 완료

2026-06-01 로컬 검증:

- `node web_ui/predictive_air_quality.test.js` 통과
- `python3 -m py_compile ...` 통과
- `bash -n run_demo.sh start_laptop.sh start_raspberry_pi.sh stop_demo.sh` 통과

## 5. 남은 확인 사항

- 실제 TurtleBot3에서 `/cmd_vel` 타입이 `geometry_msgs/TwistStamped`로 일치하는지 확인
- 실제 네트워크에서 `docker0` 비활성화 후 `/map_web`, `/robot_pose_web` 표시 확인
- Raspberry Pi에서 `PMS_PORT`가 `/dev/serial0`로 잡히는지 확인
- 릴레이 핀 번호가 실제 결선과 일치하는지 확인: physical pin 12
- mock 외부 PM2.5 값 `62`에서 팬 기준이 `85`로 표시되는지 확인
- 외부 API 모드 사용 시 실제 API 응답 JSON path 확인
- 웹 UI 외부 CDN 의존성 로컬 번들링 검토
