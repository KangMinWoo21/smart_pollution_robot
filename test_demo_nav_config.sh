#!/usr/bin/env bash
set -euo pipefail

grep -Fq "MAP_FILE=\"\${MAP_FILE:-\$PROJECT_DIR/linetrace_map.yaml}\"" start_laptop.sh || { echo FAIL: original map default >&2; exit 1; }
grep -Fq "NAV2_PARAMS_FILE=\"\${NAV2_PARAMS_FILE:-\$PROJECT_DIR/demo_nav2_params.yaml}\"" start_laptop.sh || { echo FAIL: nav2 params default >&2; exit 1; }
grep -Fq "params_file:=" start_laptop.sh || { echo FAIL: params launch arg missing >&2; exit 1; }
grep -Fq "NAV2_PARAMS_FILE" start_laptop.sh || { echo FAIL: params launch arg variable missing >&2; exit 1; }
test -f demo_nav2_params.yaml || { echo FAIL: demo_nav2_params.yaml missing >&2; exit 1; }
grep -q "plugins: \[\"obstacle_layer\", \"inflation_layer\"\]" demo_nav2_params.yaml || { echo FAIL: local obstacle+inflation >&2; exit 1; }
grep -q "plugins: \[\"static_layer\", \"obstacle_layer\", \"inflation_layer\"\]" demo_nav2_params.yaml || { echo FAIL: global static+obstacle+inflation >&2; exit 1; }
grep -q "inflation_radius: 0.30" demo_nav2_params.yaml || { echo FAIL: inflation 0.30 >&2; exit 1; }
grep -q "movement_time_allowance: 20.0" demo_nav2_params.yaml || { echo FAIL: movement allowance >&2; exit 1; }

line_of() {
  local pattern="$1"
  local file="$2"
  awk -v pattern="$pattern" "index(\$0, pattern) { print NR; exit }" "$file"
}

rosbridge_line="$(line_of "start_process \"rosbridge\"" start_laptop.sh)"
web_line="$(line_of "start_process \"web_ui\"" start_laptop.sh)"
map_line="$(line_of "start_process \"map_web_publisher\"" start_laptop.sh)"
pose_line="$(line_of "start_process \"robot_pose_web_publisher\"" start_laptop.sh)"
outdoor_line="$(line_of "start_process \"outdoor_air_quality\"" start_laptop.sh)"
robot_wait_line="$(line_of "wait_for_robot_ready" start_laptop.sh)"
nav2_line="$(line_of "start_process \"navigation2\"" start_laptop.sh)"

test -n "$rosbridge_line" && test -n "$web_line" && test -n "$map_line" && test -n "$pose_line" && test -n "$outdoor_line" && test -n "$robot_wait_line" && test -n "$nav2_line" || { echo FAIL: missing laptop launch steps >&2; exit 1; }
test "$rosbridge_line" -lt "$robot_wait_line" || { echo FAIL: rosbridge must start before robot wait >&2; exit 1; }
test "$web_line" -lt "$robot_wait_line" || { echo FAIL: web UI must start before robot wait >&2; exit 1; }
test "$map_line" -lt "$robot_wait_line" || { echo FAIL: map web publisher must start before robot wait >&2; exit 1; }
test "$pose_line" -lt "$robot_wait_line" || { echo FAIL: pose web publisher must start before robot wait >&2; exit 1; }
test "$outdoor_line" -lt "$robot_wait_line" || { echo FAIL: outdoor air quality must start before robot wait >&2; exit 1; }
test "$robot_wait_line" -lt "$nav2_line" || { echo FAIL: robot wait must happen before Nav2 only >&2; exit 1; }

grep -Fq "sleep 10;" run_demo.sh || { echo FAIL: web smoke check should run after 10 seconds >&2; exit 1; }
grep -Fq "[웹 서버 HTTP]" run_demo.sh || { echo FAIL: missing web smoke label >&2; exit 1; }
grep -Fq "sleep 35;" run_demo.sh || { echo FAIL: ROS smoke check should run after 35 seconds >&2; exit 1; }
grep -Fq "[ROS 데이터 연결]" run_demo.sh || { echo FAIL: missing ROS data smoke label >&2; exit 1; }
grep -Fq "노트북: http://127.0.0.1:8000/" run_demo.sh || { echo FAIL: missing laptop web URL >&2; exit 1; }
grep -Fq "iPad/다른 기기: http://172.20.10.5:8000/" run_demo.sh || { echo FAIL: missing mobile web URL >&2; exit 1; }
echo demo nav config ok
