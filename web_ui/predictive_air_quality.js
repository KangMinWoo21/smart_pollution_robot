(function(root) {
    const ZONE_BASE_RISK = {
        kitchen: 30,
        bathroom: 22,
        entry: 18,
        window: 16,
        corridor: 6,
        living: 10,
    };

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function getTimeRiskForZone(type, hour) {
        const h = Number(hour);
        if (type === 'kitchen' && ((h >= 6 && h <= 8) || (h >= 11 && h <= 13) || (h >= 17 && h <= 20))) {
            return 24;
        }
        if (type === 'bathroom' && ((h >= 7 && h <= 9) || (h >= 21 && h <= 23))) {
            return 14;
        }
        if ((type === 'entry' || type === 'window') && ((h >= 7 && h <= 9) || (h >= 17 && h <= 19))) {
            return 10;
        }
        return 0;
    }

    function getTimeReason(type, hour) {
        const h = Number(hour);
        if (type === 'kitchen' && ((h >= 6 && h <= 8) || (h >= 11 && h <= 13) || (h >= 17 && h <= 20))) {
            return '식사 준비 시간대';
        }
        if (type === 'bathroom' && ((h >= 7 && h <= 9) || (h >= 21 && h <= 23))) {
            return '사용 빈도 높은 시간대';
        }
        if ((type === 'entry' || type === 'window') && ((h >= 7 && h <= 9) || (h >= 17 && h <= 19))) {
            return '출입/환기 가능 시간대';
        }
        return '';
    }

    function classifyPriority(score) {
        if (score >= 78) return '우선 점검';
        if (score >= 52) return '주의 관찰';
        return '일반 순찰';
    }

    function calculateAdaptiveThreshold(outdoorPm25) {
        const value = Number(outdoorPm25);
        if (!Number.isFinite(value)) return 100;
        if (value > 75) return 70;
        if (value >= 36) return 85;
        return 100;
    }

    function rankPredictiveZones(zones, context) {
        const ctx = context || {};
        const hour = Number.isFinite(Number(ctx.hour)) ? Number(ctx.hour) : new Date().getHours();
        const currentPm25 = Number(ctx.currentPm25 || 0);
        const outdoorPm25 = Number(ctx.outdoorPm25 || 0);

        return zones.map(function(zone) {
            const baseRisk = ZONE_BASE_RISK[zone.type] || 8;
            const measuredPm = Number(zone.lastPm25 || currentPm25 || 0);
            const pollutionScore = clamp(measuredPm * 0.55, 0, 55);
            const timeRisk = getTimeRiskForZone(zone.type, hour);
            const outdoorRisk = (zone.type === 'entry' || zone.type === 'window') ? clamp((outdoorPm25 - 35) * 0.45, 0, 24) : 0;
            const distanceCost = clamp(Number(zone.distance || 0) * 6, 0, 24);
            const recentPenalty = Number(zone.recentVisitMinutes || 999) < 20 ? 14 : 0;
            const unexploredBonus = zone.lastPm25 == null ? 10 : 0;
            const score = Math.round(clamp(baseRisk + pollutionScore + timeRisk + outdoorRisk + unexploredBonus - distanceCost - recentPenalty, 0, 100));
            const reasons = [];

            if (measuredPm >= 75) reasons.push('실측 오염 높음');
            else if (measuredPm >= 36) reasons.push('실측 주의');
            if (baseRisk >= 18) reasons.push('오염 가능 구역');
            const timeReason = getTimeReason(zone.type, hour);
            if (timeReason) reasons.push(timeReason);
            if (outdoorRisk > 0) reasons.push('외부 미세먼지 영향');
            if (unexploredBonus > 0) reasons.push('미측정 구역');
            if (reasons.length === 0) reasons.push('정기 순찰');

            return Object.assign({}, zone, {
                score: score,
                priority: classifyPriority(score),
                reasons: reasons,
            });
        }).sort(function(a, b) {
            return b.score - a.score;
        });
    }

    const api = {
        rankPredictiveZones: rankPredictiveZones,
        getTimeRiskForZone: getTimeRiskForZone,
        classifyPriority: classifyPriority,
        calculateAdaptiveThreshold: calculateAdaptiveThreshold,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    root.PredictiveAirQuality = api;
})(typeof window !== 'undefined' ? window : globalThis);
