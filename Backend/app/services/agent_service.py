"""
Agent Service — Multi-Agent Orchestrator.
Replaces the single-agent architecture with a supervisor-based multi-agent system.
"""

import logging
from typing import Optional, Dict, Any, List

from langchain_core.messages import HumanMessage

from .guardrails_service import guardrail_service
from ..config import settings

logger = logging.getLogger(__name__)


class RegulatoryAgentService:
    """
    Multi-agent service that orchestrates specialized agents for regulatory compliance.
    Uses LangGraph with a supervisor pattern to route queries to:
    - Regulatory Monitor Agent
    - Obligation Extractor Agent
    - Impact Assessor Agent
    - Compliance Reporter Agent
    """

    def __init__(self):
        self.llm = None
        self.graph = None
        self.full_pipeline_graph = None
        self.tools_by_category = {}
        self._initialized = False
        self._init_error = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM based on configuration."""
        try:
            # Initialize LLM based on configured provider
            self.llm = self._create_llm()

            if self.llm is None:
                self._init_error = (
                    "Could not initialize LLM. Please ensure Ollama is running "
                    "(run 'ollama serve' and 'ollama pull llama3'), or configure "
                    "an alternative provider in .env"
                )
                logger.error(self._init_error)
                return

            if self.llm is None:
                self._init_error = "Could not initialize LLM."
                logger.error(self._init_error)
                return

            self._initialized = True
            logger.info("RegulatoryAgentService LLM initialized successfully")

        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Error initializing RegulatoryAgentService: {e}")

    def _create_llm(self):
        """Create the LLM instance based on configuration."""
        provider = settings.LLM_PROVIDER.lower()

        if provider == "ollama":
            try:
                # pyrefly: ignore [missing-import]
                from langchain_ollama import ChatOllama
                llm = ChatOllama(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    base_url=settings.LLM_BASE_URL,
                )
                # Quick connectivity check
                logger.info(f"Connecting to Ollama at {settings.LLM_BASE_URL} with model {settings.LLM_MODEL}")
                return llm
            except Exception as e:
                logger.error(f"Failed to initialize Ollama: {e}")
                return None

        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY not set")
                return None
            try:
                # pyrefly: ignore [missing-import]
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    api_key=settings.OPENAI_API_KEY,
                )
            except ImportError:
                logger.error("langchain-openai not installed. Run: pip install langchain-openai")
                return None

        elif provider == "google":
            if not settings.GOOGLE_API_KEY:
                logger.error("GOOGLE_API_KEY not set")
                return None
            try:
                # pyrefly: ignore [missing-import]
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    google_api_key=settings.GOOGLE_API_KEY,
                )
            except ImportError:
                logger.error("langchain-google-genai not installed. Run: pip install langchain-google-genai")
                return None

        else:
            logger.error(f"Unknown LLM provider: {provider}")
            return None

    async def process_query(self, query: str, run_full_pipeline: bool = False) -> Dict[str, Any]:
        """
        Process a user query through the multi-agent system over MCP.
        """
        input_validation = guardrail_service.validate_input(query)
        if not input_validation.is_valid and settings.GUARDRAILS_STRICT_MODE:
            return {
                "response": input_validation.validated_text,
                "agent_used": "guardrails",
                "sources": ["Input validation"],
                "guardrail_applied": True,
                "processing_steps": [{"step": "input_validation", "status": "blocked"}],
            }

        validated_query = input_validation.validated_text

        if not self._initialized:
            return self._handle_uninitialized(validated_query, run_full_pipeline)

        # Connect to MCP server dynamically
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession
        from langchain_mcp_adapters.tools import load_mcp_tools

        try:
            async with sse_client("http://localhost:8000/mcp/sse") as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    mcp_tools = await load_mcp_tools(session)
                    
                    # Map tools manually based on known names
                    self.tools_by_category = {
                        "regulatory": [t for t in mcp_tools if "regulatory" in t.name or "rbi" in t.name],
                        "policy": [t for t in mcp_tools if "policy" in t.name or "policies" in t.name],
                        "obligation": [t for t in mcp_tools if "obligation" in t.name],
                        "all": mcp_tools,
                    }

                    from .agents.supervisor import SupervisorGraph
                    supervisor = SupervisorGraph(self.llm, self.tools_by_category)
                    self.graph = supervisor.graph
                    self.full_pipeline_graph = supervisor.build_full_pipeline_graph()
                    self._supervisor = supervisor

                    if run_full_pipeline:
                        return await self._run_full_pipeline(validated_query)
                    else:
                        return await self._run_single_query(validated_query)

        except Exception as e:
            logger.error(f"Agent processing error (MCP Network): {e}")
            return self._generate_fallback_response(validated_query, str(e))

    async def _run_single_query(self, query: str) -> Dict[str, Any]:
        """Run a single query through the supervisor graph asynchronously."""
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "current_agent": "",
            "regulatory_data": None,
            "obligations": None,
            "impact_assessment": None,
            "compliance_report": None,
            "guardrail_violations": [],
            "processing_steps": [],
        }

        result = await self.graph.ainvoke(initial_state)

        # Extract the final response
        messages = result.get("messages", [])
        final_content = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content and "[Supervisor]" not in msg.content:
                final_content = msg.content
                break

        if not final_content:
            final_content = "No response generated. Please try rephrasing your query."

        # Apply output guardrails
        output_validation = guardrail_service.validate_output(final_content)

        return {
            "response": output_validation.validated_text,
            "agent_used": result.get("current_agent", "supervisor"),
            "sources": ["Multi-agent system", f"Agent: {result.get('current_agent', 'unknown')}"],
            "guardrail_applied": not output_validation.is_valid,
            "processing_steps": result.get("processing_steps", []),
        }

    async def _run_full_pipeline(self, query: str) -> Dict[str, Any]:
        """Run the full LRR pipeline asynchronously: Monitor → Extract → Assess → Report."""
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "current_agent": "full_pipeline",
            "regulatory_data": None,
            "obligations": None,
            "impact_assessment": None,
            "compliance_report": None,
            "guardrail_violations": [],
            "processing_steps": [],
        }

        result = await self.full_pipeline_graph.ainvoke(initial_state)

        final_content = result.get("compliance_report", "")
        if not final_content:
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    final_content = msg.content
                    break

        # Apply guardrails
        output_validation = guardrail_service.validate_output(final_content)

        return {
            "response": output_validation.validated_text,
            "agent_used": "full_pipeline",
            "sources": [
                "Regulatory Monitor", "Obligation Extractor",
                "Impact Assessor", "Compliance Reporter",
            ],
            "guardrail_applied": not output_validation.is_valid,
            "processing_steps": result.get("processing_steps", []),
        }

    def _handle_uninitialized(self, query: str, run_full_pipeline: bool) -> Dict[str, Any]:
        """Handle queries when LLM is not available — use rule-based fallbacks."""
        logger.warning("Agent not initialized, using fallback processing")

        if run_full_pipeline:
            # Run the pipeline using only rule-based tools
            from .lrr_service import lrr_service

            updates = lrr_service.fetch_latest_updates()
            mapped = lrr_service.map_to_policies(updates)

            report = "# 📋 Compliance Report (Rule-Based Fallback)\n\n"
            report += f"*Note: LLM is not available ({self._init_error}). "
            report += "Using rule-based analysis.*\n\n"

            report += f"## 📰 Regulatory Updates ({len(updates)} found)\n"
            for u in updates[:5]:
                report += f"• **{u.get('title', 'N/A')}**\n  {u.get('summary', '')[:200]}\n\n"

            report += "## ⚖️ Obligations & Impact\n"
            for m in mapped[:5]:
                report += f"• **{m.get('title', 'N/A')}**\n"
                for ob in m.get("obligations", []):
                    report += f"  - [{ob.get('impact', 'N/A')}] {ob.get('action', '')[:150]}\n"
                report += "\n"

            report += (
                "\n---\n"
                "⚖️ *Disclaimer: This is a rule-based analysis. For AI-powered insights, "
                "please ensure Ollama is running with the llama3 model.*"
            )

            validated = guardrail_service.validate_output(report)
            return {
                "response": validated.validated_text,
                "agent_used": "fallback_rule_based",
                "sources": ["Rule-based analysis (LLM unavailable)"],
                "guardrail_applied": not validated.is_valid,
                "processing_steps": [{"step": "fallback", "reason": self._init_error}],
            }

        else:
            # Simple query — try to answer from available data
            return self._generate_fallback_response(query, self._init_error)

    def _generate_fallback_response(self, query: str, error: str) -> Dict[str, Any]:
        """Generate a fallback response using rule-based tools when LLM is unavailable."""
        query_lower = query.lower()

        response = ""

        # Try to provide relevant data based on query keywords
        if any(kw in query_lower for kw in ["update", "latest", "rbi", "regulation", "new"]):
            from .lrr_service import lrr_service
            updates = lrr_service.fetch_latest_updates()
            response = f"Latest Regulatory Updates ({len(updates)} found):\n\n"
            for u in updates[:5]:
                response += f"📰 **{u.get('title', 'N/A')}**\n"
                response += f"   {u.get('summary', '')[:300]}\n"
                response += f"   🔗 {u.get('link', '')}\n\n"

        elif any(kw in query_lower for kw in ["policy", "policies", "internal"]):
            from .mcp_tools.policy_tools import INTERNAL_POLICIES
            response = "Available Internal Policies:\n\n"
            for pid, p in INTERNAL_POLICIES.items():
                response += f"📋 **{p['name']}** ({pid}, v{p['version']})\n"
                response += f"   Department: {p['department']}\n"
                response += f"   {p['summary'][:200]}\n\n"

        elif any(kw in query_lower for kw in ["obligation", "pending", "action"]):
            response = (
                "To view active obligations, the system needs database access. "
                "Please use the LRR Dashboard in the UI or run a full pipeline cycle first."
            )

        else:
            response = (
                f"I'm currently operating in fallback mode because the LLM is not available.\n\n"
                f"**Error**: {error}\n\n"
                f"**Available actions without LLM**:\n"
                f"• Ask about latest RBI regulatory updates\n"
                f"• View internal policies\n"
                f"• Run a full compliance pipeline (rule-based)\n\n"
                f"**To enable AI-powered features**:\n"
                f"1. Install Ollama: https://ollama.com\n"
                f"2. Run: `ollama pull llama3`\n"
                f"3. Ensure Ollama is running: `ollama serve`"
            )

        validated = guardrail_service.validate_output(response)
        return {
            "response": validated.validated_text,
            "agent_used": "fallback",
            "sources": ["Fallback (LLM unavailable)"],
            "guardrail_applied": not validated.is_valid,
            "processing_steps": [{"step": "fallback", "error": error}],
        }

    def get_agents_info(self) -> List[Dict[str, Any]]:
        """Return information about all available agents."""
        if self._initialized and hasattr(self, "_supervisor"):
            return self._supervisor.get_agent_info()

        # Return static info if not initialized
        return [
            {
                "name": "regulatory_monitor",
                "description": "Monitors and summarizes latest RBI regulatory changes",
                "capabilities": ["Fetch updates", "Summarize changes", "Track deadlines"],
                "tools": ["get_regulatory_updates", "scrape_rbi_circular", "search_rbi_archive"],
            },
            {
                "name": "obligation_extractor",
                "description": "Extracts structured obligations from regulatory text",
                "capabilities": ["Extract obligations", "Identify deadlines", "Classify severity"],
                "tools": ["extract_obligations", "get_active_obligations"],
            },
            {
                "name": "impact_assessor",
                "description": "Assesses regulatory impact on internal policies",
                "capabilities": ["Map to policies", "Assess risk", "Estimate effort"],
                "tools": ["search_internal_policies", "get_policy_mapping"],
            },
            {
                "name": "compliance_reporter",
                "description": "Generates comprehensive compliance reports",
                "capabilities": ["Create reports", "Executive summaries", "Audit documentation"],
                "tools": ["get_regulatory_updates", "get_active_obligations", "search_internal_policies"],
            },
            {
                "name": "supervisor",
                "description": "Orchestrates specialist agents and routes queries",
                "capabilities": ["Query routing", "Multi-agent orchestration", "Full pipeline"],
                "tools": [],
            },
        ]


# Singleton instance
agent_service = RegulatoryAgentService()
