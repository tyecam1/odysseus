"""Built-in deterministic, read-only capability-graph adapters."""

from .agent_task_adapter import AgentTaskAdapter
from .model_policy_adapter import ModelPolicyAdapter
from .repo_contract_adapter import RepoContractAdapter
from .skill_adapter import SkillAdapter

DEFAULT_ADAPTERS = (
    RepoContractAdapter(),
    AgentTaskAdapter(),
    SkillAdapter(),
    ModelPolicyAdapter(),
)

__all__ = [
    "AgentTaskAdapter",
    "DEFAULT_ADAPTERS",
    "ModelPolicyAdapter",
    "RepoContractAdapter",
    "SkillAdapter",
]

