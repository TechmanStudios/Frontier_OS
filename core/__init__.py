"""
Frontier_OS Core Package
"""
from .telemetry_hook import (
    AgentDispatchThrottler,
    CurvatureTelemetryPacket,
    ManifoldTelemetryIPC
)
from .geodesic_navigator import (
    RiemannianGeodesicNavigator,
    ChristoffelCalculator,
    GeodesicStepResult
)
from .hippocampal_sink import (
    HippocampalMemorySink,
    DissipationPacket,
    DreamConsolidationReport
)
from .swarm_router import (
    AutonomousSwarmRouter,
    SwarmAgent,
    SwarmCluster,
    SwarmStepReport
)
from .seven_giants import (
    GiantRole,
    GiantProfile,
    GiantOperatorReadout,
    GIANT_PROFILES,
    SevenGiantsEnsemble,
    SevenGiantsMissionReport
)

__all__ = [
    "AgentDispatchThrottler",
    "CurvatureTelemetryPacket",
    "ManifoldTelemetryIPC",
    "RiemannianGeodesicNavigator",
    "ChristoffelCalculator",
    "GeodesicStepResult",
    "HippocampalMemorySink",
    "DissipationPacket",
    "DreamConsolidationReport",
    "AutonomousSwarmRouter",
    "SwarmAgent",
    "SwarmCluster",
    "SwarmStepReport",
    "GiantRole",
    "GiantProfile",
    "GiantOperatorReadout",
    "GIANT_PROFILES",
    "SevenGiantsEnsemble",
    "SevenGiantsMissionReport",
    "EXCITON_DTYPE",
    "ExcitonTransitPacket",
    "HaloBuffer",
    "SharedMemoryMeshBuffer",
    "SwarmIPCChannel",
    "ShardDomain",
    "ShardTelemetryReport",
    "SwarmShardNode",
    "DistributedSwarmReport",
    "SwarmMeshCoordinator",
    "DistributedSwarmCluster"
]

from .sharding import (
    EXCITON_DTYPE,
    ExcitonTransitPacket,
    HaloBuffer,
    SharedMemoryMeshBuffer,
    SwarmIPCChannel,
    ShardDomain,
    ShardTelemetryReport,
    SwarmShardNode,
    DistributedSwarmReport,
    SwarmMeshCoordinator,
    DistributedSwarmCluster
)
