const assert = require('assert');
const {
    rankPredictiveZones,
    getTimeRiskForZone,
    calculateAdaptiveThreshold,
} = require('./predictive_air_quality');

function runTest(name, fn) {
    try {
        fn();
        console.log('PASS ' + name);
    } catch (error) {
        console.error('FAIL ' + name);
        console.error(error.stack || error.message);
        process.exitCode = 1;
    }
}

runTest('kitchen during dinner ranks above low-risk corridor', () => {
    const zones = [
        { id: 'kitchen', label: '부엌', type: 'kitchen', distance: 1.8, recentVisitMinutes: 80, lastPm25: 82 },
        { id: 'corridor', label: '복도', type: 'corridor', distance: 0.4, recentVisitMinutes: 90, lastPm25: 28 },
    ];

    const ranked = rankPredictiveZones(zones, {
        hour: 18,
        currentPm25: 74,
        outdoorPm25: 61,
    });

    assert.strictEqual(ranked[0].id, 'kitchen');
    assert.ok(ranked[0].score > ranked[1].score);
    assert.ok(ranked[0].reasons.includes('실측 오염 높음'));
    assert.ok(ranked[0].reasons.includes('식사 준비 시간대'));
});

runTest('entry risk increases when outdoor fine dust is high', () => {
    const cleanAirRisk = rankPredictiveZones([
        { id: 'entry', label: '출입구', type: 'entry', distance: 1.0, recentVisitMinutes: 60, lastPm25: 32 },
    ], { hour: 15, currentPm25: 30, outdoorPm25: 20 })[0].score;

    const badAirRisk = rankPredictiveZones([
        { id: 'entry', label: '출입구', type: 'entry', distance: 1.0, recentVisitMinutes: 60, lastPm25: 32 },
    ], { hour: 15, currentPm25: 30, outdoorPm25: 85 })[0].score;

    assert.ok(badAirRisk > cleanAirRisk);
});

runTest('bathroom has morning and night time risk', () => {
    assert.ok(getTimeRiskForZone('bathroom', 8) > 0);
    assert.ok(getTimeRiskForZone('bathroom', 22) > 0);
    assert.strictEqual(getTimeRiskForZone('bathroom', 14), 0);
});


runTest('adaptive threshold stays default when outdoor data is missing or clean', () => {
    assert.strictEqual(calculateAdaptiveThreshold(null), 100);
    assert.strictEqual(calculateAdaptiveThreshold(undefined), 100);
    assert.strictEqual(calculateAdaptiveThreshold(20), 100);
    assert.strictEqual(calculateAdaptiveThreshold(35), 100);
});

runTest('adaptive threshold lowers when outdoor air is bad', () => {
    assert.strictEqual(calculateAdaptiveThreshold(36), 85);
    assert.strictEqual(calculateAdaptiveThreshold(62), 85);
    assert.strictEqual(calculateAdaptiveThreshold(75), 85);
});

runTest('adaptive threshold lowers further when outdoor air is very bad', () => {
    assert.strictEqual(calculateAdaptiveThreshold(76), 70);
    assert.strictEqual(calculateAdaptiveThreshold(120), 70);
});
