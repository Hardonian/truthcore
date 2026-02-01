import { createBelief, currentConfidence, updateBelief } from '../primitives/belief.js';
export var CompositionStrategy;
(function (CompositionStrategy) {
    CompositionStrategy["AVERAGE"] = "average";
    CompositionStrategy["MAX"] = "max";
    CompositionStrategy["MIN"] = "min";
    CompositionStrategy["WEIGHTED_AVERAGE"] = "weighted_average";
    CompositionStrategy["BAYESIAN"] = "bayesian";
})(CompositionStrategy || (CompositionStrategy = {}));
export class BeliefEngine {
    beliefs = new Map();
    beliefsByAssertion = new Map();
    // Graph for future lineage-aware operations
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _graph;
    constructor(graph) {
        this._graph = graph;
    }
    formBelief(input) {
        const belief = createBelief(input);
        this.beliefs.set(belief.beliefId, belief);
        if (!this.beliefsByAssertion.has(belief.assertionId)) {
            this.beliefsByAssertion.set(belief.assertionId, new Set());
        }
        this.beliefsByAssertion.get(belief.assertionId).add(belief.beliefId);
        return belief;
    }
    updateBeliefConfidence(beliefId, newConfidence, metadata) {
        const belief = this.beliefs.get(beliefId);
        if (belief === undefined) {
            throw new Error(`Belief ${beliefId} not found`);
        }
        const updated = updateBelief(belief, newConfidence, metadata);
        this.beliefs.set(beliefId, updated);
        return updated;
    }
    getBelief(beliefId) {
        return this.beliefs.get(beliefId);
    }
    getBeliefsForAssertion(assertionId) {
        const beliefIds = this.beliefsByAssertion.get(assertionId);
        if (beliefIds === undefined) {
            return [];
        }
        return Array.from(beliefIds)
            .map((id) => this.beliefs.get(id))
            .filter((b) => b !== undefined);
    }
    composeBeliefsForAssertion(assertionId, strategy = CompositionStrategy.WEIGHTED_AVERAGE) {
        const beliefs = this.getBeliefsForAssertion(assertionId);
        if (beliefs.length === 0) {
            return 0.0;
        }
        return this.composeBeliefs({ beliefs, strategy });
    }
    composeBeliefs(input) {
        const { beliefs, strategy, weights } = input;
        if (beliefs.length === 0) {
            return 0.0;
        }
        const confidences = beliefs.map((b) => currentConfidence(b));
        switch (strategy) {
            case CompositionStrategy.AVERAGE:
                return confidences.reduce((sum, c) => sum + c, 0) / confidences.length;
            case CompositionStrategy.MAX:
                return Math.max(...confidences);
            case CompositionStrategy.MIN:
                return Math.min(...confidences);
            case CompositionStrategy.WEIGHTED_AVERAGE: {
                const effectiveWeights = weights ?? beliefs.map((b) => 1.0 / (1.0 - b.confidence + 0.1));
                const totalWeight = effectiveWeights.reduce((sum, w) => sum + w, 0);
                if (totalWeight === 0) {
                    return 0.0;
                }
                return confidences.reduce((sum, c, i) => sum + c * effectiveWeights[i], 0) / totalWeight;
            }
            case CompositionStrategy.BAYESIAN: {
                let posterior = confidences[0];
                for (let i = 1; i < confidences.length; i++) {
                    posterior = this.bayesianUpdate(posterior, confidences[i]);
                }
                return posterior;
            }
            default:
                return confidences[0];
        }
    }
    bayesianUpdate(prior, likelihood) {
        const evidence = prior * likelihood + (1 - prior) * (1 - likelihood);
        if (evidence === 0) {
            return 0;
        }
        return (prior * likelihood) / evidence;
    }
    propagateDecay(upstreamBeliefId, decayThreshold = 0.5) {
        const upstreamBelief = this.beliefs.get(upstreamBeliefId);
        if (upstreamBelief === undefined) {
            return [];
        }
        const upstreamConfidence = currentConfidence(upstreamBelief);
        if (upstreamConfidence >= decayThreshold) {
            return [];
        }
        const updated = [];
        for (const belief of this.beliefs.values()) {
            if (belief.upstreamDependencies.includes(upstreamBeliefId)) {
                const decayFactor = upstreamConfidence / decayThreshold;
                const newConfidence = belief.confidence * decayFactor;
                const updatedBelief = updateBelief(belief, newConfidence, {
                    decay_source: upstreamBeliefId,
                    decay_factor: decayFactor
                });
                this.beliefs.set(updatedBelief.beliefId, updatedBelief);
                updated.push(updatedBelief);
            }
        }
        return updated;
    }
    pruneExpired(now = new Date()) {
        let pruned = 0;
        for (const [beliefId, belief] of this.beliefs.entries()) {
            const confidence = currentConfidence(belief, now);
            if (confidence === 0.0) {
                this.beliefs.delete(beliefId);
                const assertionBeliefs = this.beliefsByAssertion.get(belief.assertionId);
                if (assertionBeliefs !== undefined) {
                    assertionBeliefs.delete(beliefId);
                }
                pruned++;
            }
        }
        return pruned;
    }
    getAllBeliefs() {
        return Array.from(this.beliefs.values());
    }
    stats() {
        const beliefs = this.getAllBeliefs();
        const confidences = beliefs.map((b) => currentConfidence(b));
        return {
            total: beliefs.length,
            highConfidence: confidences.filter((c) => c >= 0.8).length,
            lowConfidence: confidences.filter((c) => c < 0.5).length,
            averageConfidence: confidences.reduce((sum, c) => sum + c, 0) / (beliefs.length || 1)
        };
    }
}
//# sourceMappingURL=belief-engine.js.map