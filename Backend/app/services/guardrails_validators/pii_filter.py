"""
PII Filter Validator.
Detects and masks personally identifiable information (PII) in LLM inputs/outputs.
Focused on Indian banking PII patterns: Aadhaar, PAN, account numbers, IFSC, etc.
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

# PII patterns specific to Indian banking
PII_PATTERNS = {
    "aadhaar": {
        "pattern": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        "description": "Aadhaar Number (12-digit)",
        "mask": "XXXX-XXXX-XXXX",
        # Exclude patterns that are clearly not Aadhaar (years, amounts, etc.)
        "exclude": r"(?:19|20)\d{2}",
    },
    "pan": {
        "pattern": r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "description": "PAN Card Number",
        "mask": "XXXXX0000X",
    },
    "bank_account": {
        "pattern": r"\b\d{9,18}\b",
        "description": "Bank Account Number (9-18 digits)",
        "mask": "XXXXXXXXXX",
        # Must appear near banking context words
        "context_required": ["account", "a/c", "acct", "bank", "savings", "current"],
    },
    "ifsc": {
        "pattern": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        "description": "IFSC Code",
        "mask": "XXXX0XXXXXX",
    },
    "mobile": {
        "pattern": r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b",
        "description": "Indian Mobile Number",
        "mask": "+91-XXXXXXXXXX",
    },
    "email": {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "description": "Email Address",
        "mask": "***@***.***",
    },
    "credit_card": {
        "pattern": r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "description": "Credit/Debit Card Number",
        "mask": "XXXX-XXXX-XXXX-XXXX",
    },
    "upi_id": {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[a-z]{2,}\b",
        "description": "UPI ID",
        "mask": "***@***",
        # Must look like a UPI ID, not a regular email
        "context_required": ["upi", "pay", "payment", "transfer"],
    },
}


@register_validator(
    name="regulatory/pii_filter",
    data_type="string",
)
class PIIFilterValidator(Validator):
    """
    Detects and masks PII in text, focusing on Indian banking PII patterns.

    Args:
        pii_types: List of PII types to detect. If None, detects all types.
        mask_pii: If True, replaces detected PII with masks. If False, just flags.
        on_fail: Action to take on failure.
    """

    def __init__(
        self,
        pii_types: Optional[List[str]] = None,
        mask_pii: bool = True,
        on_fail: Optional[Callable] = None,
        **kwargs: Any,
    ):
        super().__init__(on_fail=on_fail, **kwargs)
        self.pii_types = pii_types or list(PII_PATTERNS.keys())
        self.mask_pii = mask_pii

    def validate(self, value: str, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Check for PII in the text."""
        if not value:
            return PassResult()

        detections = []
        value_lower = value.lower()

        for pii_type in self.pii_types:
            if pii_type not in PII_PATTERNS:
                continue

            config = PII_PATTERNS[pii_type]
            pattern = re.compile(config["pattern"])
            matches = pattern.finditer(value)

            for match in matches:
                matched_text = match.group()

                # Check exclusion patterns
                if "exclude" in config:
                    if re.match(config["exclude"], matched_text):
                        continue

                # Check context requirements
                if "context_required" in config:
                    has_context = any(
                        ctx in value_lower for ctx in config["context_required"]
                    )
                    if not has_context:
                        continue

                detections.append({
                    "type": pii_type,
                    "description": config["description"],
                    "position": (match.start(), match.end()),
                    "mask": config["mask"],
                    "matched": matched_text,
                })

        if detections:
            logger.warning(
                f"PIIFilterValidator: Found {len(detections)} PII instance(s): "
                f"{[d['type'] for d in detections]}"
            )

            if self.mask_pii:
                fixed_value = self._mask_pii(value, detections)
            else:
                fixed_value = value

            return FailResult(
                error_message=(
                    f"Output contains {len(detections)} PII instance(s): "
                    f"{', '.join(set(d['description'] for d in detections))}. "
                    "PII has been masked for security."
                ),
                fix_value=fixed_value,
            )

        return PassResult()

    def _mask_pii(self, text: str, detections: List[Dict]) -> str:
        """Replace detected PII with mask patterns. Process in reverse order to preserve positions."""
        # Sort by position in reverse order to avoid offset issues
        sorted_detections = sorted(detections, key=lambda d: d["position"][0], reverse=True)

        masked = text
        for detection in sorted_detections:
            start, end = detection["position"]
            masked = masked[:start] + f"[{detection['mask']}]" + masked[end:]

        return masked
