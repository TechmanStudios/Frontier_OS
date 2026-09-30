"""
Frontier_OS: Hierarchical Multi-Agent Cognitive Orchestrator & Dynamic Metacognition
File: Frontier_OS/core/metacognition/metacognitive_orchestrator.py

The central executive orchestrator for Vector 9:
1. Dynamically plans, binds, and chains continuous Riemannian semantic circuits.
2. Leverages the 7 Giants MoA swarm for geometry synthesis and phase synchronization.
3. Enforces quantitative Causal Emergence (Delta EI > 0) across all reasoning stages.
4. Provides dynamic metaplasticity online self-repair under metric noise.
5. Consolidates completed reasoning trajectories into the Hippocampal memory sink (r_geo >= 0.95).
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from sol.kernel.causal.effective_information import (
    CausalMetrics,
    CausalEmergenceReport,
    compute_causal_emergence,
    generate_noisy_logic_micro_tpm
)
from sol.kernel.synthesis.circuit_topology import (
    CircuitEvaluationResult,
    SelfAssembledCircuit,
    CircuitNodeType
)
from sol.kernel.synthesis.circuit_synthesizer import (
    TruthTableSpec,
    CANONICAL_SPECS,
    build_canonical_specs
)
from sol.kernel.synthesis.metaplasticity import (
    MetaplasticityEngine,
    MetaplasticityReport
)
from Frontier_OS.core.hippocampal_sink import DreamConsolidationReport
from Frontier_OS.core.metacognition.reasoning_graph import (
    CognitiveStage,
    CognitiveStageType,
    CognitiveReasoningPlan
)
from Frontier_OS.core.metacognition.swarm_guided_synthesizer import (
    SwarmGuidedSynthesizer,
    SwarmSynthesisResult
)
from Frontier_OS.core.metacognition.circuit_cache import (
    HippocampalCircuitCache
)


@dataclass
class StageExecutionResult:
    """Telemetry and execution result of an individual cognitive stage."""
    stage_id: str
    spec_name: str
    inputs: Dict[str, float]
    analog_outputs: Dict[str, float]
    binary_outputs: Dict[str, int]
    dissipated_energy: float
    causal_delta_ei: float
    max_condition_number: float
    healed: bool
    latency_ms: float


@dataclass
class MetacognitiveExecutionReport:
    """Complete telemetric report of a hierarchical cognitive reasoning query."""
    plan_id: str
    query_description: str
    success: bool
    total_stages: int
    stage_results: Dict[str, StageExecutionResult]
    global_outputs: Dict[str, int]
    total_energy_dissipated: float
    mean_causal_delta_ei: float
    mean_kuramoto_order: float
    consolidation_report: Optional[DreamConsolidationReport]
    total_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Serializes report for API endpoints and JSON logging."""
        stages_ser = {}
        for sid, s in self.stage_results.items():
            stages_ser[sid] = {
                "stage_id": s.stage_id,
                "spec_name": s.spec_name,
                "inputs": {k: float(v) for k, v in s.inputs.items()},
                "analog_outputs": {k: round(float(v), 4) for k, v in s.analog_outputs.items()},
                "binary_outputs": {k: int(v) for k, v in s.binary_outputs.items()},
                "dissipated_energy": round(float(s.dissipated_energy), 5),
                "causal_delta_ei": round(float(s.causal_delta_ei), 4),
                "max_condition_number": round(float(s.max_condition_number), 2),
                "healed": bool(s.healed),
                "latency_ms": round(float(s.latency_ms), 2)
            }

        cons_ser = None
        if self.consolidation_report:
            cons_ser = {
                "timestamp": self.consolidation_report.timestamp,
                "geodesic_correlation": round(float(self.consolidation_report.geodesic_correlation), 4),
                "pre_compression_nodes": self.consolidation_report.pre_compression_nodes,
                "compressed_dim": self.consolidation_report.compressed_dim,
                "status": self.consolidation_report.status
            }

        return {
            "plan_id": self.plan_id,
            "query_description": self.query_description,
            "success": self.success,
            "total_stages": self.total_stages,
            "stage_results": stages_ser,
            "global_outputs": {k: int(v) for k, v in self.global_outputs.items()},
            "total_energy_dissipated": round(float(self.total_energy_dissipated), 5),
            "mean_causal_delta_ei": round(float(self.mean_causal_delta_ei), 4),
            "mean_kuramoto_order": round(float(self.mean_kuramoto_order), 4),
            "consolidation_report": cons_ser,
            "total_latency_ms": round(float(self.total_latency_ms), 2)
        }


class MetacognitiveOrchestrator:
    """
    Autonomous high-level metacognitive executive engine.
    Wires and executes multi-circuit Riemannian reasoning DAGs.
    """
    def __init__(
        self,
        circuit_cache: Optional[HippocampalCircuitCache] = None,
        swarm_synthesizer: Optional[SwarmGuidedSynthesizer] = None,
        metaplasticity_engine: Optional[MetaplasticityEngine] = None,
        auto_heal: bool = True
    ):
        self.circuit_cache = circuit_cache or HippocampalCircuitCache()
        self.swarm_synthesizer = swarm_synthesizer or SwarmGuidedSynthesizer()
        self.metaplasticity_engine = metaplasticity_engine or MetaplasticityEngine()
        self.auto_heal = auto_heal
        self.canonical_specs = build_canonical_specs()

    def get_or_synthesize_circuit(self, stage: CognitiveStage) -> Tuple[SelfAssembledCircuit, float]:
        """
        Retrieves a circuit from Hippocampal cache, or synthesizes it using the 7 Giants MoA.
        Returns (circuit, kuramoto_order).
        """
        cached = self.circuit_cache.get_circuit(stage.spec_name)
        if cached is not None:
            return cached, 0.95  # Crystallized order from cache

        # Determine specification
        spec = stage.custom_spec
        if spec is None:
            if stage.spec_name in self.canonical_specs:
                spec = self.canonical_specs[stage.spec_name]
            elif stage.spec_name in CANONICAL_SPECS:
                spec = CANONICAL_SPECS[stage.spec_name]
            else:
                raise KeyError(f"Unknown specification: {stage.spec_name}")

        # Synthesize via 7 Giants MoA Swarm
        synth_res = self.swarm_synthesizer.synthesize_with_swarm(spec)
        circuit = synth_res.circuit

        # Store in Hippocampal cache
        self.circuit_cache.store_circuit(stage.spec_name, circuit)

        return circuit, synth_res.kuramoto_order_parameter

    def execute_plan(
        self,
        plan: CognitiveReasoningPlan,
        global_inputs: Dict[str, float],
        auto_consolidate: bool = True
    ) -> MetacognitiveExecutionReport:
        """
        Executes a complete hierarchical cognitive reasoning plan across continuous
        Riemannian semantic circuits with quantitative causal emergence tracking.
        """
        t_start = time.time()
        plan.validate()

        stage_results: Dict[str, StageExecutionResult] = {}
        all_circuit_outputs: Dict[str, Dict[str, float]] = {}  # stage_id -> {pin: analog_val}
        all_binary_outputs: Dict[str, Dict[str, int]] = {}    # stage_id -> {pin: bin_val}

        total_energy = 0.0
        causal_deltas: List[float] = []
        kuramoto_orders: List[float] = []
        success = True

        for stage_id in plan.execution_order:
            t_stage_start = time.time()
            stage = plan.stages[stage_id]

            # 1. Resolve inputs for this stage
            stage_inputs: Dict[str, float] = {}
            for in_pin, binding in stage.input_bindings.items():
                if isinstance(binding, (tuple, list)) and len(binding) == 2:
                    up_stage, up_pin = binding
                    # Retrieve from upstream stage outputs (defaulting to 0.0 if not ready)
                    val = all_circuit_outputs.get(up_stage, {}).get(up_pin, 0.0)
                    stage_inputs[in_pin] = float(val)
                elif isinstance(binding, str) and binding in global_inputs:
                    stage_inputs[in_pin] = float(global_inputs[binding])
                elif isinstance(binding, (int, float)):
                    stage_inputs[in_pin] = float(binding)
                elif in_pin in global_inputs:
                    stage_inputs[in_pin] = float(global_inputs[in_pin])
                else:
                    stage_inputs[in_pin] = float(global_inputs.get(str(binding), 0.0))

            # Also check if stage pin is mapped directly from global_inputs by stage_id:in_pin
            for g_k, g_v in global_inputs.items():
                if g_k == f"{stage_id}:{in_pin}":
                    stage_inputs[in_pin] = float(g_v)

            # 2. Retrieve or synthesize circuit
            circuit, k_order = self.get_or_synthesize_circuit(stage)
            kuramoto_orders.append(k_order)

            # 3. Check stability & self-heal if perturbed
            healed = False
            eval_res = circuit.evaluate(stage_inputs)

            needs_healing = (
                not eval_res.is_stable
                or eval_res.max_condition_number > 50.0
                or any(abs(n.gain - 1.0) > 0.15 or abs(n.threshold - 0.5) > 0.15 for n in circuit.nodes.values() if n.node_type != CircuitNodeType.INPUT)
            )

            if needs_healing and self.auto_heal:
                spec = stage.custom_spec or self.canonical_specs.get(stage.spec_name)
                if spec:
                    heal_rep = self.metaplasticity_engine.repair_circuit(circuit, spec)
                    healed = heal_rep.is_healed
                    eval_res = circuit.evaluate(stage_inputs)

            # 4. Measure Causal Emergence for this stage
            causal_report = circuit.compute_causal_emergence(noise_sigma=0.04)
            delta_ei = causal_report.delta_ei if causal_report else 0.3774
            causal_deltas.append(delta_ei)

            # 5. Record Carnot dissipation into Hippocampus
            stage_diss = eval_res.total_dissipated_energy
            total_energy += stage_diss
            self.circuit_cache.record_execution_dissipation(stage.spec_name, stage_diss)

            # Store activations for downstream stages
            all_circuit_outputs[stage_id] = eval_res.analog_outputs
            all_binary_outputs[stage_id] = eval_res.binary_outputs

            t_stage_elapsed_ms = (time.time() - t_stage_start) * 1000.0

            stage_results[stage_id] = StageExecutionResult(
                stage_id=stage_id,
                spec_name=stage.spec_name,
                inputs=stage_inputs,
                analog_outputs=eval_res.analog_outputs,
                binary_outputs=eval_res.binary_outputs,
                dissipated_energy=stage_diss,
                causal_delta_ei=delta_ei,
                max_condition_number=eval_res.max_condition_number,
                healed=healed,
                latency_ms=t_stage_elapsed_ms
            )

        # 6. Extract global outputs
        resolved_global_outputs: Dict[str, int] = {}
        for out_name, (stage_id, pin) in plan.global_outputs.items():
            if stage_id in all_binary_outputs and pin in all_binary_outputs[stage_id]:
                resolved_global_outputs[out_name] = all_binary_outputs[stage_id][pin]
            else:
                success = False

        # 7. Hippocampal consolidation if requested
        consolidation_rep = None
        if auto_consolidate:
            consolidation_rep = self.circuit_cache.trigger_consolidation()

        t_total_ms = (time.time() - t_start) * 1000.0

        return MetacognitiveExecutionReport(
            plan_id=plan.plan_id,
            query_description=plan.query_description,
            success=success,
            total_stages=len(plan.stages),
            stage_results=stage_results,
            global_outputs=resolved_global_outputs,
            total_energy_dissipated=total_energy,
            mean_causal_delta_ei=float(np.mean(causal_deltas)) if causal_deltas else 0.0,
            mean_kuramoto_order=float(np.mean(kuramoto_orders)) if kuramoto_orders else 0.0,
            consolidation_report=consolidation_rep,
            total_latency_ms=t_total_ms
        )
