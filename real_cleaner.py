import math
import os
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy._rclpy_pybind11 import RCLError
from std_msgs.msg import Int32, Bool, String
from geometry_msgs.msg import TwistStamped, PoseStamped
from sensor_msgs.msg import LaserScan
from nav2_msgs.action import NavigateToPose

from cleaning_logic import (
    DEFAULT_POLLUTION_THRESHOLD,
    adaptive_pollution_threshold,
    HybridSearchController,
    normalize_pm25_reading,
    filter_waypoints_for_zone,
    parse_patrol_waypoints,
    should_interrupt_for_pm25_spike,
    is_humidifier_suspected_pm25,
)


def yaw_to_quaternion(yaw):
    half_yaw = yaw * 0.5
    return math.sin(half_yaw), math.cos(half_yaw)


def normalize_yaw(yaw):
    return math.atan2(math.sin(yaw), math.cos(yaw))


def quaternion_to_yaw(q):
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)


def detect_round_lidar_obstacle(ranges, angle_min, angle_increment, min_range, max_range, target_diameter=0.10, tolerance=0.05, max_center_range=1.6):
    clusters = []
    current = []
    for index, value in enumerate(ranges):
        distance = float(value)
        valid = math.isfinite(distance) and min_range <= distance <= max_range and distance <= max_center_range
        if not valid:
            if current:
                clusters.append(current)
                current = []
            continue
        angle = angle_min + index * angle_increment
        current.append((distance * math.cos(angle), distance * math.sin(angle)))
    if current:
        clusters.append(current)

    best = None
    best_error = None
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        xs = [point[0] for point in cluster]
        ys = [point[1] for point in cluster]
        diameter = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if abs(diameter - target_diameter) > tolerance:
            continue
        center = (sum(xs) / len(xs), sum(ys) / len(ys))
        error = abs(diameter - target_diameter)
        if best is None or error < best_error:
            best = (center[0], center[1], diameter)
            best_error = error
    return best


class AutonomousPurifier(Node):
    def __init__(self):
        super().__init__('autonomous_purifier')
        
        self.DEFAULT_POLLUTION_THRESHOLD = DEFAULT_POLLUTION_THRESHOLD
        self.POLLUTION_THRESHOLD = self.DEFAULT_POLLUTION_THRESHOLD
        self.CLEAN_THRESHOLD = 45
        self.OUTDOOR_STALE_SECONDS = float(os.environ.get("OUTDOOR_AIR_STALE_SECONDS", "1800"))
        
        self.current_pm = 0
        self.outdoor_pm25 = None
        self.outdoor_pm25_updated_at = 0.0
        self.is_purifying = False
        self.purify_started_at = None
        self.purify_duration_seconds = float(os.environ.get("TARGET_PURIFY_SECONDS", "7"))
        self.current_mode = 'manual' # 기본은 수동 모드
        self.goal_in_progress = False
        self.active_goal_handle = None
        self.goal_sequence = 0
        self.last_nav_warning_at = 0.0
        self.pm25_samples = []
        self.normal_baseline_pm25 = None
        self.sample_started_at = None
        self.sample_goal = None
        self.sample_baseline_pm25 = None
        self.active_goal = None
        self.active_goal_kind = None
        self.current_pose_goal = None
        self.last_live_interrupt_at = 0.0
        self.live_interrupt_cooldown_seconds = float(os.environ.get("TARGET_LIVE_INTERRUPT_COOLDOWN_SECONDS", "4"))
        live_interrupt_zones = os.environ.get("TARGET_LIVE_INTERRUPT_ZONES", "kitchen")
        self.live_interrupt_zones = {zone.strip().lower() for zone in live_interrupt_zones.split(",") if zone.strip()}
        self.lidar_target_diameter_m = float(os.environ.get("TARGET_LIDAR_DIAMETER_M", "0.10"))
        self.lidar_target_tolerance_m = float(os.environ.get("TARGET_LIDAR_DIAMETER_TOLERANCE_M", "0.05"))
        self.lidar_target_max_range_m = float(os.environ.get("TARGET_LIDAR_MAX_RANGE_M", "1.6"))
        self.lidar_target_stale_seconds = float(os.environ.get("TARGET_LIDAR_STALE_SECONDS", "2.5"))
        self.latest_lidar_target = None
        self.latest_lidar_target_at = 0.0
        self.pending_purify_average_pm25 = None
        self.sample_duration_seconds = float(os.environ.get("TARGET_SAMPLE_SECONDS", "4"))
        self.target_zone = os.environ.get("TARGET_ZONE", "all").strip().lower() or "all"
        self.max_targets = int(os.environ.get("TARGET_COUNT", "2"))
        demo_scenario = os.environ.get("TARGET_DEMO_SCENARIO", "1").strip().lower()
        self.demo_scenario_enabled = demo_scenario not in ("0", "false", "no", "off")
        self.demo_first_clean_done = False
        self.demo_pending_clean_zone = None
        self.second_search_started_at = None
        self.second_search_cooldown_seconds = float(
            os.environ.get("TARGET_SECOND_SEARCH_COOLDOWN_SECONDS", "15")
        )
        try:
            self.patrol_waypoints = parse_patrol_waypoints(os.environ.get("AUTO_CLEAN_WAYPOINTS", ""))
        except ValueError as exc:
            self.get_logger().error(f"AUTO_CLEAN_WAYPOINTS 값 오류, 기본 순찰 지점 사용: {exc}")
            self.patrol_waypoints = parse_patrol_waypoints("")
        self.search_controller = HybridSearchController(
            filter_waypoints_for_zone(self.patrol_waypoints, self.target_zone) or self.patrol_waypoints,
            trigger_threshold=float(os.environ.get("TARGET_PM25_THRESHOLD", "70")),
            trigger_delta=float(os.environ.get("TARGET_PM25_TRIGGER_DELTA", "15")),
            track_step_m=float(os.environ.get("TARGET_TRACK_STEP_M", "0.6")),
            improvement_delta=float(os.environ.get("TARGET_PM25_IMPROVEMENT_DELTA", "5")),
            ignore_radius_m=float(os.environ.get("TARGET_IGNORE_RADIUS_M", "1.0")),
            signal_ignore_radius_m=float(os.environ.get("TARGET_SIGNAL_IGNORE_RADIUS_M", "1.8")),
        )
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 구독 및 발행 설정
        self.create_subscription(Int32, '/pms7003/pm25', self.sensor_callback, 10)
        self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.create_subscription(PoseStamped, '/robot_pose_web', self.pose_callback, 10)
        self.create_subscription(String, '/robot_mode', self.mode_callback, 10)
        self.create_subscription(String, '/target_zone', self.target_zone_callback, 10)
        self.create_subscription(Int32, '/air_quality/outdoor_pm25', self.outdoor_pm25_callback, 10)
        self.cmd_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.relay_pub = self.create_publisher(Bool, '/hardware/relay', 10)
        self.threshold_pub = self.create_publisher(Int32, '/air_quality/adaptive_threshold', 10)
        self.status_pub = self.create_publisher(String, '/purifier_status', 10)
        
        # 0.5초마다 주행 상태를 제어하는 타이머
        self.timer = self.create_timer(0.5, self.behavior_loop)
        
        self.get_logger().info(f"실전 관제용 두뇌 가동: Nav2 자동 순찰 지점 {len(self.patrol_waypoints)}개 준비")

    def pose_callback(self, msg):
        if msg.header.frame_id != "map":
            return
        pose = msg.pose
        yaw = quaternion_to_yaw(pose.orientation)
        self.current_pose_goal = (pose.position.x, pose.position.y, yaw)

    def scan_callback(self, msg):
        if self.current_pose_goal is None:
            return
        obstacle = detect_round_lidar_obstacle(
            msg.ranges,
            msg.angle_min,
            msg.angle_increment,
            msg.range_min,
            msg.range_max,
            self.lidar_target_diameter_m,
            self.lidar_target_tolerance_m,
            self.lidar_target_max_range_m,
        )
        if obstacle is None:
            return

        robot_x, robot_y, robot_yaw = self.current_pose_goal
        local_x, local_y, diameter = obstacle
        world_x = robot_x + math.cos(robot_yaw) * local_x - math.sin(robot_yaw) * local_y
        world_y = robot_y + math.sin(robot_yaw) * local_x + math.cos(robot_yaw) * local_y
        self.latest_lidar_target = (world_x, world_y, robot_yaw, diameter)
        self.latest_lidar_target_at = time.monotonic()

    def recent_lidar_target_goal(self, now=None):
        latest = getattr(self, "latest_lidar_target", None)
        if latest is None:
            return None
        current_time = time.monotonic() if now is None else now
        stale_seconds = getattr(self, "lidar_target_stale_seconds", 2.5)
        if current_time - getattr(self, "latest_lidar_target_at", 0.0) > stale_seconds:
            return None
        x, y, yaw, _diameter = latest
        return (x, y, yaw)

    def recent_lidar_target(self, now=None):
        latest = getattr(self, "latest_lidar_target", None)
        if latest is None:
            return None
        current_time = time.monotonic() if now is None else now
        stale_seconds = getattr(self, "lidar_target_stale_seconds", 2.5)
        if current_time - getattr(self, "latest_lidar_target_at", 0.0) > stale_seconds:
            return None
        return latest

    def lidar_confirmed_measurement_goal(self, now=None):
        if self.current_pose_goal is None:
            return None
        latest = self.recent_lidar_target(now)
        if latest is None:
            return None

        target_x, target_y, _target_yaw, diameter = latest
        robot_x, robot_y, _robot_yaw = self.current_pose_goal
        yaw_to_target = math.atan2(target_y - robot_y, target_x - robot_x)
        return (robot_x, robot_y, yaw_to_target), diameter

    def mode_callback(self, msg):
        """아이패드에서 수동/자동 버튼을 누를 때 실행되는 함수"""
        new_mode = msg.data.strip().lower()
        if new_mode not in ("auto", "manual"):
            self.get_logger().warn(f"알 수 없는 로봇 모드 무시: {msg.data}")
            return

        if self.current_mode == "auto" and new_mode == "manual":
            self.get_logger().warn("자동 모드 해제 -> Nav2 목표 취소 및 정지")
            self.cancel_active_goal()
            self.stop_robot()

        if new_mode == "manual":
            self.is_purifying = False

        self.current_mode = new_mode
        self.get_logger().info(f"모드 변경됨: {self.current_mode.upper()} 모드")

        if self.current_mode == "auto" and not self.is_purifying:
            self.refresh_normal_baseline("auto")
            self.start_next_patrol_goal()

    def target_zone_callback(self, msg):
        zone = msg.data.strip().lower() or "all"
        self.target_zone = zone
        waypoints = AutonomousPurifier.demo_waypoints_for_zone(self, zone)
        if waypoints is None:
            waypoints = filter_waypoints_for_zone(self.patrol_waypoints, zone)
        if not waypoints:
            self.get_logger().warn(f"선택 구역에 순찰 지점이 없어 전체 탐색을 사용합니다: {zone}")
            waypoints = self.patrol_waypoints
        self.search_controller.set_search_waypoints(waypoints)
        self.get_logger().info(f"집중 순찰 구역 변경: {zone}, 후보 {len(waypoints)}개")
        if self.current_mode == "auto":
            self.cancel_active_goal()
            self.refresh_normal_baseline(zone)
            self.start_next_patrol_goal()

    def demo_waypoints_for_zone(self, zone):
        if not getattr(self, "demo_scenario_enabled", False):
            return None
        if len(getattr(self, "patrol_waypoints", [])) < 4:
            return None

        normalized_zone = (zone or "all").strip().lower()
        if normalized_zone == "kitchen":
            return [self.patrol_waypoints[2], self.patrol_waypoints[3]]
        if normalized_zone == "all" and getattr(self, "demo_first_clean_done", False):
            return [self.patrol_waypoints[0]]
        return None

    def outdoor_pm25_callback(self, msg):
        self.outdoor_pm25 = int(msg.data)
        self.outdoor_pm25_updated_at = time.monotonic()
        self.update_adaptive_threshold()

    def calculate_adaptive_threshold(self):
        if self.outdoor_pm25 is None:
            return adaptive_pollution_threshold(None)

        age = time.monotonic() - self.outdoor_pm25_updated_at
        if age > self.OUTDOOR_STALE_SECONDS:
            return adaptive_pollution_threshold(None)

        return adaptive_pollution_threshold(self.outdoor_pm25)

    def update_adaptive_threshold(self):
        self.POLLUTION_THRESHOLD = self.calculate_adaptive_threshold()
        msg = Int32()
        msg.data = int(self.POLLUTION_THRESHOLD)
        self.threshold_pub.publish(msg)

    def sensor_callback(self, msg):
        pm25 = normalize_pm25_reading(msg.data)
        if pm25 is None:
            self.get_logger().warn(f"비정상 PM2.5 값 무시: {msg.data}")
            return

        now = time.monotonic()
        recent_values = [value for timestamp, value in self.pm25_samples if now - timestamp <= 10.0]
        self.current_pm = pm25
        self.pm25_samples.append((now, pm25))
        self.pm25_samples = [sample for sample in self.pm25_samples if now - sample[0] <= 30.0]

        if self.should_interrupt_active_goal(pm25, recent_values, now):
            self.handle_active_pm25_spike()
            return
        
        # 수동 모드에서는 PM2.5 값으로 팬을 자동 제어하지 않는다.
        # 팬은 웹 UI의 수동 ON/OFF 버튼이 /hardware/relay로 직접 제어한다.

        # 자동 정화 중 팬 OFF는 PM 절댓값이 아니라 고정 정화 시간으로 처리한다.

    def should_interrupt_active_goal(self, pm25, recent_values, now):
        if self.current_mode != "auto" or self.is_purifying:
            return False
        if not self.goal_in_progress or self.sample_goal is not None:
            return False
        if self.current_pose_goal is None:
            return False
        if now - self.last_live_interrupt_at < self.live_interrupt_cooldown_seconds:
            return False
        if self.search_controller.mode != "search":
            return False
        if not AutonomousPurifier.is_live_interrupt_enabled_for_zone(self):
            return False
        if AutonomousPurifier.recent_lidar_target_goal(self, now) is None:
            return False
        if self.search_controller.is_signal_ignored(self.current_pose_goal):
            return False
        if self.is_second_search_cooling_down():
            return False
        reference_values = recent_values
        normal_baseline_pm25 = getattr(self, "normal_baseline_pm25", None)
        if normal_baseline_pm25 is not None:
            reference_values = [normal_baseline_pm25]

        return should_interrupt_for_pm25_spike(
            pm25,
            reference_values,
            self.search_controller.trigger_threshold,
            self.search_controller.trigger_delta,
        )

    def is_live_interrupt_enabled_for_zone(self):
        zones = getattr(self, "live_interrupt_zones", {"kitchen"})
        return "*" in zones or self.target_zone in zones

    def handle_active_pm25_spike(self):
        if self.current_pose_goal is None:
            return False

        target_goal = AutonomousPurifier.recent_lidar_target_goal(self) or self.current_pose_goal
        mode = self.search_controller.record_live_signal(target_goal, self.current_pm)
        if mode != "track":
            return False

        self.get_logger().warn(
            f"PM2.5 상승 + 라이다 원형 장애물 감지 -> 가습기 후보 추적 전환: "
            f"goal={target_goal}, pm25={self.current_pm}"
        )
        self.cancel_active_goal()
        self.stop_robot()
        self.last_live_interrupt_at = time.monotonic()
        self.start_next_patrol_goal()
        return True

    def behavior_loop(self):
        """로봇의 주행 상태 제어 루프"""
        self.update_adaptive_threshold()

        if self.is_purifying:
            self.stop_robot()
            if self.purify_started_at is not None:
                elapsed = time.monotonic() - self.purify_started_at
                if elapsed >= self.purify_duration_seconds:
                    self.finish_purifying(f"{self.purify_duration_seconds:.1f}초 정화 완료")
            return

        if self.current_mode != "auto":
            return

        if self.sample_goal is not None:
            self.finish_sample_if_ready()
            return

        if not self.goal_in_progress:
            self.start_next_patrol_goal()


    def finish_sample_if_ready(self):
        if time.monotonic() - self.sample_started_at < self.sample_duration_seconds:
            return

        average_pm25 = self.average_pm25_since(self.sample_started_at)
        if average_pm25 is None:
            self.get_logger().warn("PM2.5 샘플이 없어 같은 지점을 다시 샘플링합니다.")
            self.sample_started_at = time.monotonic()
            return

        sampled_goal = self.sample_goal
        self.sample_goal = None
        self.sample_started_at = None

        if self.search_controller.is_signal_ignored(sampled_goal):
            self.get_logger().warn(
                f"기존 발견 목표 주변 샘플 무시: goal={sampled_goal}, avg_pm25={average_pm25:.1f}"
            )
            self.start_next_patrol_goal()
            return

        if self.is_second_search_cooling_down():
            self.get_logger().warn(
                f"두 번째 탐색 쿨다운 중 샘플 무시: goal={sampled_goal}, avg_pm25={average_pm25:.1f}"
            )
            self.start_next_patrol_goal()
            return

        if self.confirm_lidar_target_if_tracking(average_pm25):
            return

        baseline_pm25 = self.sample_baseline_pm25
        self.sample_baseline_pm25 = None
        if AutonomousPurifier.confirm_demo_target_if_needed(self, sampled_goal, average_pm25):
            return

        mode = self.search_controller.record_sample(sampled_goal, average_pm25, baseline_pm25)
        self.get_logger().info(
            f"목표 샘플 완료: goal={sampled_goal}, baseline={self.format_pm25(baseline_pm25)}, "
            f"avg_pm25={average_pm25:.1f}, search_mode={mode}"
        )
        if self.is_sample_humidifier_suspected(average_pm25, baseline_pm25):
            self.get_logger().warn(
                f"PM2.5 기준선 대비 상승 -> 가습기 의심: "
                f"goal={sampled_goal}, baseline={self.format_pm25(baseline_pm25)}, avg_pm25={average_pm25:.1f}"
            )

        if mode == "found":
            self.handle_found_target(average_pm25)
            return

        self.start_next_patrol_goal()

    def confirm_lidar_target_if_tracking(self, average_pm25):
        if self.search_controller.mode != "track":
            return False

        confirmed = self.lidar_confirmed_measurement_goal()
        if confirmed is None:
            return False

        found_goal, diameter = confirmed
        if self.search_controller.is_signal_ignored(found_goal):
            return False

        self.search_controller.best_sample = (found_goal, float(average_pm25))
        self.search_controller.mode = "found"
        self.get_logger().warn(
            f"라이다 원형 후보 확인 -> 가습기 확정: "
            f"goal={found_goal}, diameter={diameter:.3f}m, avg_pm25={average_pm25:.1f}"
        )
        self.handle_found_target(average_pm25)
        return True

    def confirm_demo_target_if_needed(self, sampled_goal, average_pm25):
        if not AutonomousPurifier.is_demo_clean_target_goal(self, sampled_goal):
            return False

        self.search_controller.best_sample = (tuple(sampled_goal), float(average_pm25))
        self.search_controller.mode = "found"
        self.get_logger().warn(
            f"시연 시나리오 목표 도착 -> 가습기 확정: goal={sampled_goal}, avg_pm25={average_pm25:.1f}"
        )
        self.handle_found_target(average_pm25)
        return True

    def is_demo_passthrough_goal(self, goal):
        if not getattr(self, "demo_scenario_enabled", False):
            return False
        if getattr(self, "target_zone", "all") != "kitchen":
            return False
        return AutonomousPurifier.is_near_patrol_waypoint(self, goal, 2)

    def is_demo_clean_target_goal(self, goal):
        if not getattr(self, "demo_scenario_enabled", False):
            return False
        zone = getattr(self, "target_zone", "all")
        if zone == "kitchen":
            return AutonomousPurifier.is_near_patrol_waypoint(self, goal, 3)
        if zone == "all" and getattr(self, "demo_first_clean_done", False):
            return AutonomousPurifier.is_near_patrol_waypoint(self, goal, 0)
        return False

    def is_near_patrol_waypoint(self, goal, waypoint_index, radius=0.35):
        waypoints = getattr(self, "patrol_waypoints", [])
        if goal is None or len(waypoints) <= waypoint_index:
            return False
        waypoint = waypoints[waypoint_index]
        return math.hypot(float(goal[0]) - waypoint[0], float(goal[1]) - waypoint[1]) <= radius

    def advance_after_demo_passthrough(self):
        if self.search_controller.mode == "search":
            self.search_controller.search_index += 1

    def is_sample_humidifier_suspected(self, average_pm25, baseline_pm25):
        if baseline_pm25 is None:
            return False
        return float(average_pm25) > float(baseline_pm25) + self.search_controller.trigger_delta

    def recent_pm25_baseline(self, now, lookback_seconds=30.0):
        values = [value for timestamp, value in self.pm25_samples if timestamp < now and now - timestamp <= lookback_seconds]
        if not values:
            return None
        return min(values)

    def refresh_normal_baseline(self, reason, now=None):
        current_time = time.monotonic() if now is None else now
        baseline = self.recent_pm25_baseline(current_time)
        if baseline is None and self.current_pm > 0:
            baseline = self.current_pm
        if baseline is not None and self.normal_baseline_pm25 is not None:
            baseline = min(baseline, self.normal_baseline_pm25)
        self.normal_baseline_pm25 = baseline
        self.get_logger().info(
            f"PM2.5 평상시 기준선 갱신: reason={reason}, baseline={self.format_pm25(baseline)}"
        )
        return baseline

    
    @staticmethod
    def format_pm25(value):
        if value is None:
            return "none"
        return f"{float(value):.1f}"

    def is_second_search_cooling_down(self):
        if self.second_search_started_at is None:
            return False
        return time.monotonic() - self.second_search_started_at < self.second_search_cooldown_seconds

    def handle_found_target(self, average_pm25):
        found_goal = self.search_controller.record_found_target_and_continue()
        found_count = len(self.search_controller.found_targets)
        self.get_logger().warn(
            f"가습기 목표 후보 {found_count}/{self.max_targets} 발견: goal={found_goal}, avg_pm25={average_pm25:.1f}"
        )

        if found_count >= self.max_targets:
            if getattr(self, "demo_scenario_enabled", False):
                self.demo_pending_clean_zone = self.target_zone
            self.start_fan_alignment_goal(found_goal, average_pm25)
            return

        self.target_zone = "all"
        self.second_search_started_at = time.monotonic()
        self.search_controller.set_search_waypoints(self.patrol_waypoints)
        self.refresh_normal_baseline("all")
        self.get_logger().info("발견 위치를 제외하고 전체 맵에서 다음 가습기를 탐색합니다.")
        self.start_next_patrol_goal()

    @staticmethod
    def fan_alignment_goal(found_goal):
        x, y, yaw = found_goal
        return (x, y, normalize_yaw(float(yaw)))

    def start_fan_alignment_goal(self, found_goal, average_pm25):
        self.pending_purify_average_pm25 = average_pm25
        if found_goal is None:
            self.start_purifying("가습기 위치 없음")
            return

        alignment_goal = self.fan_alignment_goal(found_goal)
        if not self.nav_client.wait_for_server(timeout_sec=0.0):
            self.get_logger().warn("Nav2 서버가 없어 전면 정렬 없이 팬을 켭니다.")
            self.start_purifying("정렬 목표 전송 불가")
            return

        self.get_logger().info(
            f"가습기 확정 -> 전면 정렬 목표 전송: x={alignment_goal[0]:.2f}, "
            f"y={alignment_goal[1]:.2f}, yaw={alignment_goal[2]:.2f}"
        )
        self.send_nav_goal(alignment_goal, "fan_align", "fan_align")

    def start_purifying(self, reason):
        average = self.pending_purify_average_pm25
        self.pending_purify_average_pm25 = None
        self.is_purifying = True
        self.purify_started_at = time.monotonic()
        self.current_mode = "manual"
        self.stop_robot()
        self.turn_on_fan()
        self.publish_purifier_status("purifying")
        if average is None:
            self.get_logger().info(
                f"목표 개수 탐색 완료 -> 팬 ON: {reason}, duration={self.purify_duration_seconds:.1f}s"
            )
        else:
            self.get_logger().info(
                f"목표 개수 탐색 완료 -> 팬 ON: {reason}, avg_pm25={average:.1f}, "
                f"duration={self.purify_duration_seconds:.1f}s"
            )

    def finish_purifying(self, reason):
        if not self.is_purifying:
            return
        self.is_purifying = False
        self.purify_started_at = None
        self.turn_off_fan()
        self.publish_purifier_status("cleaned")
        pending_zone = getattr(self, "demo_pending_clean_zone", None)
        if getattr(self, "demo_scenario_enabled", False) and pending_zone == "kitchen":
            self.demo_first_clean_done = True
        should_return_home = getattr(self, "demo_scenario_enabled", False) and pending_zone == "all"
        if getattr(self, "demo_scenario_enabled", False):
            self.demo_pending_clean_zone = None
        self.get_logger().info(f"✨ 정화 완료! {reason} -> 팬을 끕니다.")
        if should_return_home:
            AutonomousPurifier.start_demo_return_home(self)

    def start_demo_return_home(self):
        if len(getattr(self, "patrol_waypoints", [])) < 2:
            self.get_logger().warn("시연 복귀 목표가 없어 현재 위치에서 종료합니다.")
            self.current_mode = "manual"
            self.stop_robot()
            return False

        return_goal = self.patrol_waypoints[1]
        if not self.nav_client.wait_for_server(timeout_sec=0.0):
            self.get_logger().warn("Nav2 서버가 없어 출발지 복귀 없이 종료합니다.")
            self.current_mode = "manual"
            self.stop_robot()
            return False

        self.current_mode = "auto"
        self.publish_purifier_status("returning")
        self.get_logger().info(
            f"시연 종료 -> 출발지 복귀 목표 전송: x={return_goal[0]:.2f}, y={return_goal[1]:.2f}"
        )
        self.send_nav_goal(return_goal, "demo_return", "demo_return")
        return True

    def average_pm25_since(self, started_at):
        values = [value for timestamp, value in self.pm25_samples if timestamp >= started_at]
        if not values:
            return None
        return sum(values) / len(values)

    def start_next_patrol_goal(self):
        if self.goal_in_progress or self.current_mode != "auto" or self.is_purifying:
            return

        if not self.nav_client.wait_for_server(timeout_sec=0.0):
            now = time.monotonic()
            if now - self.last_nav_warning_at > 5.0:
                self.get_logger().warn("Nav2 navigate_to_pose 액션 서버 대기 중입니다.")
                self.last_nav_warning_at = now
            return

        next_goal = self.search_controller.next_goal()
        if self.search_controller.mode == "found":
            self.handle_found_target(self.current_pm)
            return
        if next_goal is None:
            self.get_logger().warn("탐색 가능한 후보 지점이 없습니다. 자동 탐색을 종료합니다.")
            self.current_mode = "manual"
            self.stop_robot()
            return

        if AutonomousPurifier.is_demo_passthrough_goal(self, next_goal):
            self.send_nav_goal(next_goal, "passthrough", "passthrough")
            return

        self.send_nav_goal(next_goal, "sample", self.search_controller.mode)

    def send_nav_goal(self, goal, kind, mode_label):
        x, y, yaw = goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        orientation_z, orientation_w = yaw_to_quaternion(float(yaw))
        goal_msg.pose.pose.orientation.z = orientation_z
        goal_msg.pose.pose.orientation.w = orientation_w

        self.goal_in_progress = True
        self.active_goal = goal
        self.active_goal_kind = kind
        self.goal_sequence += 1
        sequence = self.goal_sequence
        self.get_logger().info(
            f"Nav2 탐색 목표 전송: mode={mode_label}, x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"
        )
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(
            lambda future: self.goal_response_callback(future, sequence)
        )

    def goal_response_callback(self, future, sequence):
        if sequence != self.goal_sequence:
            return

        goal_kind = getattr(self, "active_goal_kind", None)
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.get_logger().error(f"Nav2 목표 전송 실패: {exc}")
            self.goal_in_progress = False
            self.active_goal = None
            self.active_goal_kind = None
            if goal_kind == "fan_align":
                self.start_purifying("정렬 목표 전송 실패")
            return

        if not goal_handle.accepted:
            self.get_logger().warn("Nav2 목표가 거부되었습니다. 다음 루프에서 다음 지점을 시도합니다.")
            self.goal_in_progress = False
            self.active_goal = None
            self.active_goal_kind = None
            if goal_kind == "fan_align":
                self.start_purifying("정렬 목표 거부")
            return

        self.active_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda result: self.goal_result_callback(result, sequence)
        )

    def goal_result_callback(self, future, sequence):
        if sequence != self.goal_sequence:
            return

        try:
            result = future.result()
            self.get_logger().info(f"Nav2 탐색 목표 종료: status={result.status}")
        except Exception as exc:
            self.get_logger().error(f"Nav2 결과 수신 실패: {exc}")
            self.active_goal_handle = None
            self.goal_in_progress = False
            self.active_goal = None
            return

        self.active_goal_handle = None
        self.goal_in_progress = False
        goal_kind = getattr(self, "active_goal_kind", None)
        self.active_goal_kind = None
        if goal_kind == "demo_return":
            self.active_goal = None
            self.current_mode = "manual"
            self.stop_robot()
            if result.status == 4:
                self.publish_purifier_status("returned")
                self.get_logger().info("시연 출발지 복귀 완료 -> 수동 대기")
            else:
                self.get_logger().warn("출발지 복귀 목표가 성공 상태가 아니어서 현재 위치에서 수동 대기합니다.")
            return

        if result.status != 4:
            if goal_kind == "fan_align":
                self.get_logger().warn("후면 정렬 목표가 성공하지 못했지만 현재 위치에서 팬을 켭니다.")
                self.active_goal = None
                self.start_purifying("정렬 실패 fallback")
                return
            self.get_logger().warn("Nav2 목표가 성공 상태가 아니어서 샘플링하지 않고 다음 후보를 시도합니다.")
            self.active_goal = None
            return

        if goal_kind == "fan_align":
            self.active_goal = None
            self.start_purifying("후면 정렬 완료")
            return

        if goal_kind == "passthrough":
            AutonomousPurifier.advance_after_demo_passthrough(self)
            self.active_goal = None
            AutonomousPurifier.start_next_patrol_goal(self)
            return

        sample_started_at = time.monotonic()
        self.sample_goal = self.active_goal
        self.sample_started_at = sample_started_at
        self.sample_baseline_pm25 = self.normal_baseline_pm25
        if self.sample_baseline_pm25 is None:
            self.sample_baseline_pm25 = self.recent_pm25_baseline(sample_started_at)
        self.active_goal = None
        self.get_logger().info(
            f"PM2.5 샘플링 시작: duration={self.sample_duration_seconds:.1f}s, "
            f"baseline={self.format_pm25(self.sample_baseline_pm25)}"
        )

    def cancel_active_goal(self):
        self.goal_sequence += 1
        self.goal_in_progress = False
        self.sample_goal = None
        self.sample_started_at = None
        self.sample_baseline_pm25 = None
        self.active_goal = None
        self.active_goal_kind = None
        self.pending_purify_average_pm25 = None
        self.purify_started_at = None
        if self.active_goal_handle is not None:
            self.active_goal_handle.cancel_goal_async()
            self.active_goal_handle = None

    def stop_robot(self):
        """로봇에게 즉시 속도 0을 보내 완전히 멈추게 하는 함수"""
        stop_msg = TwistStamped()
        stop_msg.header.stamp = self.get_clock().now().to_msg()
        stop_msg.twist.linear.x = 0.0
        stop_msg.twist.angular.z = 0.0
        try:
            self.cmd_pub.publish(stop_msg)
        except RCLError:
            pass

    def turn_on_fan(self):
        msg = Bool()
        msg.data = True
        try:
            self.relay_pub.publish(msg)
        except RCLError:
            pass

    def turn_off_fan(self):
        msg = Bool()
        msg.data = False
        try:
            self.relay_pub.publish(msg)
        except RCLError:
            pass

    def publish_purifier_status(self, status):
        msg = String()
        msg.data = status
        try:
            self.status_pub.publish(msg)
        except RCLError:
            pass

def main(args=None):
    rclpy.init(args=args)
    node = AutonomousPurifier()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, RCLError):
        node.cancel_active_goal()
        node.stop_robot()
        node.turn_off_fan()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
