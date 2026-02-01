import { Belief, createBelief, currentConfidence, updateBelief, BeliefInput } from '../primitives/belief.js';
import { AssertionGraph } from './assertion-graph.js';

export enum CompositionStrategy {
  AVERAGE = 'average',
  MAX = 'max',
  MIN = 'min',
  WEIGHTED_AVERAGE = 'weighted_average',
  BAYESIAN = 'bayesian'
}

export interface BeliefCompositionInput {
  beliefs: Belief[];
  strategy: CompositionStrategy;
  weights?: number[];
}

export class BeliefEngine {
  private beliefs: Map<string, Belief> = new Map();
  private beliefsByAssertion: Map<string, Set<string>> = new Map();
  // Graph for future lineage-aware operations
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private _graph: AssertionGraph;

  constructor(graph: AssertionGraph) {
    this._graph = graph;
  }

  formBelief(input: BeliefInput): Belief {
    const belief = createBelief(input);
    this.beliefs.set(belief.beliefId, belief);

    if (!this.beliefsByAssertion.has(belief.assertionId)) {
      this.beliefsByAssertion.set(belief.assertionId, new Set());
    }
    this.beliefsByAssertion.get(belief.assertionId)!.add(belief.beliefId);

    return belief;
  }

  updateBeliefConfidence(beliefId: string, newConfidence: number, metadata?: Record<string, unknown>): Belief {
    const belief = this.beliefs.get(beliefId);
    if (belief === undefined) {
      throw new Error(`Belief ${beliefId} not found`);
    }

    const updated = updateBelief(belief, newConfidence, metadata);
    this.beliefs.set(beliefId, updated);

    return updated;
  }

  getBelief(beliefId: string): Belief | undefined {
    return this.beliefs.get(beliefId);
  }

  getBeliefsForAssertion(assertionId: string): Belief[] {
    const beliefIds = this.beliefsByAssertion.get(assertionId);
    if (beliefIds === undefined) {
      return [];
    }

    return Array.from(beliefIds)
      .map((id) => this.beliefs.get(id))
      .filter((b): b is Belief => b !== undefined);
  }

  composeBeliefsForAssertion(assertionId: string, strategy: CompositionStrategy = CompositionStrategy.WEIGHTED_AVERAGE): number {
    const beliefs = this.getBeliefsForAssertion(assertionId);

    if (beliefs.length === 0) {
      return 0.0;
    }

    return this.composeBeliefs({ beliefs, strategy });
  }

  composeBeliefs(input: BeliefCompositionInput): number {
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

  private bayesianUpdate(prior: number, likelihood: number): number {
    const evidence = prior * likelihood + (1 - prior) * (1 - likelihood);
    if (evidence === 0) {
      return 0;
    }
    return (prior * likelihood) / evidence;
  }

  propagateDecay(upstreamBeliefId: string, decayThreshold: number = 0.5): Belief[] {
    const upstreamBelief = this.beliefs.get(upstreamBeliefId);
    if (upstreamBelief === undefined) {
      return [];
    }

    const upstreamConfidence = currentConfidence(upstreamBelief);
    if (upstreamConfidence >= decayThreshold) {
      return [];
    }

    const updated: Belief[] = [];

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

  pruneExpired(now: Date = new Date()): number {
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

  getAllBeliefs(): Belief[] {
    return Array.from(this.beliefs.values());
  }

  stats(): { total: number; highConfidence: number; lowConfidence: number; averageConfidence: number } {
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
