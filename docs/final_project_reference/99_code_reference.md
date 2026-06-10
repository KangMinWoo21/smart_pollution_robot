# 코드 참고 문서

PPT 제작 시 코드 기반 설명이나 질의응답 대비용으로 사용합니다. 발표 슬라이드에는 전체 코드를 넣기보다, 아래 역할 설명과 짧은 코드 조각만 사용하는 것을 권장합니다.

## 핵심 파일 역할

| 파일 | 역할 |
| --- | --- |
| `cleaning_logic.py` | 자동 정화 판단에 필요한 순수 로직: PM2.5 필터링, 기준값 조정, 정화 후보 지점 파싱/필터링, 하이브리드 탐색 컨트롤러 |
| `real_cleaner.py` | ROS 2 노드로 실행되는 자동 정화 본체: 센서 구독, Nav2 목표 전송, 현장 측정, 오염원 확정, 팬 제어 |
| `pms_ros_node.py` | PMS7003 UART 데이터를 읽어 `/pms7003/pm25` 발행 |
| `relay_control_node.py` | `/hardware/relay`를 구독해 Raspberry Pi GPIO physical pin 12로 릴레이 제어 |
| `outdoor_air_quality_node.py` | 외부 PM2.5 API 또는 mock 값을 `/air_quality/outdoor_pm25`로 발행 |
| `map_web_publisher.py` | Nav2 map을 Web UI용 `/map_web`으로 재발행 |
| `robot_pose_web_publisher.py` | AMCL 또는 odometry pose를 Web UI용 `/robot_pose_web`으로 발행 |
| `cmd_vel_nav_relay.py` | Nav2 smoothed velocity를 TurtleBot이 받는 `/cmd_vel`로 relay |
| `web_ui/index.html` | 관제 화면, 지도, 수동/자동 모드, 주방 집중, 팬 제어 |
| `run_demo.sh` | 노트북과 Raspberry Pi 시연 스택 통합 실행 |
| `start_laptop.sh` | 노트북 쪽 Zenoh, Nav2, Web UI, 자동 정화 실행 |
| `start_raspberry_pi.sh` | Pi 쪽 TurtleBot bringup, PMS, relay 실행 |

## `cleaning_logic.py`

### PM2.5 비정상값 제거

```python
MAX_VALID_PM25 = 500

def normalize_pm25_reading(value):
    if value < 0 or value > MAX_VALID_PM25:
        return None
    return value
```

설명:

- 센서 오류로 비정상적으로 큰 값이 들어오면 자동 정화 판단에서 제외합니다.
- 발표에서는 “센서 이상값 필터링”으로 설명하면 됩니다.

### 외부 미세먼지 기반 기준값 조정

```python
def adaptive_pollution_threshold(outdoor_pm25):
    if outdoor_pm25 is None:
        return DEFAULT_POLLUTION_THRESHOLD
    if outdoor_pm25 > HIGH_OUTDOOR_THRESHOLD:
        return HIGH_POLLUTION_THRESHOLD
    if outdoor_pm25 >= MODERATE_OUTDOOR_THRESHOLD:
        return MODERATE_POLLUTION_THRESHOLD
    return DEFAULT_POLLUTION_THRESHOLD
```

설명:

- 외부 공기질이 나쁘면 실내 오염 판단 기준을 조금 낮춥니다.
- 창문이 닫힌 실내 시연 환경을 고려해 과도하게 낮추지는 않습니다.

### 집중 정화 구역 필터링

```python
def filter_waypoints_for_zone(waypoints, zone_id, zones=None):
    if zone_id in (None, "", "all"):
        return list(waypoints)

    zone_map = DEFAULT_ZONES if zones is None else zones
    if zone_id not in zone_map:
        return list(waypoints)

    min_x, max_x, min_y, max_y = zone_map[zone_id]["bounds"]
    return [
        waypoint for waypoint in waypoints
        if min_x <= waypoint[0] <= max_x and min_y <= waypoint[1] <= max_y
    ]
```

발표용 표현:

- `waypoints`: 정화 후보 지점 목록
- `zone_id`: 집중 정화 구역
- 기능: 주방 집중 구역 안의 후보 지점만 우선 탐색

## `HybridSearchController`

역할:

- 정화 후보 지점을 순서대로 선택합니다.
- PM2.5 변화가 감지되면 주변 추적 모드로 전환합니다.
- 이미 발견한 오염원 주변은 다시 탐색하지 않도록 무시 반경을 적용합니다.
- 주변 후보 측정이 끝나면 가장 높은 측정 지점을 오염원으로 확정합니다.

발표용 흐름:

```text
search: 정화 후보 지점 이동
track: 상승 지점 주변 추가 확인
found: 가장 높은 측정 지점을 오염원으로 확정
```

## `real_cleaner.py`

### 주요 구독 토픽

```python
self.create_subscription(Int32, '/pms7003/pm25', self.sensor_callback, 10)
self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
self.create_subscription(PoseStamped, '/robot_pose_web', self.pose_callback, 10)
self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
self.create_subscription(String, '/target_zone', self.target_zone_callback, 10)
self.create_subscription(Int32, '/air_quality/outdoor_pm25', self.outdoor_pm25_callback, 10)
```

설명:

- 센서, LiDAR, 현재 위치, 웹 모드, 집중 정화 구역, 외부 미세먼지 값을 모두 받아 자동 정화 판단에 사용합니다.

### 주요 발행 토픽

```python
self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
self.relay_pub = self.create_publisher(Bool, '/hardware/relay', 10)
self.threshold_pub = self.create_publisher(Int32, '/air_quality/adaptive_threshold', 10)
self.status_pub = self.create_publisher(String, '/purifier_status', 10)
```

설명:

- 로봇 정지 명령, 팬 제어, 적응형 기준값, 정화 상태를 발행합니다.

### 주방 집중 선택 처리

```python
def target_zone_callback(self, msg):
    zone = msg.data.strip().lower() or "all"
    self.target_zone = zone
    waypoints = AutonomousPurifier.demo_waypoints_for_zone(self, zone)
    if waypoints is None:
        waypoints = filter_waypoints_for_zone(self.patrol_waypoints, zone)
    if not waypoints:
        waypoints = self.patrol_waypoints
    self.search_controller.set_search_waypoints(waypoints)
```

발표용 표현:

> Web UI에서 주방 집중을 선택하면 `/target_zone` 토픽으로 값이 전달되고, 자동 정화 노드는 주방 집중 구역의 정화 후보 지점을 우선 탐색하도록 후보 목록을 갱신합니다.

### LiDAR 후보와 PM2.5 상승 시 추적 전환

```python
def handle_active_pm25_spike(self):
    target_goal = AutonomousPurifier.recent_lidar_target_goal(self) or self.current_pose_goal
    mode = self.search_controller.record_live_signal(target_goal, self.current_pm)
    if mode != "track":
        return False

    self.cancel_active_goal()
    self.stop_robot()
    self.start_next_patrol_goal()
    return True
```

설명:

- 이동 중 PM2.5가 상승하고 최근 LiDAR 후보가 있으면 현재 목표를 취소합니다.
- 이후 후보 주변을 더 자세히 확인하는 추적 흐름으로 전환합니다.

### 오염원 확정 후 팬 정화

```python
def start_purifying(self, reason):
    self.is_purifying = True
    self.purify_started_at = time.monotonic()
    self.current_mode = "manual"
    self.stop_robot()
    self.turn_on_fan()
    self.publish_purifier_status("purifying")
```

설명:

- 오염원 확정 후 로봇을 멈추고 팬을 켭니다.
- 팬은 정해진 시간 동안 작동한 뒤 꺼집니다.

## Web UI 코드 흐름

### 수동/자동 모드

```javascript
function setMode(mode) {
    setControlPanelForMode(mode);
    if (mode === 'manual') openJoystick();
    if (mode === 'auto') closeJoystick();
    modeTopic.publish(new ROSLIB.Message({ data: mode }));
}
```

설명:

- 수동 모드에서는 조이스틱과 팬 제어를 보여줍니다.
- 자동 모드에서는 집중 정화 구역 선택을 보여줍니다.

### 주방 집중 선택

```javascript
function setTargetZone(zone) {
    currentTargetZone = zone;
    updateTargetZoneLabel(zone);
    targetZoneTopic.publish(new ROSLIB.Message({ data: zone }));
    setMode('auto');
}
```

설명:

- `주방 집중` 버튼은 `/target_zone`에 `kitchen`을 발행합니다.
- 동시에 자동 모드로 전환해 로봇이 바로 탐색을 시작하게 합니다.

### 수동 팬 제어

```javascript
function setManualFan(enabled) {
    fanRelayTopic.publish(new ROSLIB.Message({ data: Boolean(enabled) }));
}
```

설명:

- 수동 모드에서는 PM2.5 기준과 관계없이 사용자가 팬을 직접 켜고 끌 수 있습니다.

## 테스트로 검증한 내용

| 테스트 파일 | 검증 내용 |
| --- | --- |
| `test_cleaning_logic.py` | PM2.5 이상값 필터링, 외부 공기질 기준값, 후보 지점 파싱, 주방 구역 필터링, 하이브리드 탐색 |
| `test_real_cleaner.py` | 수동 모드 팬 자동 ON 방지, LiDAR 후보 요구, 현장 측정 기준선, 팬 정렬, 정화 완료, 시연 복귀 |
| `web_ui/index_layout.test.js` | Web UI의 수동/자동 제어, 주방 집중 버튼, 팬 토픽, 지도 마커, 상태 표시 |
| `web_ui/predictive_air_quality.test.js` | 예측 점수, 시간대 위험도, 외부 공기질 기반 기준값 |
| `test_demo_nav_config.sh` | Nav2 시연 설정 파일 유효성 |

## 발표에 넣기 좋은 코드 설명 문장

- `cleaning_logic.py`는 ROS에 의존하지 않는 순수 판단 로직으로 분리해 테스트하기 쉽게 만들었습니다.
- `real_cleaner.py`는 ROS 토픽과 Nav2 액션을 연결해 실제 로봇 동작을 제어합니다.
- Web UI는 `rosbridge`를 통해 브라우저에서 직접 ROS 토픽을 발행하고 구독합니다.
- 팬은 `/hardware/relay` 토픽을 통해 실제 릴레이 제어까지 연결됩니다.
