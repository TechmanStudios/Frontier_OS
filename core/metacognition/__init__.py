"""
Frontier_OS: Vector 9 Hierarchical Multi-Agent Cognitive Orchestration & Dynamic Metacognition
Package: Frontier_OS.core.metacognition

Exports:
- CognitiveStageType, CognitiveStage, CognitiveReasoningPlan
- create_ripple_carry_adder_plan, create_hierarchical_arbiter_plan, create_counterfactual_equality_plan
- SwarmGuidedSynthesizer, SwarmSynthesisResult
- HippocampalCircuitCache, CachedCircuitEntry
- MetacognitiveOrchestrator, StageExecutionResult, MetacognitiveExecutionReport
"""

from Frontier_OS.core.metacognition.circuit_cache import (
    CachedCircuitEntry,
    HippocampalCircuitCache,
)
from Frontier_OS.core.metacognition.metacognitive_orchestrator import (
    MetacognitiveExecutionReport,
    MetacognitiveOrchestrator,
    StageExecutionResult,
)
from Frontier_OS.core.metacognition.reasoning_graph import (
    CognitiveReasoningPlan,
    CognitiveStage,
    CognitiveStageType,
    assemble_4bit_wave_alu_circuit,
    create_4bit_wave_alu_plan,
    create_counterfactual_equality_plan,
    create_hierarchical_arbiter_plan,
    create_ripple_carry_adder_plan,
)
from Frontier_OS.core.metacognition.swarm_guided_synthesizer import (
    SwarmGuidedSynthesizer,
    SwarmSynthesisResult,
)

__all__ = [
    "CognitiveStageType",
    "CognitiveStage",
    "CognitiveReasoningPlan",
    "create_ripple_carry_adder_plan",
    "create_hierarchical_arbiter_plan",
    "create_counterfactual_equality_plan",
    "create_4bit_wave_alu_plan",
    "assemble_4bit_wave_alu_circuit",
    "SwarmGuidedSynthesizer",
    "SwarmSynthesisResult",
    "HippocampalCircuitCache",
    "CachedCircuitEntry",
    "StageExecutionResult",
    "MetacognitiveExecutionReport",
    "MetacognitiveOrchestrator"
]
