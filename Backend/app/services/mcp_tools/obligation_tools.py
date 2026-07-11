"""
MCP Tools for Obligation Management.
Provides tools for extracting, tracking, and managing regulatory obligations.
"""

import logging
from typing import Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_obligation_tools(mcp: FastMCP):
    """Register all obligation management tools on the MCP server."""

    @mcp.tool()
    def extract_obligations_from_text(text: str) -> str:
        """
        Extract actionable regulatory obligations from a given text using NLP.
        Identifies mandatory requirements ('shall', 'must', 'required to'),
        deadlines, and responsible entities.

        Args:
            text: Regulatory text to analyze for obligations.
        """
        if not text or not text.strip():
            return "No text provided for obligation extraction."

        # Rule-based obligation extraction
        # Look for obligation indicators in the text
        obligation_indicators = [
            "shall", "must", "required to", "obligated to",
            "mandatory", "is required", "are required",
            "shall ensure", "shall comply", "shall submit",
            "within a period of", "not later than", "by the date",
            "shall be liable", "penalty", "non-compliance",
        ]

        import re
        sentences = re.split(r'[.!?]+', text)
        obligations = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 20:
                continue

            sentence_lower = sentence.lower()

            for indicator in obligation_indicators:
                if indicator in sentence_lower:
                    # Determine severity based on keywords
                    severity = "medium"
                    if any(w in sentence_lower for w in ["penalty", "non-compliance", "liable", "revoke"]):
                        severity = "high"
                    elif any(w in sentence_lower for w in ["shall ensure", "mandatory", "must"]):
                        severity = "high"
                    elif any(w in sentence_lower for w in ["may", "should consider", "recommended"]):
                        severity = "low"

                    # Extract deadline hints
                    deadline = "Not specified"
                    deadline_patterns = [
                        r"within\s+(\d+\s+(?:days?|months?|weeks?|years?))",
                        r"by\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
                        r"not\s+later\s+than\s+([\w\s,]+\d{4})",
                        r"before\s+([\w\s,]+\d{4})",
                        r"effective\s+from\s+([\w\s,]+\d{4})",
                    ]
                    for dp in deadline_patterns:
                        dm = re.search(dp, sentence, re.IGNORECASE)
                        if dm:
                            deadline = dm.group(1).strip()
                            break

                    # Determine affected entity
                    entity = "Not specified"
                    entity_patterns = [
                        r"((?:commercial|scheduled|cooperative)\s+banks?)",
                        r"(NBFCs?|Non-Banking Financial (?:Companies|Company))",
                        r"((?:all\s+)?(?:regulated|lending)\s+(?:entities|institutions))",
                        r"(payment\s+(?:banks?|aggregators?))",
                        r"(housing\s+finance\s+companies)",
                    ]
                    for ep in entity_patterns:
                        em = re.search(ep, sentence, re.IGNORECASE)
                        if em:
                            entity = em.group(1).strip()
                            break

                    obligations.append({
                        "text": sentence,
                        "indicator": indicator,
                        "severity": severity,
                        "deadline": deadline,
                        "affected_entity": entity,
                    })
                    break  # Only capture the first matching indicator per sentence

        if not obligations:
            return (
                "No specific obligations identified in the provided text. "
                "The text may not contain regulatory directives, or the obligations "
                "may be expressed in non-standard language."
            )

        # Format results
        formatted = [f"📋 Extracted {len(obligations)} obligation(s):\n"]
        for i, ob in enumerate(obligations, 1):
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(ob["severity"], "⚪")
            formatted.append(
                f"--- Obligation {i} ---\n"
                f"  {severity_emoji} Severity: {ob['severity'].upper()}\n"
                f"  📝 Text: {ob['text'][:200]}\n"
                f"  ⏰ Deadline: {ob['deadline']}\n"
                f"  🏢 Affected: {ob['affected_entity']}\n"
                f"  🔑 Indicator: '{ob['indicator']}'"
            )

        return "\n\n".join(formatted)

    @mcp.tool()
    def get_active_obligations(category: Optional[str] = None) -> str:
        """
        List active (pending/in-progress) obligations from the database.
        Optionally filter by regulatory category.

        Args:
            category: Optional category filter (e.g., 'KYC', 'Digital Lending', 'Capital Adequacy').
        """
        try:
            from ...database import SessionLocal
            from ... import models

            db = SessionLocal()
            try:
                query = db.query(models.Obligation).filter(
                    models.Obligation.status.in_(["pending", "in_progress"])
                )

                if category:
                    query = query.filter(
                        models.Obligation.category.ilike(f"%{category}%")
                    )

                obligations = query.order_by(
                    models.Obligation.created_at.desc()
                ).limit(20).all()

                if not obligations:
                    msg = f"No active obligations found"
                    if category:
                        msg += f" for category '{category}'"
                    return msg + "."

                formatted = [f"📋 Active Obligations ({len(obligations)}):\n"]
                for ob in obligations:
                    severity_emoji = {
                        "critical": "🔴", "high": "🔴",
                        "medium": "🟡", "low": "🟢", "info": "ℹ️"
                    }.get(ob.severity, "⚪")
                    status_emoji = {
                        "pending": "⏳", "in_progress": "🔄"
                    }.get(ob.status, "❓")

                    formatted.append(
                        f"  {status_emoji}{severity_emoji} [{ob.id}] {ob.text[:100]}...\n"
                        f"     Category: {ob.category or 'N/A'} | "
                        f"Deadline: {ob.deadline or 'Not set'} | "
                        f"Status: {ob.status}"
                    )

                return "\n".join(formatted)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error getting obligations: {e}")
            return f"Error retrieving obligations: {str(e)}"

    @mcp.tool()
    def search_historical_obligations(query: str) -> str:
        """
        Semantically search the bank's historical contract parsing database.
        Use this tool when you need context on how similar obligations were parsed 
        in previous contracts or to find historical precedents.

        Args:
            query: Semantic search query (e.g., 'data privacy breach notification penalties').
        """
        try:
            from ..vector_store_service import vector_store_service
            results = vector_store_service.search_contract_parsing_index(query=query, top_k=3, min_score=0.7)

            if not results:
                return f"No historical contract obligation parses found matching '{query}'."

            formatted = []
            for i, r in enumerate(results, 1):
                entry = (
                    f"--- Match {i} (Score: {r.get('score', 0):.2f}) ---\n"
                    f"Source Contract: {r.get('source_contract', 'Unknown')}\n"
                    f"Obligation Type: {r.get('obligation_type', 'Unknown')}\n"
                    f"Text:\n{r.get('text', 'N/A')}\n"
                )
                formatted.append(entry)

            return f"Found {len(results)} historical parse(s) for '{query}':\n\n" + "\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Error searching historical obligations: {e}")
            return f"Error searching historical obligations: {str(e)}"

    @mcp.tool()
    def update_obligation_status(obligation_id: str, status: str) -> str:
        """
        Update the status of a specific obligation.

        Args:
            obligation_id: The obligation ID (numeric).
            status: New status ('pending', 'in_progress', 'addressed', 'overdue', 'not_applicable').
        """
        valid_statuses = ["pending", "in_progress", "addressed", "overdue", "not_applicable"]
        status = status.lower().strip()

        if status not in valid_statuses:
            return f"Invalid status '{status}'. Valid options: {', '.join(valid_statuses)}"

        try:
            from ...database import SessionLocal
            from ... import models

            db = SessionLocal()
            try:
                obligation = db.query(models.Obligation).filter(
                    models.Obligation.id == int(obligation_id)
                ).first()

                if not obligation:
                    return f"Obligation with ID {obligation_id} not found."

                old_status = obligation.status
                obligation.status = status
                db.commit()

                return (
                    f"✅ Obligation {obligation_id} status updated: "
                    f"{old_status} → {status}\n"
                    f"Obligation: {obligation.text[:100]}..."
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error updating obligation: {e}")
            return f"Error updating obligation status: {str(e)}"
