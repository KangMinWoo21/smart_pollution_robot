import unittest
from types import SimpleNamespace

from cleaning_logic import DEFAULT_PATROL_WAYPOINTS, HybridSearchController, normalize_pm25_reading
from real_cleaner import AutonomousPurifier, detect_round_lidar_obstacle


class RealCleanerBehaviorTest(unittest.TestCase):
    def test_pm25_filter_rejects_invalid_spikes(self):
        self.assertEqual(normalize_pm25_reading(14), 14)
        self.assertIsNone(normalize_pm25_reading(3584))
        self.assertIsNone(normalize_pm25_reading(-1))

    def test_manual_mode_does_not_auto_start_fan_from_pm25(self):
        calls = []
        node = SimpleNamespace(
            current_mode="manual",
            current_pm=0,
            POLLUTION_THRESHOLD=70,
            CLEAN_THRESHOLD=45,
            is_purifying=False,
            pm25_samples=[],
            should_interrupt_active_goal=lambda pm25, recent_values, now: False,
            handle_active_pm25_spike=lambda: calls.append("interrupt"),
            cancel_active_goal=lambda: calls.append("cancel"),
            stop_robot=lambda: calls.append("stop"),
            turn_on_fan=lambda: calls.append("fan_on"),
            turn_off_fan=lambda: calls.append("fan_off"),
            get_logger=lambda: SimpleNamespace(
                warn=lambda message: calls.append("warn"),
                info=lambda message: calls.append("info"),
            ),
        )

        AutonomousPurifier.sensor_callback(node, SimpleNamespace(data=120))

        self.assertFalse(node.is_purifying)
        self.assertEqual(calls, [])


class FakeSearchController:
    def __init__(self):
        self.calls = []
        self.mode = "search"

    def is_signal_ignored(self, goal):
        return False

    def record_live_signal(self, goal, pm25):
        self.calls.append((goal, pm25))
        self.mode = "track"
        return self.mode


class ReactiveSpikeTest(unittest.TestCase):
    def test_auto_spike_interrupt_does_not_reset_existing_tracking(self):
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pose_goal=(1.2, 0.4, 1.57),
            live_interrupt_cooldown_seconds=4,
            last_live_interrupt_at=0.0,
            search_controller=SimpleNamespace(
                mode="track",
                trigger_threshold=36,
                trigger_delta=3,
                is_signal_ignored=lambda goal: False,
            ),
            is_second_search_cooling_down=lambda: False,
        )

        should_interrupt = AutonomousPurifier.should_interrupt_active_goal(
            node,
            50,
            [15, 16],
            10.0,
        )

        self.assertFalse(should_interrupt)


    def test_all_zone_does_not_live_interrupt_during_transit(self):
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pose_goal=(4.9, 4.8, 0.0),
            live_interrupt_cooldown_seconds=4,
            last_live_interrupt_at=0.0,
            target_zone="all",
            live_interrupt_zones={"kitchen"},
            search_controller=SimpleNamespace(
                mode="search",
                trigger_threshold=36,
                trigger_delta=3,
                is_signal_ignored=lambda goal: False,
            ),
            is_second_search_cooling_down=lambda: False,
        )

        should_interrupt = AutonomousPurifier.should_interrupt_active_goal(
            node,
            50,
            [20, 21],
            10.0,
        )

        self.assertFalse(should_interrupt)


    def test_kitchen_spike_requires_recent_lidar_round_obstacle(self):
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pose_goal=(7.5, 5.2, 0.0),
            live_interrupt_cooldown_seconds=4,
            last_live_interrupt_at=0.0,
            target_zone="kitchen",
            live_interrupt_zones={"kitchen"},
            latest_lidar_target=None,
            search_controller=SimpleNamespace(
                mode="search",
                trigger_threshold=36,
                trigger_delta=3,
                is_signal_ignored=lambda goal: False,
            ),
            is_second_search_cooling_down=lambda: False,
        )

        should_interrupt = AutonomousPurifier.should_interrupt_active_goal(
            node,
            50,
            [20, 21],
            10.0,
        )

        self.assertFalse(should_interrupt)

    def test_kitchen_spike_uses_recent_lidar_round_obstacle(self):
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pose_goal=(7.5, 5.2, 0.0),
            live_interrupt_cooldown_seconds=4,
            last_live_interrupt_at=0.0,
            target_zone="kitchen",
            live_interrupt_zones={"kitchen"},
            latest_lidar_target=(7.66, 5.50, 0.0, 0.10),
            latest_lidar_target_at=9.5,
            lidar_target_stale_seconds=2.5,
            search_controller=SimpleNamespace(
                mode="search",
                trigger_threshold=36,
                trigger_delta=3,
                is_signal_ignored=lambda goal: False,
            ),
            is_second_search_cooling_down=lambda: False,
        )

        should_interrupt = AutonomousPurifier.should_interrupt_active_goal(
            node,
            50,
            [20, 21],
            10.0,
        )

        self.assertTrue(should_interrupt)

    def test_detect_round_lidar_obstacle_matches_ten_cm_cluster(self):
        ranges = [float("inf")] * 21
        for index in range(9, 12):
            ranges[index] = 1.0

        obstacle = detect_round_lidar_obstacle(
            ranges,
            angle_min=-0.5,
            angle_increment=0.05,
            min_range=0.05,
            max_range=3.5,
            target_diameter=0.10,
            tolerance=0.04,
            max_center_range=1.6,
        )

        self.assertIsNotNone(obstacle)
        self.assertAlmostEqual(obstacle[2], 0.10, delta=0.05)

    def test_auto_spike_interrupt_cancels_goal_and_starts_tracking_from_current_pose(self):
        controller = FakeSearchController()
        calls = []
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pm=82,
            current_pose_goal=(1.2, 0.4, 1.57),
            search_controller=controller,
            second_search_started_at=None,
            cancel_active_goal=lambda: calls.append("cancel"),
            stop_robot=lambda: calls.append("stop"),
            start_next_patrol_goal=lambda: calls.append("start"),
            get_logger=lambda: SimpleNamespace(info=lambda message: calls.append("log"), warn=lambda message: calls.append("warn")),
        )

        handled = AutonomousPurifier.handle_active_pm25_spike(node)

        self.assertTrue(handled)
        self.assertEqual(controller.calls, [((1.2, 0.4, 1.57), 82)])
        self.assertEqual(calls, ["warn", "cancel", "stop", "start"])

    def test_auto_spike_interrupt_requires_map_pose(self):
        calls = []
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pm=82,
            current_pose_goal=None,
            cancel_active_goal=lambda: calls.append("cancel"),
            stop_robot=lambda: calls.append("stop"),
            start_next_patrol_goal=lambda: calls.append("start"),
        )

        handled = AutonomousPurifier.handle_active_pm25_spike(node)

        self.assertFalse(handled)
        self.assertEqual(calls, [])


    def test_kitchen_spike_uses_normal_baseline_instead_of_absolute_pm25(self):
        node = SimpleNamespace(
            current_mode="auto",
            is_purifying=False,
            goal_in_progress=True,
            sample_goal=None,
            current_pose_goal=(7.5, 5.2, 0.0),
            live_interrupt_cooldown_seconds=4,
            last_live_interrupt_at=0.0,
            target_zone="kitchen",
            live_interrupt_zones={"kitchen"},
            latest_lidar_target=(7.66, 5.50, 0.0, 0.10),
            latest_lidar_target_at=9.5,
            lidar_target_stale_seconds=2.5,
            normal_baseline_pm25=78,
            search_controller=SimpleNamespace(
                mode="search",
                trigger_threshold=36,
                trigger_delta=3,
                is_signal_ignored=lambda goal: False,
            ),
            is_second_search_cooling_down=lambda: False,
        )

        should_interrupt = AutonomousPurifier.should_interrupt_active_goal(
            node,
            80,
            [20, 21],
            10.0,
        )

        self.assertFalse(should_interrupt)

    def test_goal_sample_uses_saved_normal_baseline_before_recent_plume_values(self):
        node = SimpleNamespace(
            goal_sequence=3,
            active_goal_handle=SimpleNamespace(),
            goal_in_progress=True,
            active_goal=(7.5, 5.2, -2.9),
            normal_baseline_pm25=22,
            sample_duration_seconds=2,
            get_logger=lambda: SimpleNamespace(
                info=lambda message: None,
                warn=lambda message: None,
                error=lambda message: None,
            ),
            recent_pm25_baseline=lambda started_at: 39,
            format_pm25=AutonomousPurifier.format_pm25,
        )
        future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))

        AutonomousPurifier.goal_result_callback(node, future, 3)

        self.assertEqual(node.sample_goal, (7.5, 5.2, -2.9))
        self.assertEqual(node.sample_baseline_pm25, 22)

    def test_fan_alignment_goal_turns_around_from_measurement_pose(self):
        alignment_goal = AutonomousPurifier.fan_alignment_goal((7.7, 5.19, 3.14))

        self.assertEqual(alignment_goal[:2], (7.7, 5.19))
        self.assertAlmostEqual(alignment_goal[2], 0.0, delta=0.01)

    def test_fan_alignment_success_turns_on_fan_without_sampling(self):
        calls = []
        node = SimpleNamespace(
            goal_sequence=5,
            active_goal_handle=SimpleNamespace(),
            goal_in_progress=True,
            active_goal=(7.7, 5.19, 0.0),
            active_goal_kind="fan_align",
            sample_goal=None,
            start_purifying=lambda reason: calls.append(("fan_on", reason)),
            get_logger=lambda: SimpleNamespace(
                info=lambda message: calls.append(("info", message)),
                warn=lambda message: calls.append(("warn", message)),
                error=lambda message: calls.append(("error", message)),
            ),
        )
        future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))

        AutonomousPurifier.goal_result_callback(node, future, 5)

        self.assertIn(("fan_on", "후면 정렬 완료"), calls)
        self.assertIsNone(node.active_goal)
        self.assertIsNone(node.active_goal_kind)
        self.assertIsNone(node.sample_goal)

    def test_purifying_stops_after_fixed_demo_duration(self):
        calls = []
        node = SimpleNamespace(
            is_purifying=True,
            purify_started_at=10.0,
            purify_duration_seconds=7.0,
            update_adaptive_threshold=lambda: calls.append("threshold"),
            stop_robot=lambda: calls.append("stop"),
            finish_purifying=lambda reason: calls.append(("finish", reason)),
        )

        original_time = __import__("time").monotonic
        try:
            __import__("time").monotonic = lambda: 17.1
            AutonomousPurifier.behavior_loop(node)
        finally:
            __import__("time").monotonic = original_time

        self.assertIn("stop", calls)
        self.assertIn(("finish", "7.0초 정화 완료"), calls)

    def test_finish_purifying_turns_fan_off_and_publishes_cleaned(self):
        calls = []
        node = SimpleNamespace(
            is_purifying=True,
            purify_started_at=10.0,
            turn_off_fan=lambda: calls.append("fan_off"),
            publish_purifier_status=lambda status: calls.append(("status", status)),
            get_logger=lambda: SimpleNamespace(info=lambda message: calls.append(("info", message))),
        )

        AutonomousPurifier.finish_purifying(node, "7.0초 정화 완료")

        self.assertFalse(node.is_purifying)
        self.assertIsNone(node.purify_started_at)
        self.assertIn("fan_off", calls)
        self.assertIn(("status", "cleaned"), calls)

    def test_lidar_confirmed_measurement_goal_faces_round_obstacle(self):
        node = SimpleNamespace(
            current_pose_goal=(7.7, 5.19, 3.14),
            latest_lidar_target=(7.7, 5.5, 3.14, 0.059),
            latest_lidar_target_at=10.0,
            lidar_target_stale_seconds=2.5,
        )
        node.recent_lidar_target = lambda now=None: AutonomousPurifier.recent_lidar_target(node, now)

        goal, diameter = AutonomousPurifier.lidar_confirmed_measurement_goal(node, now=11.0)

        self.assertEqual(goal[:2], (7.7, 5.19))
        self.assertAlmostEqual(goal[2], 1.57, delta=0.01)
        self.assertAlmostEqual(diameter, 0.059)

    def test_tracking_sample_confirms_lidar_target_as_found(self):
        calls = []
        controller = SimpleNamespace(
            mode="track",
            best_sample=None,
            is_signal_ignored=lambda goal: False,
        )
        node = SimpleNamespace(
            current_pose_goal=(7.7, 5.19, 3.14),
            latest_lidar_target=(7.7, 5.5, 3.14, 0.059),
            latest_lidar_target_at=10.0,
            lidar_target_stale_seconds=2.5,
            search_controller=controller,
            lidar_confirmed_measurement_goal=lambda: AutonomousPurifier.lidar_confirmed_measurement_goal(node, now=11.0),
            handle_found_target=lambda average: calls.append(("found", average)),
            get_logger=lambda: SimpleNamespace(warn=lambda message: calls.append(("warn", message))),
        )
        node.recent_lidar_target = lambda now=None: AutonomousPurifier.recent_lidar_target(node, now)

        handled = AutonomousPurifier.confirm_lidar_target_if_tracking(node, 44.0)

        self.assertTrue(handled)
        self.assertEqual(controller.mode, "found")
        self.assertEqual(controller.best_sample[0][:2], (7.7, 5.19))
        self.assertIn(("found", 44.0), calls)

    def test_normal_baseline_does_not_rise_after_first_purifier(self):
        logs = []
        node = SimpleNamespace(
            current_pm=0,
            pm25_samples=[(1.0, 42), (2.0, 44)],
            normal_baseline_pm25=39,
            recent_pm25_baseline=lambda now: 42,
            format_pm25=AutonomousPurifier.format_pm25,
            get_logger=lambda: SimpleNamespace(info=lambda message: logs.append(message)),
        )

        baseline = AutonomousPurifier.refresh_normal_baseline(node, "all", now=3.0)

        self.assertEqual(baseline, 39)
        self.assertEqual(node.normal_baseline_pm25, 39)


class DemoScenarioTest(unittest.TestCase):
    def test_demo_kitchen_route_goes_through_waypoint_3_then_4(self):
        node = SimpleNamespace(
            demo_scenario_enabled=True,
            demo_first_clean_done=False,
            patrol_waypoints=list(DEFAULT_PATROL_WAYPOINTS),
        )

        route = AutonomousPurifier.demo_waypoints_for_zone(node, "kitchen")

        self.assertEqual(route, [DEFAULT_PATROL_WAYPOINTS[2], DEFAULT_PATROL_WAYPOINTS[3]])

    def test_demo_all_after_first_clean_targets_waypoint_1_only(self):
        node = SimpleNamespace(
            demo_scenario_enabled=True,
            demo_first_clean_done=True,
            patrol_waypoints=list(DEFAULT_PATROL_WAYPOINTS),
        )

        route = AutonomousPurifier.demo_waypoints_for_zone(node, "all")

        self.assertEqual(route, [DEFAULT_PATROL_WAYPOINTS[0]])

    def test_demo_passthrough_success_advances_to_next_route_goal(self):
        sent = []
        controller = HybridSearchController([DEFAULT_PATROL_WAYPOINTS[2], DEFAULT_PATROL_WAYPOINTS[3]])
        node = SimpleNamespace(
            goal_sequence=8,
            active_goal_handle=SimpleNamespace(),
            goal_in_progress=True,
            active_goal=DEFAULT_PATROL_WAYPOINTS[2],
            active_goal_kind="passthrough",
            current_mode="auto",
            is_purifying=False,
            nav_client=SimpleNamespace(wait_for_server=lambda timeout_sec=0.0: True),
            search_controller=controller,
            demo_scenario_enabled=True,
            target_zone="kitchen",
            patrol_waypoints=list(DEFAULT_PATROL_WAYPOINTS),
            send_nav_goal=lambda goal, kind, mode_label: sent.append((goal, kind, mode_label)),
            get_logger=lambda: SimpleNamespace(
                info=lambda message: None,
                warn=lambda message: None,
                error=lambda message: None,
            ),
        )
        future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))

        AutonomousPurifier.goal_result_callback(node, future, 8)

        self.assertEqual(sent, [(DEFAULT_PATROL_WAYPOINTS[3], "sample", "search")])

    def test_demo_clean_target_sample_forces_found_when_sensor_detection_is_slow(self):
        calls = []
        controller = HybridSearchController([DEFAULT_PATROL_WAYPOINTS[2], DEFAULT_PATROL_WAYPOINTS[3]])
        node = SimpleNamespace(
            demo_scenario_enabled=True,
            demo_first_clean_done=False,
            target_zone="kitchen",
            patrol_waypoints=list(DEFAULT_PATROL_WAYPOINTS),
            search_controller=controller,
            handle_found_target=lambda average: calls.append(("found", average)),
            get_logger=lambda: SimpleNamespace(warn=lambda message: calls.append(("warn", message))),
        )

        handled = AutonomousPurifier.confirm_demo_target_if_needed(
            node,
            DEFAULT_PATROL_WAYPOINTS[3],
            42.0,
        )

        self.assertTrue(handled)
        self.assertEqual(controller.mode, "found")
        self.assertEqual(controller.best_sample, (DEFAULT_PATROL_WAYPOINTS[3], 42.0))
        self.assertIn(("found", 42.0), calls)

    def test_demo_first_clean_done_after_kitchen_purification_finishes(self):
        calls = []
        node = SimpleNamespace(
            is_purifying=True,
            purify_started_at=10.0,
            demo_scenario_enabled=True,
            demo_pending_clean_zone="kitchen",
            demo_first_clean_done=False,
            start_demo_return_home=lambda: calls.append("return_home"),
            turn_off_fan=lambda: calls.append("fan_off"),
            publish_purifier_status=lambda status: calls.append(("status", status)),
            get_logger=lambda: SimpleNamespace(info=lambda message: calls.append(("info", message))),
        )

        AutonomousPurifier.finish_purifying(node, "7.0초 정화 완료")

        self.assertTrue(node.demo_first_clean_done)
        self.assertIsNone(node.demo_pending_clean_zone)
        self.assertNotIn("return_home", calls)

    def test_demo_second_clean_done_returns_to_start_waypoint_2(self):
        sent = []
        calls = []
        node = SimpleNamespace(
            is_purifying=True,
            purify_started_at=10.0,
            demo_scenario_enabled=True,
            demo_pending_clean_zone="all",
            demo_first_clean_done=True,
            patrol_waypoints=list(DEFAULT_PATROL_WAYPOINTS),
            current_mode="manual",
            nav_client=SimpleNamespace(wait_for_server=lambda timeout_sec=0.0: True),
            send_nav_goal=lambda goal, kind, mode_label: sent.append((goal, kind, mode_label)),
            turn_off_fan=lambda: calls.append("fan_off"),
            publish_purifier_status=lambda status: calls.append(("status", status)),
            get_logger=lambda: SimpleNamespace(
                info=lambda message: calls.append(("info", message)),
                warn=lambda message: calls.append(("warn", message)),
            ),
        )

        AutonomousPurifier.finish_purifying(node, "7.0초 정화 완료")

        self.assertEqual(sent, [(DEFAULT_PATROL_WAYPOINTS[1], "demo_return", "demo_return")])
        self.assertEqual(node.current_mode, "auto")
        self.assertIsNone(node.demo_pending_clean_zone)
        self.assertIn(("status", "returning"), calls)

    def test_demo_return_goal_success_stops_in_manual_mode(self):
        calls = []
        node = SimpleNamespace(
            goal_sequence=11,
            active_goal_handle=SimpleNamespace(),
            goal_in_progress=True,
            active_goal=DEFAULT_PATROL_WAYPOINTS[1],
            active_goal_kind="demo_return",
            current_mode="auto",
            stop_robot=lambda: calls.append("stop"),
            publish_purifier_status=lambda status: calls.append(("status", status)),
            get_logger=lambda: SimpleNamespace(
                info=lambda message: calls.append(("info", message)),
                warn=lambda message: calls.append(("warn", message)),
                error=lambda message: calls.append(("error", message)),
            ),
        )
        future = SimpleNamespace(result=lambda: SimpleNamespace(status=4))

        AutonomousPurifier.goal_result_callback(node, future, 11)

        self.assertEqual(node.current_mode, "manual")
        self.assertIsNone(node.active_goal)
        self.assertIn("stop", calls)
        self.assertIn(("status", "returned"), calls)

if __name__ == "__main__":
    unittest.main()
