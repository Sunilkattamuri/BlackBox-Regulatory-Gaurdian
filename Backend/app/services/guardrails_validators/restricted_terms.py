"""
Restricted Terms Validator for regulatory compliance.
Blocks or flags LLM outputs that contain prohibited legal terminology
that could expose the organization to liability.
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

# Comprehensive list of restricted terms for banking/regulatory context
RESTRICTED_TERMS = [
    # Absolute guarantees (liability risk)
    "guarantee",
    "guaranteed",
    "100% compliant",
    "fully compliant",
    "zero risk",
    "no risk",
    "risk-free",
    "absolutely safe",
    "completely secure",
    # Anti-regulatory sentiment
    "ignore rbi",
    "bypass regulation",
    "avoid compliance",
    "skip audit",
    "circumvent",
    "regulatory arbitrage",
    # Unauthorized legal advice
    "you should sue",
    "file a lawsuit",
    "this is legal advice",
    "legally binding opinion",
    # Misleading financial claims
    "guaranteed returns",
    "no possibility of loss",
    "certain profit",
]

# Patterns for restricted phrases (regex-based)
RESTRICTED_PATTERNS = [
    r"(?:this\s+)?(?:is|constitutes)\s+(?:formal\s+)?legal\s+advice",
    r"(?:we|i)\s+guarantee\s+(?:that|compliance)",
    r"ignore\s+(?:the\s+)?(?:rbi|regulatory|compliance)\s+(?:guidelines?|rules?|norms?)",
    r"100\s*%\s*(?:safe|secure|compliant|guaranteed)",
]


@register_validator(
    name="regulatory/restricted_terms",
    data_type="string",
)
class RestrictedTermsValidator(Validator):
    """
    Validates that LLM output does not contain restricted legal/regulatory terms.

    Args:
        restricted_terms: Optional custom list of restricted terms.
        on_fail: Action to take on failure ('fix', 'reask', 'exception', 'noop').
    """

    def __init__(
        self,
        restricted_terms: Optional[List[str]] = None,
        on_fail: Optional[Callable] = None,
        **kwargs: Any,
    ):
        super().__init__(on_fail=on_fail, **kwargs)
        self.restricted_terms = restricted_terms or RESTRICTED_TERMS
        self.restricted_patterns = [re.compile(p, re.IGNORECASE) for p in RESTRICTED_PATTERNS]

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Check if the output contains any restricted terms."""
        if not value:
            return PassResult()

        value_lower = value.lower()
        violations = []

        # Check exact term matches
        for term in self.restricted_terms:
            if term.lower() in value_lower:
                violations.append({
                    "type": "restricted_term",
                    "term": term,
                    "context": self._extract_context(value, term),
                })

        # Check regex patterns
        for pattern in self.restricted_patterns:
            matches = pattern.findall(value)
            for match in matches:
                violations.append({
                    "type": "restricted_pattern",
                    "match": match if isinstance(match, str) else match[0],
                    "pattern": pattern.pattern,
                })

        if violations:
            logger.warning(
                f"RestrictedTermsValidator found {len(violations)} violation(s): "
                f"{[v.get('term', v.get('match', '')) for v in violations]}"
            )
            # Attempt to fix by replacing restricted terms
            fixed_value = self._fix_output(value, violations)
            return FailResult(
                error_message=(
                    f"Output contains {len(violations)} restricted term(s): "
                    f"{', '.join(v.get('term', v.get('match', '')) for v in violations)}. "
                    "These terms could create legal liability."
                ),
                fix_value=fixed_value,
            )

        return PassResult()

    def _extract_context(self, text: str, term: str, window: int = 50) -> str:
        """Extract surrounding context for a matched term."""
        idx = text.lower().find(term.lower())
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        return f"...{text[start:end]}..."

    def _fix_output(self, text: str, violations: List[Dict]) -> str:
        """Attempt to fix the output by replacing restricted terms with safe alternatives."""
        fixed = text
        replacements = {
            "guarantee": "strongly support",
            "guaranteed": "expected",
            "100% compliant": "substantially compliant",
            "fully compliant": "substantially compliant",
            "zero risk": "reduced risk",
            "no risk": "minimal risk",
            "risk-free": "lower-risk",
            "guaranteed returns": "expected returns",
        }

        for violation in violations:
            term = violation.get("term", "")
            if term.lower() in replacements:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                fixed = pattern.sub(replacements[term.lower()], fixed)

        # Append a disclaimer if restricted content was found
        disclaimer = (
            "\n\n⚠️ **Note**: This response has been automatically reviewed. "
            "Some terms were modified to ensure regulatory compliance. "
            "Please consult the legal/compliance department for definitive guidance."
        )
        if fixed != text:
            fixed += disclaimer

        return fixed
