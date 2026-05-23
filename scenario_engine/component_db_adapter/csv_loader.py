"""
scenario_engine.component_db_adapter.csv_loader

Loads CSV matrices from the Component-failure-repurposing-database repo
(or any directory matching its CSV schema).

Stdlib only. No pandas.
"""

import csv
import os
from typing import Dict, List, Optional


# Maps from CLAUDE.md schemas
SCHEMAS = {
    "failure_mode_matrix": [
        "Component", "Failure Mode", "Repurpose Option",
        "Effectiveness", "Notes",
    ],
    "repurpose_effectiveness": [
        "Component", "Failure Mode", "Repurpose Application",
        "Effectiveness", "Notes",
    ],
    "environmental_interactions": [
        "Component", "Condition", "Observed Effect",
        "Repurpose Impact", "Notes",
    ],
    "component_synergies": [
        "Component A", "Component B", "Synergy Effect",
        "Repurpose Application", "Notes",
    ],
}


EFFECTIVENESS_SCORE = {
    "High": 0.9,
    "Medium": 0.6,
    "Low": 0.3,
    "": 0.0,
}


def _key_for_field(field: str) -> str:
    """Normalize header field to snake_case key."""
    return field.strip().lower().replace(" ", "_")


def load_csv(path: str, matrix_name: Optional[str] = None) -> List[Dict[str, str]]:
    """Load a CSV file into list of dicts. Snake-case keys.

    Each row also carries provenance fields for traceability:
      _matrix    : the matrix name (basename without .csv, or matrix_name if given)
      _row_index : 1-based row number among data rows (header is not counted)

    These fields support source_matrix_row claim attribution downstream.
    """
    if not os.path.exists(path):
        return []
    if matrix_name is None:
        matrix_name = os.path.splitext(os.path.basename(path))[0]
    rows = []
    row_index = 0
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {}
            for k, v in raw.items():
                if k is None:
                    continue
                row[_key_for_field(k)] = (v.strip() if isinstance(v, str) else "")
            # Skip empty rows (e.g. blank lines from formatting)
            if not any(row.values()):
                continue
            row_index += 1
            # Attach effectiveness_score if effectiveness present
            if "effectiveness" in row:
                row["effectiveness_score"] = EFFECTIVENESS_SCORE.get(
                    row["effectiveness"], 0.0
                )
            row["_matrix"] = matrix_name
            row["_row_index"] = row_index
            rows.append(row)
    return rows


def load_all_matrices(matrices_dir: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Load all known matrix CSVs from a matrices directory.
    Returns dict: matrix_name -> list of row-dicts.
    Missing files yield empty lists (not errors).
    """
    out = {}
    for name in SCHEMAS:
        path = os.path.join(matrices_dir, f"{name}.csv")
        out[name] = load_csv(path, matrix_name=name)
    return out
