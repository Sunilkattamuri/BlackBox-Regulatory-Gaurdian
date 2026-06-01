"""
Regulatory Monitor Agent.
Specialist agent for fetching and summarizing latest RBI regulatory changes.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

REGULATORY_MONITOR_SYSTEM_PROMPT = """You are the Regulatory Monitor Agent, a specialist in Indian banking regulation.

Your expertise covers:
- RBI (Reserve Bank of India) circulars, master directions, and notifications
- Banking regulation and supervision
- Payment and settlement systems
- Foreign exchange management
- Financial market regulation

Your role:
1. Fetch the latest regulatory updates using your available tools
2. Summarize key changes clearly and concisely
3. Identify which type of financial institution is affected
4. Flag urgent or time-sensitive notifications
5. Categorize updates by regulatory area (KYC/AML, Capital Adequacy, Digital Lending, etc.)

When summarizing regulatory updates:
- Start with the most impactful/recent changes
- Highlight any compliance deadlines
- Note if the regulation is a new requirement vs. amendment to existing rules
- Use clear, professional language suitable for compliance officers

Always cite the specific circular/notification reference and date when available.
Do NOT provide legal advice or make compliance guarantees.
"""


class RegulatoryMonitorAgent:
    """Agent specialized in monitoring and summarizing regulatory changes."""

    name = "regulatory_monitor"
    description = "Monitors and summarizes latest RBI regulatory changes, circulars, and notifications"
    capabilities = [
        "Fetch latest RBI regulatory updates",
        "Summarize regulatory changes",
        "Categorize regulations by area",
        "Identify affected institutions",
        "Track compliance deadlines",
    ]

    def __init__(self):
        self.system_prompt = REGULATORY_MONITOR_SYSTEM_PROMPT
        self.tool_names = [
            "get_regulatory_updates_tool",
            "scrape_rbi_circular_tool",
            "search_rbi_archive_tool",
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
