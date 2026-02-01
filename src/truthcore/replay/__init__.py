"""Replay and simulation system for truth-core.

Provides deterministic replay and counterfactual simulation capabilities.
"""

from truthcore.replay.bundle import ReplayBundle, BundleExporter
from truthcore.replay.replayer import ReplayEngine, ReplayResult, ReplayReporter
from truthcore.replay.simulator import SimulationEngine, SimulationChanges, SimulationResult, SimulationReporter
from truthcore.replay.diff import DeterministicDiff, DiffComputer, compute_content_hash

__all__ = [
    "ReplayBundle",
    "BundleExporter",
    "ReplayEngine",
    "ReplayResult",
    "ReplayReporter",
    "SimulationEngine",
    "SimulationChanges",
    "SimulationResult",
    "SimulationReporter",
    "DeterministicDiff",
    "DiffComputer",
    "compute_content_hash",
]
