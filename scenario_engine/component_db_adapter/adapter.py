"""
scenario_engine.component_db_adapter.adapter

Wire-in: connect ComponentDB to the AIBody's query_component_db op.

The existing OpInterface.query_component_db returned only a body-cost
result. This adapter wraps it so the AI gets BOTH:
  - cost result (cycles, memory, cache_hit) — still real body cost
  - data result (component characteristics from CSV-backed DB)

The AI's decider can now make repurposing decisions grounded in
your verified component knowledge, not just generic heuristics.
"""

import os
from typing import Dict, Any, Optional, List

from .component_db import ComponentDB


# Default sample data location bundled with the adapter
_DEFAULT_SAMPLE_DIR = os.path.join(
    os.path.dirname(__file__), "sample_data"
)


class ComponentDBAdapter:
    """
    Wraps an OpInterface to inject DB query results.

    Usage:

        from scenario_engine.runner import OpInterface
        from scenario_engine.component_db_adapter import ComponentDBAdapter

        adapter = ComponentDBAdapter(matrices_dir="/path/to/Component-failure-repurposing-database/matrices")
        # or: adapter = ComponentDBAdapter()  # uses bundled sample_data

        # In session loop, after creating op_iface:
        op_iface = OpInterface(body)
        wrapped = adapter.wrap(op_iface)
        # Pass `wrapped` to ai_decide instead of `op_iface`
    """

    def __init__(self, matrices_dir: Optional[str] = None):
        if matrices_dir is None:
            matrices_dir = _DEFAULT_SAMPLE_DIR
        if not os.path.isdir(matrices_dir):
            raise ValueError(f"matrices_dir does not exist: {matrices_dir}")
        self.matrices_dir = matrices_dir
        self.db = ComponentDB(matrices_dir)

    def wrap(self, op_iface):
        """Return a wrapped op interface with DB-augmented query."""
        return _WrappedOpInterface(op_iface, self.db)


class _WrappedOpInterface:
    """
    Delegates to the underlying OpInterface for all body operations.
    Overrides query_component_db to also return DB data.
    """

    def __init__(self, op_iface, db: ComponentDB):
        self._op = op_iface
        self._db = db

    def __getattr__(self, name):
        # Delegate any unknown attribute to the wrapped op interface
        return getattr(self._op, name)

    def query_component_db(
        self,
        cache_key: str,
        component_type: Optional[str] = None,
        failure_mode: Optional[str] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Body cost as before, PLUS structured DB lookup.

        Parameters:
          cache_key       : same as before, used for body cache accounting
          component_type  : e.g. "BJT_NPN", "electrolytic_cap"
          failure_mode    : e.g. "thermal_runaway", "ESR_drift"
          include         : list of result types to fetch. Options:
                              "repurpose_options" (default)
                              "repurpose_applications"
                              "environmental"
                              "synergies"
                              "best"
                            If None, returns ["repurpose_options", "best"].

        Returns:
          {
            # body-cost fields (from underlying op)
            "success": bool,
            "cycles_used": int,
            "memory_used": int,
            "cache_hit": bool,
            # DB-augmented fields
            "db": {
              "repurpose_options": [...],
              "best": {...},
              "environmental": [...],
              "synergies": [...],
              "queried_component": "BJT_NPN",
              "queried_failure_mode": "thermal_runaway",
            } | None if cost call failed
          }
        """
        cost = self._op.query_component_db(cache_key)
        result = dict(cost)

        if not cost.get("success"):
            result["db"] = None
            return result

        if component_type is None:
            result["db"] = {
                "warning": "no component_type provided; DB not queried",
            }
            return result

        if include is None:
            include = ["repurpose_options", "best"]

        db_out: Dict[str, Any] = {
            "queried_component": component_type,
            "queried_failure_mode": failure_mode,
        }

        if "repurpose_options" in include:
            db_out["repurpose_options"] = self._db.repurpose_options(
                component_type, failure_mode
            )
        if "best" in include:
            if failure_mode is None:
                db_out["best"] = None
            else:
                db_out["best"] = self._db.best_intervention(
                    component_type, failure_mode
                )
        if "repurpose_applications" in include:
            db_out["repurpose_applications"] = self._db.repurpose_applications(
                component_type, failure_mode
            )
        if "environmental" in include:
            db_out["environmental"] = self._db.environmental_factors(
                component_type
            )
        if "synergies" in include:
            db_out["synergies"] = self._db.synergies(component_type)

        result["db"] = db_out
        return result
