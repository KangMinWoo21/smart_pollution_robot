#!/usr/bin/env bash
set -Eeuo pipefail

# Laptop side launcher.
# Starts Navigation2, rosbridge, web UI server, and the air purifier FSM node.

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"
ROS_LOG_DIR="${ROS_LOG_DIR:-$LOG_DIR/ros}"
MAP_FILE="${MAP_FILE:-$PROJECT_DIR/linetrace_map.yaml}"
WEB_DIR="${WEB_DIR:-$PROJECT_DIR/web_ui}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-8000}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-waffle}"

DISABLE_DOCKER0="${DISABLE_DOCKER0:-1}"
START_NAV2="${START_NAV2:-1}"
START_ROSBRIDGE="${START_ROSBRIDGE:-1}"
START_WEB="${START_WEB:-1}"
START_MAP_WEB="${START_MAP_WEB:-1}"
START_POSE_WEB="${START_POSE_WEB:-1}"
START_OUTDOOR_AIR="${START_OUTDOOR_AIR:-1}"
START_FSM="${START_FSM:-1}"
OUTDOOR_AIR_NODE="${OUTDOOR_AIR_NODE:-$PROJECT_DIR/outdoor_air_quality_node.py}"

PIDS=()

start_process() {
  local name="$1"
  local command="$2"
  local log_file="$LOG_DIR/${name}.log"

  echo "[start] $name"
  bash -lc "
    source '$ROS_SETUP'
    export ROS_DOMAIN_ID='$ROS_DOMAIN_ID'
    export TURTLEBOT3_MODEL='$TURTLEBOT3_MODEL'
    export ROS_LOG_DIR='$ROS_LOG_DIR'
    export OUTDOOR_AIR_MODE='${OUTDOOR_AIR_MODE:-mock}'
    export OUTDOOR_PM25_MOCK='${OUTDOOR_PM25_MOCK:-62}'
    export OUTDOOR_AIR_API_URL='${OUTDOOR_AIR_API_URL:-}'
    export OUTDOOR_AIR_API_JSON_PATH='${OUTDOOR_AIR_API_JSON_PATH:-pm25}'
    export OUTDOOR_AIR_INTERVAL_SECONDS='${OUTDOOR_AIR_INTERVAL_SECONDS:-60}'
    export OUTDOOR_AIR_STALE_SECONDS='${OUTDOOR_AIR_STALE_SECONDS:-1800}'
    cd '$PROJECT_DIR'
    exec $command
  " >"$log_file" 2>&1 &

  PIDS+=("$!")
  echo "        log: $log_file"
}

cleanup() {
  echo
  echo "[stop] shutting down laptop launcher processes..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup INT TERM

mkdir -p "$LOG_DIR"
mkdir -p "$ROS_LOG_DIR"

if [[ ! -f "$ROS_SETUP" ]]; then
  echo "[error] ROS setup file not found: $ROS_SETUP" >&2
  exit 1
fi

if [[ ! -f "$MAP_FILE" ]]; then
  echo "[error] map file not found: $MAP_FILE" >&2
  exit 1
fi

if [[ ! -d "$WEB_DIR" ]]; then
  echo "[error] web UI directory not found: $WEB_DIR" >&2
  exit 1
fi

echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "TURTLEBOT3_MODEL=$TURTLEBOT3_MODEL"
echo "PROJECT_DIR=$PROJECT_DIR"
echo "MAP_FILE=$MAP_FILE"
echo "WEB_DIR=$WEB_DIR"
echo "ROS_LOG_DIR=$ROS_LOG_DIR"
echo "OUTDOOR_AIR_MODE=${OUTDOOR_AIR_MODE:-mock}"
echo "OUTDOOR_PM25_MOCK=${OUTDOOR_PM25_MOCK:-62}"
echo

if [[ "$DISABLE_DOCKER0" == "1" ]]; then
  if ip link show docker0 >/dev/null 2>&1; then
    echo "[network] disabling docker0 to avoid FastDDS interface conflicts"
    sudo ip link set dev docker0 down
  else
    echo "[network] docker0 not found; skipping"
  fi
fi

if [[ "$START_NAV2" == "1" ]]; then
  start_process "navigation2" "ros2 launch turtlebot3_navigation2 navigation2.launch.py map:='$MAP_FILE'"
  sleep 5
fi

if [[ "$START_ROSBRIDGE" == "1" ]]; then
  start_process "rosbridge" "ros2 launch rosbridge_server rosbridge_websocket_launch.xml"
  sleep 2
fi

if [[ "$START_WEB" == "1" ]]; then
  start_process "web_ui" "python3 '$PROJECT_DIR/no_cache_web_server.py' --host '$WEB_HOST' --port '$WEB_PORT' --directory '$WEB_DIR'"
  sleep 1
fi

if [[ "$START_MAP_WEB" == "1" ]]; then
  start_process "map_web_publisher" "python3 '$PROJECT_DIR/map_web_publisher.py'"
  sleep 1
fi

if [[ "$START_POSE_WEB" == "1" ]]; then
  start_process "robot_pose_web_publisher" "python3 '$PROJECT_DIR/robot_pose_web_publisher.py'"
  sleep 1
fi

if [[ "$START_OUTDOOR_AIR" == "1" ]]; then
  if [[ -f "$OUTDOOR_AIR_NODE" ]]; then
    start_process "outdoor_air_quality" "python3 '$OUTDOOR_AIR_NODE'"
    sleep 1
  else
    echo "[warn] outdoor air quality node not found: $OUTDOOR_AIR_NODE"
  fi
fi

if [[ "$START_FSM" == "1" ]]; then
  start_process "real_cleaner" "python3 '$PROJECT_DIR/real_cleaner.py'"
fi

echo
echo "[ready] Laptop processes started."
echo "        Open: http://<laptop-ip>:$WEB_PORT"
echo "        In RViz, set the initial pose with '2D Pose Estimate' before autonomous use."
echo "        Press Ctrl+C to stop processes launched by this script."
wait
