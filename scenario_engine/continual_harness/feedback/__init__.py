"""
scenario_engine.continual_harness.feedback

Corrective signal layer: reads accumulated claim history and detects
systematic patterns the AI itself is not seeing. Outputs are structural
facts about the claim record — no narrative interpretation.
"""

from .pattern_extractor import (
    by_scenario_accuracy,
    by_decision_accuracy,
    numeric_error_distribution,
    systematic_bias,
    recurring_failure_pattern,
    db_effectiveness_audit,
    signed_bias_from_outcomes,
    extract_all_patterns,
)
from .state_prediction_calibration import (
    STATE_VALUES,
    confusion_matrix,
    state_accuracy,
    systematic_state_bias,
    recommend_threshold_adjustment,
)

__all__ = [
    "by_scenario_accuracy",
    "by_decision_accuracy",
    "numeric_error_distribution",
    "systematic_bias",
    "recurring_failure_pattern",
    "db_effectiveness_audit",
    "signed_bias_from_outcomes",
    "extract_all_patterns",
    "STATE_VALUES",
    "confusion_matrix",
    "state_accuracy",
    "systematic_state_bias",
    "recommend_threshold_adjustment",
]
