"""Validators: grade claim predictions against scenario ground truth."""

from .outcome_checker import OutcomeChecker, Verdict
from .validate import validate_prediction

__all__ = ["OutcomeChecker", "Verdict", "validate_prediction"]
