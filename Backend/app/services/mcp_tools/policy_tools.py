"""
MCP Tools for Internal Policy Management.
Provides tools for searching, mapping, and comparing internal banking policies.
"""

import logging
from typing import Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Simulated internal policy database
# In production, this would connect to a real policy management system
INTERNAL_POLICIES = {
    "POL-001": {
        "id": "POL-001",
        "name": "Investment Valuation Policy",
        "version": "2.1",
        "department": "Treasury",
        "categories": ["investment", "valuation", "trading book", "market risk"],
        "summary": "Guidelines for classification, valuation, and operation of investment portfolios. "
                   "All commercial banks must re-value their trading book positions monthly using "
                   "mark-to-market methodology. HTM portfolio review quarterly.",
        "last_updated": "2024-06-15",
        "regulatory_references": ["RBI/2023-24/35", "Master Direction DOR.STR.REC.13/21.04.048/2023-24"],
    },
    "POL-002": {
        "id": "POL-002",
        "name": "Digital Lending Policy",
        "version": "3.0",
        "department": "Retail Banking",
        "categories": ["digital lending", "fintech", "dlg", "outsourcing", "nbfc"],
        "summary": "Framework governing digital lending partnerships with fintech entities. "
                   "DLG arrangements capped at 5% of loan portfolio. Mandatory disclosure "
                   "requirements for all digital loan products. KYC must be performed by the bank.",
        "last_updated": "2024-08-20",
        "regulatory_references": ["RBI/2023-24/157", "DOR.CRE.REC.66/21.07.001/2023-24"],
    },
    "POL-003": {
        "id": "POL-003",
        "name": "KYC and AML Policy",
        "version": "5.2",
        "department": "Compliance",
        "categories": ["kyc", "aml", "cft", "customer due diligence", "pml act", "identity verification"],
        "summary": "Customer identification, verification, and ongoing monitoring procedures. "
                   "Enhanced due diligence for PEPs and high-risk customers. STR reporting within "
                   "7 days. Periodic KYC updates mandatory.",
        "last_updated": "2024-09-10",
        "regulatory_references": ["RBI/2024-25/12", "DBOD.AML.BC.18/14.01.001/2024-25"],
    },
    "POL-004": {
        "id": "POL-004",
        "name": "Capital Adequacy & CRAR Policy",
        "version": "4.0",
        "department": "Risk Management",
        "categories": ["capital adequacy", "crar", "basel", "tier 1", "tier 2", "rwa", "pillar"],
        "summary": "Maintaining minimum Capital to Risk-weighted Assets Ratio (CRAR) of 9% "
                   "as per Basel III norms. Internal capital adequacy assessment process (ICAAP). "
                   "Stress testing framework for credit, market, and operational risk.",
        "last_updated": "2024-07-01",
        "regulatory_references": ["RBI/2023-24/48", "Master Circular DOR.CAP.REC.4/21.06.201/2023-24"],
    },
    "POL-005": {
        "id": "POL-005",
        "name": "Priority Sector Lending Policy",
        "version": "2.5",
        "department": "Credit",
        "categories": ["priority sector", "agriculture", "msme", "weaker sections", "psl"],
        "summary": "Achieving PSL targets: 40% of ANBC to priority sectors. Sub-targets: "
                   "Agriculture 18%, Micro enterprises 7.5%, Weaker sections 12%. "
                   "PSLC trading guidelines. Shortfall reporting and penalties.",
        "last_updated": "2024-04-01",
        "regulatory_references": ["RBI/2024-25/3", "FIDD.CO.Plan.BC.5/04.09.01/2024-25"],
    },
    "POL-006": {
        "id": "POL-006",
        "name": "Outsourcing Policy",
        "version": "1.8",
        "department": "Operations",
        "categories": ["outsourcing", "third party", "vendor", "service provider", "cloud"],
        "summary": "Guidelines for outsourcing financial services activities. Risk assessment "
                   "of service providers. Data security requirements. Business continuity "
                   "provisions. Regulatory reporting for material outsourcing arrangements.",
        "last_updated": "2024-05-15",
        "regulatory_references": ["RBI/2023-24/92"],
    },
    "POL-007": {
        "id": "POL-007",
        "name": "Interest Rate Policy",
        "version": "3.1",
        "department": "Treasury",
        "categories": ["interest rate", "mclr", "eblr", "repo rate", "lending rate", "deposit rate"],
        "summary": "Framework for setting and reviewing lending and deposit interest rates. "
                   "EBLR reset mechanism. Spread determination methodology. Interest rate "
                   "risk management in banking book (IRRBB).",
        "last_updated": "2024-10-01",
        "regulatory_references": ["RBI/2024-25/28"],
    },
}

# Category-to-policy mapping
CATEGORY_POLICY_MAP = {
    "investment": ["POL-001"],
    "valuation": ["POL-001"],
    "digital lending": ["POL-002"],
    "fintech": ["POL-002", "POL-006"],
    "dlg": ["POL-002"],
    "kyc": ["POL-003"],
    "aml": ["POL-003"],
    "capital adequacy": ["POL-004"],
    "basel": ["POL-004"],
    "priority sector": ["POL-005"],
    "agriculture": ["POL-005"],
    "msme": ["POL-005"],
    "outsourcing": ["POL-006"],
    "interest rate": ["POL-007"],
    "lending rate": ["POL-007"],
    "deposit rate": ["POL-007"],
}


def register_policy_tools(mcp: FastMCP):
    """Register all internal policy tools on the MCP server."""

    @mcp.tool()
    def search_internal_policies(query: str) -> str:
        """
        Search internal banking policies for a given topic or query.
        Uses Pinecone semantic search if configured, falling back to keyword search if not.

        Args:
            query: Search query (e.g., 'investment valuation', 'digital lending DLG', 'KYC norms').
        """
        from ..vector_store_service import vector_store_service
        
        # Check if Pinecone is configured and ready
        if vector_store_service.is_configured():
            logger.info(f"Using Pinecone vector semantic search for query: '{query}'")
            results = vector_store_service.search_policies(query, min_score=0.7)
            if results:
                formatted = []
                for p in results[:5]:
                    formatted.append(
                        f"📋 {p['name']} (v{p['version']})\n"
                        f"   ID: {p['id']} | Department: {p['department']}\n"
                        f"   Last Updated: {p['last_updated']}\n"
                        f"   Summary: {p['summary']}\n"
                        f"   Regulatory Refs: {', '.join(p['regulatory_references']) if isinstance(p['regulatory_references'], list) else p['regulatory_references']}\n"
                        f"   Semantic Score (Cosine): {p.get('score', 0.0):.4f}"
                    )
                return f"Found {len(results)} matching policy/policies via Pinecone semantic search:\n\n" + "\n\n".join(formatted)
            else:
                logger.info("Pinecone semantic search returned no results; attempting simulated fallback")

        # Fallback to simulated in-memory keyword search
        logger.info(f"Using simulated keyword search fallback for query: '{query}'")
        query_lower = query.lower()
        results = []

        for policy_id, policy in INTERNAL_POLICIES.items():
            score = 0
            # Check name match
            if query_lower in policy["name"].lower():
                score += 10
            # Check category match
            for cat in policy["categories"]:
                if cat in query_lower or query_lower in cat:
                    score += 5
            # Check summary match
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in policy["summary"].lower():
                    score += 2

            if score > 0:
                results.append((score, policy))

        if not results:
            return f"No internal policies found matching '{query}'. Available policy areas: " + \
                   ", ".join(sorted(CATEGORY_POLICY_MAP.keys()))

        # Sort by relevance score
        results.sort(key=lambda x: x[0], reverse=True)

        formatted = []
        for score, p in results[:5]:
            formatted.append(
                f"📋 {p['name']} (v{p['version']})\n"
                f"   ID: {p['id']} | Department: {p['department']}\n"
                f"   Last Updated: {p['last_updated']}\n"
                f"   Summary: {p['summary']}\n"
                f"   Regulatory Refs: {', '.join(p['regulatory_references'])}\n"
                f"   Relevance Score: {score} (Simulated Fallback)"
            )

        return f"Found {len(results)} matching policy/policies (Simulated Fallback):\n\n" + "\n\n".join(formatted)

    @mcp.tool()
    def get_policy_mapping(regulation_category: str) -> str:
        """
        Map a regulation category to affected internal policies.
        Returns which internal policies are impacted by changes in a regulatory area.

        Args:
            regulation_category: Category of regulation (e.g., 'digital lending', 'kyc', 'capital adequacy').
        """
        category_lower = regulation_category.lower().strip()

        # Direct match
        if category_lower in CATEGORY_POLICY_MAP:
            policy_ids = CATEGORY_POLICY_MAP[category_lower]
        else:
            # Fuzzy match
            policy_ids = []
            for cat, pids in CATEGORY_POLICY_MAP.items():
                if category_lower in cat or cat in category_lower:
                    policy_ids.extend(pids)
            policy_ids = list(set(policy_ids))

        if not policy_ids:
            return (
                f"No internal policies mapped to regulation category '{regulation_category}'. "
                f"Known categories: {', '.join(sorted(CATEGORY_POLICY_MAP.keys()))}"
            )

        formatted = [f"🔗 Policies affected by '{regulation_category}' regulations:\n"]
        for pid in policy_ids:
            if pid in INTERNAL_POLICIES:
                p = INTERNAL_POLICIES[pid]
                formatted.append(
                    f"  • {p['name']} ({pid}) — Dept: {p['department']}, v{p['version']}"
                )

        return "\n".join(formatted)

    @mcp.tool()
    def get_policy_details(policy_id: str) -> str:
        """
        Get full details of a specific internal policy.

        Args:
            policy_id: Policy identifier (e.g., 'POL-001', 'POL-003').
        """
        policy_id = policy_id.upper().strip()

        if policy_id not in INTERNAL_POLICIES:
            available = ", ".join(sorted(INTERNAL_POLICIES.keys()))
            return f"Policy '{policy_id}' not found. Available policies: {available}"

        p = INTERNAL_POLICIES[policy_id]
        return (
            f"📋 Policy Details: {p['name']}\n"
            f"{'=' * 50}\n"
            f"ID: {p['id']}\n"
            f"Version: {p['version']}\n"
            f"Department: {p['department']}\n"
            f"Last Updated: {p['last_updated']}\n"
            f"Categories: {', '.join(p['categories'])}\n\n"
            f"Summary:\n{p['summary']}\n\n"
            f"Regulatory References:\n"
            + "\n".join(f"  • {ref}" for ref in p['regulatory_references'])
        )

    @mcp.tool()
    def compare_policy_versions(policy_id: str, version_a: str, version_b: str) -> str:
        """
        Compare two versions of an internal policy to identify changes.
        Note: Version history is simulated for the prototype.

        Args:
            policy_id: Policy identifier (e.g., 'POL-002').
            version_a: First version number (e.g., '2.0').
            version_b: Second version number (e.g., '3.0').
        """
        policy_id = policy_id.upper().strip()

        if policy_id not in INTERNAL_POLICIES:
            return f"Policy '{policy_id}' not found."

        p = INTERNAL_POLICIES[policy_id]

        return (
            f"📊 Policy Version Comparison: {p['name']}\n"
            f"{'=' * 50}\n"
            f"Comparing v{version_a} → v{version_b}\n\n"
            f"Current Version: {p['version']}\n\n"
            f"Key Changes (Simulated):\n"
            f"  • Updated regulatory references to latest RBI circulars\n"
            f"  • Enhanced compliance monitoring requirements\n"
            f"  • Added new risk assessment parameters\n"
            f"  • Updated reporting timelines per latest guidelines\n\n"
            f"Note: Full version diff requires access to the policy management system. "
            f"Contact the {p['department']} department for detailed change logs."
        )
