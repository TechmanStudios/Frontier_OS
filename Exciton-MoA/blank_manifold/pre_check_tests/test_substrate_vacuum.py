# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""
Exciton-MoA: Substrate Vacuum Diagnostics

Verifies that the blank manifold boots with the requested number of nodes and a
fully traversable baseline topology so higher-level exciton operators have a
stable physical substrate to work against.
"""

import networkx as nx

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore


def test_substrate_vacuum():
    config = BlankManifoldConfig(base_node_count=1024, dimensionality=3)
    manifold_core = BlankManifoldCore(config)
    graph = manifold_core.generate_manifold()

    assert graph.number_of_nodes() == config.base_node_count
    assert nx.is_connected(graph), "FAIL: Blank manifold substrate is disconnected."
    assert graph.number_of_edges() > 0, "FAIL: Blank manifold has no baseline topology."


if __name__ == "__main__":
    test_substrate_vacuum()