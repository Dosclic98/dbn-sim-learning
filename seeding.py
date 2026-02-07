"""Reproducibility helpers.

Centralizing seeding for experiment reproducibility.
"""

from __future__ import annotations

from typing import Any

DEFAULT_SEED: int = 98


def set_global_seed(seed: int = DEFAULT_SEED) -> None:
    """Seed common Python RNGs used by experiments."""

    try:
        import random

        random.seed(seed)
    except Exception:
        pass

    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass


def seed_pysmile_network(net: Any, seed: int = DEFAULT_SEED) -> None:
    """Seed PySMILE network RNG (used by sampling algorithms like EPIS)."""

    try:
        net.set_rand_seed(int(seed))
    except Exception:
        # Some contexts may not have PySMILE or the method may be unavailable.
        pass


def seed_pysmile_em(em: Any, seed: int = DEFAULT_SEED) -> None:
    """Seed PySMILE EM learner RNG."""

    try:
        em.set_seed(int(seed))
    except Exception:
        pass
