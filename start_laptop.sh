#!/usr/bin/env bash
set -Eeuo pipefail

# Laptop side launcher.
# Starts Navigation2, rosbridge, web UI server, and the air purifier FSM node.

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"
ROS_LOG_DIR="${ROS_LOG_DIR:-$LOG_DIR/ros}"
MAP_FILE="${MAP_FILE:-$PROJECT_DIR/linetrace_map.yaml}"
NAV2_PARAMS_FILE="${NAV2_PARAMS_FILE:-$PROJECT_DIR/demo_nav2_params.yaml}"
WEB_DIR="${WEB_DIR:-$PROJECT_DIR/web_ui}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-8000}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-waffle}"

USE_ZENOH="${USE_ZENOH:-1}"
ZENOH_ROUTER_ENDPOINT="${ZENOH_ROUTER_ENDPOINT:-tcp/0.0.0.0:7447}"
ZENOH_SESSION_ENDPOINT="${ZENOH_SESSION_ENDPOINT:-tcp/localhost:7447}"
ZENOH_SESSION_CONFIG_URI="${ZENOH_SESSION_CONFIG_URI:-$LOG_DIR/zenoh_laptop_session.json5}"

DISABLE_DOCKER0="${DISABLE_DOCKER0:-1}"
START_NAV2="${START_NAV2:-1}"
START_ROSBRIDGE="${START_ROSBRIDGE:-1}"
START_WEB="${START_WEB:-1}"
START_MAP_WEB="${START_MAP_WEB:-1}"
START_POSE_WEB="${START_POSE_WEB:-1}"
START_OUTDOOR_AIR="${START_OUTDOOR_AIR:-1}"
START_FSM="${START_FSM:-1}"
START_CMD_VEL_RELAY="${START_CMD_VEL_RELAY:-1}"

export AUTO_CLEAN_WAYPOINTS="${AUTO_CLEAN_WAYPOINTS:-3.07,4.98,-1.59;5.18,1.62,0.05;8.00,1.40,1.47;7.50,5.19,-2.90;5.42,4.68,3.01}"
export TARGET_PM25_THRESHOLD="${TARGET_PM25_THRESHOLD:-36}"
export TARGET_PM25_TRIGGER_DELTA="${TARGET_PM25_TRIGGER_DELTA:-3}"
export TARGET_TRACK_STEP_M="${TARGET_TRACK_STEP_M:-0.20}"
export TARGET_PM25_IMPROVEMENT_DELTA="${TARGET_PM25_IMPROVEMENT_DELTA:-2}"
export TARGET_SAMPLE_SECONDS="${TARGET_SAMPLE_SECONDS:-2}"
export TARGET_PURIFY_SECONDS="${TARGET_PURIFY_SECONDS:-7}"
export TARGET_COUNT="${TARGET_COUNT:-1}"
export TARGET_IGNORE_RADIUS_M="${TARGET_IGNORE_RADIUS_M:-0.5}"
export TARGET_SIGNAL_IGNORE_RADIUS_M="${TARGET_SIGNAL_IGNORE_RADIUS_M:-0.7}"
export TARGET_LIVE_INTERRUPT_ZONES="${TARGET_LIVE_INTERRUPT_ZONES:-kitchen,all}"
export TARGET_LIDAR_DIAMETER_M="${TARGET_LIDAR_DIAMETER_M:-0.10}"
export TARGET_LIDAR_DIAMETER_TOLERANCE_M="${TARGET_LIDAR_DIAMETER_TOLERANCE_M:-0.05}"
export TARGET_LIDAR_MAX_RANGE_M="${TARGET_LIDAR_MAX_RANGE_M:-1.6}"
export TARGET_LIDAR_STALE_SECONDS="${TARGET_LIDAR_STALE_SECONDS:-2.5}"
OUTDOOR_AIR_NODE="${OUTDOOR_AIR_NODE:-$PROJECT_DIR/outdoor_air_quality_node.py}"

PIDS=()

prepare_zenoh_session_config() {
  cat >"$ZENOH_SESSION_CONFIG_URI" <<EOF
{
  mode: "client",
  connect: {
    endpoints: ["$ZENOH_SESSION_ENDPOINT"],
  },
  listen: {
    endpoints: [],
  },
  scouting: {
    multicast: { enabled: false },
    gossip: { enabled: false },
  },
}
EOF
}

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
    if [[ '$USE_ZENOH' == '1' ]]; then
      export RMW_IMPLEMENTATION='rmw_zenoh_cpp'
      export ZENOH_SESSION_CONFIG_URI='$ZENOH_SESSION_CONFIG_URI'
    fi
    export OUTDOOR_AIR_MODE='${OUTDOOR_AIR_MODE:-api}'
    export OUTDOOR_PM25_MOCK='${OUTDOOR_PM25_MOCK:-27}'
    export OUTDOOR_AIR_API_URL='${OUTDOOR_AIR_API_URL:-http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty?serviceKey=c89c15d9fef538a1ff9c7fda338b572fadc42359f38309424387fe2b571e1357&returnType=json&numOfRows=1&pageNo=1&stationName=%EB%B3%B5%EB%8C%80%EB%8F%99&dataTerm=DAILY&ver=1.3}'
    export OUTDOOR_AIR_API_JSON_PATH='${OUTDOOR_AIR_API_JSON_PATH:-response.body.items.0.pm25Value}'
    export OUTDOOR_AIR_INTERVAL_SECONDS='${OUTDOOR_AIR_INTERVAL_SECONDS:-10}'
    export OUTDOOR_AIR_STALE_SECONDS='${OUTDOOR_AIR_STALE_SECONDS:-1800}'
    cd '$PROJECT_DIR'
    exec $command
  " >"$log_file" 2>&1 &

  PIDS+=("$!")
  echo "        log: $log_file"
}

wait_for_robot_ready() {
  local timeout_seconds="${ROBOT_READY_TIMEOUT_SECONDS:-30}"
  local started_at now
  started_at="$(date +%s)"
  echo "[robot] waiting for /scan, /odom, and odom->base_footprint before Nav2"
  while true; do
    if (
      set +u
      source "$ROS_SETUP"
      set -u
      export ROS_DOMAIN_ID="$ROS_DOMAIN_ID"
      export TURTLEBOT3_MODEL="$TURTLEBOT3_MODEL"
      export ROS_LOG_DIR="$ROS_LOG_DIR"
      if [[ "$USE_ZENOH" == "1" ]]; then
        export RMW_IMPLEMENTATION="rmw_zenoh_cpp"
        export ZENOH_SESSION_CONFIG_URI="$ZENOH_SESSION_CONFIG_URI"
      fi
      ros2 topic info /scan 2>/dev/null | grep -q "Publisher count: [1-9]" &&
      ros2 topic info /odom 2>/dev/null | grep -q "Publisher count: [1-9]" &&
      timeout 2 ros2 run tf2_ros tf2_echo odom base_footprint >/dev/null 2>&1
    ); then
      echo "[robot] ready"
      return 0
    fi
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[warn] robot topics/TF not ready after ${timeout_seconds}s; starting Nav2 anyway"
      return 0
    fi
    sleep 2
  done
}

activate_inactive_nav2_nodes() {
  local log_file="$LOG_DIR/nav2_lifecycle_activate.log"
  echo "[nav2] activating inactive lifecycle nodes"
  (
    set +u
    source "$ROS_SETUP"
    set -u
    export ROS_DOMAIN_ID="$ROS_DOMAIN_ID"
    export TURTLEBOT3_MODEL="$TURTLEBOT3_MODEL"
    export ROS_LOG_DIR="$ROS_LOG_DIR"
    if [[ "$USE_ZENOH" == "1" ]]; then
      export RMW_IMPLEMENTATION="rmw_zenoh_cpp"
      export ZENOH_SESSION_CONFIG_URI="$ZENOH_SESSION_CONFIG_URI"
    fi
    for node in controller_server planner_server smoother_server behavior_server bt_navigator waypoint_follower velocity_smoother map_server amcl; do
      state="$(timeout 5 ros2 lifecycle get "/$node" 2>/dev/null || true)"
      if [[ "$state" == *inactive* ]]; then
        echo "[activate] /$node"
        timeout 8 ros2 lifecycle set "/$node" activate || true
      fi
    done
  ) >"$log_file" 2>&1 || true
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

if [[ ! -f "$NAV2_PARAMS_FILE" ]]; then
  echo "[error] Nav2 params file not found: $NAV2_PARAMS_FILE" >&2
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
echo "NAV2_PARAMS_FILE=$NAV2_PARAMS_FILE"
echo "WEB_DIR=$WEB_DIR"
echo "ROS_LOG_DIR=$ROS_LOG_DIR"
echo "OUTDOOR_AIR_MODE=${OUTDOOR_AIR_MODE:-api}"
echo "OUTDOOR_PM25_MOCK=${OUTDOOR_PM25_MOCK:-62}"
echo "AUTO_CLEAN_WAYPOINTS=$AUTO_CLEAN_WAYPOINTS"
echo "TARGET_PM25_THRESHOLD=$TARGET_PM25_THRESHOLD"
echo "TARGET_PM25_TRIGGER_DELTA=$TARGET_PM25_TRIGGER_DELTA"
echo "TARGET_TRACK_STEP_M=$TARGET_TRACK_STEP_M"
echo "TARGET_PM25_IMPROVEMENT_DELTA=$TARGET_PM25_IMPROVEMENT_DELTA"
echo "TARGET_SAMPLE_SECONDS=$TARGET_SAMPLE_SECONDS"
echo "TARGET_PURIFY_SECONDS=$TARGET_PURIFY_SECONDS"
echo "TARGET_COUNT=$TARGET_COUNT"
echo "TARGET_IGNORE_RADIUS_M=$TARGET_IGNORE_RADIUS_M"
echo "TARGET_SIGNAL_IGNORE_RADIUS_M=$TARGET_SIGNAL_IGNORE_RADIUS_M"
echo "TARGET_LIVE_INTERRUPT_ZONES=$TARGET_LIVE_INTERRUPT_ZONES"
echo "TARGET_LIDAR_DIAMETER_M=$TARGET_LIDAR_DIAMETER_M"
echo "TARGET_LIDAR_DIAMETER_TOLERANCE_M=$TARGET_LIDAR_DIAMETER_TOLERANCE_M"
echo "TARGET_LIDAR_MAX_RANGE_M=$TARGET_LIDAR_MAX_RANGE_M"
echo "TARGET_LIDAR_STALE_SECONDS=$TARGET_LIDAR_STALE_SECONDS"
echo "USE_ZENOH=$USE_ZENOH"
if [[ "$USE_ZENOH" == "1" ]]; then
  echo "ZENOH_ROUTER_ENDPOINT=$ZENOH_ROUTER_ENDPOINT"
  echo "ZENOH_SESSION_ENDPOINT=$ZENOH_SESSION_ENDPOINT"
  echo "ZENOH_SESSION_CONFIG_URI=$ZENOH_SESSION_CONFIG_URI"
fi
echo

if [[ "$USE_ZENOH" == "1" ]]; then
  prepare_zenoh_session_config
  start_process "zenoh_router" "ros2 run rmw_zenoh_cpp rmw_zenohd -l '$ZENOH_ROUTER_ENDPOINT'"
  sleep 2
fi

if [[ "$DISABLE_DOCKER0" == "1" ]]; then
  if ip link show docker0 >/dev/null 2>&1; then
    echo "[network] disabling docker0 to avoid FastDDS interface conflicts"
    if ! sudo -n ip link set dev docker0 down; then
      echo "[warn] could not disable docker0 without sudo password; continuing"
    fi
  else
    echo "[network] docker0 not found; skipping"
  fi
fi

if [[ "$START_ROSBRIDGE" == "1" ]]; then
  start_process "rosbridge" "ros2 launch rosbridge_server rosbridge_websocket_launch.xml"
  sleep 2
fi

if [[ "$START_WEB" == "1" ]]; then
  start_process "web_ui" "python3 \"$PROJECT_DIR/no_cache_web_server.py\" --host \"$WEB_HOST\" --port \"$WEB_PORT\" --directory \"$WEB_DIR\""
  sleep 1
fi

if [[ "$START_MAP_WEB" == "1" ]]; then
  start_process "map_web_publisher" "python3 \"$PROJECT_DIR/map_web_publisher.py\""
  sleep 1
fi

if [[ "$START_POSE_WEB" == "1" ]]; then
  start_process "robot_pose_web_publisher" "python3 \"$PROJECT_DIR/robot_pose_web_publisher.py\""
  sleep 1
fi

if [[ "$START_OUTDOOR_AIR" == "1" ]]; then
  if [[ -f "$OUTDOOR_AIR_NODE" ]]; then
    start_process "outdoor_air_quality" "python3 \"$OUTDOOR_AIR_NODE\""
    sleep 1
  else
    echo "[warn] outdoor air quality node not found: $OUTDOOR_AIR_NODE"
  fi
fi

if [[ "$START_CMD_VEL_RELAY" == "1" ]]; then
  start_process "cmd_vel_nav_relay" "python3 \"$PROJECT_DIR/cmd_vel_nav_relay.py\""
  sleep 1
fi

if [[ "$START_FSM" == "1" ]]; then
  start_process "real_cleaner" "python3 \"$PROJECT_DIR/real_cleaner.py\""
  sleep 1
fi

if [[ "$START_NAV2" == "1" ]]; then
  wait_for_robot_ready
  start_process "navigation2" "ros2 launch turtlebot3_navigation2 navigation2.launch.py map:=\"$MAP_FILE\" params_file:=\"$NAV2_PARAMS_FILE\""
  sleep 5
  activate_inactive_nav2_nodes
fi


echo
echo "[ready] Laptop processes started."
echo "        Open: http://<laptop-ip>:$WEB_PORT"
echo "        In RViz, set the initial pose with '2D Pose Estimate' before autonomous use."
echo "        Press Ctrl+C to stop processes launched by this script."
wait
