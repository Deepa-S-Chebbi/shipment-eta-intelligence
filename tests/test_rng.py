"""Unit tests for SeedSequence RNG manager and stream independence."""

import numpy as np
import pytest
from eta_data.rng import RNGManager


def test_rng_reproducibility():
    """Identical seed must produce identical sequences across all streams."""
    rng1 = RNGManager(master_seed=20261022)
    rng2 = RNGManager(master_seed=20261022)

    val1 = rng1.get_stream("master_facilities").random(10)
    val2 = rng2.get_stream("master_facilities").random(10)

    np.testing.assert_array_equal(val1, val2)


def test_stream_independence():
    """Drawing from stream A must not alter stream B."""
    rng1 = RNGManager(master_seed=20261022)
    rng2 = RNGManager(master_seed=20261022)

    # In rng1, draw 1000 numbers from master_carriers
    rng1.get_stream("master_carriers").random(1000)

    # In both, draw from master_facilities
    fac1 = rng1.get_stream("master_facilities").random(10)
    fac2 = rng2.get_stream("master_facilities").random(10)

    np.testing.assert_array_equal(fac1, fac2)


def test_entity_spawning():
    """Per-entity child generator spawning is deterministic."""
    rng1 = RNGManager(master_seed=20261022)
    rng2 = RNGManager(master_seed=20261022)

    child1 = rng1.spawn_entity_generator("shipment_generation", 42)
    child2 = rng2.spawn_entity_generator("shipment_generation", 42)

    np.testing.assert_array_equal(child1.random(5), child2.random(5))
