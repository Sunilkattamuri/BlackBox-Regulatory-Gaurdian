"""
Guardrails Service — Orchestrates all validators for input/output validation.
Uses Guardrails AI Guard with custom validators for regulatory compliance.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from guardrails import Guard

from .guardrails_validators.restricted_terms import RestrictedTermsValidator
from .guardrails_validators.compliance_disclaimer import ComplianceDisclaimerValidator
from .guardrails_validators.hallucination_detector import HallucinationDetector
from .guardrails_validators.pii_filter import PIIFilterValidator
from ..config import settings

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a guardrail validation."""

    def __init__(
        self,
        is_valid: bool,
        original_text: str,
        validated_text: str,
        violations: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.is_valid = is_valid
        self.original_text = original_text
        self.validated_text = validated_text
        self.violations = violations or []
        self.warnings = warnings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "validated_text": self.validated_text,
            "violation_count": len(self.violations),
            "violations": self.violations,
            "warnings": self.warnings,
        }


class GuardrailsService:
    """
    Orchestrates Guardrails AI validators for all LLM I/O in the platform.

    Provides:
    - Input validation (PII detection, injection filtering)
    - Output validation (restricted terms, disclaimers, hallucination detection)
    - Audit logging of all validation events
    """

    def __init__(self):
        self.strict_mode = settings.GUARDRAILS_STRICT_MODE
        self.log_violations = settings.GUARDRAILS_LOG_VIOLATIONS
        self.block_on_failure = settings.GUARDRAILS_BLOCK_ON_FAILURE
        self._validation_history: List[Dict[str, Any]] = []

        # Initialize validators
        self.restricted_terms_validator = RestrictedTermsValidator(on_fail="fix")
        self.disclaimer_validator = ComplianceDisclaimerValidator(on_fail="fix")
        self.hallucination_detector = HallucinationDetector(
            strict_mode=self.strict_mode, on_fail="fix"
        )
        self.pii_filter = PIIFilterValidator(mask_pii=True, on_fail="fix")

        # Build Guards
        self._output_guard = Guard().use(
            self.restricted_terms_validator,
            self.disclaimer_validator,
            self.hallucination_detector,
            self.pii_filter,
        )

        self._input_guard = Guard().use(
            self.pii_filter,
        )

        logger.info("GuardrailsService initialized with validators: "
                     "RestrictedTerms, ComplianceDisclaimer, HallucinationDetector, PIIFilter")

    def validate_input(self, text: str) -> ValidationResult:
        """
        Validate user input before passing to LLM.
        Checks for PII and prompt injection patterns.
        """
        if not text or not text.strip():
            return ValidationResult(
                is_valid=True,
                original_text=text,
                validated_text=text,
            )

        violations = []
        warnings = []
        validated_text = text

        # PII check on input
        try:
            result = self._input_guard.validate(text)
            if result.validation_passed:
                validated_text = text
            else:
                validated_text = result.validated_output if result.validated_output else text
                violations.append({
                    "validator": "pii_filter",
                    "type": "input_pii_detected",
                    "details": "PII detected in input and masked.",
                })
        except Exception as e:
            logger.error(f"Input validation error: {e}")
            warnings.append(f"Input validation encountered an error: {str(e)}")

        # Prompt injection detection using llm-guard
        try:
            from llm_guard.input_scanners import PromptInjection, Toxicity
            from llm_guard.input_scanners.prompt_injection import MatchType
            
            # Initialize scanners once and cache them on the service
            if not hasattr(self, '_pi_scanner'):
                logger.info("Initializing llm-guard PromptInjection scanner...")
                self._pi_scanner = PromptInjection(threshold=0.5, match_type=MatchType.FULL)
            if not hasattr(self, '_toxicity_scanner'):
                logger.info("Initializing llm-guard Toxicity scanner...")
                self._toxicity_scanner = Toxicity(threshold=0.5)
                
            # Scan for Prompt Injection
            sanitized_prompt, pi_is_valid, pi_risk_score = self._pi_scanner.scan(text)
            if not pi_is_valid:
                violations.append({
                    "validator": "injection_detector",
                    "type": "prompt_injection_attempt",
                    "risk_score": pi_risk_score,
                })
                if self.block_on_failure:
                    validated_text = "I cannot process this request as it appears to contain unauthorized instructions or prompt injection attempts. Please rephrase your query to align with standard regulatory inquiries."
                else:
                    warnings.append(
                        "⚠️ Potential prompt injection pattern detected. Proceeding with caution."
                    )
                    
            # Scan for Toxicity/Profanity
            if pi_is_valid: # Only run toxicity if it passed injection check
                sanitized_prompt, tox_is_valid, tox_risk_score = self._toxicity_scanner.scan(text)
                if not tox_is_valid:
                    violations.append({
                        "validator": "toxicity_detector",
                        "type": "toxic_input_detected",
                        "risk_score": tox_risk_score,
                    })
                    if self.block_on_failure:
                        validated_text = "I cannot process this request as it contains toxic, offensive, or inappropriate language. Please maintain a professional tone."
                    else:
                        warnings.append(
                            "⚠️ Toxic language detected. Proceeding with caution."
                        )
                        
        except ImportError:
            logger.error("llm-guard is not installed. Skipping semantic injection detection.")
            warnings.append("Semantic injection detection is disabled (llm-guard missing).")
        except Exception as e:
            logger.error(f"Error running PromptInjection scanner: {e}")
            warnings.append(f"Prompt injection scanning encountered an error: {str(e)}")

        is_valid = len(violations) == 0

        self._log_validation_event(
            event_type="input_validation",
            original=text[:200],
            validated=validated_text[:200],
            passed=is_valid,
            violations=violations,
        )

        return ValidationResult(
            is_valid=is_valid,
            original_text=text,
            validated_text=validated_text,
            violations=violations,
            warnings=warnings,
        )

    def validate_output(self, text: str, context: str = "") -> ValidationResult:
        """
        Validate LLM output before returning to user.
        Applies all output validators: restricted terms, disclaimers,
        hallucination detection, and PII masking.
        """
        if not text or not text.strip():
            return ValidationResult(
                is_valid=True,
                original_text=text,
                validated_text=text,
            )

        violations = []
        warnings = []
        validated_text = text

        try:
            result = self._output_guard.validate(text)

            if result.validation_passed:
                validated_text = text
            else:
                # Use the fixed output from validators
                validated_text = result.validated_output if result.validated_output else text

                # Collect violation details
                if hasattr(result, "error") and result.error:
                    violations.append({
                        "validator": "output_guard",
                        "type": "output_validation_failed",
                        "details": str(result.error),
                    })

                if self.block_on_failure and violations:
                    validated_text = (
                        "⚠️ **Response Blocked**: The AI-generated response did not pass "
                        "regulatory compliance checks. Please rephrase your query or "
                        "consult the compliance team directly."
                    )

        except Exception as e:
            logger.error(f"Output validation error: {e}")
            warnings.append(f"Output validation encountered an error: {str(e)}")
            # On error, apply basic safety — just append disclaimer
            validated_text = text + (
                "\n\n**⚖️ Disclaimer**: This AI-generated content could not be fully validated. "
                "Please verify all information independently."
            )

        is_valid = len(violations) == 0

        self._log_validation_event(
            event_type="output_validation",
            original=text[:200],
            validated=validated_text[:200],
            passed=is_valid,
            violations=violations,
        )

        return ValidationResult(
            is_valid=is_valid,
            original_text=text,
            validated_text=validated_text,
            violations=violations,
            warnings=warnings,
        )

    def validate_response(self, response: str) -> str:
        """
        Convenience method — validates output and returns the validated text.
        Backward-compatible with the original guardrails_service interface.
        """
        result = self.validate_output(response)
        return result.validated_text

    def get_validation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent validation events for audit purposes."""
        return self._validation_history[-limit:]

    def get_validation_stats(self) -> Dict[str, Any]:
        """Return aggregate validation statistics."""
        total = len(self._validation_history)
        if total == 0:
            return {"total_validations": 0, "pass_rate": 1.0}

        passed = sum(1 for e in self._validation_history if e.get("passed", True))
        input_validations = sum(1 for e in self._validation_history if e["event_type"] == "input_validation")
        output_validations = sum(1 for e in self._validation_history if e["event_type"] == "output_validation")

        return {
            "total_validations": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 1.0,
            "input_validations": input_validations,
            "output_validations": output_validations,
        }

    def update_known_references(self, references: set):
        """Update the hallucination detector with known RBI references from DB."""
        self.hallucination_detector.update_known_references(references)

    def _log_validation_event(
        self,
        event_type: str,
        original: str,
        validated: str,
        passed: bool,
        violations: List[Dict],
    ):
        """Log a validation event for audit trail."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "violation_count": len(violations),
            "violations": violations,
            "original_preview": original[:100],
            "validated_preview": validated[:100],
        }

        self._validation_history.append(event)

        if self.log_violations and not passed:
            logger.warning(
                f"Guardrail violation [{event_type}]: "
                f"{len(violations)} violation(s) - "
                f"{[v.get('type', 'unknown') for v in violations]}"
            )


# Singleton instance
guardrail_service = GuardrailsService()
