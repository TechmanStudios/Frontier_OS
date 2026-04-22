# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
def _linear_algebraist_tensor_scaling(self, epicenter_id: str):
        """
        The Linear Algebraist Exciton.
        Executes native dimensionality reduction (PCA) by calculating the local 
        covariance of state vectors and applying Anisotropic Metric Scaling. 
        It flattens redundant dimensions and carves a geodesic 'canyon' along 
        the principal eigenvector.
        """
        node_data = self.manifold.nodes[epicenter_id]
        neighbors = list(self.manifold.neighbors(epicenter_id))
        
        if len(neighbors) < 2:
            return # Need a minimum local neighborhood to compute variance
            
        # 1. Extract the Local Semantic Field (The Neighborhood Matrix)
        # We gather the state vectors of the epicenter and its neighbors to 
        # understand the shape of the local data flux.
        states = [node_data.get("state_vector", np.zeros(self.manifold_core.config.dimensionality))]
        for n in neighbors:
            states.append(self.manifold.nodes[n].get("state_vector", np.zeros(self.manifold_core.config.dimensionality)))
            
        states_matrix = np.array(states)
        
        # 2. Compute the Local Covariance and Eigen-Decomposition
        # We center the data and find the axes of maximum variance (Principal Components)
        centered_states = states_matrix - np.mean(states_matrix, axis=0)
        covariance_matrix = np.cov(centered_states, rowvar=False)
        
        # For a 3D config, this yields 3 eigenvalues and 3 eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
        
        # Sort by eigenvalue descending to find the primary axis of variance
        sorted_indices = np.argsort(eigenvalues)[::-1]
        principal_eigenvector = eigenvectors[:, sorted_indices[0]]
        
        print(f"  -> [CANYON CARVED] Linear Algebraist detected principal variance axis at {epicenter_id}.")

        # 3. Anisotropic Edge Scaling (Carving the Canyon)
        # We iterate through the local edges and align their geometry to the principal vector.
        epicenter_coords = np.array(node_data.get("coords"))
        
        for n in neighbors:
            neighbor_coords = np.array(self.manifold.nodes[n].get("coords"))
            
            # Calculate the physical directional vector of the edge in the manifold
            edge_vector = neighbor_coords - epicenter_coords
            edge_norm = np.linalg.norm(edge_vector)
            
            if edge_norm == 0:
                continue
                
            edge_direction = edge_vector / edge_norm
            
            # Calculate how closely this edge aligns with the principal eigenvector
            # (Absolute dot product: 1.0 means perfectly parallel, 0.0 means perfectly orthogonal)
            alignment = np.abs(np.dot(edge_direction, principal_eigenvector))
            
            # Fetch the current edge weight
            current_weight = self.manifold[epicenter_id][n].get("weight", 0.1)
            
            # The Physics: Anisotropic Deformation
            # If the edge aligns with the principal component, we INCREASE its weight 
            # (decreasing geodesic distance, making it a fast-flowing canyon floor).
            # If it is orthogonal (noise), we DECREASE its weight (steepening the canyon walls).
            
            # Map alignment [0, 1] to a scaling factor [0.5, 2.0]
            scaling_factor = 0.5 + (1.5 * alignment) 
            
            self.manifold[epicenter_id][n]["weight"] = current_weight * scaling_factor