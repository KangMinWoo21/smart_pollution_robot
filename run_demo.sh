#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"
mkdir -p "$LOG_DIR"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-waffle}"
export LDS_MODEL="${LDS_MODEL:-LDS-02}"

LAPTOP_WEB_URL="http://127.0.0.1:8000/"
IPAD_WEB_URL="http://172.20.10.5:8000/"
ZENOH_SESSION_CONFIG_URI="${ZENOH_SESSION_CONFIG_URI:-$LOG_DIR/zenoh_laptop_session.json5}"

echo "[cleanup] stopping previous demo stacks"
pkill -f "start_laptop.sh|rmw_zenohd|component_container_isolated|turtlebot3_navigation2|rosbridge_websocket|rosapi_node|rviz2|real_cleaner.py|map_web_publisher.py|robot_pose_web_publisher.py|outdoor_air_quality_node.py|no_cache_web_server.py|cmd_vel_nav_relay.py" 2>/dev/null || true
ssh -o ConnectTimeout=3 a@172.20.10.2 "pkill -f \"[s]tart_raspberry_pi.sh|[r]obot.launch.py|[t]urtlebot3_ros|[r]obot_state_publisher|[l]d08_driver|[p]ms_ros_node.py|[r]elay_control_node.py\" 2>/dev/null || true" 2>/dev/null || true
sleep 2

# 1. Laptop: Zenoh + rosbridge + web + map/pose + outdoor PM API immediately; Nav2 waits for robot data inside start_laptop.sh.
gnome-terminal --title="1. Laptop Stack" -- bash -c \
"cd \"$PROJECT_DIR\" && USE_ZENOH=1 ./start_laptop.sh; exec bash"

sleep 2

# 2. TurtleBot3 / Raspberry Pi: bringup + PMS7003 + relay/fan
gnome-terminal --title="2. Raspberry Pi Robot" -- bash -c \
"ssh -t a@172.20.10.2 \"cd /home/a/pollution_robot && USE_ZENOH=1 ZENOH_ROUTER_ENDPOINT=tcp/172.20.10.5:7447 PMS_PORT=/dev/ttyS0 ./start_raspberry_pi.sh\"; exec bash"

sleep 2

# 3. Web smoke check: web should be reachable before robot/Nav2 is fully ready.
gnome-terminal --title="3. Web Smoke Check" -- bash -c \
"sleep 10; echo \"[웹 서버 HTTP]\"; curl -I \"$LAPTOP_WEB_URL\"; echo; echo \"노트북: $LAPTOP_WEB_URL\"; echo \"iPad/다른 기기: $IPAD_WEB_URL\"; exec bash"

# 4. ROS data smoke check: robot topics and Nav2 lifecycle can legitimately arrive later.
gnome-terminal --title="4. ROS Data Smoke Check" -- bash -c \
"sleep 35; cd \"$PROJECT_DIR\"; echo \"[ROS 데이터 연결]\"; curl -I http://127.0.0.1:9090/ || true; if [[ -f /opt/ros/jazzy/setup.bash ]]; then source /opt/ros/jazzy/setup.bash; export ROS_DOMAIN_ID=\"$ROS_DOMAIN_ID\"; export TURTLEBOT3_MODEL=\"$TURTLEBOT3_MODEL\"; export RMW_IMPLEMENTATION=rmw_zenoh_cpp; export ZENOH_SESSION_CONFIG_URI=\"$ZENOH_SESSION_CONFIG_URI\"; echo; echo \"[/scan]\"; ros2 topic info /scan || true; echo; echo \"[/odom]\"; ros2 topic info /odom || true; for node in bt_navigator controller_server planner_server; do echo; echo \"[/\$node lifecycle]\"; ros2 lifecycle get \"/\$node\" || true; done; echo; echo \"[자동 주행 노드]\"; ros2 node list | grep autonomous_purifier || echo WARN_autonomous_purifier_missing; echo; echo \"[/robot_mode]\"; ros2 topic info /robot_mode || true; else echo \"[warn] /opt/ros/jazzy/setup.bash not found; skipping ROS topic checks\"; fi; exec bash"

echo "통합 시연 스택 실행 요청 완료"
echo "- 바로 접속:"
echo "  - 노트북: $LAPTOP_WEB_URL"
echo "  - iPad/다른 기기: $IPAD_WEB_URL"
echo "- 웹 화면은 먼저 뜨고, 지도/로봇 위치/센서 데이터는 rosbridge, map publisher, Nav2 준비 후 몇 초 늦게 들어올 수 있습니다."
echo "- Pi: TurtleBot3 bringup, PMS7003, relay/fan"
echo "- Laptop: Zenoh, Nav2, rosbridge, web, map/pose publisher, outdoor PM API, real_cleaner"
echo "- Check windows: Raspberry Pi Robot / Laptop Stack / Web Smoke Check / ROS Data Smoke Check"
