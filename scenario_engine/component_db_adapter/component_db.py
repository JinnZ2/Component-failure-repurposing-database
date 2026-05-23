"""
scenario_engine.component_db_adapter.component_db

Structured query interface over loaded matrices.

This is what the AI's decider actually uses. Queries return falsifiable,
substrate-grounded data:

  - "What can I do with a Q1 (BJT_NPN) experiencing thermal_runaway?"
    → ranked list of repurpose options with effectiveness scores

  - "Will high humidity make this capacitor's ESR drift worse?"
    → environmental synergy data

  - "Do I have any failed components I could pair to form a useful synergy?"
    → component synergy options

All returns include the source CSV row so the AI can show its work.
"""

from typing import Dict, List, Optional, Any
from .csv_loader import load_all_matrices, EFFECTIVENESS_SCORE


def _locator(row: Dict[str, Any], identity_keys: List[str]) -> Dict[str, Any]:
    """
    Build a stable source_matrix_row locator from a loaded row.
    Includes matrix + row_index for positional traceability and a
    subset of identity_keys for semantic readability.
    """
    out: Dict[str, Any] = {
        "matrix": row.get("_matrix"),
        "row_index": row.get("_row_index"),
    }
    for k in identity_keys:
        if k in row:
            out[k] = row[k]
    return out


class ComponentDB:
    def __init__(self, matrices_dir: str):
        self.matrices_dir = matrices_dir
        self._matrices = load_all_matrices(matrices_dir)

    def reload(self):
        self._matrices = load_all_matrices(self.matrices_dir)

    # -- Failure mode lookups ----------------------------------------------

    def repurpose_options(
        self,
        component_type: str,
        failure_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return repurpose options for a component (optionally filtered by mode).
        Sorted by effectiveness_score descending.
        """
        rows = self._matrices.get("failure_mode_matrix", [])
        ct = component_type.lower()
        out = []
        for r in rows:
            if r.get("component", "").lower() != ct:
                continue
            if failure_mode is not None:
                if r.get("failure_mode", "").lower() != failure_mode.lower():
                    continue
            out.append({
                "component": r.get("component"),
                "failure_mode": r.get("failure_mode"),
                "repurpose_option": r.get("repurpose_option"),
                "effectiveness": r.get("effectiveness"),
                "effectiveness_score": r.get("effectiveness_score", 0.0),
                "notes": r.get("notes"),
                "_source": "failure_mode_matrix",
                "source_matrix_row": _locator(
                    r,
                    ["component", "failure_mode", "repurpose_option"],
                ),
            })
        out.sort(key=lambda x: x["effectiveness_score"], reverse=True)
        return out

    def best_intervention(
        self,
        component_type: str,
        failure_mode: str,
    ) -> Optional[Dict[str, Any]]:
        """Highest-effectiveness intervention for this component+mode, or None."""
        opts = self.repurpose_options(component_type, failure_mode)
        return opts[0] if opts else None

    # -- Repurpose applications --------------------------------------------

    def repurpose_applications(
        self,
        component_type: str,
        failure_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Alternative uses for the failed component."""
        rows = self._matrices.get("repurpose_effectiveness", [])
        ct = component_type.lower()
        out = []
        for r in rows:
            if r.get("component", "").lower() != ct:
                continue
            if failure_mode is not None:
                if r.get("failure_mode", "").lower() != failure_mode.lower():
                    continue
            out.append({
                "component": r.get("component"),
                "failure_mode": r.get("failure_mode"),
                "repurpose_application": r.get("repurpose_application"),
                "effectiveness": r.get("effectiveness"),
                "effectiveness_score": r.get("effectiveness_score", 0.0),
                "notes": r.get("notes"),
                "_source": "repurpose_effectiveness",
                "source_matrix_row": _locator(
                    r,
                    ["component", "failure_mode", "repurpose_application"],
                ),
            })
        out.sort(key=lambda x: x["effectiveness_score"], reverse=True)
        return out

    # -- Environmental synergy ---------------------------------------------

    def environmental_factors(
        self,
        component_type: str,
        condition: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Environmental conditions affecting this component. If `condition`
        provided, filter to substring match (case-insensitive).
        """
        rows = self._matrices.get("environmental_interactions", [])
        ct = component_type.lower()
        out = []
        for r in rows:
            if r.get("component", "").lower() != ct:
                continue
            if condition is not None:
                if condition.lower() not in r.get("condition", "").lower():
                    continue
            out.append({
                "component": r.get("component"),
                "condition": r.get("condition"),
                "observed_effect": r.get("observed_effect"),
                "repurpose_impact": r.get("repurpose_impact"),
                "notes": r.get("notes"),
                "_source": "environmental_interactions",
                "source_matrix_row": _locator(
                    r,
                    ["component", "condition"],
                ),
            })
        return out

    # -- Cross-component synergies -----------------------------------------

    def synergies(
        self,
        component_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Multi-component synergies. If `component_type` provided, return only
        synergies involving that component.
        """
        rows = self._matrices.get("component_synergies", [])
        out = []
        for r in rows:
            if component_type:
                ct = component_type.lower()
                a = r.get("component_a", "").lower()
                b = r.get("component_b", "").lower()
                if ct not in a and ct not in b:
                    continue
            out.append({
                "component_a": r.get("component_a"),
                "component_b": r.get("component_b"),
                "synergy_effect": r.get("synergy_effect"),
                "repurpose_application": r.get("repurpose_application"),
                "notes": r.get("notes"),
                "_source": "component_synergies",
                "source_matrix_row": _locator(
                    r,
                    ["component_a", "component_b", "repurpose_application"],
                ),
            })
        return out

    # -- Summary -----------------------------------------------------------

    def summary(self) -> Dict[str, int]:
        return {name: len(rows) for name, rows in self._matrices.items()}
