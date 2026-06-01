# Predictive Air Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add predictive zone ranking plus outdoor PM2.5 based adaptive fan thresholds to the existing TurtleBot3 air purifier demo.

**Architecture:** Keep prediction logic deterministic and testable in `web_ui/predictive_air_quality.js`. Add one optional ROS node, `outdoor_air_quality_node.py`, that publishes outdoor PM2.5 in mock mode first and API mode when configured. Update `real_cleaner.py` to lower the fan ON threshold based on fresh outdoor PM2.5 while preserving the existing indoor sensor safety gate.

**Tech Stack:** ROS 2 Jazzy Python scripts, `std_msgs/Int32`, browser JavaScript, Node.js `assert` tests, Bash launch scripts.

---

## File Structure

- Modify `web_ui/predictive_air_quality.js`: zone ranking helpers plus adaptive threshold helpers.
- Modify `web_ui/predictive_air_quality.test.js`: deterministic Node tests for ranking and thresholds.
- Modify `web_ui/index.html`: subscribe to `/air_quality/outdoor_pm25` and `/air_quality/adaptive_threshold`; show a compact predictive panel.
- Create `outdoor_air_quality_node.py`: optional ROS node with mock mode and API mode.
- Modify `real_cleaner.py`: subscribe to outdoor PM2.5, compute current threshold, publish `/air_quality/adaptive_threshold`.
- Modify `start_laptop.sh`: optionally start the outdoor air node.
- Modify `README.md` and `current_status.md`: document predictive response behavior, environment variables, topics, and checks.

## Task 1: Add Adaptive Threshold Tests And JS Helper

**Files:**
- Modify: `web_ui/predictive_air_quality.test.js`
- Modify: `web_ui/predictive_air_quality.js`

- [ ] **Step 1: Write failing threshold tests**

Add `calculateAdaptiveThreshold` to the test import and append these tests to `web_ui/predictive_air_quality.test.js`:

```js
const {
    rankPredictiveZones,
    getTimeRiskForZone,
    calculateAdaptiveThreshold,
} = require('./predictive_air_quality');

runTest('adaptive threshold stays default when outdoor data is missing or clean', () => {
    assert.strictEqual(calculateAdaptiveThreshold(null), 100);
    assert.strictEqual(calculateAdaptiveThreshold(undefined), 100);
    assert.strictEqual(calculateAdaptiveThreshold(20), 100);
    assert.strictEqual(calculateAdaptiveThreshold(35), 100);
});

runTest('adaptive threshold lowers when outdoor air is bad', () => {
    assert.strictEqual(calculateAdaptiveThreshold(36), 85);
    assert.strictEqual(calculateAdaptiveThreshold(62), 85);
    assert.strictEqual(calculateAdaptiveThreshold(75), 85);
});

runTest('adaptive threshold lowers further when outdoor air is very bad', () => {
    assert.strictEqual(calculateAdaptiveThreshold(76), 70);
    assert.strictEqual(calculateAdaptiveThreshold(120), 70);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node web_ui/predictive_air_quality.test.js
```

Expected: FAIL with an error that `calculateAdaptiveThreshold` is not a function.

- [ ] **Step 3: Implement the helper**

Add this function to `web_ui/predictive_air_quality.js` after `classifyPriority`:

```js
function calculateAdaptiveThreshold(outdoorPm25) {
    const value = Number(outdoorPm25);
    if (!Number.isFinite(value)) return 100;
    if (value > 75) return 70;
    if (value >= 36) return 85;
    return 100;
}
```

Export it in the `api` object:

```js
const api = {
    rankPredictiveZones: rankPredictiveZones,
    getTimeRiskForZone: getTimeRiskForZone,
    classifyPriority: classifyPriority,
    calculateAdaptiveThreshold: calculateAdaptiveThreshold,
};
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
node web_ui/predictive_air_quality.test.js
```

Expected: all existing tests and the three new threshold tests print `PASS`.

- [ ] **Step 5: Commit**

```bash
git add web_ui/predictive_air_quality.js web_ui/predictive_air_quality.test.js
git commit -m "feat: add adaptive threshold helper"
```

## Task 2: Connect Existing Predictive Panel To Outdoor ROS Topics

**Files:**
- Modify: `web_ui/index.html`

- [ ] **Step 1: Locate existing ROS state and PM display code**

Run:

```bash
rg -n "pm25|PM2|robot_mode|ROSLIB.Topic|PredictiveAirQuality|update" web_ui/index.html
```

Expected: confirm the existing variables `currentPm25`, `predictionZones`, `latestPrediction`, and the function `updatePredictiveCare()`.

- [ ] **Step 2: Add outdoor topic state variables**

Near the existing JavaScript state variables after `var pmTopic = null;`, add:

```js
var outdoorPm25Topic = null;
var adaptiveThresholdTopic = null;
var outdoorPm25FromRos = null;
var outdoorPm25UpdatedAt = 0;
var adaptiveThreshold = 100;
```

- [ ] **Step 3: Extend the existing predictive panel markup**

In the existing `.prediction_grid`, keep the manual `outdoor_pm25_input` for mock/demo control and add a fan-threshold metric after the `prediction_basis` metric:

```html
<div class="metric">
    <div class="metric_label">팬 ON 기준</div>
    <div id="adaptive_threshold_value" class="metric_value">100</div>
</div>
<div class="metric">
    <div class="metric_label">외부 데이터</div>
    <div id="outdoor_pm25_source" class="metric_value">수동 입력</div>
</div>
```

- [ ] **Step 4: Subscribe to outdoor topics in `initMap()`**

After the existing `/pms7003/pm25` subscription block in `initMap()`, add:

```js
outdoorPm25Topic = new ROSLIB.Topic({
    ros: ros,
    name: '/air_quality/outdoor_pm25',
    messageType: 'std_msgs/Int32'
});
outdoorPm25Topic.subscribe(function(msg) {
    outdoorPm25FromRos = Number(msg.data);
    outdoorPm25UpdatedAt = Date.now();
    var input = document.getElementById('outdoor_pm25_input');
    if (input && Number.isFinite(outdoorPm25FromRos)) {
        input.value = String(outdoorPm25FromRos);
    }
    updatePredictiveCare();
});

adaptiveThresholdTopic = new ROSLIB.Topic({
    ros: ros,
    name: '/air_quality/adaptive_threshold',
    messageType: 'std_msgs/Int32'
});
adaptiveThresholdTopic.subscribe(function(msg) {
    adaptiveThreshold = Number(msg.data);
    updatePredictiveCare();
});
```

- [ ] **Step 5: Update `updatePredictiveCare()` to show adaptive threshold**

Inside `updatePredictiveCare()`, after `var outdoorPm25 = Number(outdoorInput ? outdoorInput.value : 0);`, add:

```js
var thresholdValue = Number.isFinite(adaptiveThreshold)
    ? adaptiveThreshold
    : window.PredictiveAirQuality.calculateAdaptiveThreshold(outdoorPm25);
var thresholdEl = document.getElementById('adaptive_threshold_value');
if (thresholdEl) thresholdEl.innerText = String(thresholdValue);

var sourceEl = document.getElementById('outdoor_pm25_source');
if (sourceEl) sourceEl.innerText = outdoorPm25FromRos == null ? '수동 입력' : 'ROS 수신';
```

- [ ] **Step 6: Make manual input update the derived threshold before ROS is available**

In the existing `outdoorPm25Input.addEventListener('input', updatePredictiveCare);` block, change it to:

```js
outdoorPm25Input.addEventListener('input', function() {
    if (window.PredictiveAirQuality) {
        adaptiveThreshold = window.PredictiveAirQuality.calculateAdaptiveThreshold(Number(outdoorPm25Input.value));
    }
    updatePredictiveCare();
});
```

- [ ] **Step 7: Smoke test the HTML**

Run:

```bash
node web_ui/predictive_air_quality.test.js
python3 -m py_compile no_cache_web_server.py
```

Expected: Node tests pass and Python compile exits with code 0.

- [ ] **Step 8: Commit**

```bash
git add web_ui/index.html
git commit -m "feat: show predictive air quality panel"
```

## Task 3: Add Outdoor Air Quality Node With Mock Mode

**Files:**
- Create: `outdoor_air_quality_node.py`

- [ ] **Step 1: Create node with deterministic mock mode**

Create `outdoor_air_quality_node.py`:

```python
#!/usr/bin/env python3
import json
import os
import urllib.request

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32


class OutdoorAirQualityNode(Node):
    def __init__(self):
        super().__init__("outdoor_air_quality_node")
        self.publisher = self.create_publisher(Int32, "/air_quality/outdoor_pm25", 10)
        self.mode = os.environ.get("OUTDOOR_AIR_MODE", "mock").strip().lower()
        self.mock_value = int(os.environ.get("OUTDOOR_PM25_MOCK", "62"))
        self.api_url = os.environ.get("OUTDOOR_AIR_API_URL", "").strip()
        self.api_json_path = os.environ.get("OUTDOOR_AIR_API_JSON_PATH", "pm25").strip()
        self.timer = self.create_timer(float(os.environ.get("OUTDOOR_AIR_INTERVAL_SECONDS", "60")), self.publish_reading)
        self.get_logger().info(f"Outdoor air quality node started in {self.mode} mode.")
        self.publish_reading()

    def publish_reading(self):
        value = self.mock_value if self.mode == "mock" else self.fetch_api_value()
        if value is None:
            self.get_logger().warn("Outdoor PM2.5 unavailable; skipping publish.")
            return

        msg = Int32()
        msg.data = int(value)
        self.publisher.publish(msg)
        self.get_logger().info(f"Outdoor PM2.5: {msg.data}")

    def fetch_api_value(self):
        if not self.api_url:
            self.get_logger().warn("OUTDOOR_AIR_API_URL is empty.")
            return None

        try:
            with urllib.request.urlopen(self.api_url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            value = payload
            for key in self.api_json_path.split("."):
                value = value[key]
            return int(float(value))
        except Exception as exc:
            self.get_logger().warn(f"Outdoor air API fetch failed: {exc}")
            return None


def main(args=None):
    rclpy.init(args=args)
    node = OutdoorAirQualityNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Compile the node**

Run:

```bash
python3 -m py_compile outdoor_air_quality_node.py
```

Expected: exits with code 0.

- [ ] **Step 3: Commit**

```bash
git add outdoor_air_quality_node.py
git commit -m "feat: add outdoor air quality node"
```

## Task 4: Add Adaptive Threshold To Real Cleaner

**Files:**
- Modify: `real_cleaner.py`

- [ ] **Step 1: Update imports**

Ensure `time` is imported and `Int32` is already available:

```python
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool, String
from geometry_msgs.msg import TwistStamped
```

- [ ] **Step 2: Add threshold state and topics**

In `AutonomousPurifier.__init__`, replace fixed threshold-only state with:

```python
self.DEFAULT_POLLUTION_THRESHOLD = 100
self.POLLUTION_THRESHOLD = self.DEFAULT_POLLUTION_THRESHOLD
self.CLEAN_THRESHOLD = 45
self.OUTDOOR_STALE_SECONDS = float(os.environ.get("OUTDOOR_AIR_STALE_SECONDS", "1800"))

self.current_pm = 0
self.outdoor_pm25 = None
self.outdoor_pm25_updated_at = 0.0
self.is_purifying = False
self.current_mode = 'manual'
```

Add the new subscription and publisher next to existing ROS interfaces:

```python
self.create_subscription(Int32, '/air_quality/outdoor_pm25', self.outdoor_pm25_callback, 10)
self.threshold_pub = self.create_publisher(Int32, '/air_quality/adaptive_threshold', 10)
```

- [ ] **Step 3: Add threshold helper methods**

Add these methods to `AutonomousPurifier`:

```python
def outdoor_pm25_callback(self, msg):
    self.outdoor_pm25 = int(msg.data)
    self.outdoor_pm25_updated_at = time.monotonic()
    self.update_adaptive_threshold()

def calculate_adaptive_threshold(self):
    if self.outdoor_pm25 is None:
        return self.DEFAULT_POLLUTION_THRESHOLD

    age = time.monotonic() - self.outdoor_pm25_updated_at
    if age > self.OUTDOOR_STALE_SECONDS:
        return self.DEFAULT_POLLUTION_THRESHOLD

    if self.outdoor_pm25 > 75:
        return 70
    if self.outdoor_pm25 >= 36:
        return 85
    return self.DEFAULT_POLLUTION_THRESHOLD

def update_adaptive_threshold(self):
    self.POLLUTION_THRESHOLD = self.calculate_adaptive_threshold()
    msg = Int32()
    msg.data = int(self.POLLUTION_THRESHOLD)
    self.threshold_pub.publish(msg)
```

- [ ] **Step 4: Publish threshold from the behavior loop**

At the start of `behavior_loop`, add:

```python
self.update_adaptive_threshold()
```

This ensures stale external data returns to threshold `100` even if no new outdoor messages arrive.

- [ ] **Step 5: Update pollution log message**

In `sensor_callback`, change the pollution detection log to include the adaptive threshold:

```python
self.get_logger().warn(
    f"🚨 오염 감지! PM2.5={self.current_pm}, threshold={self.POLLUTION_THRESHOLD}. 정화를 시작합니다."
)
```

- [ ] **Step 6: Compile**

Run:

```bash
python3 -m py_compile real_cleaner.py
```

Expected: exits with code 0.

- [ ] **Step 7: Commit**

```bash
git add real_cleaner.py
git commit -m "feat: adapt fan threshold from outdoor air"
```

## Task 5: Start Outdoor Air Node From Laptop Launcher

**Files:**
- Modify: `start_laptop.sh`

- [ ] **Step 1: Add launcher flag**

Near the existing `START_*` variables, add:

```bash
START_OUTDOOR_AIR="${START_OUTDOOR_AIR:-1}"
OUTDOOR_AIR_NODE="${OUTDOOR_AIR_NODE:-$PROJECT_DIR/outdoor_air_quality_node.py}"
```

- [ ] **Step 2: Export outdoor configuration inside `start_process`**

Inside the `bash -lc` block in `start_process`, add:

```bash
    export OUTDOOR_AIR_MODE='${OUTDOOR_AIR_MODE:-mock}'
    export OUTDOOR_PM25_MOCK='${OUTDOOR_PM25_MOCK:-62}'
    export OUTDOOR_AIR_API_URL='${OUTDOOR_AIR_API_URL:-}'
    export OUTDOOR_AIR_API_JSON_PATH='${OUTDOOR_AIR_API_JSON_PATH:-pm25}'
    export OUTDOOR_AIR_INTERVAL_SECONDS='${OUTDOOR_AIR_INTERVAL_SECONDS:-60}'
    export OUTDOOR_AIR_STALE_SECONDS='${OUTDOOR_AIR_STALE_SECONDS:-1800}'
```

- [ ] **Step 3: Echo configuration**

In the startup summary, add:

```bash
echo "OUTDOOR_AIR_MODE=${OUTDOOR_AIR_MODE:-mock}"
echo "OUTDOOR_PM25_MOCK=${OUTDOOR_PM25_MOCK:-62}"
```

- [ ] **Step 4: Start the node before FSM**

Before the `START_FSM` block, add:

```bash
if [[ "$START_OUTDOOR_AIR" == "1" ]]; then
  if [[ -f "$OUTDOOR_AIR_NODE" ]]; then
    start_process "outdoor_air_quality" "python3 '$OUTDOOR_AIR_NODE'"
    sleep 1
  else
    echo "[warn] outdoor air quality node not found: $OUTDOOR_AIR_NODE"
  fi
fi
```

- [ ] **Step 5: Check shell syntax**

Run:

```bash
bash -n start_laptop.sh
```

Expected: exits with code 0.

- [ ] **Step 6: Commit**

```bash
git add start_laptop.sh
git commit -m "feat: launch outdoor air quality node"
```

## Task 6: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `current_status.md`

- [ ] **Step 1: Add topics to README**

In the README topic table, add:

```markdown
| `/air_quality/outdoor_pm25` | `std_msgs/Int32` | `outdoor_air_quality_node.py` | `real_cleaner.py`, 웹 UI | 외부 PM2.5 |
| `/air_quality/adaptive_threshold` | `std_msgs/Int32` | `real_cleaner.py` | 웹 UI | 현재 팬 ON 기준 |
```

- [ ] **Step 2: Add environment variables to README**

Near the `start_laptop.sh` environment examples, add:

```bash
OUTDOOR_AIR_MODE=mock OUTDOOR_PM25_MOCK=62 ./start_laptop.sh
OUTDOOR_AIR_MODE=api OUTDOOR_AIR_API_URL='https://example.com/air.json' OUTDOOR_AIR_API_JSON_PATH='pm25' ./start_laptop.sh
```

- [ ] **Step 3: Add adaptive threshold explanation to README**

Add this paragraph near the FSM section:

```markdown
외부 PM2.5 값이 들어오면 팬 ON 기준은 적응형으로 바뀝니다. 외부 데이터가 없거나 정상 수준이면 기준은 `100`이고, 외부 PM2.5가 `36-75`이면 `85`, `76` 이상이면 `70`으로 낮아집니다. 외부 대기질만으로 팬을 켜지는 않고, 실내 PMS7003 값이 현재 기준 이상일 때만 정화를 시작합니다.
```

- [ ] **Step 4: Update current status**

In `current_status.md`, add completed/remaining entries:

```markdown
- 외부 PM2.5 기반 적응형 팬 기준 설계 및 구현
- 선제 대응 UI 패널 추가
```

Add remaining field checks:

```markdown
- mock 외부 PM2.5 값 `62`에서 팬 기준이 `85`로 표시되는지 확인
- 외부 API 모드 사용 시 실제 API 응답 JSON path 확인
```

- [ ] **Step 5: Commit**

```bash
git add README.md current_status.md
git commit -m "docs: document predictive air quality response"
```

## Task 7: Final Verification

**Files:**
- Verify all modified files from Tasks 1-6.

- [ ] **Step 1: Run JavaScript tests**

```bash
node web_ui/predictive_air_quality.test.js
```

Expected: all tests print `PASS`.

- [ ] **Step 2: Run Python compile checks**

```bash
python3 -m py_compile real_cleaner.py outdoor_air_quality_node.py map_web_publisher.py robot_pose_web_publisher.py no_cache_web_server.py pms_ros_node.py relay_control_node.py virtual_cleaner.py scan_masker.py my_cartographer.launch.py
```

Expected: exits with code 0.

- [ ] **Step 3: Run shell syntax checks**

```bash
bash -n run_demo.sh start_laptop.sh start_raspberry_pi.sh stop_demo.sh
```

Expected: exits with code 0.

- [ ] **Step 4: Review final diff**

```bash
git diff --stat HEAD
git status --short
```

Expected: only intentional files are modified or untracked.

- [ ] **Step 5: Commit final verification fixes if any**

If verification required fixes, commit those fixes:

```bash
git add web_ui/predictive_air_quality.js web_ui/predictive_air_quality.test.js web_ui/index.html outdoor_air_quality_node.py real_cleaner.py start_laptop.sh README.md current_status.md
git commit -m "fix: complete predictive air quality verification"
```

If no fixes were needed, do not create an empty commit.

## Self-Review Notes

- Spec coverage: zone ranking, adaptive threshold, outdoor PM2.5 node, UI panel, launcher integration, documentation, and verification are covered.
- Scope control: AI room recognition and autonomous Nav2 dispatch remain outside the first implementation.
- Type consistency: outdoor PM2.5 and adaptive threshold use `std_msgs/Int32`; JS and Python threshold boundaries match `100 / 85 / 70`.
- Fallback behavior: missing, invalid, or stale outdoor data returns to threshold `100`.

