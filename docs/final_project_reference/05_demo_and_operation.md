# 시연과 실행 방법

PPT 제작 시 `데모 시나리오`, `동작 상태`, `검증 결과`, `향후 진행 일정` 슬라이드에 사용하기 좋은 내용입니다.

## 통합 실행

시연은 노트북에서 아래 명령으로 시작합니다.

```bash
./run_demo.sh
```

`run_demo.sh`는 노트북 쪽 프로세스와 Raspberry Pi 쪽 프로세스를 함께 실행합니다.

## 노트북에서 실행되는 것

- Zenoh router
- Nav2
- rosbridge websocket
- Web UI 서버
- 지도 웹 발행 노드
- 로봇 위치 웹 발행 노드
- 외부 미세먼지 API 노드
- 자동 정화 알고리즘 노드
- Nav2 속도 명령 relay 노드

## Raspberry Pi에서 실행되는 것

- TurtleBot3 bringup
- LDS-02 LiDAR `/scan`
- odometry `/odom`
- PMS7003 미세먼지 센서 노드
- 릴레이 팬 제어 노드
- `/dev/ttyS0` 사용 전 `serial-getty@ttyS0.service` 정지

## 접속 주소와 기본 포트

| 항목 | 주소/포트 |
| --- | --- |
| Web UI | `http://172.20.10.5:8000` |
| 노트북 로컬 Web UI | `http://127.0.0.1:8000` |
| rosbridge | `9090` |
| Zenoh router | `7447` |

## 시연 전 확인 토픽

```bash
ros2 topic list | grep -E '/scan|/odom|/pms7003/pm25|/hardware/relay|/air_quality/outdoor_pm25|/air_quality/adaptive_threshold'
```

중요 확인:

- `/scan` publisher가 있어야 LiDAR와 Nav2가 동작합니다.
- `/odom` publisher가 있어야 로봇 위치 추정이 가능합니다.
- `odom -> base_footprint` TF가 있어야 2D Pose Estimate와 Nav2가 정상 동작합니다.
- `/pms7003/pm25` publisher가 있어야 자동 정화 판단이 가능합니다.
- `/hardware/relay` subscriber가 있어야 팬 제어가 가능합니다.

## 시연 순서

1. `./run_demo.sh` 실행
2. Web UI 접속
3. ROS 연결 상태와 지도 표시 확인
4. 수동 모드에서 조이스틱 주행 확인
5. 수동 모드에서 팬 ON/OFF 확인
6. RViz에서 2D Pose Estimate 설정
7. Nav2 목표 이동이 가능한지 확인
8. Web UI에서 자동 모드 선택
9. `주방 집중` 선택
10. 로봇이 주방 주변 정화 후보 지점으로 이동하는지 확인
11. PM2.5 변화와 LiDAR 후보 기반 판단 흐름 설명
12. 오염원 확정 후 정화 방향 정렬과 팬 정화 시연
13. 정화 완료 상태와 필요 시 출발지 복귀 확인

## 실제 확인된 동작

현재 프로젝트 상태 기준으로 다음 항목들이 실제 테스트에서 확인되었습니다.

- 노트북과 TurtleBot Pi가 같은 네트워크에서 통신
- Web UI HTTP 200 응답
- TurtleBot bringup 정상
- `/odom`, `/scan` 수신
- 릴레이 노드 root 권한 실행 후 `/hardware/relay` 구독
- 웹 팬 ON/OFF로 릴레이와 팬 실제 동작
- 수동 `/cmd_vel` 주행
- 웹 조이스틱 수동 주행
- Nav2 lifecycle node 수동 activate 후 goal `SUCCEEDED`
- PMS7003 `/dev/ttyS0`에서 실제 PM2.5 값 수신

## 자주 나는 문제와 해결

### Web UI가 안 뜨는 경우

확인:

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:9090/
```

해결:

```bash
./run_demo.sh
```

또는 노트북 쪽만 재시작:

```bash
USE_ZENOH=1 ./start_laptop.sh
```

### 2D Pose Estimate가 안 잡히는 경우

확인:

```bash
ros2 topic info /scan
ros2 topic info /odom
ros2 run tf2_ros tf2_echo odom base_footprint
```

원인:

- Raspberry Pi bringup이 죽음
- `/scan` 또는 `/odom` publisher 없음
- TF가 들어오지 않음

### PMS7003 센서가 안 뜨는 경우

확인:

```bash
ros2 topic echo /pms7003/pm25 --once
```

해결:

```bash
ssh -t a@172.20.10.2 'sudo systemctl stop serial-getty@ttyS0.service'
ssh -t a@172.20.10.2 'cd /home/a/pollution_robot && PMS_PORT=/dev/ttyS0 ./start_raspberry_pi.sh'
```

### 팬이 안 켜지는 경우

확인:

```bash
ros2 topic echo /hardware/relay --once
ros2 topic pub --once /hardware/relay std_msgs/msg/Bool "{data: true}"
```

원인:

- 릴레이 노드가 죽음
- Raspberry Pi GPIO 권한 문제
- `/hardware/relay` subscriber 없음

### 주방 집중이 전체 순찰처럼 보이는 경우

확인:

```bash
ros2 topic echo /target_zone --once
```

정상 로그 예시:

```text
집중 순찰 구역 변경: kitchen, 후보 N개
```

원인:

- 오래된 자동 정화 프로세스가 살아 있음
- Web UI에서 `/target_zone`이 publish되지 않음
- 시연장 좌표와 주방 집중 구역 범위가 맞지 않음

## 발표용 시연 설명

> 시연은 Web UI에서 시작합니다. 먼저 수동 모드에서 조이스틱과 팬 제어가 되는지 확인하고, 이후 자동 모드에서 주방 집중 정화를 선택합니다. 로봇은 주방 주변 정화 후보 지점을 우선 방문하고, PM2.5 변화량과 LiDAR 후보 정보를 확인한 뒤 현장 측정을 수행합니다. 오염원으로 확정되면 정화 방향을 맞춘 뒤 팬을 작동합니다.
