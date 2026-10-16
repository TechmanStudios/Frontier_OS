"""
Frontier_OS: Metacognitive Reasoning Graph & Query Decomposition
File: Frontier_OS/core/metacognition/reasoning_graph.py

Decomposes complex multi-step symbolic reasoning tasks into a Directed Acyclic Graph (DAG)
of continuous Riemannian semantic circuits. Coordinates signal piping, input/output
pin binding, and execution order across arithmetic, logic, and arbiter stages.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np

from sol.kernel.synthesis.circuit_synthesizer import (
    TruthTableSpec,
    CANONICAL_SPECS,
    build_canonical_specs
)


class CognitiveStageType(str, Enum):
    """Types of cognitive reasoning operations executed on Riemannian manifolds."""
    ARITHMETIC_ADD = "ARITHMETIC_ADD"         # Multi-bit ripple carry addition
    ARITHMETIC_SUB = "ARITHMETIC_SUB"         # Subtraction with borrow logic
    DECISION_ARBITER = "DECISION_ARBITER"     # Majority voting or priority multiplexing
    PARITY_VERIFICATION = "PARITY_VERIFICATION" # Parity checking & integrity verification
    EQUALITY_COMPARATOR = "EQUALITY_COMPARATOR" # Identity and equivalence testing
    DNF_CUSTOM = "DNF_CUSTOM"                 # Open-ended DNF propositional logic synthesis


@dataclass
class CognitiveStage:
    """
    An individual processing stage in the hierarchical cognitive reasoning plan.
    Corresponds to a discrete Riemannian semantic circuit.
    """
    stage_id: str
    stage_type: CognitiveStageType
    spec_name: str
    input_bindings: Dict[str, Union[float, Tuple[str, str]]] = field(default_factory=dict)
    output_names: List[str] = field(default_factory=list)
    custom_spec: Optional[TruthTableSpec] = None
    target_accuracy: float = 1.0
    min_delta_ei: float = 0.10
    description: str = ""

    def get_dependencies(self) -> Set[str]:
        """Returns the set of upstream stage IDs this stage depends on."""
        deps = set()
        for binding in self.input_bindings.values():
            if isinstance(binding, (tuple, list)) and len(binding) == 2:
                upstream_stage_id, _ = binding
                deps.add(upstream_stage_id)
        return deps

    def to_dict(self) -> Dict[str, Any]:
        """Serializes stage definition for telemetry and API consumption."""
        bindings_serialized = {}
        for k, v in self.input_bindings.items():
            if isinstance(v, (tuple, list)):
                bindings_serialized[k] = list(v)
            elif isinstance(v, str):
                bindings_serialized[k] = v
            else:
                bindings_serialized[k] = float(v)

        return {
            "stage_id": self.stage_id,
            "stage_type": self.stage_type.value,
            "spec_name": self.spec_name,
            "input_bindings": bindings_serialized,
            "output_names": self.output_names,
            "target_accuracy": self.target_accuracy,
            "min_delta_ei": self.min_delta_ei,
            "description": self.description
        }


@dataclass
class CognitiveReasoningPlan:
    """
    Complete hierarchical reasoning DAG specifying stages, inter-stage signal flow,
    and global inputs and outputs.
    """
    plan_id: str
    query_description: str
    stages: Dict[str, CognitiveStage] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    global_inputs: List[str] = field(default_factory=list)
    global_outputs: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # out_name -> (stage_id, pin)

    def add_stage(self, stage: CognitiveStage) -> None:
        """Adds a cognitive stage to the plan."""
        self.stages[stage.stage_id] = stage
        self.execution_order = self.compute_topological_order()

    def compute_topological_order(self) -> List[str]:
        """Computes valid topological execution order, detecting cycles."""
        adj: Dict[str, List[str]] = {sid: [] for sid in self.stages}
        in_degree: Dict[str, int] = {sid: 0 for sid in self.stages}

        for sid, stage in self.stages.items():
            for dep in stage.get_dependencies():
                if dep in adj:
                    adj[dep].append(sid)
                    in_degree[sid] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.stages):
            unresolved = [sid for sid, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Cycle detected in reasoning graph stages: {unresolved}")

        return order

    def validate(self) -> bool:
        """Verifies graph consistency, ensuring all bindings and pins are resolvable."""
        self.execution_order = self.compute_topological_order()

        known_stages = set(self.stages.keys())
        for sid, stage in self.stages.items():
            for pin, binding in stage.input_bindings.items():
                if isinstance(binding, (tuple, list)) and len(binding) == 2:
                    up_stage, up_pin = binding
                    if up_stage not in known_stages:
                        raise KeyError(f"Stage '{sid}' references non-existent upstream stage '{up_stage}'")
                    up_outputs = self.stages[up_stage].output_names
                    if up_outputs and up_pin not in up_outputs:
                        raise KeyError(f"Stage '{sid}' references pin '{up_pin}' not in upstream '{up_stage}' outputs ({up_outputs})")

        for out_name, (stage_id, pin) in self.global_outputs.items():
            if stage_id not in known_stages:
                raise KeyError(f"Global output '{out_name}' references non-existent stage '{stage_id}'")
            up_outputs = self.stages[stage_id].output_names
            if up_outputs and pin not in up_outputs:
                raise KeyError(f"Global output '{out_name}' references non-existent pin '{pin}' in stage '{stage_id}'")

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the entire plan for telemetry and API responses."""
        return {
            "plan_id": self.plan_id,
            "query_description": self.query_description,
            "execution_order": self.execution_order,
            "global_inputs": self.global_inputs,
            "global_outputs": {k: list(v) for k, v in self.global_outputs.items()},
            "num_stages": len(self.stages),
            "stages": {sid: s.to_dict() for sid, s in self.stages.items()}
        }


# ==============================================================================
# Plan Factory Functions for Canonical Multi-Step Tasks
# ==============================================================================

def create_ripple_carry_adder_plan(bits: int = 2, with_parity: bool = True) -> CognitiveReasoningPlan:
    """
    Creates a hierarchical multi-step arithmetic reasoning plan:
    2-bit ripple carry adder (A1 A0 + B1 B0 -> COUT S1 S0) with optional parity check.
    """
    plan = CognitiveReasoningPlan(
        plan_id=f"plan_ripple_carry_{bits}bit",
        query_description=f"{bits}-Bit Riemannian Ripple-Carry Adder with Parity Integrity Verification"
    )

    # Global inputs: A0, B0, A1, B1
    plan.global_inputs = ["A0", "B0", "A1", "B1"]

    # Stage 0: Half Adder for bit 0 (inputs: A0, B0)
    stage0 = CognitiveStage(
        stage_id="stage_bit0",
        stage_type=CognitiveStageType.ARITHMETIC_ADD,
        spec_name="HALF_ADDER",
        input_bindings={"A": "A0", "B": "B0"},
        output_names=["SUM", "CARRY"],
        description="Low bit half adder (A0 + B0 -> S0, C0)"
    )
    plan.add_stage(stage0)

    # Stage 1: Full Adder for bit 1 (inputs: A1, B1, CIN from stage_bit0:CARRY)
    stage1 = CognitiveStage(
        stage_id="stage_bit1",
        stage_type=CognitiveStageType.ARITHMETIC_ADD,
        spec_name="FULL_ADDER",
        input_bindings={
            "A": "A1",
            "B": "B1",
            "CIN": ("stage_bit0", "CARRY")
        },
        output_names=["SUM", "COUT"],
        description="High bit full adder (A1 + B1 + C0 -> S1, COUT)"
    )
    plan.add_stage(stage1)

    # Stage 2: Parity verification over (S0, S1, COUT)
    if with_parity:
        stage_parity = CognitiveStage(
            stage_id="stage_parity",
            stage_type=CognitiveStageType.PARITY_VERIFICATION,
            spec_name="PARITY_3",
            input_bindings={
                "A": ("stage_bit0", "SUM"),
                "B": ("stage_bit1", "SUM"),
                "C": ("stage_bit1", "COUT")
            },
            output_names=["Y"],
            description="3-way Parity verification of arithmetic result bits"
        )
        plan.add_stage(stage_parity)
        plan.global_outputs["PARITY"] = ("stage_parity", "Y")

    plan.global_outputs["S0"] = ("stage_bit0", "SUM")
    plan.global_outputs["S1"] = ("stage_bit1", "SUM")
    plan.global_outputs["COUT"] = ("stage_bit1", "COUT")

    plan.validate()
    return plan


def create_hierarchical_arbiter_plan() -> CognitiveReasoningPlan:
    """
    Creates a 2-stage hierarchical decision arbiter plan:
    Stage 1: 3-agent majority consensus (V1, V2, V3 -> VoteMaj).
    Stage 2: Priority multiplexer (OverrideFlag selects between VoteMaj and PriorityVote).
    """
    plan = CognitiveReasoningPlan(
        plan_id="plan_hierarchical_arbiter",
        query_description="Hierarchical Decision Arbiter: Swarm Majority Consensus with Priority Override"
    )
    plan.global_inputs = ["V1", "V2", "V3", "OVERRIDE", "PRIORITY_VOTE"]

    # Stage 1: Majority 3
    stage_maj = CognitiveStage(
        stage_id="stage_majority",
        stage_type=CognitiveStageType.DECISION_ARBITER,
        spec_name="MAJORITY_3",
        input_bindings={"A": "V1", "B": "V2", "C": "V3"},
        output_names=["Y"],
        description="3-agent majority voting consensus"
    )
    plan.add_stage(stage_maj)

    # Stage 2: 2-to-1 Multiplexer (S=OVERRIDE, I0=VoteMaj, I1=PRIORITY_VOTE)
    stage_mux = CognitiveStage(
        stage_id="stage_mux",
        stage_type=CognitiveStageType.DECISION_ARBITER,
        spec_name="MUX_2to1",
        input_bindings={
            "S": "OVERRIDE",
            "I0": ("stage_majority", "Y"),
            "I1": "PRIORITY_VOTE"
        },
        output_names=["Y"],
        description="Executive multiplexer overriding consensus when OVERRIDE=1"
    )
    plan.add_stage(stage_mux)

    plan.global_outputs["MAJORITY_RAW"] = ("stage_majority", "Y")
    plan.global_outputs["FINAL_DECISION"] = ("stage_mux", "Y")

    plan.validate()
    return plan


def create_counterfactual_equality_plan() -> CognitiveReasoningPlan:
    """
    Creates a counterfactual equality reasoning plan:
    Stage 1: Test 2-bit equality between Concept A (A1, A0) and Concept B (B1, B0).
    Stage 2: If unequal, compute difference via Half-Subtractor (A0 - B0).
    Stage 3: Multiplex difference depending on equality flag.
    """
    plan = CognitiveReasoningPlan(
        plan_id="plan_counterfactual_equality",
        query_description="Counterfactual Concept Equality and Difference Inference"
    )
    plan.global_inputs = ["A1", "A0", "B1", "B0"]

    # Stage 1: 2-bit equality
    stage_eq = CognitiveStage(
        stage_id="stage_equals",
        stage_type=CognitiveStageType.EQUALITY_COMPARATOR,
        spec_name="EQUALS_2BIT",
        input_bindings={"A1": "A1", "A0": "A0", "B1": "B1", "B0": "B0"},
        output_names=["EQUAL"],
        description="2-bit concept equality evaluation"
    )
    plan.add_stage(stage_eq)

    # Stage 2: Half subtractor
    stage_sub = CognitiveStage(
        stage_id="stage_subtractor",
        stage_type=CognitiveStageType.ARITHMETIC_SUB,
        spec_name="HALF_SUBTRACTOR",
        input_bindings={"A": "A0", "B": "B0"},
        output_names=["DIFF", "BORROW"],
        description="Bitwise difference calculation"
    )
    plan.add_stage(stage_sub)

    # Stage 3: Multiplexer selects DIFF if NOT equal, or 0 if equal
    stage_mux = CognitiveStage(
        stage_id="stage_diff_select",
        stage_type=CognitiveStageType.DECISION_ARBITER,
        spec_name="MUX_2to1",
        input_bindings={
            "S": ("stage_equals", "EQUAL"),
            "I0": ("stage_subtractor", "DIFF"),
            "I1": 0.0  # If EQUAL=1, difference is 0
        },
        output_names=["Y"],
        description="Selects difference when concepts differ, collapses to 0 when equal"
    )
    plan.add_stage(stage_mux)

    plan.global_outputs["EQUAL"] = ("stage_equals", "EQUAL")
    plan.global_outputs["RESIDUAL_DIFF"] = ("stage_diff_select", "Y")

    plan.validate()
    return plan
