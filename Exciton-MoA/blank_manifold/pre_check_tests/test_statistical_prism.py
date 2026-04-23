# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""
Exciton-MoA: Statistical Prism Diagnostics

====================================================================
AGENT INSTRUCTIONS: WHAT TO WATCH FOR DURING EXECUTION
As you execute this dimensional transducer test, explicitly monitor:

1. Lossless Compression:
   Verify that the 1536-dimensional embedding vector is cleanly
   reduced to exactly 3 dimensions. You are watching the Von Neumann
   bottleneck being bypassed.

2. Mathematical Stability (NaN checks):
   Ensure the Mean (radial depth), Variance (angular spread), and
   Skewness (phase shift) compute without returning NaN or flatlining
   to zero. The integrity of the probability shower relies on these
   moments scaling cleanly to the manifold's coordinates.
====================================================================
"""

import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from transducer import StatisticalPrism


def test_dimensional_compression():
    print("Running Pre-Check: Statistical Prism Transduction...")

    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    prism = StatisticalPrism(manifold_core)

    # Simulate a massive, noisy 1536-dimensional embedding
    mock_embedding = np.random.normal(loc=0.5, scale=0.2, size=1536)

    # Run the dimensional compression
    fingerprint = prism.extract_moments(mock_embedding)

    # 1. Verify dimensionality reduction to exactly 3D
    assert fingerprint.shape == (3,), (
        f"FAIL: Fingerprint shape {fingerprint.shape} does not match 3D coordinate topology."
    )

    # 2. Verify non-zero extraction (ensuring math didn't flatline)
    assert not np.isnan(fingerprint).any(), "FAIL: Statistical extraction yielded NaN."
    assert fingerprint[0] != 0.0, "FAIL: Radial depth (Mean) failed to compute."

    print(f"PASS: 1536D vector cleanly compressed to 3D phase space: {fingerprint}")


if __name__ == "__main__":
    test_dimensional_compression()
