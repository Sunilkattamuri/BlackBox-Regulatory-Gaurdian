"""
MCP Tools for Contract Data Access.
Provides tools for retrieving and searching processed contract data.
"""

import logging
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_contract_tools(mcp: FastMCP):
    """Register all contract data tools on the MCP server."""

    @mcp.tool()
    def get_contract_clause(contract_id: str, clause_type: str) -> str:
        """
        Retrieve a specific extracted clause from a processed contract.

        Args:
            contract_id: The contract ID (numeric).
            clause_type: Type of clause to retrieve (e.g., 'governing_law', 'termination',
                        'confidentiality', 'effective_date', 'parties').
        """
        try:
            from ...database import SessionLocal
            from ... import models

            db = SessionLocal()
            try:
                contract = db.query(models.Contract).filter(
                    models.Contract.id == int(contract_id)
                ).first()

                if not contract:
                    return f"Contract with ID {contract_id} not found."

                if not contract.extracted_data:
                    return f"Contract {contract_id} ({contract.filename}) has not been processed yet."

                clauses = contract.extracted_data.get("clauses", {})
                if not clauses:
                    return f"No clauses extracted from contract {contract_id}."

                # Map clause_type to the question used during extraction
                clause_map = {
                    "effective_date": "What is the effective date of the contract?",
                    "parties": "Who are the parties to the contract?",
                    "governing_law": "What is the governing law?",
                    "termination": "Are there any termination clauses?",
                    "confidentiality": "Is there a confidentiality or non-disclosure agreement?",
                }

                question = clause_map.get(clause_type.lower())
                if question and question in clauses:
                    clause_data = clauses[question]
                    return (
                        f"📄 Contract: {contract.filename} (ID: {contract_id})\n"
                        f"📋 Clause Type: {clause_type}\n"
                        f"📝 Answer: {clause_data.get('answer', 'N/A')}\n"
                        f"🎯 Confidence: {clause_data.get('score', 0):.2%}"
                    )

                # If no exact match, search all clauses
                for q, data in clauses.items():
                    if clause_type.lower() in q.lower():
                        return (
                            f"📄 Contract: {contract.filename} (ID: {contract_id})\n"
                            f"📋 Question: {q}\n"
                            f"📝 Answer: {data.get('answer', 'N/A')}\n"
                            f"🎯 Confidence: {data.get('score', 0):.2%}"
                        )

                available_types = ", ".join(clause_map.keys())
                return (
                    f"Clause type '{clause_type}' not found in contract {contract_id}. "
                    f"Available types: {available_types}"
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error retrieving contract clause: {e}")
            return f"Error: {str(e)}"

    @mcp.tool()
    def search_contracts(query: str) -> str:
        """
        Search across all processed contracts for specific terms or clauses.

        Args:
            query: Search query (e.g., 'governing law India', 'termination notice period').
        """
        try:
            from ...database import SessionLocal
            from ... import models

            db = SessionLocal()
            try:
                contracts = db.query(models.Contract).filter(
                    models.Contract.status == "completed"
                ).all()

                if not contracts:
                    return "No processed contracts found in the system."

                results = []
                query_lower = query.lower()

                for contract in contracts:
                    # Search in raw text
                    if contract.raw_text and query_lower in contract.raw_text.lower():
                        results.append({
                            "id": contract.id,
                            "filename": contract.filename,
                            "match_type": "raw_text",
                        })
                        continue

                    # Search in extracted clauses
                    if contract.extracted_data:
                        clauses = contract.extracted_data.get("clauses", {})
                        for question, data in clauses.items():
                            answer = data.get("answer", "")
                            if query_lower in answer.lower() or query_lower in question.lower():
                                results.append({
                                    "id": contract.id,
                                    "filename": contract.filename,
                                    "match_type": "clause",
                                    "matched_clause": question,
                                    "answer": answer,
                                })
                                break

                if not results:
                    return f"No contracts found matching '{query}'."

                formatted = [f"Found {len(results)} contract(s) matching '{query}':\n"]
                for r in results:
                    entry = f"  • Contract {r['id']}: {r['filename']} (matched in: {r['match_type']})"
                    if "answer" in r:
                        entry += f"\n    Clause: {r['matched_clause']}\n    Answer: {r['answer']}"
                    formatted.append(entry)

                return "\n".join(formatted)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error searching contracts: {e}")
            return f"Error: {str(e)}"

    @mcp.tool()
    def get_contract_risk_summary(contract_id: str) -> str:
        """
        Get a risk assessment summary for a specific processed contract.

        Args:
            contract_id: The contract ID (numeric).
        """
        try:
            from ...database import SessionLocal
            from ... import models

            db = SessionLocal()
            try:
                contract = db.query(models.Contract).filter(
                    models.Contract.id == int(contract_id)
                ).first()

                if not contract:
                    return f"Contract with ID {contract_id} not found."

                if not contract.extracted_data:
                    return f"Contract {contract_id} has not been processed yet."

                risk_flags = contract.extracted_data.get("risk_flags", [])
                clauses = contract.extracted_data.get("clauses", {})

                # Build risk summary
                summary = [
                    f"🔍 Risk Summary: {contract.filename} (ID: {contract_id})",
                    f"Status: {contract.status}",
                    f"Uploaded: {contract.uploaded_at}",
                    f"\n📊 Risk Flags ({len([r for r in risk_flags if r])} identified):",
                ]

                for flag in risk_flags:
                    if flag:
                        severity_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(
                            flag.get("severity", "Medium"), "⚪"
                        )
                        summary.append(f"  {severity_emoji} {flag.get('type', 'Unknown')}: {flag.get('severity', 'N/A')}")

                summary.append(f"\n📋 Extracted Clauses ({len(clauses)}):")
                for question, data in clauses.items():
                    score = data.get("score", 0)
                    score_emoji = "✅" if score > 0.5 else "⚠️" if score > 0.2 else "❌"
                    summary.append(f"  {score_emoji} {question[:60]}... → Confidence: {score:.1%}")

                return "\n".join(summary)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error getting risk summary: {e}")
            return f"Error: {str(e)}"
