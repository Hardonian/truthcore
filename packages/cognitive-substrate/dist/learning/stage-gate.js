import { PatternType } from './pattern-detector.js';
export var Stage;
(function (Stage) {
    Stage["EARLY"] = "early";
    Stage["SCALING"] = "scaling";
    Stage["MATURE"] = "mature";
})(Stage || (Stage = {}));
export function detectStageGate(indicators, patterns, _policies, _decisions) {
    const scores = {
        [Stage.EARLY]: 0,
        [Stage.SCALING]: 0,
        [Stage.MATURE]: 0
    };
    const detectedIndicators = [];
    if (indicators.teamSize < 10) {
        scores[Stage.EARLY] += 3;
        detectedIndicators.push('Small team (<10 members)');
    }
    else if (indicators.teamSize < 50) {
        scores[Stage.SCALING] += 3;
        detectedIndicators.push('Growing team (10-50 members)');
    }
    else {
        scores[Stage.MATURE] += 3;
        detectedIndicators.push('Large team (>50 members)');
    }
    if (indicators.policyCount < 5) {
        scores[Stage.EARLY] += 2;
        detectedIndicators.push('Few policies (<5)');
    }
    else if (indicators.policyCount < 20) {
        scores[Stage.SCALING] += 2;
        detectedIndicators.push('Moderate policies (5-20)');
    }
    else {
        scores[Stage.MATURE] += 2;
        detectedIndicators.push('Extensive policies (>20)');
    }
    if (indicators.overrideRate > 0.3) {
        scores[Stage.EARLY] += 2;
        detectedIndicators.push('High override rate (>30%)');
    }
    else if (indicators.overrideRate > 0.1) {
        scores[Stage.SCALING] += 2;
        detectedIndicators.push('Moderate override rate (10-30%)');
    }
    else {
        scores[Stage.MATURE] += 2;
        detectedIndicators.push('Low override rate (<10%)');
    }
    if (indicators.deployFrequency > 5) {
        scores[Stage.EARLY] += 1;
        detectedIndicators.push('High deploy frequency (>5/week)');
    }
    else if (indicators.deployFrequency > 2) {
        scores[Stage.SCALING] += 1;
        detectedIndicators.push('Moderate deploy frequency (2-5/week)');
    }
    else {
        scores[Stage.MATURE] += 1;
        detectedIndicators.push('Gated deploys (<2/week)');
    }
    const velocityFocused = patterns.some((p) => p.patternType === PatternType.VELOCITY_FOCUSED);
    const riskAverse = patterns.some((p) => p.patternType === PatternType.RISK_AVERSE);
    if (velocityFocused) {
        scores[Stage.EARLY] += 1;
        detectedIndicators.push('Velocity-focused pattern detected');
    }
    if (riskAverse) {
        scores[Stage.MATURE] += 1;
        detectedIndicators.push('Risk-averse pattern detected');
    }
    const totalScore = scores[Stage.EARLY] + scores[Stage.SCALING] + scores[Stage.MATURE];
    const stageConfidence = {
        [Stage.EARLY]: scores[Stage.EARLY] / totalScore,
        [Stage.SCALING]: scores[Stage.SCALING] / totalScore,
        [Stage.MATURE]: scores[Stage.MATURE] / totalScore
    };
    const detectedStage = Object.entries(stageConfidence).reduce((max, curr) => curr[1] > max[1] ? curr : max)[0];
    return {
        stage: detectedStage,
        confidence: stageConfidence[detectedStage],
        indicators: Object.freeze(detectedIndicators),
        detectedAt: new Date().toISOString(),
        metadata: {
            scores,
            stage_confidence: stageConfidence,
            indicators: indicators
        }
    };
}
export var MismatchType;
(function (MismatchType) {
    MismatchType["OVER_ENGINEERED"] = "over_engineered";
    MismatchType["UNDER_GOVERNED"] = "under_governed";
    MismatchType["WRONG_FOCUS"] = "wrong_focus";
})(MismatchType || (MismatchType = {}));
export var MismatchSeverity;
(function (MismatchSeverity) {
    MismatchSeverity["LOW"] = "low";
    MismatchSeverity["MEDIUM"] = "medium";
    MismatchSeverity["HIGH"] = "high";
})(MismatchSeverity || (MismatchSeverity = {}));
export function detectToolingMismatch(stageGate, indicators) {
    const { stage } = stageGate;
    if (stage === Stage.EARLY && indicators.policyCount > 20) {
        return {
            mismatchType: MismatchType.OVER_ENGINEERED,
            currentStage: stage,
            currentTooling: `${indicators.policyCount} active policies, extensive governance`,
            severity: MismatchSeverity.MEDIUM,
            recommendation: 'Consider reducing policy count for faster iteration in early stage',
            detectedAt: new Date().toISOString(),
            metadata: {
                policy_count: indicators.policyCount,
                team_size: indicators.teamSize
            }
        };
    }
    if (stage === Stage.MATURE && indicators.policyCount < 10) {
        return {
            mismatchType: MismatchType.UNDER_GOVERNED,
            currentStage: stage,
            currentTooling: `Only ${indicators.policyCount} policies, minimal governance`,
            severity: MismatchSeverity.HIGH,
            recommendation: 'Mature teams typically benefit from more structured governance',
            detectedAt: new Date().toISOString(),
            metadata: {
                policy_count: indicators.policyCount,
                team_size: indicators.teamSize
            }
        };
    }
    if (stage === Stage.MATURE && indicators.deployFrequency > 10) {
        return {
            mismatchType: MismatchType.WRONG_FOCUS,
            currentStage: stage,
            currentTooling: `High deployment frequency (${indicators.deployFrequency}/week) without gating`,
            severity: MismatchSeverity.LOW,
            recommendation: 'Consider adding review gates for mature team stability',
            detectedAt: new Date().toISOString(),
            metadata: {
                deploy_frequency: indicators.deployFrequency,
                team_size: indicators.teamSize
            }
        };
    }
    return null;
}
//# sourceMappingURL=stage-gate.js.map