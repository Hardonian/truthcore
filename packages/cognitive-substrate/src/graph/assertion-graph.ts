import { Assertion } from '../primitives/assertion.js';
import { Evidence } from '../primitives/evidence.js';

export interface AssertionLineage {
  rootAssertion: Assertion;
  upstreamAssertions: Assertion[];
  evidenceChain: Evidence[];
  transformations: string[];
}

export class AssertionGraph {
  private assertions: Map<string, Assertion> = new Map();
  private evidence: Map<string, Evidence> = new Map();
  private edges: Map<string, Set<string>> = new Map();

  addAssertion(assertion: Assertion): void {
    this.assertions.set(assertion.assertionId, assertion);

    for (const evidenceId of assertion.evidenceIds) {
      if (!this.edges.has(assertion.assertionId)) {
        this.edges.set(assertion.assertionId, new Set());
      }
      this.edges.get(assertion.assertionId)!.add(evidenceId);
    }
  }

  addEvidence(evidence: Evidence): void {
    this.evidence.set(evidence.evidenceId, evidence);
  }

  getAssertion(assertionId: string): Assertion | undefined {
    return this.assertions.get(assertionId);
  }

  getEvidence(evidenceId: string): Evidence | undefined {
    return this.evidence.get(evidenceId);
  }

  getLineage(assertionId: string): AssertionLineage | null {
    const rootAssertion = this.assertions.get(assertionId);
    if (rootAssertion === undefined) {
      return null;
    }

    const upstreamAssertions: Assertion[] = [];
    const evidenceChain: Evidence[] = [];
    const transformations: string[] = [];

    const visited = new Set<string>();
    const queue: string[] = [assertionId];

    while (queue.length > 0) {
      const currentId = queue.shift()!;
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

  getAllAssertions(): Assertion[] {
    return Array.from(this.assertions.values());
  }

  getAllEvidence(): Evidence[] {
    return Array.from(this.evidence.values());
  }

  size(): { assertions: number; evidence: number } {
    return {
      assertions: this.assertions.size,
      evidence: this.evidence.size
    };
  }

  clear(): void {
    this.assertions.clear();
    this.evidence.clear();
    this.edges.clear();
  }

  toDict(): Record<string, unknown> {
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
