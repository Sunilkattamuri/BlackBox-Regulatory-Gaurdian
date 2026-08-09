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

    async def invoke_agent(self, llm, summary_text: str, obligations: list, impacts: list) -> str:
        """Invokes the Compliance Reporter agent autonomously with tool access."""
        from app.services.mcp_server import get_all_mcp_tools
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        import json

        tools = get_all_mcp_tools().get("compliance", [])
        
        system_prompt = self.system_prompt + "\n\nOutput the final report in clean markdown format."
        
        try:
            agent_executor = create_react_agent(llm, tools, prompt=system_prompt)
            result = await agent_executor.ainvoke({
                "messages": [HumanMessage(content=f"Generate a compliance report based on this summary:\n{summary_text}\n\nObligations:\n{json.dumps(obligations)}\n\nImpacts:\n{json.dumps(impacts)}")]
            })
            
            return result["messages"][-1].content.strip()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error during Compliance Reporter Agent execution: {e}")
            raise
