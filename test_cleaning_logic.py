import unittest
from pathlib import Path

from outdoor_air_quality_node import extract_json_path

from cleaning_logic import (
    HUMIDIFIER_SUSPECT_PM25_THRESHOLD,
    is_humidifier_suspected_pm25,
    DEFAULT_PATROL_WAYPOINTS,
    HybridSearchController,
    adaptive_pollution_threshold,
    normalize_pm25_reading,
    filter_waypoints_for_zone,
    parse_patrol_waypoints,
    select_next_waypoint_index,
    should_interrupt_for_pm25_spike,
)


class CleaningLogicTest(unittest.TestCase):
    def test_pm25_filter_rejects_invalid_spikes(self):
        self.assertEqual(normalize_pm25_reading(14), 14)
        self.assertIsNone(normalize_pm25_reading(3584))
        self.assertIsNone(normalize_pm25_reading(-1))

    def test_adaptive_threshold_uses_outdoor_air_quality(self):
        self.assertEqual(adaptive_pollution_threshold(None), 50)
        self.assertEqual(adaptive_pollution_threshold(20), 50)
        self.assertEqual(adaptive_pollution_threshold(36), 48)
        self.assertEqual(adaptive_pollution_threshold(75), 48)
        self.assertEqual(adaptive_pollution_threshold(76), 45)

    def test_parse_patrol_waypoints_from_environment_string(self):
        waypoints = parse_patrol_waypoints("-8.5,0.2,0; -5.5,3.5,1.57")

        self.assertEqual(waypoints, [(-8.5, 0.2, 0.0), (-5.5, 3.5, 1.57)])

    def test_parse_patrol_waypoints_uses_demo_defaults_for_blank_value(self):
        demo_waypoints = [
            (3.07, 4.98, -1.59),
            (5.18, 1.62, 0.05),
            (8.00, 1.40, 1.47),
            (7.50, 5.19, -2.90),
            (5.42, 4.68, 3.01),
        ]

        self.assertEqual(DEFAULT_PATROL_WAYPOINTS, demo_waypoints)
        self.assertEqual(parse_patrol_waypoints(""), demo_waypoints)
        self.assertEqual(
            filter_waypoints_for_zone(parse_patrol_waypoints(""), "kitchen"),
            [(8.00, 1.40, 1.47), (7.50, 5.19, -2.90)],
        )

    def test_parse_patrol_waypoints_rejects_malformed_entries(self):
        with self.assertRaises(ValueError):
            parse_patrol_waypoints("-8.5,0.2; -5.5,3.5,1.57")

    def test_select_next_waypoint_index_wraps_around(self):
        self.assertEqual(select_next_waypoint_index(None, 4), 0)
        self.assertEqual(select_next_waypoint_index(0, 4), 1)
        self.assertEqual(select_next_waypoint_index(3, 4), 0)


    def test_filter_waypoints_for_zone_limits_focus_area(self):
        waypoints = [
            (3.07, 4.98, -1.59),
            (5.18, 1.62, 0.05),
            (8.00, 1.40, 1.47),
            (7.50, 5.19, -2.90),
            (5.42, 4.68, 3.01),
        ]

        self.assertEqual(
            filter_waypoints_for_zone(waypoints, "kitchen"),
            [(8.00, 1.40, 1.47), (7.50, 5.19, -2.90)],
        )
        self.assertEqual(filter_waypoints_for_zone(waypoints, "all"), waypoints)
        self.assertEqual(filter_waypoints_for_zone(waypoints, "unknown"), waypoints)

    def test_hybrid_search_skips_ignored_found_target(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            ignore_radius_m=1.0,
        )
        controller.add_ignored_target((0.2, 0.0, 0.0))

        self.assertEqual(controller.next_goal(), (2.0, 0.0, 0.0))

    def test_hybrid_search_records_found_target_and_continues(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            trigger_threshold=40,
            improvement_delta=5,
        )
        controller.record_sample((0.0, 0.0, 0.0), 20)
        controller.record_sample((0.0, 0.0, 0.0), 45)
        while controller.mode == "track":
            controller.record_sample(controller.next_goal(), 42)

        found_goal = controller.record_found_target_and_continue()

        self.assertEqual(found_goal, (0.0, 0.0, 0.0))
        self.assertEqual(controller.mode, "search")
        self.assertEqual(controller.found_targets, [(0.0, 0.0, 0.0)])
        self.assertEqual(controller.next_goal(), (2.0, 0.0, 0.0))


    def test_signal_ignored_sample_does_not_start_tracking(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
            trigger_threshold=40,
            signal_ignore_radius_m=1.8,
        )
        controller.add_ignored_target((0.0, 0.0, 0.0))

        mode = controller.record_sample((1.0, 0.0, 0.0), 95)

        self.assertEqual(mode, "search")
        self.assertIsNone(controller.best_goal())

    def test_signal_outside_ignored_area_can_start_tracking(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
            trigger_threshold=40,
            signal_ignore_radius_m=1.8,
        )
        controller.add_ignored_target((0.0, 0.0, 0.0))

        controller.record_sample((3.0, 0.0, 0.0), 20)
        mode = controller.record_sample((2.2, 0.0, 0.0), 95)

        self.assertEqual(mode, "track")
        self.assertEqual(controller.best_goal(), (2.2, 0.0, 0.0))


    def test_hybrid_search_uses_grid_until_concentration_rises(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
            trigger_threshold=40,
            trigger_delta=10,
        )

        self.assertEqual(controller.next_goal(), (0.0, 0.0, 0.0))
        controller.record_sample((0.0, 0.0, 0.0), 18)

        self.assertEqual(controller.mode, "search")
        self.assertEqual(controller.next_goal(), (1.0, 0.0, 0.0))

        controller.record_sample((1.0, 0.0, 0.0), 43)

        self.assertEqual(controller.mode, "track")
        self.assertIn(controller.next_goal(), controller.track_candidates)

    def test_hybrid_search_confirms_found_after_tracking_neighbors(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0)],
            trigger_threshold=40,
            trigger_delta=10,
            track_step_m=0.5,
            improvement_delta=5,
        )
        controller.record_sample((0.0, 0.0, 0.0), 20)
        controller.record_sample((0.0, 0.0, 0.0), 45)

        while controller.mode == "track":
            controller.record_sample(controller.next_goal(), 42)

        self.assertEqual(controller.mode, "found")
        self.assertEqual(controller.best_goal(), (0.0, 0.0, 0.0))

    def test_live_signal_can_start_tracking_from_current_pose(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            trigger_threshold=70,
            track_step_m=0.5,
        )

        controller.record_live_signal((0.5, 0.0, 0.0), 20)
        mode = controller.record_live_signal((1.2, 0.4, 1.57), 74)

        self.assertEqual(mode, "track")
        self.assertEqual(controller.best_goal(), (1.2, 0.4, 1.57))
        self.assertIn((1.7, 0.4, 3.14), controller.track_candidates)

    def test_live_signal_ignored_near_previous_found_target(self):
        controller = HybridSearchController(
            search_waypoints=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            trigger_threshold=70,
            signal_ignore_radius_m=1.8,
        )
        controller.add_ignored_target((0.0, 0.0, 0.0))

        mode = controller.record_live_signal((1.0, 0.0, 0.0), 120)

        self.assertEqual(mode, "search")
        self.assertIsNone(controller.best_goal())

    def test_humidifier_suspect_threshold_is_over_35(self):
        self.assertEqual(HUMIDIFIER_SUSPECT_PM25_THRESHOLD, 36)
        self.assertFalse(is_humidifier_suspected_pm25(35))
        self.assertTrue(is_humidifier_suspected_pm25(36))


    def test_pm25_spike_interrupt_uses_threshold_or_recent_rise(self):
        self.assertTrue(should_interrupt_for_pm25_spike(75, [20, 22], 70, 15))
        self.assertTrue(should_interrupt_for_pm25_spike(45, [20, 22, 24], 70, 15))
        self.assertFalse(should_interrupt_for_pm25_spike(32, [20, 22, 24], 70, 15))
        self.assertFalse(should_interrupt_for_pm25_spike(45, [], 70, 15))
        self.assertFalse(should_interrupt_for_pm25_spike(38, [35, 36], 36, 3))
        self.assertTrue(should_interrupt_for_pm25_spike(39, [35, 36], 36, 3))
        self.assertFalse(should_interrupt_for_pm25_spike(80, [78, 79], 36, 3))


    def test_demo_launchers_pin_demo_environment(self):
        root = Path(__file__).resolve().parent
        laptop = (root / "start_laptop.sh").read_text(encoding="utf-8")
        pi = (root / "start_raspberry_pi.sh").read_text(encoding="utf-8")

        self.assertIn('USE_ZENOH="${USE_ZENOH:-1}"', laptop)
        self.assertIn("3.07,4.98,-1.59;5.18,1.62,0.05;8.00,1.40,1.47;7.50,5.19,-2.90;5.42,4.68,3.01", laptop)
        self.assertIn("TARGET_PM25_THRESHOLD:-36", laptop)
        self.assertIn("TARGET_PM25_TRIGGER_DELTA:-3", laptop)
        self.assertIn("TARGET_TRACK_STEP_M:-0.20", laptop)
        self.assertIn("BaseObstacle.scale: 0.35", laptop + (root / "demo_nav2_params.yaml").read_text(encoding="utf-8"))
        self.assertIn("robot_radius: 0.20", laptop + (root / "demo_nav2_params.yaml").read_text(encoding="utf-8"))
        self.assertIn("inflation_radius: 0.50", laptop + (root / "demo_nav2_params.yaml").read_text(encoding="utf-8"))
        self.assertIn("TARGET_PM25_IMPROVEMENT_DELTA:-2", laptop)
        self.assertIn("TARGET_SAMPLE_SECONDS:-2", laptop)
        self.assertIn("TARGET_PURIFY_SECONDS:-7", laptop)
        self.assertIn("TARGET_COUNT:-1", laptop)
        self.assertIn("TARGET_IGNORE_RADIUS_M:-0.5", laptop)
        self.assertIn("TARGET_SIGNAL_IGNORE_RADIUS_M:-0.7", laptop)
        self.assertIn("TARGET_LIVE_INTERRUPT_ZONES:-kitchen,all", laptop)
        self.assertIn('start_process "real_cleaner"', laptop)
        self.assertLess(laptop.index('start_process "real_cleaner"'), laptop.index('if [[ "$START_NAV2" == "1" ]]'))
        self.assertIn("timeout 5 ros2 lifecycle get", laptop)
        self.assertIn("timeout 8 ros2 lifecycle set", laptop)
        self.assertIn("activate_inactive_nav2_nodes", laptop)
        self.assertIn("PMS_PORT:-/dev/ttyS0", pi)
        self.assertIn("serial-getty@ttyS0.service", pi)
        self.assertIn("sudo -S -E", pi)
        self.assertIn("/usr/bin/python3", pi)


    def test_extract_outdoor_pm25_from_air_korea_response(self):
        payload = {
            "response": {
                "body": {
                    "items": [
                        {"stationName": "복대동", "pm25Value": "18"}
                    ]
                }
            }
        }

        self.assertEqual(extract_json_path(payload, "response.body.items.0.pm25Value"), 18)

    def test_extract_outdoor_pm25_returns_none_for_missing_air_korea_value(self):
        payload = {"response": {"body": {"items": [{"pm25Value": "-"}]}}}

        self.assertIsNone(extract_json_path(payload, "response.body.items.0.pm25Value"))


if __name__ == "__main__":
    unittest.main()
