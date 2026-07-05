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

    async def invoke_agent(self, llm, obligations: list) -> list:
        """Invokes the agent autonomously with tool access over the MCP network."""
        from langchain_core.messages import HumanMessage, SystemMessage
        from langgraph.prebuilt import create_react_agent
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession
        from langchain_mcp_adapters.tools import load_mcp_tools
        import json
        import re

        system_prompt = self.system_prompt + "\n\nOutput strictly as a JSON array of objects mapping to the input obligations, with keys: Action Items, Departments, Risk Level, Effort. Do NOT include markdown formatting."
        
        try:
            async with sse_client("http://localhost:8000/mcp/sse") as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    mcp_tools = await load_mcp_tools(session)
                    
                    # Filter specifically for policy tools for this agent
                    tools = [t for t in mcp_tools if "policy" in t.name or "policies" in t.name]
                    
                    agent_executor = create_react_agent(llm, tools, prompt=system_prompt)
                    result = await agent_executor.ainvoke({
                        "messages": [HumanMessage(content=f"Assess the impact of these obligations:\n\n{json.dumps(obligations)}")]
                    })
                    content = result["messages"][-1].content
                    
                    match = re.search(r'\[[\s\S]*\]', content)
                    if match:
                        json_str = match.group(0)
                        try:
                            return json.loads(json_str)
                        except Exception as parse_e:
                            logger.error(f"Failed to parse JSON array from agent output: {parse_e}. Attempting LLM fix...")
                            try:
                                fix_prompt = (
                                    "The following JSON array is invalid. It likely contains unescaped double quotes inside string values. "
                                    "You MUST fix it by escaping any inner double quotes with a backslash (e.g. \\\") or changing them to single quotes. "
                                    "Output ONLY the valid JSON array. Do not include markdown blocks (```) or any other text.\n\n"
                                    f"{json_str}"
                                )
                                fix_response = await llm.ainvoke([HumanMessage(content=fix_prompt)])
                                fixed_match = re.search(r'\[[\s\S]*\]', fix_response.content)
                                if fixed_match:
                                    try:
                                        return json.loads(fixed_match.group(0))
                                    except Exception as e2:
                                        logger.error(f"Second parse failed: {e2}")
                                        return [{"Action Items": "Manual review required", "Departments": "Compliance", "Risk Level": "Unknown", "Effort": "Unknown"}]
                            except Exception as fix_e:
                                logger.error(f"LLM failed to fix JSON: {fix_e}")
        except Exception as e:
            logger.error(f"Error during autonomous Agent execution (MCP Network): {e}")
            try:
                response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=f"Assess the impact of these obligations:\n\n{json.dumps(obligations)}")])
                match = re.search(r'\[[\s\S]*\]', response.content)
                if match:
                    json_str = match.group(0)
                    try:
                        return json.loads(json_str)
                    except Exception as parse_e:
                        logger.error(f"Fallback parse failed: {parse_e}. Attempting LLM fix...")
                        fix_prompt = (
                            "The following JSON array is invalid. It likely contains unescaped double quotes inside string values. "
                            "You MUST fix it by escaping any inner double quotes with a backslash (e.g. \\\") or changing them to single quotes. "
                            "Output ONLY the valid JSON array. Do not include markdown blocks (```) or any other text.\n\n"
                            f"{json_str}"
                        )
                        fix_response = await llm.ainvoke([HumanMessage(content=fix_prompt)])
                        fixed_match = re.search(r'\[[\s\S]*\]', fix_response.content)
                        if fixed_match:
                            try:
                                return json.loads(fixed_match.group(0))
                            except Exception as e2:
                                logger.error(f"Second parse failed: {e2}")
                                return [{"Action Items": "Manual review required", "Departments": "Compliance", "Risk Level": "Unknown", "Effort": "Unknown"}]
            except Exception:
                pass
                
        return []
