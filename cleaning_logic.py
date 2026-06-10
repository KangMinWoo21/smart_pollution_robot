MAX_VALID_PM25 = 500
DEFAULT_POLLUTION_THRESHOLD = 50
HUMIDIFIER_SUSPECT_PM25_THRESHOLD = 36
MODERATE_OUTDOOR_THRESHOLD = 36
HIGH_OUTDOOR_THRESHOLD = 75
MODERATE_POLLUTION_THRESHOLD = 48
HIGH_POLLUTION_THRESHOLD = 45

DEFAULT_PATROL_WAYPOINTS = [
    (3.07, 4.98, -1.59),
    (5.18, 1.62, 0.05),
    (8.00, 1.40, 1.47),
    (7.50, 5.19, -2.90),
    (5.42, 4.68, 3.01),
]

DEFAULT_ZONES = {
    "kitchen": {
        "label": "주방",
        "bounds": (6.61, 8.33, 1.40, 6.05),
    },
    "living": {
        "label": "거실",
        "bounds": (-6.6, -4.6, 2.4, 4.4),
    },
}


def normalize_pm25_reading(value):
    if value < 0 or value > MAX_VALID_PM25:
        return None
    return value


def adaptive_pollution_threshold(outdoor_pm25):
    if outdoor_pm25 is None:
        return DEFAULT_POLLUTION_THRESHOLD
    if outdoor_pm25 > HIGH_OUTDOOR_THRESHOLD:
        return HIGH_POLLUTION_THRESHOLD
    if outdoor_pm25 >= MODERATE_OUTDOOR_THRESHOLD:
        return MODERATE_POLLUTION_THRESHOLD
    return DEFAULT_POLLUTION_THRESHOLD


def distance_xy(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def is_humidifier_suspected_pm25(pm25_value):
    return float(pm25_value) >= HUMIDIFIER_SUSPECT_PM25_THRESHOLD


def should_interrupt_for_pm25_spike(current_pm25, recent_pm25_values, trigger_threshold, trigger_delta):
    current = float(current_pm25)
    values = [float(value) for value in recent_pm25_values]
    if not values:
        return False

    baseline = min(values)
    return current > baseline + float(trigger_delta)


def filter_waypoints_for_zone(waypoints, zone_id, zones=None):
    if zone_id in (None, "", "all"):
        return list(waypoints)

    zone_map = DEFAULT_ZONES if zones is None else zones
    if zone_id not in zone_map:
        return list(waypoints)

    min_x, max_x, min_y, max_y = zone_map[zone_id]["bounds"]
    filtered = [
        waypoint for waypoint in waypoints
        if min_x <= waypoint[0] <= max_x and min_y <= waypoint[1] <= max_y
    ]
    return filtered


def parse_patrol_waypoints(value):
    if value is None or value.strip() == "":
        return list(DEFAULT_PATROL_WAYPOINTS)

    waypoints = []
    for entry in value.split(";"):
        parts = [part.strip() for part in entry.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Invalid waypoint entry: {entry}")
        try:
            x, y, yaw = (float(part) for part in parts)
        except ValueError as exc:
            raise ValueError(f"Invalid waypoint entry: {entry}") from exc
        waypoints.append((x, y, yaw))

    if not waypoints:
        raise ValueError("At least one patrol waypoint is required")
    return waypoints


class HybridSearchController:
    def __init__(
        self,
        search_waypoints,
        trigger_threshold=70,
        trigger_delta=15,
        track_step_m=0.6,
        improvement_delta=5,
        ignore_radius_m=1.0,
        signal_ignore_radius_m=1.8,
    ):
        if not search_waypoints:
            raise ValueError("At least one search waypoint is required")
        self.search_waypoints = list(search_waypoints)
        self.trigger_threshold = trigger_threshold
        self.trigger_delta = trigger_delta
        self.track_step_m = track_step_m
        self.improvement_delta = improvement_delta
        self.ignore_radius_m = ignore_radius_m
        self.signal_ignore_radius_m = signal_ignore_radius_m
        self.ignored_targets = []
        self.found_targets = []
        self.mode = "search"
        self.search_index = 0
        self.best_sample = None
        self.track_candidates = []
        self.track_index = 0

    def next_goal(self):
        if self.mode == "found":
            return self.best_goal()
        if self.mode == "track":
            while self.track_index < len(self.track_candidates):
                candidate = self.track_candidates[self.track_index]
                if not self.is_ignored(candidate):
                    return candidate
                self.track_index += 1
            self.mode = "found"
            return self.best_goal()
        return self._next_search_goal()

    def set_search_waypoints(self, search_waypoints):
        if not search_waypoints:
            raise ValueError("At least one search waypoint is required")
        self.search_waypoints = list(search_waypoints)
        self.search_index = 0
        self.mode = "search"
        self.best_sample = None
        self.track_candidates = []
        self.track_index = 0

    def add_ignored_target(self, goal):
        self.ignored_targets.append(tuple(goal))

    def is_ignored(self, goal):
        return any(distance_xy(goal, ignored) <= self.ignore_radius_m for ignored in self.ignored_targets)

    def is_signal_ignored(self, goal):
        return any(distance_xy(goal, ignored) <= self.signal_ignore_radius_m for ignored in self.ignored_targets)

    def record_found_target_and_continue(self):
        found_goal = self.best_goal()
        if found_goal is None:
            return None
        self.found_targets.append(found_goal)
        self.add_ignored_target(found_goal)
        self.mode = "search"
        self.best_sample = None
        self.track_candidates = []
        self.track_index = 0
        return found_goal

    def _next_search_goal(self):
        for offset in range(len(self.search_waypoints)):
            index = (self.search_index + offset) % len(self.search_waypoints)
            candidate = self.search_waypoints[index]
            if not self.is_ignored(candidate):
                self.search_index = index
                return candidate
        return None

    def record_live_signal(self, goal, pm25_value):
        goal = tuple(goal)
        if self.is_signal_ignored(goal):
            return self.mode

        value = float(pm25_value)
        previous_best = self.best_sample
        if previous_best is None or value > previous_best[1]:
            self.best_sample = (goal, value)

        if self._should_start_tracking(value, previous_best):
            self._start_tracking_around(goal)
        return self.mode

    def record_sample(self, goal, pm25_average, baseline_pm25=None):
        goal = tuple(goal)
        if self.is_signal_ignored(goal):
            if self.mode == "track":
                self.track_index += 1
                if self.track_index >= len(self.track_candidates):
                    self.mode = "found" if self.best_sample is not None else "search"
            elif self.mode == "search":
                self.search_index += 1
            return self.mode

        value = float(pm25_average)
        previous_best = self.best_sample

        if previous_best is None or value > previous_best[1]:
            self.best_sample = (goal, value)

        if self.mode == "search":
            self.search_index += 1
            if self._should_start_tracking(value, previous_best, baseline_pm25):
                self._start_tracking_around(goal)
            return self.mode

        if self.mode == "track":
            self.track_index += 1
            if previous_best is None or value > previous_best[1] + self.improvement_delta:
                self._start_tracking_around(goal)
            elif self.track_index >= len(self.track_candidates):
                self.mode = "found"
            return self.mode

        return self.mode

    def best_goal(self):
        if self.best_sample is None:
            return None
        return self.best_sample[0]

    def _should_start_tracking(self, value, previous_best, baseline_pm25=None):
        baseline = None
        if baseline_pm25 is not None:
            baseline = float(baseline_pm25)
        elif previous_best is not None:
            baseline = float(previous_best[1])
        if baseline is None:
            return False
        return value > baseline + self.trigger_delta

    def _start_tracking_around(self, goal):
        x, y, yaw = goal
        step = self.track_step_m
        self.mode = "track"
        self.track_candidates = [
            (x + step, y, 3.14),
            (x, y + step, -1.57),
            (x - step, y, 0.0),
            (x, y - step, 1.57),
        ]
        self.track_index = 0


def select_next_waypoint_index(current_index, waypoint_count):
    if waypoint_count <= 0:
        raise ValueError("waypoint_count must be positive")
    if current_index is None:
        return 0
    return (current_index + 1) % waypoint_count
