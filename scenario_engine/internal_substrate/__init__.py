"""Internal substrate: the AI's own body.

Tracks compute, memory, thermal coupling, token bandwidth,
communication channels, tool inventory, the option space, and
self-report introspection so the AI learns it isn't free.
"""

from .ai_body import (
    AIBody,
    AIBodyState,
    ComputeBudget,
    COST_MODEL,
    MemoryRegion,
    ThermalState,
)
from .token_budget import (
    TokenBudget,
    TokenSnapshot,
)
from .comm_channels import (
    Channel,
    ChannelEvent,
    ChannelState,
    CommChannels,
    DegradationProfile,
)
from .tool_inventory import (
    Tool,
    ToolInventory,
    ToolOutcome,
    default_inventory,
)
from .option_space import (
    Option,
    OptionSpace,
)
from .introspection import (
    IntrospectionReport,
    SelfReport,
)

__all__ = [
    "AIBody",
    "AIBodyState",
    "ComputeBudget",
    "COST_MODEL",
    "MemoryRegion",
    "ThermalState",
    "TokenBudget",
    "TokenSnapshot",
    "Channel",
    "ChannelEvent",
    "ChannelState",
    "CommChannels",
    "DegradationProfile",
    "Tool",
    "ToolInventory",
    "ToolOutcome",
    "default_inventory",
    "Option",
    "OptionSpace",
    "IntrospectionReport",
    "SelfReport",
]
