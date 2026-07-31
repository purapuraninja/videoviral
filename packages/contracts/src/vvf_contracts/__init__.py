"""VVF shared contracts.

Pydantic models shared between the API, discovery worker, and local render agent.
These models are the single source of truth for the request/response shapes that
flow across the VPS <-> local-PC boundary.
"""

from vvf_contracts.common import (
    AspectRatio,
    LanguageCode,
    Platform,
    RiskFlag,
    TimestampMixin,
)
from vvf_contracts.research import (
    CandidateCreate,
    CandidateOut,
    CandidateStatus,
    ResearchRunCreate,
    ResearchRunOut,
    ResearchRunStatus,
    SourceDocumentOut,
    SourceDocumentRaw,
)
from vvf_contracts.render import (
    ApprovalOut,
    JobCandidate,
    JobCreative,
    JobVideo,
    RenderJobEventOut,
    RenderJobOut,
    RenderJobPayload,
    RenderJobStatus,
    RenderProfileCreate,
    RenderProfileOut,
    VideoOutputOut,
)
from vvf_contracts.agent import (
    AgentHeartbeatIn,
    AgentJobCompleteIn,
    AgentJobEventIn,
    AgentJobFailIn,
    AgentRegisterIn,
    AgentRegisterOut,
    ClaimJobIn,
    ClaimJobOut,
)
from vvf_contracts.mpt import MPTVideoParams

__all__ = [
    # common
    "AspectRatio",
    "LanguageCode",
    "Platform",
    "RiskFlag",
    "TimestampMixin",
    # research
    "CandidateCreate",
    "CandidateOut",
    "CandidateStatus",
    "ResearchRunCreate",
    "ResearchRunOut",
    "ResearchRunStatus",
    "SourceDocumentOut",
    "SourceDocumentRaw",
    # render
    "ApprovalOut",
    "JobCandidate",
    "JobCreative",
    "JobVideo",
    "RenderJobEventOut",
    "RenderJobOut",
    "RenderJobPayload",
    "RenderJobStatus",
    "RenderProfileCreate",
    "RenderProfileOut",
    "VideoOutputOut",
    # agent
    "AgentHeartbeatIn",
    "AgentJobCompleteIn",
    "AgentJobEventIn",
    "AgentJobFailIn",
    "AgentRegisterIn",
    "AgentRegisterOut",
    "ClaimJobIn",
    "ClaimJobOut",
    # mpt
    "MPTVideoParams",
]
