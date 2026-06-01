"""
Compliance Disclaimer Validator.
Ensures all legal/regulatory advisory outputs include proper disclaimers.
"""

import re
import logging
from typing import Any, Callable, Dict, List, Optional
from guardrails.validator_base import (
    FailResult,
    PassResult,
    ValidationResult,
    Validator,
    register_validator,
)

logger = logging.getLogger(__name__)

# Keywords that indicate the output is providing legal/regulatory advice
ADVISORY_KEYWORDS = [
    "legal advice",
    "regulatory advice",
    "compliance recommendation",
    "you should",
    "we recommend",
    "must comply",
    "obligated to",
    "required to",
    "mandatory requirement",
    "binding obligation",
    "rbi circular",
    "rbi guidelines",
    "master direction",
    "regulatory requirement",
    "compliance action",
    "penalty",
    "non-compliance",
]

STANDARD_DISCLAIMER = (
    "\n\n---\n"
    "**⚖️ Disclaimer**: This AI-generated analysis is for informational purposes only "
    "and does not constitute formal legal, regulatory, or compliance advice. "
    "All findings should be reviewed by qualified legal and compliance professionals "
    "before any action is taken. Regulatory interpretations may vary and are subject "
    "to change. Please consult the Legal and Compliance department for authoritative guidance."
)

DISCLAIMER_INDICATORS = [
    "disclaimer",
    "informational purposes only",
    "does not constitute",
    "not formal legal advice",
    "consult the legal",
    "consult legal",
    "consult compliance",
    "subject to change",
    "for reference only",
]


@register_validator(
    name="regulatory/compliance_disclaimer",
    data_type="string",
)
class ComplianceDisclaimerValidator(Validator):
    """
    Ensures that outputs containing legal/regulatory advice include proper disclaimers.

    Args:
        advisory_keywords: Custom keywords that trigger disclaimer requirement.
        custom_disclaimer: Custom disclaimer text to append.
        on_fail: Action to take on failure.
    """

    def __init__(
        self,
        advisory_keywords: Optional[List[str]] = None,
        custom_disclaimer: Optional[str] = None,
        on_fail: Optional[Callable] = None,
        **kwargs: Any,
    ):
        super().__init__(on_fail=on_fail, **kwargs)
        self.advisory_keywords = advisory_keywords or ADVISORY_KEYWORDS
        self.custom_disclaimer = custom_disclaimer or STANDARD_DISCLAIMER

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Check if advisory content includes proper disclaimer."""
        if not value:
            return PassResult()

        value_lower = value.lower()

        # Check if the output contains advisory content
        is_advisory = any(kw.lower() in value_lower for kw in self.advisory_keywords)

        if not is_advisory:
            return PassResult()

        # Check if a disclaimer already exists
        has_disclaimer = any(ind.lower() in value_lower for ind in DISCLAIMER_INDICATORS)

        if has_disclaimer:
            return PassResult()

        # Advisory content without disclaimer — fix it
        fixed_value = value.rstrip() + self.custom_disclaimer

        # Find which advisory keywords triggered this
        triggered_keywords = [
            kw for kw in self.advisory_keywords if kw.lower() in value_lower
        ]

        logger.info(
            f"ComplianceDisclaimerValidator: Appending disclaimer. "
            f"Triggered by: {triggered_keywords[:3]}..."
        )

        return FailResult(
            error_message=(
                f"Output contains regulatory/legal advisory content "
                f"(keywords: {', '.join(triggered_keywords[:3])}) "
                f"but lacks a proper disclaimer."
            ),
            fix_value=fixed_value,
        )
