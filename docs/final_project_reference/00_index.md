# 최종 프로젝트 참고 문서 목차

이 폴더는 윈도우에서 최종 프로젝트 발표 PPT를 만들 때 참고하기 위한 프로젝트 전체 정리본입니다. 발표의 중심은 `자율주행 스마트 공기청정 로봇`이며, 주방 집중 정화는 전체 기능 중 하나로 설명합니다.

## 문서 구성

1. [01_project_summary.md](01_project_summary.md)
   - 프로젝트 개요, 문제 정의, 목표, 차별성, 최종 발표 핵심 메시지
2. [02_hardware_system.md](02_hardware_system.md)
   - TurtleBot3 Waffle, Raspberry Pi, LiDAR, PMS7003, 릴레이, 팬, 전원 구성
3. [03_software_system.md](03_software_system.md)
   - ROS 2 Jazzy, Zenoh, Nav2, rosbridge, Web UI, 주요 노드와 토픽
4. [04_core_algorithm.md](04_core_algorithm.md)
   - 자동 정화 FSM, 정화 후보 지점 탐색, PM2.5 변화 감지, LiDAR 후보, 현장 측정, 오염원 확정, 팬 정화
5. [05_demo_and_operation.md](05_demo_and_operation.md)
   - 실행 방법, 노트북/Pi 역할, 시연 순서, 확인 토픽, 문제 해결
6. [06_presentation_slide_material.md](06_presentation_slide_material.md)
   - PPT 슬라이드별로 넣을 내용, 발표 대본, 디자인 참고사항
7. [99_code_reference.md](99_code_reference.md)
   - 핵심 코드 파일별 역할, 주요 함수/클래스 설명, 발표에 넣을 코드 조각

## PPT 제작 순서 추천

1. `06_presentation_slide_material.md`에서 전체 슬라이드 흐름을 잡습니다.
2. 각 슬라이드의 기술 설명이 부족하면 `01`부터 `05` 문서를 참고합니다.
3. 알고리즘이나 구현 근거를 보여주고 싶으면 `99_code_reference.md`에서 짧은 코드 조각을 가져옵니다.
4. 발표에서는 영어 개발 용어보다 아래 발표용 용어를 사용합니다.

## 발표자료 용어 기준

| 개발/영어 표현 | 발표자료 표현 |
| --- | --- |
| waypoint | 정화 후보 지점 |
| kitchen zone | 주방 집중 구역 |
| target zone | 집중 정화 구역 |
| sample | 현장 측정 |
| found target | 오염원 확정 |

## 최종 발표 핵심 문장

이 프로젝트는 실내 공기질을 단순히 표시하는 시스템이 아니라, 로봇이 미세먼지 센서와 LiDAR 정보를 바탕으로 오염 가능성이 높은 위치를 판단하고, Nav2 자율주행으로 이동한 뒤 팬을 작동해 정화까지 수행하는 자율주행 스마트 공기청정 로봇입니다.
