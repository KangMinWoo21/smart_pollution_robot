const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const body = html.slice(html.indexOf('<body>'));

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

[
  'status_box',
  'pm25_value',
  'air_quality_label',
  'air_ring',
  'pose_value',
  'mode_value',
  'target_zone_label',
  'outdoor_pm25_value',
  'outdoor_pm25_status',
  'btn_manual',
  'btn_auto',
  'zone_all',
  'zone_kitchen',
  'auto_controls',
  'manual_fan_controls',
  'btn_fan_on',
  'btn_fan_off',
  'map',
  'map_canvas',
  'map_status',
  'zone_joystick',
].forEach((id) => {
  assert(html.includes(`id="${id}"`), `missing #${id}`);
});

assert(!html.includes('id="zone_living"'), 'living focus zone should be removed for demo');
assert(!html.includes('부엌'), 'UI text should use 주방, not 부엌');
assert(html.includes('주방 집중'), 'UI should show kitchen focus as 주방 집중');
assert(body.includes('class="ops_header"'), 'missing compact operations header');
assert(body.includes('class="command_dock"'), 'missing fixed command dock');
assert(html.includes('[hidden] {') && html.includes('display: none !important;'), 'hidden controls must not be made visible by grid or flex CSS');
assert(body.includes('id="joystick_drawer" class="drawer" hidden'), 'joystick drawer should be hidden by default');
assert(!body.includes('id="detail_drawer"'), 'detail status drawer should be removed');
assert(!body.includes('id="detail_controls"'), 'detail status button should be removed');
assert(!body.includes('상세 상태'), 'detail status UI text should be removed');
assert(!body.includes('class="hero_card"'), 'old hero card layout should be removed');
assert(!body.includes('class="panel joystick_panel"'), 'always-visible joystick panel should be removed');

const mapOverlayStart = body.indexOf('class="map_overlay"');
const mapOverlayEnd = body.indexOf('id="map_status"', mapOverlayStart);
const mapOverlay = body.slice(mapOverlayStart, mapOverlayEnd);
assert(mapOverlay.includes('id="target_zone_label"'), 'map overlay should show selected target zone');
assert(!mapOverlay.includes('id="prediction_target"'), 'map overlay should not show predictive patrol candidate');
assert(!body.includes('id="btn_drive_panel"'), 'separate joystick button should be removed');
assert(!body.includes('onclick="toggleJoystick()"'), 'joystick should not be opened by a separate utility button');
assert(body.includes("if (mode === 'manual') openJoystick();"), 'manual mode should open joystick');
assert(body.includes("if (mode === 'auto') closeJoystick();"), 'auto mode should close joystick');
assert(body.includes("setControlPanelForMode(mode);"), 'mode changes should update visible control panel');
assert(body.includes("manualControls.hidden = mode !== 'manual';"), 'manual fan controls should only show in manual mode');
assert(body.includes("autoControls.hidden = mode !== 'auto';"), 'zone controls should only show in auto mode');
assert(!body.includes("detailControls"), 'detail controls JS should be removed');
assert(!body.includes("toggleDetails"), 'detail drawer JS should be removed');
assert(body.includes("name: '/hardware/relay'"), 'fan relay topic is missing');
assert(body.includes("name: '/air_quality/outdoor_pm25'"), 'outdoor PM2.5 topic is missing');
assert(body.includes("function updateOutdoorPm25Ui(value)"), 'outdoor PM2.5 UI updater is missing');
assert(body.includes("outdoorPm25Topic.subscribe(function(msg)"), 'outdoor PM2.5 subscription is missing');
assert(body.includes("updateOutdoorPm25Ui(msg.data);"), 'outdoor PM2.5 subscription should update visible UI');
assert(body.includes("function setManualFan(enabled)"), 'manual fan control function is missing');
assert(body.includes('function updateTargetZoneLabel(zone)'), 'target zone label updater is missing');
assert(body.includes("if (zone === 'kitchen') return '선택: 주방 집중';"), 'kitchen target label should be 주방 집중');
assert(!body.includes("document.getElementById('prediction_target').innerText = top.label"), 'detail target should not show predictive candidate names');
assert(body.includes("targetZoneTopic.publish(new ROSLIB.Message({ data: zone }));"), 'target zone selection should publish selected zone');
assert(body.includes("targetZoneTopic.publish(new ROSLIB.Message({ data: zone }));\n            setMode('auto');"), 'target zone selection should restart auto mode, including all');
assert(body.includes("name: '/purifier_status'"), 'UI should subscribe to purifier status');
assert(body.includes("purifierStatusOverride = '정화 완료';"), 'UI should show cleaned status without changing sensor PM');
assert(body.includes("purifierStatusOverride = '복귀 중';"), 'UI should show demo return status');
assert(body.includes("purifierStatusOverride = '출발지 복귀 완료';"), 'UI should show demo return completion');
assert(body.includes("var patrolWaypoints = ["), 'map priority markers should use demo patrol waypoints');
assert(body.includes("x: 5.18, y: 1.62"), "map priority markers should include updated waypoint 2");
assert(body.includes("x: 8.00, y: 1.40"), "map priority markers should include updated waypoint 3");
assert(!body.includes("x: 3.00, y: 1.25"), "map priority markers should not include old waypoint 2");
assert(!body.includes("x: 7.11, y: 1.48"), "map priority markers should not include old waypoint 3");
assert(body.includes("x: 7.50, y: 5.19"), "map priority markers should include the kitchen waypoint world coordinate");
assert(body.includes("var displayOnlyMapDots = ["), "map should define web-only display dots");
assert(body.includes("x: 8.40, y: 4.00"), "map should include web-only dot at 8.4,4.0");
assert(body.includes("x: 2.82, y: 0.50"), "map should include web-only dot at 2.82,0.50");
assert(body.includes("drawDisplayOnlyMapDots(ctx);"), "map should render web-only display dots");
assert(body.includes("var MAP_DOT_RADIUS_PX = 9;"), "map dots should share one radius constant");
assert(!body.includes("index === 0 ? 12 : 9"), "map priority dots should not use different sizes");
assert(body.includes("ctx.fillStyle = '#4577ff';"), "web-only display dots should be blue");
assert(!body.includes("zone.score >= 52 ? '#b8872e'"), "map should not render yellow priority dots");
assert(body.includes("MAP_VIEW_SCALE"), "map should expose a view scale constant for demo zoom");
assert(body.includes("worldToCanvas(zone.x, zone.y)"), 'map priority markers should use world coordinates');
assert(!body.includes("zone.mapX * mapDrawState.width"), 'map priority markers should not use fake relative x positions');
assert(!body.includes("zone.mapY * mapDrawState.height"), 'map priority markers should not use fake relative y positions');
assert(!body.includes("index === 0 ? '!' : String(index + 1)"), 'top priority marker should be numbered 1, not !');
assert(!body.includes("ctx.fillText(String(index + 1)"), 'priority markers should not display waypoint numbers');
assert(body.includes("var kitchenBounds = { minX: 6.61, maxX: 8.33, minY: 1.40"), 'kitchen bounds should include waypoint 3');

['선택 구역', '팬 ON 기준', '탐색 방식', '시연 단계', '시연 경로', '정화 시간', '복귀 위치'].forEach((label) => {
  assert(!body.includes(label), `detail panel label should be removed: ${label}`);
});
assert(!body.includes('outdoor_pm25_input'), 'detail panel should not expose outdoor PM input');
assert(!body.includes('function updateAlgorithmDetails()'), 'algorithm detail updater should be removed');
assert(!body.includes("document.getElementById('prediction_score').innerText = top.score"), 'predictive score should not update detail panel');

assert(body.includes('function initJoystick()'), 'joystick should initialize lazily after drawer opens');
assert(body.includes('initJoystick();'), 'opening joystick drawer should initialize joystick');
assert(!body.includes('var joystick = nipplejs.create'), 'joystick should not initialize while hidden');
assert(body.includes("name: '/cmd_vel'"), 'joystick command velocity topic is missing');
assert(body.includes("joystick.on('move'"), 'joystick move handler is missing');
assert(body.includes("joystick.on('end'"), 'joystick stop handler is missing');

console.log('index_layout.test.js: PASS');
