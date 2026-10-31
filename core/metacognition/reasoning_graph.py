"""
Frontier_OS: Metacognitive Reasoning Graph & Query Decomposition
File: Frontier_OS/core/metacognition/reasoning_graph.py

Decomposes complex multi-step symbolic reasoning tasks into a Directed Acyclic Graph (DAG)
of continuous Riemannian semantic circuits. Coordinates signal piping, input/output
pin binding, and execution order across arithmetic, logic, and arbiter stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sol.kernel.synthesis.circuit_synthesizer import TruthTableSpec


class CognitiveStageType(StrEnum):
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
    input_bindings: dict[str, float | str | tuple[str, str]] = field(default_factory=dict)
    output_names: list[str] = field(default_factory=list)
    custom_spec: TruthTableSpec | None = None
    target_accuracy: float = 1.0
    min_delta_ei: float = 0.10
    description: str = ""

    def get_dependencies(self) -> set[str]:
        """Returns the set of upstream stage IDs this stage depends on."""
        deps = set()
        for binding in self.input_bindings.values():
            if isinstance(binding, (tuple, list)) and len(binding) == 2:
                upstream_stage_id, _ = binding
                deps.add(upstream_stage_id)
        return deps

    def to_dict(self) -> dict[str, Any]:
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
    stages: dict[str, CognitiveStage] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    global_inputs: list[str] = field(default_factory=list)
    global_outputs: dict[str, tuple[str, str]] = field(default_factory=dict)  # out_name -> (stage_id, pin)

    def add_stage(self, stage: CognitiveStage) -> None:
        """Adds a cognitive stage to the plan."""
        self.stages[stage.stage_id] = stage
        self.execution_order = self.compute_topological_order()

    def compute_topological_order(self) -> list[str]:
        """Computes valid topological execution order, detecting cycles."""
        adj: dict[str, list[str]] = {sid: [] for sid in self.stages}
        in_degree: dict[str, int] = {sid: 0 for sid in self.stages}

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
            for _pin, binding in stage.input_bindings.items():
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

    def to_dict(self) -> dict[str, Any]:
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


def create_4bit_wave_alu_plan() -> CognitiveReasoningPlan:
    """
    Creates a multi-stage 4-bit Wave-Routed ALU CognitiveReasoningPlan:
    Global Inputs (10 bits): A0..A3, B0..B3, OP0, OP1
      - (OP1=0, OP0=0): 4-bit Ripple-Carry ADD (A + B -> Y0..Y3, COUT, ZERO)
      - (OP1=0, OP0=1): 4-bit Two's-Complement SUB (A + ~B + 1 -> Y0..Y3, COUT, ZERO)
      - (OP1=1, OP0=0): 4-bit Bitwise Wave-AND (A & B -> Y0..Y3, COUT=0, ZERO)
      - (OP1=1, OP0=1): 4-bit Bitwise Wave-XOR (A ^ B -> Y0..Y3, COUT=0, ZERO)
    Global Outputs (6 bits): Y0, Y1, Y2, Y3, COUT, ZERO
    """
    plan = CognitiveReasoningPlan(
        plan_id="plan_4bit_wave_alu",
        query_description="4-Bit Multi-Stage Wave-Routed Arithmetic & Logic Unit (ADD/SUB/AND/XOR + Carry/Zero Flags)",
    )
    plan.global_inputs = ["A0", "A1", "A2", "A3", "B0", "B1", "B2", "B3", "OP0", "OP1"]

    and2_spec = TruthTableSpec(
        name="AND_2",
        inputs=["A", "B"],
        outputs=["Y"],
        table={(0, 0): (0,), (0, 1): (0,), (1, 0): (0,), (1, 1): (1,)},
        description="2-input Wave-AND Lens",
    )
    nor4_table: dict[tuple[int, ...], tuple[int, ...]] = {}
    for y0 in (0, 1):
        for y1 in (0, 1):
            for y2 in (0, 1):
                for y3 in (0, 1):
                    nor4_table[(y0, y1, y2, y3)] = (1 if (y0 | y1 | y2 | y3) == 0 else 0,)
    nor4_spec = TruthTableSpec(
        name="NOR_4",
        inputs=["Y0", "Y1", "Y2", "Y3"],
        outputs=["ZERO"],
        table=nor4_table,
        description="4-input Zero-Flag Destructive Quench Detector",
    )

    for i in range(4):
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_bxor_{i}",
                stage_type=CognitiveStageType.PARITY_VERIFICATION,
                spec_name="XOR",
                input_bindings={"A": f"B{i}", "B": "OP0"},
                output_names=["Y"],
                description=f"Bit {i} controlled B-inversion (B{i} ^ OP0) for ADD/SUB",
            )
        )
        cin_binding: str | tuple[str, str] = "OP0" if i == 0 else (f"stage_fa_{i - 1}", "COUT")
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_fa_{i}",
                stage_type=CognitiveStageType.ARITHMETIC_ADD,
                spec_name="FULL_ADDER",
                input_bindings={
                    "A": f"A{i}",
                    "B": (f"stage_bxor_{i}", "Y"),
                    "CIN": cin_binding,
                },
                output_names=["SUM", "COUT"],
                description=f"Bit {i} ripple-carry full adder",
            )
        )
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_and_{i}",
                stage_type=CognitiveStageType.DNF_CUSTOM,
                spec_name="AND_2",
                custom_spec=and2_spec,
                input_bindings={"A": f"A{i}", "B": f"B{i}"},
                output_names=["Y"],
                description=f"Bit {i} bitwise AND stage",
            )
        )
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_xor_{i}",
                stage_type=CognitiveStageType.PARITY_VERIFICATION,
                spec_name="XOR",
                input_bindings={"A": f"A{i}", "B": f"B{i}"},
                output_names=["Y"],
                description=f"Bit {i} bitwise XOR stage",
            )
        )
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_lmux_{i}",
                stage_type=CognitiveStageType.DECISION_ARBITER,
                spec_name="MUX_2to1",
                input_bindings={
                    "S": "OP0",
                    "I0": (f"stage_and_{i}", "Y"),
                    "I1": (f"stage_xor_{i}", "Y"),
                },
                output_names=["Y"],
                description=f"Bit {i} logic multiplexer (AND vs XOR)",
            )
        )
        plan.add_stage(
            CognitiveStage(
                stage_id=f"stage_omux_{i}",
                stage_type=CognitiveStageType.DECISION_ARBITER,
                spec_name="MUX_2to1",
                input_bindings={
                    "S": "OP1",
                    "I0": (f"stage_fa_{i}", "SUM"),
                    "I1": (f"stage_lmux_{i}", "Y"),
                },
                output_names=["Y"],
                description=f"Bit {i} output wave multiplexer (Arithmetic vs Logic)",
            )
        )
        plan.global_outputs[f"Y{i}"] = (f"stage_omux_{i}", "Y")

    plan.add_stage(
        CognitiveStage(
            stage_id="stage_cout_mux",
            stage_type=CognitiveStageType.DECISION_ARBITER,
            spec_name="MUX_2to1",
            input_bindings={
                "S": "OP1",
                "I0": ("stage_fa_3", "COUT"),
                "I1": 0.0,
            },
            output_names=["Y"],
            description="Carry-out gate (active in arithmetic modes OP1=0, suppressed in logic modes OP1=1)",
        )
    )
    plan.global_outputs["COUT"] = ("stage_cout_mux", "Y")

    plan.add_stage(
        CognitiveStage(
            stage_id="stage_zero_flag",
            stage_type=CognitiveStageType.DNF_CUSTOM,
            spec_name="NOR_4",
            custom_spec=nor4_spec,
            input_bindings={
                "Y0": ("stage_omux_0", "Y"),
                "Y1": ("stage_omux_1", "Y"),
                "Y2": ("stage_omux_2", "Y"),
                "Y3": ("stage_omux_3", "Y"),
            },
            output_names=["ZERO"],
            description="4-bit Zero flag wave detector ~(Y0 | Y1 | Y2 | Y3)",
        )
    )
    plan.global_outputs["ZERO"] = ("stage_zero_flag", "ZERO")

    plan.validate()
    return plan


def assemble_4bit_wave_alu_circuit() -> tuple[Any, TruthTableSpec]:
    """
    Assembles a unified 10-input, 6-output continuous Riemannian SelfAssembledCircuit
    and exhaustive 1,024-row TruthTableSpec for the 4-bit Wave-Routed ALU, ready for
    64-bit SIMD bit-sliced WideWordVirtualVM / OracleWideWordVM formal verification.
    """
    import itertools

    from sol.kernel.synthesis.circuit_topology import CircuitNodeType, SelfAssembledCircuit

    inputs = ["A0", "A1", "A2", "A3", "B0", "B1", "B2", "B3", "OP0", "OP1"]
    outputs = ["Y0", "Y1", "Y2", "Y3", "COUT", "ZERO"]

    table: dict[tuple[int, ...], tuple[int, ...]] = {}
    for row in itertools.product((0, 1), repeat=10):
        a0, a1, a2, a3, b0, b1, b2, b3, op0, op1 = row
        a_val = a0 | (a1 << 1) | (a2 << 2) | (a3 << 3)
        b_val = b0 | (b1 << 1) | (b2 << 2) | (b3 << 3)
        if op1 == 0 and op0 == 0:
            tot = a_val + b_val
            y_val = tot & 0xF
            cout = (tot >> 4) & 1
        elif op1 == 0 and op0 == 1:
            tot = a_val + ((~b_val) & 0xF) + 1
            y_val = tot & 0xF
            cout = (tot >> 4) & 1
        elif op1 == 1 and op0 == 0:
            y_val = a_val & b_val
            cout = 0
        else:
            y_val = a_val ^ b_val
            cout = 0
        y_bits = tuple((y_val >> bit) & 1 for bit in range(4))
        zero = 1 if y_val == 0 else 0
        table[row] = (*y_bits, cout, zero)

    spec = TruthTableSpec(
        name="WAVE_ALU_4BIT",
        inputs=inputs,
        outputs=outputs,
        table=table,
        description="10-input, 6-output 4-Bit Multi-Stage Wave ALU (1,024 rows: ADD, SUB, AND, XOR, COUT, ZERO)",
    )

    c = SelfAssembledCircuit(circuit_id="synth_WAVE_ALU_4BIT", name="Synthesized_WAVE_ALU_4BIT")
    for idx, in_id in enumerate(inputs):
        c.add_node(in_id, CircuitNodeType.INPUT, coords=[-4.0, -4.5 + float(idx)])

    c.add_node("inv_op0", CircuitNodeType.INVERTER, coords=[-2.5, 3.5])
    c.add_edge("OP0", "inv_op0")
    c.add_node("inv_op1", CircuitNodeType.INVERTER, coords=[-2.5, 4.5])
    c.add_edge("OP1", "inv_op1")

    y_internal_nodes: list[str] = []
    for i in range(4):
        y_pos = -3.0 + 2.0 * i
        cin_id = "OP0" if i == 0 else f"fa_cout_{i - 1}"

        c.add_node(f"bxor_{i}", CircuitNodeType.INTERFERENCE, coords=[-2.5, y_pos])
        c.add_edge(f"B{i}", f"bxor_{i}")
        c.add_edge("OP0", f"bxor_{i}")

        c.add_node(f"fa_xab_{i}", CircuitNodeType.INTERFERENCE, coords=[-1.2, y_pos + 0.3])
        c.add_edge(f"A{i}", f"fa_xab_{i}")
        c.add_edge(f"bxor_{i}", f"fa_xab_{i}")

        c.add_node(f"fa_sum_{i}", CircuitNodeType.INTERFERENCE, coords=[0.0, y_pos + 0.3])
        c.add_edge(f"fa_xab_{i}", f"fa_sum_{i}")
        c.add_edge(cin_id, f"fa_sum_{i}")

        c.add_node(f"fa_aab_{i}", CircuitNodeType.LENS_AND, coords=[-1.2, y_pos - 0.3])
        c.add_edge(f"A{i}", f"fa_aab_{i}")
        c.add_edge(f"bxor_{i}", f"fa_aab_{i}")

        c.add_node(f"fa_acin_{i}", CircuitNodeType.LENS_AND, coords=[0.0, y_pos - 0.3])
        c.add_edge(cin_id, f"fa_acin_{i}")
        c.add_edge(f"fa_xab_{i}", f"fa_acin_{i}")

        c.add_node(f"fa_cout_{i}", CircuitNodeType.LENS_OR, coords=[1.0, y_pos - 0.3])
        c.add_edge(f"fa_aab_{i}", f"fa_cout_{i}")
        c.add_edge(f"fa_acin_{i}", f"fa_cout_{i}")

        c.add_node(f"land_{i}", CircuitNodeType.LENS_AND, coords=[-1.2, y_pos + 0.7])
        c.add_edge(f"A{i}", f"land_{i}")
        c.add_edge(f"B{i}", f"land_{i}")

        c.add_node(f"lxor_{i}", CircuitNodeType.INTERFERENCE, coords=[-1.2, y_pos + 1.0])
        c.add_edge(f"A{i}", f"lxor_{i}")
        c.add_edge(f"B{i}", f"lxor_{i}")

        c.add_node(f"lmux0_{i}", CircuitNodeType.LENS_AND, coords=[0.0, y_pos + 0.7])
        c.add_edge("inv_op0", f"lmux0_{i}")
        c.add_edge(f"land_{i}", f"lmux0_{i}")

        c.add_node(f"lmux1_{i}", CircuitNodeType.LENS_AND, coords=[0.0, y_pos + 1.0])
        c.add_edge("OP0", f"lmux1_{i}")
        c.add_edge(f"lxor_{i}", f"lmux1_{i}")

        c.add_node(f"lmux_{i}", CircuitNodeType.LENS_OR, coords=[1.0, y_pos + 0.85])
        c.add_edge(f"lmux0_{i}", f"lmux_{i}")
        c.add_edge(f"lmux1_{i}", f"lmux_{i}")

        c.add_node(f"omux0_{i}", CircuitNodeType.LENS_AND, coords=[2.2, y_pos + 0.3])
        c.add_edge("inv_op1", f"omux0_{i}")
        c.add_edge(f"fa_sum_{i}", f"omux0_{i}")

        c.add_node(f"omux1_{i}", CircuitNodeType.LENS_AND, coords=[2.2, y_pos + 0.85])
        c.add_edge("OP1", f"omux1_{i}")
        c.add_edge(f"lmux_{i}", f"omux1_{i}")

        c.add_node(f"y_int_{i}", CircuitNodeType.LENS_OR, coords=[3.1, y_pos + 0.55])
        c.add_edge(f"omux0_{i}", f"y_int_{i}")
        c.add_edge(f"omux1_{i}", f"y_int_{i}")
        y_internal_nodes.append(f"y_int_{i}")

        c.add_node(f"Y{i}", CircuitNodeType.BASIN, coords=[4.0, y_pos + 0.55])
        c.add_edge(f"y_int_{i}", f"Y{i}")

    c.add_node("cout_gate", CircuitNodeType.LENS_AND, coords=[2.8, 3.8])
    c.add_edge("inv_op1", "cout_gate")
    c.add_edge("fa_cout_3", "cout_gate")
    c.add_node("COUT", CircuitNodeType.BASIN, coords=[4.0, 3.8])
    c.add_edge("cout_gate", "COUT")

    c.add_node("y_any_or", CircuitNodeType.LENS_OR, coords=[3.4, -4.2])
    for y_int in y_internal_nodes:
        c.add_edge(y_int, "y_any_or")
    c.add_node("zero_inv", CircuitNodeType.INVERTER, coords=[3.7, -4.2])
    c.add_edge("y_any_or", "zero_inv")
    c.add_node("ZERO", CircuitNodeType.BASIN, coords=[4.0, -4.2])
    c.add_edge("zero_inv", "ZERO")

    return c, spec
