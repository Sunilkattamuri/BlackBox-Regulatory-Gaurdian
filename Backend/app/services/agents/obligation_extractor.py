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
