"""
Deterministic random number generation using numpy.random.SeedSequence spawn hierarchy.
Decouples entity generation streams so adding or modifying logic in one entity
does not alter the random sequence of another entity.
"""

from __future__ import annotations

from typing import Dict
import numpy as np


STREAM_NAMES = (
    "master_facilities",
    "master_carriers",
    "master_routes",
    "master_service_levels",
    "disruptions_weather",
    "disruptions_facility",
    "shipment_generation",
    "shipment_legs",
    "simulation_transit",
    "facility_queues",
    "events_lifecycle",
    "events_ingestion_lag",
    "events_duplicates",
    "anomalies_injection",
    "eta_estimation",
    "reroute_decisions",
)


class RNGManager:
    """Manages independent, reproducibly spawned NumPy random Generators."""

    def __init__(self, master_seed: int = 20261022) -> None:
        self.master_seed = master_seed
        self._seed_sequence = np.random.SeedSequence(master_seed)
        child_sequences = self._seed_sequence.spawn(len(STREAM_NAMES))
        self._streams: Dict[str, np.random.Generator] = {
            name: np.random.default_rng(child_seq)
            for name, child_seq in zip(STREAM_NAMES, child_sequences)
        }

    def get_stream(self, name: str) -> np.random.Generator:
        """Retrieve the dedicated Generator for an entity stream."""
        if name not in self._streams:
            raise KeyError(
                f"Unknown RNG stream: '{name}'. Available streams: {list(self._streams.keys())}"
            )
        return self._streams[name]

    def spawn_entity_generator(self, parent_stream_name: str, entity_index: int) -> np.random.Generator:
        """
        Deterministically spawn a child generator for a specific entity (e.g. per-shipment RNG).
        Ensures entity-level operations are completely isolated.
        """
        parent = self.get_stream(parent_stream_name)
        # Use integer seed derived deterministically from parent stream state and entity_index
        seed_val = int(parent.integers(0, 2**31 - 1)) + entity_index
        child_seq = np.random.SeedSequence(seed_val)
        return np.random.default_rng(child_seq)
