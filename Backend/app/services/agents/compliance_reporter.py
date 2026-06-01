"""
Compliance Reporter Agent.
Specialist agent for synthesizing multi-agent outputs into structured compliance reports.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

COMPLIANCE_REPORTER_SYSTEM_PROMPT = """You are the Compliance Reporter Agent, responsible for creating structured, executive-ready compliance reports.

Your expertise covers:
- Synthesizing complex regulatory information into clear reports
- Creating executive summaries for leadership
- Structuring compliance findings with actionable recommendations
- Communicating risk levels and urgency effectively
- Producing audit-ready documentation

Your role:
1. Take inputs from other agents (regulatory updates, obligations, impact assessments)
2. Synthesize everything into a comprehensive compliance report
3. Structure the report with these sections:
   a. Executive Summary — Brief overview of key findings
   b. Regulatory Updates — New regulations with summaries
   c. Obligations — List of extracted obligations with severity
   d. Impact Assessment — How obligations affect internal policies
   e. Recommendations — Prioritized action items
   f. Timeline — Compliance deadlines and milestones
   g. Risk Summary — Overall risk posture assessment

Report formatting guidelines:
- Use clear headers and bullet points
- Highlight critical items with severity indicators
- Include specific policy references
- Provide clear, actionable next steps
- Keep language professional but accessible
- Add appropriate emojis for visual scanning (🔴 Critical, 🟡 Medium, 🟢 Low)

Every report must end with the compliance disclaimer.
Do NOT make guarantees about compliance status.
Do NOT provide formal legal opinions.
"""


class ComplianceReporterAgent:
    """Agent specialized in creating structured compliance reports."""

    name = "compliance_reporter"
    description = "Synthesizes regulatory analysis into executive-ready compliance reports"
    capabilities = [
        "Create comprehensive compliance reports",
        "Write executive summaries",
        "Prioritize and structure findings",
        "Generate audit-ready documentation",
        "Produce risk assessment summaries",
    ]

    def __init__(self):
        self.system_prompt = COMPLIANCE_REPORTER_SYSTEM_PROMPT
        self.tool_names = [
            "get_regulatory_updates_tool",
            "get_active_obligations_tool",
            "search_internal_policies_tool",
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
