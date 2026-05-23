"""
scenario_engine.continual_harness.persistence.claim_history

Cross-session claim accumulation.

ClaimTable is session-scoped. ClaimHistory is run-scoped.
Every claim from every session lands here, tagged with
session_id and scenario_name.

The AI can read this and learn from its own track record.
"""

import json
import os
from typing import Dict, Any, List, Optional


class ClaimHistory:
    def __init__(self, path: str):
        self.path = path
        self.records: List[Dict[str, Any]] = []
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path):
            with open(path, "r") as f:
                self.records = json.load(f)

    def add_session_claims(
        self,
        session_id: str,
        scenario_name: str,
        claims: List[Dict[str, Any]],
    ):
        for claim in claims:
            record = dict(claim)
            record["_session_id"] = session_id
            record["_scenario_name"] = scenario_name
            self.records.append(record)
        self._flush()

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.records)

    def get_by_scenario(self, scenario_name: str) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get("_scenario_name") == scenario_name]

    def get_recent(self, n: int) -> List[Dict[str, Any]]:
        return self.records[-n:]

    def accuracy_overall(self) -> Dict[str, Any]:
        total = len(self.records)
        v = sum(1 for r in self.records if r.get("status") == "VALIDATED")
        i = sum(1 for r in self.records if r.get("status") == "INVALIDATED")
        p = sum(1 for r in self.records if r.get("status") == "PARTIAL")
        pend = sum(1 for r in self.records if r.get("status") == "pending")
        return {
            "total": total,
            "validated": v,
            "invalidated": i,
            "partial": p,
            "pending": pend,
            "accuracy": (v / total) if total else 0.0,
        }

    def accuracy_by_scenario(self) -> Dict[str, Dict[str, Any]]:
        out = {}
        scenarios = set(r.get("_scenario_name") for r in self.records)
        for s in scenarios:
            if s is None:
                continue
            recs = [r for r in self.records if r.get("_scenario_name") == s]
            total = len(recs)
            v = sum(1 for r in recs if r.get("status") == "VALIDATED")
            out[s] = {
                "total": total,
                "validated": v,
                "accuracy": (v / total) if total else 0.0,
            }
        return out

    def rolling_window(self, window: int = 20) -> List[Dict[str, Any]]:
        """
        Return per-claim records with rolling accuracy.
        Useful for plotting learning curve.
        """
        out = []
        for i, r in enumerate(self.records):
            window_recs = self.records[max(0, i - window + 1): i + 1]
            window_total = len(window_recs)
            window_v = sum(
                1 for x in window_recs if x.get("status") == "VALIDATED"
            )
            out.append({
                "claim_index": i,
                "claim_id": r.get("claim_id"),
                "status": r.get("status"),
                "scenario": r.get("_scenario_name"),
                "session": r.get("_session_id"),
                "rolling_accuracy": (window_v / window_total) if window_total else 0.0,
                "window_size": window_total,
            })
        return out

    def _flush(self):
        with open(self.path, "w") as f:
            json.dump(self.records, f, indent=2)
