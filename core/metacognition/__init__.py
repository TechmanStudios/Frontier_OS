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

from Frontier_OS.core.metacognition.reasoning_graph import (
    CognitiveStageType,
    CognitiveStage,
    CognitiveReasoningPlan,
    create_ripple_carry_adder_plan,
    create_hierarchical_arbiter_plan,
    create_counterfactual_equality_plan
)
from Frontier_OS.core.metacognition.swarm_guided_synthesizer import (
    SwarmGuidedSynthesizer,
    SwarmSynthesisResult
)
from Frontier_OS.core.metacognition.circuit_cache import (
    HippocampalCircuitCache,
    CachedCircuitEntry
)
from Frontier_OS.core.metacognition.metacognitive_orchestrator import (
    StageExecutionResult,
    MetacognitiveExecutionReport,
    MetacognitiveOrchestrator
)

__all__ = [
    "CognitiveStageType",
    "CognitiveStage",
    "CognitiveReasoningPlan",
    "create_ripple_carry_adder_plan",
    "create_hierarchical_arbiter_plan",
    "create_counterfactual_equality_plan",
    "SwarmGuidedSynthesizer",
    "SwarmSynthesisResult",
    "HippocampalCircuitCache",
    "CachedCircuitEntry",
    "StageExecutionResult",
    "MetacognitiveExecutionReport",
    "MetacognitiveOrchestrator"
]
