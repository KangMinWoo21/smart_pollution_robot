#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
PI_SSH="${PI_SSH:-a@172.20.10.2}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"

mkdir -p "$LOG_DIR"

echo "[stop] demo stack"

if [[ -f "$ROS_SETUP" ]]; then
  echo "[stop] requesting manual mode, zero velocity, and relay/fan OFF"
  (
    source "$ROS_SETUP"
    export ROS_DOMAIN_ID="$ROS_DOMAIN_ID"
    export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_zenoh_cpp}"
    export ZENOH_SESSION_CONFIG_URI="${ZENOH_SESSION_CONFIG_URI:-$LOG_DIR/zenoh_laptop_session.json5}"
    timeout 3 ros2 topic pub --once /robot_mode std_msgs/msg/String "{data: manual}" >/dev/null 2>&1 || true
    timeout 3 ros2 topic pub --once /cmd_vel geometry_msgs/msg/TwistStamped "{header: {frame_id: base_link}, twist: {linear: {x: 0.0}, angular: {z: 0.0}}}" >/dev/null 2>&1 || true
    timeout 3 ros2 topic pub --once /hardware/relay std_msgs/msg/Bool "{data: false}" >/dev/null 2>&1 || true
  ) || true
fi

echo "[stop] laptop processes"
pkill -f "start_laptop.sh|rmw_zenohd|component_container_isolated|turtlebot3_navigation2|rosbridge_websocket|rosapi_node|rviz2|real_cleaner.py|map_web_publisher.py|robot_pose_web_publisher.py|outdoor_air_quality_node.py|no_cache_web_server.py|cmd_vel_nav_relay.py" 2>/dev/null || true

echo "[stop] Raspberry Pi processes"
ssh -o ConnectTimeout=3 "$PI_SSH" "pkill -f '[s]tart_raspberry_pi.sh|[r]obot.launch.py|[t]urtlebot3_ros|[r]obot_state_publisher|[l]d08_driver|[p]ms_ros_node.py|[r]elay_control_node.py' 2>/dev/null || true" 2>/dev/null || true

sleep 1

echo "[check] remaining laptop demo processes"
pgrep -af "start_laptop.sh|rmw_zenohd|component_container_isolated|turtlebot3_navigation2|rosbridge_websocket|rosapi_node|rviz2|real_cleaner.py|map_web_publisher.py|robot_pose_web_publisher.py|outdoor_air_quality_node.py|no_cache_web_server.py|cmd_vel_nav_relay.py" || true

echo "[done] demo stack stop requested"
