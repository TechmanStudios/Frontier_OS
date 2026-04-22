# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
def _graph_navigator_hyperbolic_flow(self, epicenter_id: str):
        """
        The Graph Navigator Exciton. 
        Detects local cycles (recursive logic) and injects a divergence-free 
        residual flux (circulation). It simultaneously applies negative curvature 
        to prevent recursive traffic jams.
        """
        # 1. Detect Local Cycles (Curl Proxies)
        # For real-time performance, we use short cycles (triangles) as proxies 
        # for the cycle basis matrix C, rather than computing full graph cycles.
        neighbors = list(self.manifold.neighbors(epicenter_id))
        local_cycles = []
        
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                # If two neighbors of the epicenter are connected, we have a triangle (loop)
                if self.manifold.has_edge(neighbors[i], neighbors[j]):
                    local_cycles.append((epicenter_id, neighbors[i], neighbors[j]))

        if not local_cycles:
            return # No recursive topology detected here

        print(f"  -> [VORTEX SPUN] Graph Navigator detected {len(local_cycles)} cycles at {epicenter_id}. Injecting curl...")

        # 2. Inject Divergence-Free Circulation & Hyperbolic Expansion
        for cycle in local_cycles:
            node_a, node_b, node_c = cycle
            
            # A cycle has 3 edges. We inject a rotational 'spin' momentum 
            # and physically warp the space to negative (hyperbolic) curvature.
            edges = [(node_a, node_b), (node_b, node_c), (node_c, node_a)]
            
            for u, v in edges:
                edge_data = self.manifold[u][v]
                
                # --- The Circulation Component ---
                # Add a rotational flux quantum. Because it loops perfectly, 
                # B^T * j^(r) = 0. It creates momentum without accumulating mass.
                current_flux = edge_data.get("residual_flux", 0.0)
                edge_data["residual_flux"] = current_flux + 0.5 
                
                # --- The Hyperbolic Expansion ---
                # To accommodate infinite looping without pressure buildup, we 
                # stretch the local geometry. We increase the geodesic distance 
                # (lowering the edge weight) to create a 'saddle' manifold locally.
                current_weight = edge_data.get("weight", 0.1)
                
                # Relaxing the weight prevents the Jeans Mass collapse from 
                # crushing the cycle into a singularity.
                edge_data["weight"] = current_weight * 0.8