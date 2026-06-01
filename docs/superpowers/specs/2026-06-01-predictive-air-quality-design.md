# Predictive Air Quality Response Design

## Goal

Add a predictive air-quality response concept to the TurtleBot3 air purifier robot without destabilizing the current ROS 2 demo flow.

The feature should show that the robot can respond before pollution becomes severe by combining:

- map-based high-risk zones such as kitchen, bathroom, entry, and window areas
- time-of-day risk patterns such as meal preparation or bathroom usage hours
- live indoor PM2.5 readings from PMS7003
- outdoor PM2.5 from an internet air-quality API
- adaptive fan thresholds that become more sensitive when outdoor air quality is poor

This design intentionally keeps the first implementation rule-based. AI-based place recognition is represented as an extension path: the data model should allow future AI output to label map zones automatically, but the first demo can use manually configured zones.

## Scope

### In Scope

- Define predictive zones on the map with type, position, base risk, latest PM2.5, and recent visit metadata.
- Rank zones by predicted risk using zone type, time of day, indoor PM2.5, outdoor PM2.5, distance, and recent visits.
- Display the top-priority zone and its reasons in the web UI.
- Fetch or mock outdoor PM2.5 through a separate ROS node.
- Publish outdoor PM2.5 into ROS so both UI and control logic can use it.
- Adapt the fan ON threshold in `real_cleaner.py` based on outdoor PM2.5.
- Fall back to the default threshold when API data is missing or stale.

### Out of Scope For First Implementation

- Fully automatic AI image/map recognition of rooms.
- Autonomous Nav2 goal dispatch to predicted zones.
- Long-term learning from historical pollution measurements.
- Cloud account management or production API key storage.

These can be presented as future improvements.

## User-Facing Behavior

The web UI gets a "predictive response" panel. It should show:

- current indoor PM2.5
- current outdoor PM2.5, or "external data unavailable"
- current fan ON threshold
- highest-priority zone, such as kitchen or bathroom
- reasons for the ranking, such as "meal preparation time", "outdoor fine dust influence", or "unmeasured zone"

Example:

```text
Priority zone: Kitchen
Risk: 86 / 100
Reasons: meal preparation time, high-risk zone, recently unmeasured
Outdoor PM2.5: 62
Fan threshold: 85
```

## Zone Model

Each predictive zone should use a small structured object:

```js
{
  id: "kitchen-1",
  label: "Kitchen",
  type: "kitchen",
  x: 1.2,
  y: -0.5,
  baseRisk: 30,
  lastPm25: 58,
  recentVisitMinutes: 45,
  distance: 1.8
}
```

Initial zone types:

- `kitchen`: high baseline risk, meal-time boost
- `bathroom`: medium-high baseline risk, morning/night boost
- `entry`: outdoor-air-sensitive zone
- `window`: outdoor-air-sensitive zone
- `living`: normal baseline risk
- `corridor`: low baseline risk

Future AI place recognition can populate `type`, `label`, and approximate coordinates. The first implementation can hard-code or manually configure these values.

## Risk Ranking

The existing `web_ui/predictive_air_quality.js` module is the right place for ranking logic.

Inputs:

- `zones`
- `hour`
- `currentPm25`
- `outdoorPm25`
- robot-to-zone distance
- recent visit age

Outputs:

- sorted zones
- `score` from 0 to 100
- `priority` label
- `reasons`

Risk contributors:

- zone baseline risk
- measured indoor PM2.5
- time-of-day boost
- outdoor PM2.5 boost for entry/window zones
- unexplored-zone bonus
- distance cost
- recent-visit penalty

The function should remain deterministic and unit-testable.

## Adaptive Fan Threshold

`real_cleaner.py` currently uses:

```text
POLLUTION_THRESHOLD = 100
CLEAN_THRESHOLD = 45
```

The fan ON threshold should become adaptive:

| Outdoor PM2.5 state | Outdoor PM2.5 range | Fan ON threshold |
| --- | ---: | ---: |
| Data unavailable | unknown or stale | 100 |
| Normal | < 36 | 100 |
| Bad | 36-75 | 85 |
| Very bad | > 75 | 70 |

The clean threshold can stay fixed at `45` for the first implementation. This prevents frequent fan toggling and keeps the control logic easy to explain.

Safety rule:

- Outdoor PM2.5 never turns the fan on by itself.
- It only lowers the indoor PM2.5 threshold needed to turn the fan on.
- If external data is stale, the system returns to the conservative default threshold `100`.

## ROS Data Flow

Add one optional node:

```text
outdoor_air_quality_node.py
```

Responsibilities:

- read API configuration from environment variables
- periodically fetch outdoor PM2.5
- publish latest PM2.5 as a ROS topic
- support mock mode for demos without internet or API keys
- mark data stale when the last successful fetch is too old

Suggested topics:

| Topic | Type | Publisher | Subscriber | Purpose |
| --- | --- | --- | --- | --- |
| `/air_quality/outdoor_pm25` | `std_msgs/Int32` | `outdoor_air_quality_node.py` | `real_cleaner.py`, UI bridge | Outdoor PM2.5 |
| `/air_quality/adaptive_threshold` | `std_msgs/Int32` | `real_cleaner.py` | Web UI | Current fan ON threshold |

`real_cleaner.py` should subscribe to `/air_quality/outdoor_pm25`, compute the current threshold, and publish `/air_quality/adaptive_threshold`.

## API Handling

The first implementation should not depend on a specific paid API.

Recommended behavior:

- `OUTDOOR_AIR_MODE=mock`: publish a configurable value such as `62`
- `OUTDOOR_AIR_MODE=api`: call a real API endpoint
- `OUTDOOR_PM25_MOCK=62`: mock value
- `OUTDOOR_AIR_STALE_SECONDS=1800`: stale-data window

If API mode is configured but fetch fails:

- keep the last value until it becomes stale
- log a warning
- publish no new value
- let `real_cleaner.py` fall back to threshold `100` when stale

## Web UI Integration

The UI should use the existing `PredictiveAirQuality` module and add a compact panel rather than a new page.

Panel contents:

- top zone name and score
- reason chips
- outdoor PM2.5
- adaptive fan threshold
- API status

The map can optionally show simple zone markers. This can be a lightweight overlay using configured coordinates; it does not need full AI recognition in the first version.

## Testing

Unit tests:

- kitchen ranks high during meal times
- bathroom receives morning/night boost
- entry/window risk rises when outdoor PM2.5 is high
- adaptive threshold is `100`, `85`, or `70` based on outdoor PM2.5
- stale or missing outdoor data returns threshold `100`

Syntax checks:

- `node web_ui/predictive_air_quality.test.js`
- `python3 -m py_compile real_cleaner.py outdoor_air_quality_node.py`
- `bash -n start_laptop.sh start_raspberry_pi.sh run_demo.sh stop_demo.sh`

Manual demo checks:

- mock outdoor PM2.5 normal: threshold stays `100`
- mock outdoor PM2.5 bad: threshold becomes `85`
- mock outdoor PM2.5 very bad: threshold becomes `70`
- indoor PM2.5 above adaptive threshold turns fan on
- API/mock unavailable returns to threshold `100`

## Risks And Mitigations

- API key or internet unavailable: use mock mode and stale fallback.
- Over-sensitive fan behavior: outdoor data only lowers the threshold; it never directly turns the fan on.
- UI complexity: show only the top recommendation and current threshold in the first version.
- AI scope creep: keep room labeling manual now, describe automatic recognition as a future extension.

## Implementation Order

1. Extend predictive JS tests for adaptive thresholds.
2. Add threshold helper to `web_ui/predictive_air_quality.js`.
3. Update web UI to show outdoor PM2.5, adaptive threshold, and top zone reasons.
4. Add `outdoor_air_quality_node.py` with mock mode first.
5. Update `real_cleaner.py` to subscribe to outdoor PM2.5 and publish adaptive threshold.
6. Add launcher integration in `start_laptop.sh`.
7. Update README and `current_status.md`.

