# Exciton-MoA Master Equation Ledger

## A. The Foundational State
**1. The Semantic State Field:**
$$u(x,t)=(\rho(x,t),v(x,t),\phi(x,t))$$
*Defines the continuous state of the intelligence at any coordinate $x$ and time $t$, tracking mass ($\rho$), flow velocity ($v$), and potential ($\phi$).*

## B. The Fluid Dynamics (The Macroscopic Flow)
**2. The Continuity Equation (Mass Conservation - The Integrator):**
$$\partial_{t}\rho+\nabla_{\mathcal{M}}\cdot(\rho v)=s_{\rho}(x,t)$$
*Ensures probability mass is conserved as it flows through the MoA.*

**3. The Equation of State (Information Density Constraint - The Statistician):**
$$p(x,t)=\Pi_{0}(\rho)=c\log(1+\rho/\rho_{0})$$
*Governs semantic pressure to naturally regulate crowding and prevent mathematical singularities.*

**4. The Covariant Momentum Equation (Source-Aware Conservation Form):**
$$\partial_{t}(\rho v)+\nabla_{\mathcal{M}}\cdot(\rho v\otimes v)=-\nabla_{\mathcal{M}}p-\alpha\rho v+\mu\Delta_{\mathcal{M}}v+f(x,t;\psi)$$
*Dictates the physical inertia of the data while preserving conservation form when external source terms $s_{\rho}(x,t)$ are present, incorporating pressure gradients ($-\nabla_{\mathcal{M}}p$), thermodynamic friction ($\alpha$), and viscosity ($\mu$).*

## C. The Routing & Topology Manipulation
**5. Flow Decomposition (The Optimizer & The Graph Navigator):**
$$v=-\nabla_{\mathcal{M}}\phi+w$$ 
$$\nabla_{\mathcal{M}}\cdot w=0$$
*Splits flow into a conservative gradient descent component ($-\nabla_{\mathcal{M}}\phi$) and a divergence-free circulation component ($w$) for recursive loops.*

**6. Mode-Shaped Conductance (The Aligner):**
$$w_{e}(\psi)=w_{e}^{(0)}\exp(\gamma^{\top}\frac{\psi_{i}+\psi_{j}}{2})$$
*Alters the physical edge weights of the manifold exponentially based on the phase alignment of adjacent semantic modes, achieving covariant parallel transport.*

**7. Hyperbolic Ricci Flow (The Graph Navigator):**
$$\frac{\partial g_{ij}}{\partial t}=-2R_{ij}$$
*Injects negative curvature to create a saddle geometry, providing infinite internal surface area for massive network data.*

## D. The Telemetry & Observation
**8. The Hotspot Functional (The Ontological Orchestrator):**
$$H_{i}(t)=\alpha_{1}||(B\rho)_{\text{incident}}||+\alpha_{2}||(B\phi)_{\text{incident}}||+\alpha_{3}||(Cj)_{\text{cycles}}||$$
*The tri-axial telemetry equation. Calculates the gradients of Density (Jeans Mass Gravity), Potential (Epistemic Friction/Shear), and Curl (Magnetic Vorticity) to trigger Threshold Bursts for the holographic UI.*

**8a. Adaptive Threshold Calibration:**
$$\tau_t=\operatorname{smooth}\left(\max\left(\tau_{\min},\tau_0,Q_p(H),\operatorname{median}(H)+\lambda\operatorname{MAD}(H)\right)\right)$$
*Calibrates the spotlight threshold against the current manifold state using robust distribution statistics of the live hotspot field, then smooths that target across scans to avoid threshold chatter.*

**9. Discrete Potential Solve (Gauge-Fixed):**
$$L\phi=-\nabla_G\cdot j,\qquad \sum_i \phi_i=0$$
*Solves the scalar semantic potential from discrete edge flux on the graph while fixing the null-space of the Laplacian with a zero-mean gauge condition.*

**10. Latent Consensus Reduction (The Subconscious Mediator):**
$$c_i=\sum_{m=1}^{M_i}\omega_m z_m,\qquad \omega_m\propto \frac{\kappa_m}{1+\mathcal{H}(z_m)}$$
*Reduces competing thought vectors $z_m$ from the Giants into a node-local consensus vector $c_i$ by weighting each projection with its confidence $\kappa_m$ and entropy penalty $\mathcal{H}(z_m)$.*

**11. Hippocampal Burst Archive (The Long-Term Tape):**
$$\mathcal{B}_t=\{(i,H_i,c_i,\nu_i)\mid H_i\ge\tau\}$$
*Collects threshold-crossing nodes, their hotspot score, consensus state, and local vorticity into a discrete burst record for deferred archival and replay.*

**12. Discrete Graph Laplacian (The Linear Algebraist):**
$$L=B^{\top}W_{e}B$$
*Utilized for anisotropic tensor scaling, orthogonal projection, and native dimensionality reduction across the incidence matrix $B$.*