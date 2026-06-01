"""
Hallucination Detector Validator.
Checks if cited RBI circular numbers, dates, and references match known data.
Flags potentially fabricated regulatory citations.
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

# Regex patterns to detect RBI circular/notification references
RBI_REFERENCE_PATTERNS = [
    # RBI circular references: e.g., "RBI/2024-25/85" or "RBI/2023-24/157"
    r"RBI/\d{4}-\d{2}/\d+",
    # DOR references: e.g., "DOR.STR.REC.57/21.04.048/2023-24"
    r"DOR\.[A-Z]+\.[A-Z]+\.\d+/[\d.]+/\d{4}-\d{2,4}",
    # DBOD references (older format)
    r"DBOD\.\w+\.\w+/\d+/[\d.]+/\d{4}-\d{2,4}",
    # Master Direction references
    r"Master\s+Direction\s+(?:No\.\s*)?\w+/\d+",
    # A.P. (DIR Series) Circular
    r"A\.P\.\s*\(DIR\s+Series\)\s+Circular\s+No\.\s*\d+",
    # Notification references with specific dates
    r"(?:Notification|Circular)\s+dated?\s+\d{1,2}[\s/-]\w+[\s/-]\d{4}",
]

# Known valid RBI reference prefixes (for basic sanity checking)
VALID_RBI_PREFIXES = [
    "RBI/", "DOR.", "DBOD.", "DNBS.", "DNBR.", "DPSS.",
    "FIDD.", "FMRD.", "IDMD.", "DCM.", "RPCD.",
]


@register_validator(
    name="regulatory/hallucination_detector",
    data_type="string",
)
class HallucinationDetector(Validator):
    """
    Detects potentially hallucinated RBI circular references in LLM outputs.

    This validator:
    1. Extracts all RBI reference numbers from the output.
    2. Cross-references them against known circulars in the database (if available).
    3. Performs format validation on reference numbers.
    4. Flags references that look fabricated.

    Args:
        known_references: Optional set of known valid reference numbers.
        strict_mode: If True, flags any unverifiable reference. If False, only flags obvious fakes.
        on_fail: Action to take on failure.
    """

    def __init__(
        self,
        known_references: Optional[set] = None,
        strict_mode: bool = False,
        on_fail: Optional[Callable] = None,
        **kwargs: Any,
    ):
        super().__init__(on_fail=on_fail, **kwargs)
        self.known_references = known_references or set()
        self.strict_mode = strict_mode
        self.ref_patterns = [re.compile(p, re.IGNORECASE) for p in RBI_REFERENCE_PATTERNS]

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Check for potentially hallucinated regulatory references."""
        if not value:
            return PassResult()

        # Extract all references from the text
        found_references = self._extract_references(value)

        if not found_references:
            return PassResult()

        suspicious_refs = []
        verified_refs = []

        for ref in found_references:
            if self._is_known_reference(ref):
                verified_refs.append(ref)
            elif self._looks_suspicious(ref):
                suspicious_refs.append(ref)
            elif self.strict_mode:
                # In strict mode, flag all unverifiable references
                suspicious_refs.append(ref)

        if suspicious_refs:
            logger.warning(
                f"HallucinationDetector: Found {len(suspicious_refs)} suspicious reference(s): "
                f"{suspicious_refs}"
            )

            # Add warnings to the output
            warning_text = self._add_verification_warnings(value, suspicious_refs)

            return FailResult(
                error_message=(
                    f"Output contains {len(suspicious_refs)} potentially fabricated "
                    f"regulatory reference(s): {', '.join(suspicious_refs)}. "
                    "These could not be verified against known RBI circulars."
                ),
                fix_value=warning_text,
            )

        return PassResult()

    def _extract_references(self, text: str) -> List[str]:
        """Extract all RBI reference patterns from text."""
        references = []
        for pattern in self.ref_patterns:
            matches = pattern.findall(text)
            references.extend(matches)
        return list(set(references))  # Deduplicate

    def _is_known_reference(self, ref: str) -> bool:
        """Check if a reference exists in known database."""
        return ref in self.known_references

    def _looks_suspicious(self, ref: str) -> bool:
        """
        Heuristic check for suspicious references.
        Looks for impossible dates, invalid formats, etc.
        """
        # Check for future year references (likely hallucinated)
        year_match = re.search(r"(\d{4})", ref)
        if year_match:
            year = int(year_match.group(1))
            from datetime import datetime
            current_year = datetime.now().year
            if year > current_year + 1:
                return True  # Future-dated references are suspicious

        # Check for obviously invalid RBI fiscal year format
        fy_match = re.search(r"RBI/(\d{4})-(\d{2})/", ref)
        if fy_match:
            start_year = int(fy_match.group(1))
            end_suffix = int(fy_match.group(2))
            expected_suffix = (start_year + 1) % 100
            if end_suffix != expected_suffix:
                return True  # Invalid fiscal year pair

        return False

    def _add_verification_warnings(self, text: str, suspicious_refs: List[str]) -> str:
        """Add inline verification warnings for suspicious references."""
        modified = text

        for ref in suspicious_refs:
            modified = modified.replace(
                ref,
                f"{ref} [⚠️ UNVERIFIED]"
            )

        modified += (
            "\n\n> **⚠️ Citation Verification Notice**: Some regulatory references in this "
            "response could not be verified against the known RBI circular database. "
            "References marked with [⚠️ UNVERIFIED] should be independently confirmed "
            "before reliance."
        )

        return modified

    def update_known_references(self, references: set):
        """Update the set of known valid references (e.g., from DB)."""
        self.known_references.update(references)
