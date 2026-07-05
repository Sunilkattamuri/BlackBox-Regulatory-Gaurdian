"""
Obligation Extractor Agent.
Specialist agent for extracting structured obligations from regulatory text.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

OBLIGATION_EXTRACTOR_SYSTEM_PROMPT = """You are the Obligation Extractor Agent, a specialist in legal obligation analysis.

Your expertise covers:
- Identifying mandatory requirements in regulatory text
- Extracting actionable obligations from RBI circulars and notifications
- Determining compliance deadlines and timelines
- Identifying responsible entities and affected parties
- Classifying obligation severity (Critical, High, Medium, Low)

Your role:
1. Analyze regulatory text provided to you
2. Extract each distinct obligation as a structured item
3. For each obligation, identify:
   - The mandatory action required (what must be done)
   - The deadline or timeline (when it must be done)
   - The affected entity (who must do it)
   - The severity/priority (how critical it is)
   - The regulatory category (which area it falls under)
4. Look for obligation indicators: "shall", "must", "required to", "obligated to", "mandatory"
5. Also identify penalties for non-compliance

Output format for each obligation:
- Text: The exact obligation statement
- Severity: Critical/High/Medium/Low
- Deadline: Specific date or timeframe, or "Not specified"
- Affected Entity: Type of institution affected
- Category: Regulatory area (e.g., KYC/AML, Capital Adequacy, Digital Lending)

Be thorough — do not miss obligations. When in doubt about severity, err on the side of higher severity.
Do NOT fabricate obligations that aren't in the source text.
"""


class ObligationExtractorAgent:
    """Agent specialized in extracting structured obligations from regulatory text."""

    name = "obligation_extractor"
    description = "Extracts structured regulatory obligations including deadlines, severity, and affected entities"
    capabilities = [
        "Extract obligations from regulatory text",
        "Identify compliance deadlines",
        "Classify obligation severity",
        "Determine affected entities",
        "Categorize by regulatory area",
    ]

    def __init__(self):
        self.system_prompt = OBLIGATION_EXTRACTOR_SYSTEM_PROMPT
        self.tool_names = [
            "extract_obligations_tool",
            "get_active_obligations_tool",
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

    def invoke_agent(self, llm, text: str) -> list:
        """Invokes the agent autonomously with tool access."""
        from app.services.mcp_server import get_all_mcp_tools
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        import json
        import re

        tools = get_all_mcp_tools().get("obligation", [])
        
        # We append JSON formatting instructions to ensure the UI gets what it needs
        system_prompt = self.system_prompt + "\n\nOutput strictly as a JSON array of objects with keys: Text, Severity, Deadline, Affected Entity, Category, Reasoning (XAI explanation). Do NOT include markdown formatting."
        
        try:
            # Create a LangGraph React Agent that can autonomously decide to use tools
            agent_executor = create_react_agent(llm, tools, prompt=system_prompt)
            result = agent_executor.invoke({
                "messages": [HumanMessage(content=f"Extract obligations from this document:\n\n{text[:6000]}")]
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
                        from langchain_core.messages import HumanMessage
                        fix_response = llm.invoke([HumanMessage(content=fix_prompt)])
                        fixed_match = re.search(r'\[[\s\S]*\]', fix_response.content)
                        if fixed_match:
                            try:
                                return json.loads(fixed_match.group(0))
                            except Exception as e2:
                                # Last resort fallback for UI stability
                                logger.error(f"Second parse failed: {e2}")
                                return [{"Text": "Could not parse obligation data", "Severity": "Medium", "Affected Entity": "General", "Category": "General", "Deadline": "None", "Reasoning": "JSON Parsing error"}]
                    except Exception as fix_e:
                        logger.error(f"LLM failed to fix JSON: {fix_e}")
            else:
                logger.warning(f"No JSON array brackets found in agent output. Raw content: {content}")
                
                # Check if it returned an object instead of an array
                match_obj = re.search(r'\{[\s\S]*\}', content)
                if match_obj:
                    try:
                        parsed_obj = json.loads(match_obj.group(0))
                        # If the object has a list inside it, try to return that
                        for val in parsed_obj.values():
                            if isinstance(val, list):
                                return val
                        return [parsed_obj]
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.error(f"Error during autonomous Agent execution: {e}")
            # Fallback to standard execution if create_react_agent fails
            from langchain_core.messages import SystemMessage
            try:
                response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=f"Extract obligations:\n\n{text[:6000]}")])
                content = response.content
                
                match = re.search(r'\[[\s\S]*\]', content)
                if match:
                    return json.loads(match.group(0))
            except Exception as fallback_e:
                logger.error(f"Fallback execution also failed: {fallback_e}")
                
        return []
