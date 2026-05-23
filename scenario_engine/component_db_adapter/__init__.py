"""
scenario_engine.component_db_adapter

Adapter onto the Component-failure-repurposing-database CSV matrices.
Stdlib-only; no pandas. Loads the failure-mode / repurpose / synergy /
environmental tables documented in the project root CLAUDE.md.
"""

from .csv_loader import (
    SCHEMAS,
    EFFECTIVENESS_SCORE,
    load_csv,
    load_all_matrices,
)
from .component_db import ComponentDB
from .adapter import ComponentDBAdapter

__all__ = [
    "SCHEMAS",
    "EFFECTIVENESS_SCORE",
    "load_csv",
    "load_all_matrices",
    "ComponentDB",
    "ComponentDBAdapter",
]
