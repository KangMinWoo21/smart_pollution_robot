#!/usr/bin/env bash
set -Eeuo pipefail

# TurtleBot3 / Raspberry Pi side launcher.
# Starts robot bringup, PMS7003 sensor node, and relay control node.

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/logs}"
ROS_LOG_DIR="${ROS_LOG_DIR:-$LOG_DIR/ros}"

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-waffle}"
export LDS_MODEL="${LDS_MODEL:-LDS-02}"
export PMS_PORT="${PMS_PORT:-/dev/ttyS0}"
STOP_SERIAL_GETTY="${STOP_SERIAL_GETTY:-1}"
export SUDO_PASSWORD="${SUDO_PASSWORD:-a}"

USE_ZENOH="${USE_ZENOH:-0}"
ZENOH_ROUTER_ENDPOINT="${ZENOH_ROUTER_ENDPOINT:-tcp/172.20.10.5:7447}"
ZENOH_SESSION_CONFIG_URI="${ZENOH_SESSION_CONFIG_URI:-$LOG_DIR/zenoh_raspberry_pi_session.json5}"

PMS_NODE="${PMS_NODE:-$PROJECT_DIR/pms_ros_node.py}"
RELAY_NODE="${RELAY_NODE:-$PROJECT_DIR/relay_control_node.py}"

PIDS=()

prepare_zenoh_session_config() {
  cat >"$ZENOH_SESSION_CONFIG_URI" <<EOF
{
  mode: "client",
  connect: {
    endpoints: ["$ZENOH_ROUTER_ENDPOINT"],
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
    export LDS_MODEL='$LDS_MODEL'
    if [[ '$USE_ZENOH' == '1' ]]; then
      export RMW_IMPLEMENTATION='rmw_zenoh_cpp'
      export ZENOH_SESSION_CONFIG_URI='$ZENOH_SESSION_CONFIG_URI'
    fi
    export PMS_PORT='$PMS_PORT'
    export SUDO_PASSWORD='$SUDO_PASSWORD'
    export ROS_LOG_DIR='$ROS_LOG_DIR'
    cd '$PROJECT_DIR'
    exec $command
  " >"$log_file" 2>&1 &

  PIDS+=("$!")
  echo "        log: $log_file"
}

cleanup() {
  echo
  echo "[stop] shutting down Raspberry Pi launcher processes..."
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

echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "TURTLEBOT3_MODEL=$TURTLEBOT3_MODEL"
echo "LDS_MODEL=$LDS_MODEL"
echo "PMS_PORT=$PMS_PORT"
echo "STOP_SERIAL_GETTY=$STOP_SERIAL_GETTY"
echo "PROJECT_DIR=$PROJECT_DIR"
echo "ROS_LOG_DIR=$ROS_LOG_DIR"
echo "USE_ZENOH=$USE_ZENOH"
if [[ "$USE_ZENOH" == "1" ]]; then
  echo "ZENOH_ROUTER_ENDPOINT=$ZENOH_ROUTER_ENDPOINT"
  echo "ZENOH_SESSION_CONFIG_URI=$ZENOH_SESSION_CONFIG_URI"
  prepare_zenoh_session_config
fi
echo

if [[ "$STOP_SERIAL_GETTY" == "1" && "$PMS_PORT" == "/dev/ttyS0" ]]; then
  echo "[serial] stopping serial-getty@ttyS0.service for PMS7003"
  if ! echo "$SUDO_PASSWORD" | sudo -S systemctl stop serial-getty@ttyS0.service; then
    echo "[warn] could not stop serial-getty@ttyS0.service; PMS may not open /dev/ttyS0"
  fi
  echo "$SUDO_PASSWORD" | sudo -S chmod 666 "$PMS_PORT" 2>/dev/null || true
fi

start_process "robot_bringup" "ros2 launch turtlebot3_bringup robot.launch.py"
sleep 3

if [[ -f "$PMS_NODE" && -c "$PMS_PORT" ]]; then
  start_process "pms_sensor" "python3 '$PMS_NODE'"
else
  echo "[warn] PMS sensor not started: node missing or PMS_PORT is not a character device."
  echo "       PMS_NODE=$PMS_NODE"
  echo "       PMS_PORT=$PMS_PORT"
fi

sleep 1

if [[ -f "$RELAY_NODE" ]]; then
  start_process "relay_control" "echo \"\$SUDO_PASSWORD\" | sudo -S -E bash -lc 'source /opt/ros/jazzy/setup.bash; export ROS_DOMAIN_ID=30 RMW_IMPLEMENTATION=rmw_zenoh_cpp ZENOH_SESSION_CONFIG_URI=/home/a/pollution_robot/logs/zenoh_raspberry_pi_session.json5; /usr/bin/python3 /home/a/pollution_robot/relay_control_node.py'"
else
  echo "[warn] Relay control node not found: $RELAY_NODE"
  echo "       Set RELAY_NODE=/path/to/relay_control_node.py or add it to this project."
fi

echo
echo "[ready] Raspberry Pi processes started. Press Ctrl+C to stop processes launched by this script."
wait
