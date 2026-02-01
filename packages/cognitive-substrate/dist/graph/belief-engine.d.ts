import { Belief, BeliefInput } from '../primitives/belief.js';
import { AssertionGraph } from './assertion-graph.js';
export declare enum CompositionStrategy {
    AVERAGE = "average",
    MAX = "max",
    MIN = "min",
    WEIGHTED_AVERAGE = "weighted_average",
    BAYESIAN = "bayesian"
}
export interface BeliefCompositionInput {
    beliefs: Belief[];
    strategy: CompositionStrategy;
    weights?: number[];
}
export declare class BeliefEngine {
    private beliefs;
    private beliefsByAssertion;
    private _graph;
    constructor(graph: AssertionGraph);
    formBelief(input: BeliefInput): Belief;
    updateBeliefConfidence(beliefId: string, newConfidence: number, metadata?: Record<string, unknown>): Belief;
    getBelief(beliefId: string): Belief | undefined;
    getBeliefsForAssertion(assertionId: string): Belief[];
    composeBeliefsForAssertion(assertionId: string, strategy?: CompositionStrategy): number;
    composeBeliefs(input: BeliefCompositionInput): number;
    private bayesianUpdate;
    propagateDecay(upstreamBeliefId: string, decayThreshold?: number): Belief[];
    pruneExpired(now?: Date): number;
    getAllBeliefs(): Belief[];
    stats(): {
        total: number;
        highConfidence: number;
        lowConfidence: number;
        averageConfidence: number;
    };
}
//# sourceMappingURL=belief-engine.d.ts.map