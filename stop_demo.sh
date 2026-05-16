#!/bin/bash

# 1. 로컬(노트북)에서 돌아가는 ROS 2 프로세스 종료
pkill -f ros2
pkill -f cartographer
pkill -f rviz2
pkill -f teleop_keyboard

# 2. 로봇(SSH)에서 돌아가는 프로세스들 종료 (원격 명령)
ssh a@172.20.10.2 "pkill -f ros2; pkill -f python3"

# 3. 모든 터미널 창 닫기
pkill -f gnome-terminal

echo "모든 시연 프로세스가 안전하게 종료되었습니다."
