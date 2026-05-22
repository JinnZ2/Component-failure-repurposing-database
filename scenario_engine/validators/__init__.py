"""Validators: grade claim predictions against scenario ground truth."""

from .outcome_checker import OutcomeChecker, Verdict

__all__ = ["OutcomeChecker", "Verdict"]
