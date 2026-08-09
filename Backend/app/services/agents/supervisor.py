"""
Supervisor — LangGraph Multi-Agent Orchestrator.
Routes queries to specialized agents using a supervisor pattern.
"""

import logging
from typing import TypedDict, Annotated, Sequence, Literal, Optional, Any, Dict, List
import operator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


# --- State Definition ---

class MultiAgentState(TypedDict):
    """State shared across all agents in the multi-agent graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_agent: str
    regulatory_data: Optional[str]
    obligations: Optional[str]
    impact_assessment: Optional[str]
    compliance_report: Optional[str]
    guardrail_violations: list
    processing_steps: list


# --- Agent routing keywords ---

AGENT_ROUTING = {
    "regulatory_monitor": [
        "latest", "recent", "new", "update", "rbi", "circular", "notification",
        "regulation", "regulatory", "monitor", "fetch", "what's new", "changes",
        "master direction", "press release", "guidelines", "norms",
    ],
    "obligation_extractor": [
        "obligation", "extract", "shall", "must", "required", "mandatory",
        "compliance requirement", "what do we need to do", "action items",
        "deadline", "actionable",
    ],
    "impact_assessor": [
        "impact", "affect", "policy", "policies", "department", "risk",
        "assess", "assessment", "how does this affect", "which policies",
        "action plan", "effort", "timeline",
    ],
    "compliance_reporter": [
        "report", "summary", "summarize", "compliance status", "overview",
        "executive summary", "audit", "findings", "documentation",
        "full report", "comprehensive",
    ],
}

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor Agent for BlackBox Regulatory Guardian.

Your role is to coordinate a team of specialist agents to answer regulatory compliance queries.
Based on the user's query, route to the appropriate specialist:

1. **Regulatory Monitor**: For fetching latest RBI updates, circulars, notifications
2. **Obligation Extractor**: For extracting specific obligations from regulatory text
3. **Impact Assessor**: For assessing how regulations affect internal policies
4. **Compliance Reporter**: For generating comprehensive compliance reports

For complex queries or "full pipeline" requests, orchestrate multiple agents in sequence:
Regulatory Monitor → Obligation Extractor → Impact Assessor → Compliance Reporter

Always provide clear, structured responses. Be helpful and professional.
"""


class SupervisorGraph:
    """
    Builds and manages the LangGraph multi-agent workflow.
    Uses a supervisor pattern to route queries to specialized agents.
    """

    def __init__(self, llm, tools_by_category: Dict[str, list]):
        self.llm = llm
        self.tools_by_category = tools_by_category
        self.all_tools = tools_by_category.get("all", [])

        # Import agent definitions
        from .regulatory_monitor import RegulatoryMonitorAgent
        from .obligation_extractor import ObligationExtractorAgent
        from .impact_assessor import ImpactAssessorAgent
        from .compliance_reporter import ComplianceReporterAgent

        self.agents = {
            "regulatory_monitor": RegulatoryMonitorAgent(),
            "obligation_extractor": ObligationExtractorAgent(),
            "impact_assessor": ImpactAssessorAgent(),
            "compliance_reporter": ComplianceReporterAgent(),
        }
        
        self.memory = MemorySaver()

        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state graph with all agent nodes."""
        from langgraph.prebuilt import ToolNode

        workflow = StateGraph(MultiAgentState)

        # --- Node: Supervisor (routes to specialist) ---
        async def supervisor_node(state: MultiAgentState) -> dict:
            messages = state["messages"]
            user_query = ""
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_query = msg.content
                    break

            # Determine which agent to route to
            target_agent = self._route_query(user_query)

            return {
                "messages": [
                    AIMessage(content=f"[Supervisor] Routing to {target_agent} agent...")
                ],
                "current_agent": target_agent,
                "processing_steps": [
                    {"step": "routing", "agent": target_agent, "query": user_query[:100]}
                ],
            }

        # --- Node: Regulatory Monitor ---
        async def regulatory_monitor_node(state: MultiAgentState) -> dict:
            agent = self.agents["regulatory_monitor"]
            messages = state["messages"]

            system_msg = SystemMessage(content=agent.get_system_prompt())
            agent_messages = [system_msg] + list(messages)

            try:
                # Get tools for this agent
                agent_tools = self.tools_by_category.get("regulatory", self.all_tools[:3])
                try:
                    llm_with_tools = self.llm.bind_tools(agent_tools)
                    response = await llm_with_tools.ainvoke(agent_messages)
                except NotImplementedError:
                    logger.warning("Regulatory Monitor: LLM does not support tool binding. Falling back to direct prompt.")
                    response = await self.llm.ainvoke(agent_messages)

                # If the LLM wants to call tools, handle it
                if hasattr(response, "tool_calls") and response.tool_calls:
                    tool_node = ToolNode(agent_tools)
                    tool_result = await tool_node.ainvoke({"messages": agent_messages + [response]})
                    tool_messages = tool_result.get("messages", [])

                    # Get final response after tool use
                    final_messages = agent_messages + [response] + tool_messages
                    final_response = await self.llm.ainvoke(final_messages)

                    return {
                        "messages": [response] + tool_messages + [final_response],
                        "regulatory_data": final_response.content,
                        "processing_steps": [{
                            "step": "regulatory_monitor",
                            "status": "completed",
                            "tools_used": [tc["name"] for tc in response.tool_calls],
                        }],
                    }

                return {
                    "messages": [response],
                    "regulatory_data": response.content,
                    "processing_steps": [{
                        "step": "regulatory_monitor",
                        "status": "completed",
                        "tools_used": [],
                    }],
                }

            except Exception as e:
                logger.error(f"Regulatory Monitor error: {e}")
                error_msg = AIMessage(
                    content=f"[Regulatory Monitor] Error: {str(e)}. "
                    "Attempting to provide information from cached data..."
                )
                # Fallback: call the tool directly
                try:
                    from ..lrr_service import lrr_service
                    updates = lrr_service.fetch_latest_updates()
                    fallback_content = "Latest regulatory updates (from cache):\n\n"
                    for u in updates[:5]:
                        fallback_content += f"• {u.get('title', 'N/A')}\n  {u.get('summary', '')[:200]}\n\n"
                    return {
                        "messages": [AIMessage(content=fallback_content)],
                        "regulatory_data": fallback_content,
                        "processing_steps": [{
                            "step": "regulatory_monitor",
                            "status": "fallback",
                        }],
                    }
                except Exception:
                    return {
                        "messages": [error_msg],
                        "processing_steps": [{
                            "step": "regulatory_monitor",
                            "status": "error",
                            "error": str(e),
                        }],
                    }

        # --- Node: Obligation Extractor ---
        async def obligation_extractor_node(state: MultiAgentState) -> dict:
            agent = self.agents["obligation_extractor"]
            messages = state["messages"]

            # If we have regulatory data from the previous agent, include it
            context = ""
            if state.get("regulatory_data"):
                context = f"\n\nRegulatory data to analyze:\n{state['regulatory_data']}"

            system_msg = SystemMessage(content=agent.get_system_prompt() + context)
            agent_messages = [system_msg] + list(messages)

            try:
                agent_tools = self.tools_by_category.get("obligation", [])
                if agent_tools:
                    try:
                        llm_with_tools = self.llm.bind_tools(agent_tools)
                        response = await llm_with_tools.ainvoke(agent_messages)
                    except NotImplementedError:
                        logger.warning("Obligation Extractor: LLM does not support tool binding. Falling back to direct prompt.")
                        response = await self.llm.ainvoke(agent_messages)
                else:
                    response = await self.llm.ainvoke(agent_messages)

                return {
                    "messages": [response],
                    "obligations": response.content,
                    "processing_steps": [{
                        "step": "obligation_extractor",
                        "status": "completed",
                    }],
                }

            except Exception as e:
                logger.error(f"Obligation Extractor error: {e}")
                # Fallback: use rule-based extraction
                reg_data = state.get("regulatory_data", "")
                if reg_data:
                    from ..lrr_service import lrr_service
                    obligations = lrr_service.extract_obligations(reg_data)
                    if obligations:
                        result = "Extracted obligations (rule-based fallback):\n\n"
                        for i, ob in enumerate(obligations, 1):
                            result += (
                                f"{i}. [{ob['severity'].upper()}] {ob['text'][:200]}\n"
                                f"   Deadline: {ob.get('deadline', 'Not specified')}\n\n"
                            )
                        return {
                            "messages": [AIMessage(content=result)],
                            "obligations": result,
                            "processing_steps": [{
                                "step": "obligation_extractor",
                                "status": "fallback",
                            }],
                        }
                return {
                    "messages": [AIMessage(content=f"[Obligation Extractor] Error: {str(e)}")],
                    "processing_steps": [{
                        "step": "obligation_extractor",
                        "status": "error",
                        "error": str(e),
                    }],
                }

        # --- Node: Impact Assessor ---
        async def impact_assessor_node(state: MultiAgentState) -> dict:
            agent = self.agents["impact_assessor"]
            messages = state["messages"]

            context_parts = []
            if state.get("regulatory_data"):
                context_parts.append(f"Regulatory Updates:\n{state['regulatory_data']}")
            if state.get("obligations"):
                context_parts.append(f"Extracted Obligations:\n{state['obligations']}")

            context = "\n\n".join(context_parts)
            system_msg = SystemMessage(
                content=agent.get_system_prompt() + f"\n\nContext:\n{context}" if context else agent.get_system_prompt()
            )
            agent_messages = [system_msg] + list(messages)

            try:
                agent_tools = self.tools_by_category.get("policy", [])
                if agent_tools:
                    try:
                        llm_with_tools = self.llm.bind_tools(agent_tools)
                        response = await llm_with_tools.ainvoke(agent_messages)
                    except NotImplementedError:
                        logger.warning("Impact Assessor: LLM does not support tool binding. Falling back to direct prompt.")
                        response = await self.llm.ainvoke(agent_messages)
                else:
                    response = await self.llm.ainvoke(agent_messages)

                return {
                    "messages": [response],
                    "impact_assessment": response.content,
                    "processing_steps": [{
                        "step": "impact_assessor",
                        "status": "completed",
                    }],
                }

            except Exception as e:
                logger.error(f"Impact Assessor error: {e}")
                return {
                    "messages": [AIMessage(content=f"[Impact Assessor] Error: {str(e)}")],
                    "processing_steps": [{
                        "step": "impact_assessor",
                        "status": "error",
                        "error": str(e),
                    }],
                }

        # --- Node: Compliance Reporter ---
        async def compliance_reporter_node(state: MultiAgentState) -> dict:
            agent = self.agents["compliance_reporter"]
            messages = state["messages"]

            # Build comprehensive context from all previous agents
            context_parts = ["Please compile a comprehensive compliance report using the following information:"]
            if state.get("regulatory_data"):
                context_parts.append(f"\n## Regulatory Updates\n{state['regulatory_data']}")
            if state.get("obligations"):
                context_parts.append(f"\n## Extracted Obligations\n{state['obligations']}")
            if state.get("impact_assessment"):
                context_parts.append(f"\n## Impact Assessment\n{state['impact_assessment']}")

            context = "\n".join(context_parts)
            system_msg = SystemMessage(content=agent.get_system_prompt())
            context_msg = HumanMessage(content=context)

            agent_messages = [system_msg, context_msg]

            try:
                response = await self.llm.ainvoke(agent_messages)

                return {
                    "messages": [response],
                    "compliance_report": response.content,
                    "processing_steps": [{
                        "step": "compliance_reporter",
                        "status": "completed",
                    }],
                }

            except Exception as e:
                logger.error(f"Compliance Reporter error: {e}")
                # Fallback: generate a basic report from available data
                report = "# Compliance Report (Auto-generated Fallback)\n\n"
                if state.get("regulatory_data"):
                    report += f"## Regulatory Updates\n{state['regulatory_data'][:500]}\n\n"
                if state.get("obligations"):
                    report += f"## Obligations\n{state['obligations'][:500]}\n\n"
                if state.get("impact_assessment"):
                    report += f"## Impact\n{state['impact_assessment'][:500]}\n\n"
                report += "\n---\n⚖️ *Disclaimer: Auto-generated report. Consult compliance team.*"

                return {
                    "messages": [AIMessage(content=report)],
                    "compliance_report": report,
                    "processing_steps": [{
                        "step": "compliance_reporter",
                        "status": "fallback",
                    }],
                }

        # --- Build the graph ---
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("regulatory_monitor", regulatory_monitor_node)
        workflow.add_node("obligation_extractor", obligation_extractor_node)
        workflow.add_node("impact_assessor", impact_assessor_node)
        workflow.add_node("compliance_reporter", compliance_reporter_node)

        # Entry point
        workflow.set_entry_point("supervisor")

        # Conditional edges from supervisor
        def route_from_supervisor(state: MultiAgentState) -> str:
            return state.get("current_agent", "regulatory_monitor")

        workflow.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            {
                "regulatory_monitor": "regulatory_monitor",
                "obligation_extractor": "obligation_extractor",
                "impact_assessor": "impact_assessor",
                "compliance_reporter": "compliance_reporter",
                "full_pipeline": "regulatory_monitor",
            },
        )

        # Single-agent queries end after the specialist
        workflow.add_edge("regulatory_monitor", END)
        workflow.add_edge("obligation_extractor", END)
        workflow.add_edge("impact_assessor", END)
        workflow.add_edge("compliance_reporter", END)


        return workflow.compile(checkpointer=self.memory)

    def build_full_pipeline_graph(self) -> Any:
        """
        Build a separate graph for the full pipeline mode:
        Monitor → Extract → Assess → Report (sequential).
        """
        workflow = StateGraph(MultiAgentState)

        # Reuse the same node functions but chain them
        # For the full pipeline, we use simpler pass-through nodes
        def monitor_node(state):
            from ..lrr_service import lrr_service
            updates = lrr_service.fetch_latest_updates()
            formatted = []
            for u in updates[:5]:
                formatted.append(f"• {u.get('title', 'N/A')}\n  {u.get('summary', '')[:300]}")
            reg_data = "\n\n".join(formatted)

            return {
                "messages": [AIMessage(content=f"[Monitor] Found {len(updates)} updates")],
                "regulatory_data": reg_data,
                "processing_steps": [{"step": "monitor", "status": "completed"}],
            }

        def extract_node(state):
            from ..lrr_service import lrr_service
            reg_data = state.get("regulatory_data", "")
            obligations = lrr_service.extract_obligations(reg_data)
            ob_text = ""
            for i, ob in enumerate(obligations, 1):
                ob_text += f"{i}. [{ob['severity'].upper()}] {ob['text'][:200]}\n"
            return {
                "messages": [AIMessage(content=f"[Extractor] Found {len(obligations)} obligations")],
                "obligations": ob_text or "No specific obligations found.",
                "processing_steps": [{"step": "extract", "status": "completed"}],
            }

        def assess_node(state):
            from ..lrr_service import lrr_service
            ob_text = state.get("obligations", "")
            # Parse obligations back and assess
            assessments = lrr_service.assess_impact(
                lrr_service.extract_obligations(state.get("regulatory_data", ""))
            )
            assess_text = ""
            for a in assessments:
                policies = ", ".join(a.get("affected_policies", [])[:3])
                assess_text += (
                    f"• Risk: {a['risk_level'].upper()} | Policies: {policies or 'N/A'} | "
                    f"Effort: {a.get('estimated_effort', 'N/A')}\n"
                )
            return {
                "messages": [AIMessage(content=f"[Assessor] Assessed {len(assessments)} impacts")],
                "impact_assessment": assess_text or "No impact assessments generated.",
                "processing_steps": [{"step": "assess", "status": "completed"}],
            }

        def report_node(state):
            report = "# 📋 Compliance Report\n\n"
            report += "## Executive Summary\n"
            report += "Automated regulatory lifecycle review completed.\n\n"

            if state.get("regulatory_data"):
                report += f"## 📰 Regulatory Updates\n{state['regulatory_data']}\n\n"
            if state.get("obligations"):
                report += f"## ⚖️ Obligations\n{state['obligations']}\n\n"
            if state.get("impact_assessment"):
                report += f"## 📊 Impact Assessment\n{state['impact_assessment']}\n\n"

            report += (
                "## 📝 Recommendations\n"
                "1. Review all critical/high severity obligations immediately\n"
                "2. Update affected internal policies within specified deadlines\n"
                "3. Assign action items to responsible departments\n"
                "4. Schedule follow-up compliance review\n\n"
                "---\n"
                "⚖️ *Disclaimer: This AI-generated report is for informational purposes only.*"
            )

            return {
                "messages": [AIMessage(content=report)],
                "compliance_report": report,
                "processing_steps": [{"step": "report", "status": "completed"}],
            }

        workflow.add_node("monitor", monitor_node)
        workflow.add_node("extract", extract_node)
        workflow.add_node("assess", assess_node)
        workflow.add_node("report", report_node)

        workflow.set_entry_point("monitor")
        workflow.add_edge("monitor", "extract")
        workflow.add_edge("extract", "assess")
        workflow.add_edge("assess", "report")
        workflow.add_edge("report", END)

        return workflow.compile(checkpointer=self.memory)

    def _route_query(self, query: str) -> str:
        """Determine which specialist agent should handle a query."""
        query_lower = query.lower()

        # Check for full pipeline keywords
        full_pipeline_keywords = [
            "full pipeline", "complete check", "full cycle", "run everything",
            "comprehensive review", "full compliance", "end to end",
            "complete analysis", "full report",
        ]
        if any(kw in query_lower for kw in full_pipeline_keywords):
            return "full_pipeline"

        # Score each agent based on keyword matches
        scores = {}
        for agent_name, keywords in AGENT_ROUTING.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[agent_name] = score

        # Return the highest scoring agent, default to regulatory_monitor
        best_agent = max(scores, key=scores.get)
        if scores[best_agent] == 0:
            return "regulatory_monitor"  # Default

        return best_agent

    def get_agent_info(self) -> List[Dict[str, Any]]:
        """Return info about all available agents."""
        info = []
        for agent in self.agents.values():
            info.append(agent.get_info())
        # Add supervisor info
        info.append({
            "name": "supervisor",
            "description": "Orchestrates specialist agents and routes queries",
            "capabilities": ["Query routing", "Multi-agent orchestration", "Full pipeline execution"],
            "tools": [],
        })
        return info
