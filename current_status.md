# TurtleBot3 Air Purifier Robot - Current Status

최종 업데이트: 2026-06-05

## 1. 현재 연결 상태

### 노트북
- OS: Ubuntu 24.04
- ROS: ROS 2 Jazzy
- IP: 172.20.10.5
- 역할: Zenoh router, rosbridge websocket, Web UI 서버, Nav2/자동 정화 알고리즘 실행 측
- Web UI: http://172.20.10.5:8000
- rosbridge: ws://172.20.10.5:9090

### TurtleBot3 Raspberry Pi
- OS: Ubuntu Server 24.04
- ROS: ROS 2 Jazzy
- User: a
- IP: 172.20.10.2
- 역할: turtlebot3_bringup, lidar/odom, PMS7003 센서 노드, relay_control_node.py
- 릴레이 제어는 physical pin 12 사용
- GPIO 제어는 root 권한 필요. sudo 비밀번호는 사용자가 `a`라고 확인함.

### 통신
- ROS_DOMAIN_ID=30
- Zenoh RMW 적용 완료
- 노트북 Zenoh router endpoint: tcp/172.20.10.5:7447
- Pi Zenoh session config: /home/a/pollution_robot/logs/zenoh_raspberry_pi_session.json5
- Laptop Zenoh session config: /home/kang/pollution_robot/logs/zenoh_laptop_session.json5

## 2. 이번 세션에서 완료한 작업

### 자동 정화 알고리즘
- 기존 제자리 회전/느린 움직임 기반을 Nav2 waypoint 후보 주행 기반으로 확장.
- `cleaning_logic.py`에 하이브리드 탐색 로직 추가.
- 목표물 2개 탐색을 지원.
- 첫 번째 목표 발견 후 두 번째 목표 탐색 시 기존 발견 위치 주변 신호를 무시하도록 ignore radius / signal ignore radius 적용.
- 자동 주행 중 PM2.5 급상승 시 현재 Nav2 goal을 취소하고 현재 위치를 샘플 지점으로 기록한 뒤 주변 추적 모드로 전환하는 로직 추가.
- 관련 파일: `cleaning_logic.py`, `real_cleaner.py`, `test_cleaning_logic.py`, `test_real_cleaner.py`

### Web UI
- 모바일 웹 UI를 산업용 관제 화면처럼 재배치.
- 스크롤 의존도를 줄이고 지도 중심 + 하단 명령 도크 구조로 변경.
- 조이스틱은 수동모드에서만 표시.
- 상세 상태는 자동모드에서만 표시.
- 수동모드에서는 팬 제어만 표시: `팬 ON`, `팬 OFF`.
- 자동모드에서는 집중 제어와 상세 상태만 표시: `전체`, `주방 집중`, `거실 집중`, `상세 상태`.
- CSS `[hidden] { display: none !important; }`를 추가해 hidden 요소가 grid/flex 스타일에 덮여 보이지 않도록 수정.
- 팬 버튼은 `/hardware/relay`에 `std_msgs/Bool`을 직접 발행.
- 관련 파일: `web_ui/index.html`, `web_ui/index_layout.test.js`

### 수동 팬 제어
- `real_cleaner.py`에서 수동모드 PM2.5 기준 자동 팬 ON을 제거.
- 수동모드에서는 PM2.5 값으로 팬을 켜지 않음.
- 팬은 웹 UI의 `팬 ON / 팬 OFF` 버튼 또는 `/hardware/relay` 직접 발행으로만 제어.
- 자동 탐색이 끝나서 정화 상태에 들어가는 로직은 별도로 남아 있음.

### Zenoh
- `start_laptop.sh`, `start_raspberry_pi.sh`에 Zenoh RMW 설정 추가.
- peer mode 대신 client mode config를 사용해야 원격 토픽이 정상 발견됨.
- `USE_ZENOH=1` 사용 시 `RMW_IMPLEMENTATION=rmw_zenoh_cpp`와 `ZENOH_SESSION_CONFIG_URI`가 적용됨.

## 3. 실제 연결/동작 확인 결과

### 확인 완료
- Zenoh router 실행 확인.
- Pi TurtleBot bringup Zenoh 연결 확인.
- `/odom` 수신 확인.
- `/scan` 수신 확인.
- rosbridge websocket 9090 실행 확인.
- Web UI 8000 실행 확인.
- `/hardware/relay` 토픽 확인.
- Pi에서 relay_control_node.py를 root 권한으로 실행한 뒤 `/hardware/relay` 구독자 1개 확인.
- `/hardware/relay=True` 발행 후 Pi 로그에 `Relay ON` 확인.
- `/hardware/relay=False` 발행 후 Pi 로그에 `Relay OFF` 확인.

### 중요 주의
- 릴레이 노드는 sudo 없이 실행하면 ROS에는 붙을 수 있지만 GPIO가 준비되지 않음.
- sudo 없이 실행 시 로그: `GPIO setup failed: No access to /dev/mem. Try running as root!`
- root로 실행할 때는 root shell 안에서 ROS setup을 source해야 함. 그렇지 않으면 `ModuleNotFoundError: No module named rclpy` 발생.

## 4. 검증 완료

이번 세션에서 통과한 테스트:

- `python3 -m unittest test_cleaning_logic.py test_real_cleaner.py` 통과
- `python3 -m py_compile cleaning_logic.py real_cleaner.py test_cleaning_logic.py test_real_cleaner.py` 통과
- `node web_ui/index_layout.test.js` 통과
- `node web_ui/predictive_air_quality.test.js` 통과
- `bash -n start_laptop.sh start_raspberry_pi.sh run_demo.sh stop_demo.sh` 통과

## 5. 다음 시연 장소에서 할 일

1. 노트북과 TurtleBot Pi가 같은 네트워크에 있는지 확인.
2. 노트북 IP가 바뀌면 Zenoh endpoint와 Web UI URL을 새 IP로 맞춤.
3. Zenoh router 실행 확인.
4. Pi bringup 실행 확인.
5. Pi에서 relay_control_node.py가 root 권한으로 실행 중인지 확인.
6. `/hardware/relay` 구독자 1개 확인.
7. 웹 UI 접속 후 수동모드에서 팬 ON/OFF 확인.
8. 수동모드에서 조이스틱 주행 확인.
9. 자동모드에서 집중 제어와 상세 상태만 보이는지 확인.
10. 실제 시연장 맵/위치가 다르므로 자동 주행은 Nav2 localization, map, waypoint 좌표를 맞춘 뒤 테스트.
11. PM2.5 센서 `/pms7003/pm25` publisher가 실제로 떠 있는지 확인.
12. 자동 탐색은 먼저 안전한 저속/빈 공간에서 Nav2 goal 도달 여부를 확인한 뒤 가습기 탐색을 진행.

## 6. 남은 리스크

- 현재 맵은 실제 시연 장소 맵이 아니므로 waypoint 좌표가 시연장과 맞지 않을 수 있음.
- 자동 주행 알고리즘은 코드/테스트 기준으로는 적용됐지만, 실제 장소에서 Nav2 localization과 obstacle avoidance 확인이 필요.
- PM2.5 센서 노드가 실제 publisher로 떠 있는지는 시연장에서 다시 확인 필요.
- 릴레이 배선/전원/active-high 또는 active-low 여부는 실제 팬 반응으로 최종 확인 필요.
- 웹 UI는 no-cache 서버를 쓰지만, 브라우저 캐시가 남으면 강력 새로고침 필요.


## 2026-06-08 시연장 실제 테스트 업데이트

### 정상 확인됨
- 시연장 네트워크에서 노트북 IP는 `172.20.10.5`, TurtleBot Pi IP는 `172.20.10.2`.
- Web UI는 `http://172.20.10.5:8000`에서 HTTP 200 응답 확인.
- TurtleBot bringup 정상: OpenCR `/dev/ttyACM0`, LDS-02 라이다 `/dev/ttyUSB0` 인식.
- `/odom`, `/scan` 실제 수신 확인.
- 릴레이 노드 root 권한 실행 정상, `/hardware/relay` 구독자 1개 확인.
- 웹 팬 ON/OFF 시 릴레이 딸깍 및 팬 실제 동작 확인.
- 수동 주행 `/cmd_vel` 테스트 성공.
- 웹 조이스틱 수동 주행 성공.
- Nav2 실행 후 RViz에서 `2D Pose Estimate`로 초기 위치 설정함.
- `bt_navigator`, `waypoint_follower`, `behavior_server`, `velocity_smoother`, `collision_monitor`가 inactive였던 문제를 수동 activate로 해결.
- Nav2 `/navigate_to_pose` goal 수락 및 `SUCCEEDED` 확인.
- `/cmd_vel_nav`와 `/cmd_vel` 모두에서 Nav2 속도 명령 생성/전달 확인.

### PMS7003 확인 및 조치
- PMS 센서는 실제로 연결되어 있었고 `/dev/ttyS0`에서 데이터가 나옴.
- `/boot/firmware/cmdline.txt`에 `console=serial0,115200`가 있어 `serial-getty@ttyS0`가 포트를 잡고 있었음.
- 시연 중 `serial-getty@ttyS0.service`를 stop 하고 PMS 노드를 `PMS_PORT=/dev/ttyS0`로 실행.
- `/pms7003/pm25` publisher 1개 확인, 실제 값 `25` 수신 확인.
- PMS 로그에서 `20~27 ug/m3` 범위 출력 확인.

### 다음 할 일
1. 새 세션 시작 시 현재 실행 중인 Zenoh/Nav2/TurtleBot/PMS/relay 상태 확인.
2. Nav2 lifecycle이 재시작 후 다시 inactive가 되면 `/bt_navigator`, `/waypoint_follower`, `/behavior_server`, `/velocity_smoother`, `/collision_monitor`를 activate.
3. PMS를 계속 쓰려면 부팅 후 `serial-getty@ttyS0.service`를 멈추고 `PMS_PORT=/dev/ttyS0`로 실행. 영구 설정은 아직 안 함.
4. 다음 단계는 `real_cleaner.py` 자동 정화 알고리즘을 실제 시연장 조건에서 켜고, PM2.5 상승 시 Nav2 goal 취소/추적 전환/팬 제어까지 통합 테스트.

### 새 대화 시작 문장

```text
시연장 실제 테스트 이어서 하자. current_status.md 확인하고, 지금 떠 있는 Zenoh/Nav2/TurtleBot/PMS/relay 상태부터 점검해줘. 지난번에는 수동 주행, 웹 조이스틱, 팬 ON/OFF, PMS /dev/ttyS0, Nav2 goal SUCCEEDED까지 확인했고, 다음은 real_cleaner.py 자동 정화 알고리즘 통합 테스트부터 하면 돼.
```
