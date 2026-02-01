"""Replay and simulation system for truth-core.

Provides deterministic replay and counterfactual simulation capabilities.
"""

from truthcore.replay.bundle import BundleExporter, ReplayBundle
from truthcore.replay.diff import DeterministicDiff, DiffComputer, compute_content_hash
from truthcore.replay.replayer import ReplayEngine, ReplayReporter, ReplayResult
from truthcore.replay.simulator import (
    SimulationChanges,
    SimulationEngine,
    SimulationReporter,
    SimulationResult,
)

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
