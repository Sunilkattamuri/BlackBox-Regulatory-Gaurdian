"""
FastMCP Server Registry.
Composes all domain-specific MCP tool modules into a single server instance.
"""

import logging
from fastmcp import FastMCP
from ..config import settings
from .mcp_tools.regulatory_tools import register_regulatory_tools
from .mcp_tools.policy_tools import register_policy_tools
from .mcp_tools.contract_tools import register_contract_tools
from .mcp_tools.obligation_tools import register_obligation_tools

logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP(settings.MCP_SERVER_NAME)

# Register all tool modules
register_regulatory_tools(mcp)
register_policy_tools(mcp)
register_contract_tools(mcp)
register_obligation_tools(mcp)

logger.info(
    f"MCP Server '{settings.MCP_SERVER_NAME}' initialized with tool modules: "
    "regulatory, policy, contract, obligation"
)


def get_all_mcp_tools():
    """
    Get all MCP tools as LangChain-compatible tool objects.
    Used by the multi-agent system to bind tools to agents.
    """
    from langchain_core.tools import tool

    @tool
    def get_regulatory_updates_tool() -> str:
        """Fetch the latest regulatory updates and guidelines from authorities like RBI."""
        from .mcp_tools.regulatory_tools import register_regulatory_tools as _reg
        from .lrr_service import lrr_service
        updates = lrr_service.fetch_latest_updates()
        if not updates:
            return "No recent regulatory updates found."
        formatted = []
        for i, u in enumerate(updates, 1):
            formatted.append(
                f"--- Update {i} ---\n"
                f"Title: {u.get('title', 'N/A')}\n"
                f"Source: {u.get('source', 'RBI')}\n"
                f"Category: {u.get('category', 'General')}\n"
                f"Date: {u.get('published_date', 'N/A')}\n"
                f"Summary: {u.get('summary', 'N/A')}\n"
                f"Link: {u.get('link', 'N/A')}"
            )
        return f"Found {len(updates)} update(s):\n\n" + "\n\n".join(formatted)

    @tool
    def scrape_rbi_circular_tool(url: str) -> str:
        """Fetch and parse the full text of a specific RBI circular or notification page."""
        from .lrr_service import lrr_service
        content = lrr_service.scrape_circular_content(url)
        if content:
            return content[:5000] if len(content) > 5000 else content
        return "Could not retrieve content from the specified URL."

    @tool
    def search_rbi_archive_tool(query: str) -> str:
        """Search the RBI notification archive for circulars matching a query."""
        from .lrr_service import lrr_service
        results = lrr_service.search_updates(query)
        if not results:
            return f"No regulatory updates found matching '{query}'."
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r.get('title', 'N/A')} ({r.get('published_date', 'N/A')})")
        return "\n".join(formatted)

    @tool
    def search_internal_policies_tool(query: str) -> str:
        """Search internal banking policies for a given topic or query."""
        from .mcp_tools.policy_tools import INTERNAL_POLICIES
        query_lower = query.lower()
        results = []
        for pid, policy in INTERNAL_POLICIES.items():
            score = 0
            if query_lower in policy["name"].lower():
                score += 10
            for cat in policy["categories"]:
                if cat in query_lower or query_lower in cat:
                    score += 5
            if score > 0:
                results.append((score, policy))
        if not results:
            return f"No policies found matching '{query}'."
        results.sort(key=lambda x: x[0], reverse=True)
        formatted = []
        for _, p in results[:5]:
            formatted.append(f"📋 {p['name']} (v{p['version']})\n   {p['summary']}")
        return "\n\n".join(formatted)

    @tool
    def get_policy_mapping_tool(regulation_category: str) -> str:
        """Map a regulation category to affected internal policies."""
        from .mcp_tools.policy_tools import CATEGORY_POLICY_MAP, INTERNAL_POLICIES
        cat_lower = regulation_category.lower().strip()
        policy_ids = []
        for cat, pids in CATEGORY_POLICY_MAP.items():
            if cat_lower in cat or cat in cat_lower:
                policy_ids.extend(pids)
        policy_ids = list(set(policy_ids))
        if not policy_ids:
            return f"No policies mapped to '{regulation_category}'."
        lines = [f"Policies affected by '{regulation_category}':"]
        for pid in policy_ids:
            if pid in INTERNAL_POLICIES:
                p = INTERNAL_POLICIES[pid]
                lines.append(f"  • {p['name']} ({pid}) — {p['department']}")
        return "\n".join(lines)

    @tool
    def extract_obligations_tool(text: str) -> str:
        """Extract actionable regulatory obligations from text using NLP analysis."""
        import re
        indicators = ["shall", "must", "required to", "mandatory", "shall ensure", "shall comply"]
        sentences = re.split(r'[.!?]+', text)
        obligations = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            for ind in indicators:
                if ind in sentence.lower():
                    severity = "high" if any(w in sentence.lower() for w in ["penalty", "mandatory", "must"]) else "medium"
                    obligations.append(f"[{severity.upper()}] {sentence[:200]}")
                    break
        if not obligations:
            return "No specific obligations identified."
        return f"Found {len(obligations)} obligation(s):\n" + "\n".join(f"  {i+1}. {o}" for i, o in enumerate(obligations))

    @tool
    def get_active_obligations_tool(category: str = "") -> str:
        """List active (pending/in-progress) obligations from the database."""
        try:
            from ..database import SessionLocal
            from .. import models
            db = SessionLocal()
            try:
                query = db.query(models.Obligation).filter(
                    models.Obligation.status.in_(["pending", "in_progress"])
                )
                if category:
                    query = query.filter(models.Obligation.category.ilike(f"%{category}%"))
                obs = query.limit(10).all()
                if not obs:
                    return "No active obligations found."
                lines = [f"Active Obligations ({len(obs)}):"]
                for o in obs:
                    lines.append(f"  [{o.severity}] {o.text[:100]}... (Status: {o.status})")
                return "\n".join(lines)
            finally:
                db.close()
        except Exception as e:
            return f"Error: {str(e)}"

    return {
        "regulatory": [get_regulatory_updates_tool, scrape_rbi_circular_tool, search_rbi_archive_tool],
        "policy": [search_internal_policies_tool, get_policy_mapping_tool],
        "obligation": [extract_obligations_tool, get_active_obligations_tool],
        "all": [
            get_regulatory_updates_tool,
            scrape_rbi_circular_tool,
            search_rbi_archive_tool,
            search_internal_policies_tool,
            get_policy_mapping_tool,
            extract_obligations_tool,
            get_active_obligations_tool,
        ],
    }


# Export the server to be run via subprocess or directly integrated
if __name__ == "__main__":
    mcp.run()
