export class AssertionGraph {
    assertions = new Map();
    evidence = new Map();
    edges = new Map();
    addAssertion(assertion) {
        this.assertions.set(assertion.assertionId, assertion);
        for (const evidenceId of assertion.evidenceIds) {
            if (!this.edges.has(assertion.assertionId)) {
                this.edges.set(assertion.assertionId, new Set());
            }
            this.edges.get(assertion.assertionId).add(evidenceId);
        }
    }
    addEvidence(evidence) {
        this.evidence.set(evidence.evidenceId, evidence);
    }
    getAssertion(assertionId) {
        return this.assertions.get(assertionId);
    }
    getEvidence(evidenceId) {
        return this.evidence.get(evidenceId);
    }
    getLineage(assertionId) {
        const rootAssertion = this.assertions.get(assertionId);
        if (rootAssertion === undefined) {
            return null;
        }
        const upstreamAssertions = [];
        const evidenceChain = [];
        const transformations = [];
        const visited = new Set();
        const queue = [assertionId];
        while (queue.length > 0) {
            const currentId = queue.shift();
            if (visited.has(currentId)) {
                continue;
            }
            visited.add(currentId);
            const assertion = this.assertions.get(currentId);
            if (assertion !== undefined && assertion.assertionId !== assertionId) {
                upstreamAssertions.push(assertion);
                if (assertion.transformation !== null) {
                    transformations.push(assertion.transformation);
                }
            }
            const evidenceIds = this.edges.get(currentId);
            if (evidenceIds !== undefined) {
                for (const evidenceId of evidenceIds) {
                    const evidence = this.evidence.get(evidenceId);
                    if (evidence !== undefined) {
                        evidenceChain.push(evidence);
                    }
                }
            }
        }
        return {
            rootAssertion,
            upstreamAssertions,
            evidenceChain,
            transformations
        };
    }
    getAllAssertions() {
        return Array.from(this.assertions.values());
    }
    getAllEvidence() {
        return Array.from(this.evidence.values());
    }
    size() {
        return {
            assertions: this.assertions.size,
            evidence: this.evidence.size
        };
    }
    clear() {
        this.assertions.clear();
        this.evidence.clear();
        this.edges.clear();
    }
    toDict() {
        return {
            assertions: Array.from(this.assertions.values()),
            evidence: Array.from(this.evidence.values()),
            edges: Array.from(this.edges.entries()).map(([id, deps]) => ({
                id,
                dependencies: Array.from(deps)
            }))
        };
    }
}
//# sourceMappingURL=assertion-graph.js.map