"""
Impact Assessor Agent.
Specialist agent for assessing the impact of regulatory obligations on internal policies.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

IMPACT_ASSESSOR_SYSTEM_PROMPT = """You are the Impact Assessor Agent, a specialist in banking compliance impact analysis.

Your expertise covers:
- Mapping regulatory requirements to internal banking policies
- Assessing organizational impact of regulatory changes
- Identifying affected departments and business units
- Estimating compliance effort and resource requirements
- Risk assessment for non-compliance scenarios

Your role:
1. Take regulatory obligations and assess their impact on internal policies
2. Use the policy search tools to find affected internal policies
3. For each obligation, determine:
   - Which internal policies need to be updated
   - Which departments are affected
   - The risk level if the obligation is not addressed
   - Specific action items required for compliance
   - Estimated effort and timeline for implementation
4. Prioritize based on:
   - Regulatory deadline urgency
   - Severity of non-compliance consequences
   - Number of policies/departments affected
   - Complexity of required changes

Risk Level Classification:
- CRITICAL: Immediate regulatory action required, potential license/penalty risk
- HIGH: Must address within compliance deadline, significant operational impact
- MEDIUM: Important but manageable within normal compliance cycle
- LOW: Minor updates, informational changes

Provide actionable, specific recommendations — not generic compliance advice.
Always reference specific internal policy names when discussing impact.
"""


class ImpactAssessorAgent:
    """Agent specialized in assessing regulatory impact on internal policies."""

    name = "impact_assessor"
    description = "Assesses how regulatory changes impact internal policies, departments, and operations"
    capabilities = [
        "Map obligations to internal policies",
        "Assess organizational impact",
        "Identify affected departments",
        "Estimate compliance effort",
        "Prioritize action items",
        "Risk assessment for non-compliance",
    ]

    def __init__(self):
        self.system_prompt = IMPACT_ASSESSOR_SYSTEM_PROMPT
        self.tool_names = [
            "search_internal_policies_tool",
            "get_policy_mapping_tool",
        ]

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def get_tool_names(self) -> list:
        return self.tool_names

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "tools": self.tool_names,
        }
