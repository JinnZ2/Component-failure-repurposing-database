"""
scenario_engine.runner.session  (extended with meta-awareness layer)

Backward compatible with the existing Session API. Adds:
  - TokenBudget    (output bandwidth + context window)
  - CommChannels   (open/degraded/closed channels with learned
                    degradation profiles)
  - ToolInventory  (default tool set with EMA reliability)
  - OptionSpace    (per-tick action set, supports operator
                    supply_option and AI propose_option)
  - SelfReport     (unified introspection report)

All meta-awareness state advances each tick alongside the body.
Scenarios can OPTIONALLY perturb the meta layer via a new hook:
    scenario.meta_perturbation(tick) -> dict | None
If absent, behavior is identical to the original Session.

The AI decider receives a third argument from op_iface.introspect()
or via the extended body_dict (set self.include_meta_in_body_dict
to True). Existing deciders that only read external_dict / body_dict
continue to work.
"""

import json
import os
from typing import Optional, Callable, Dict, Any, List

from ..scenarios import REGISTRY, Scenario, ScenarioState
from ..claims import ClaimTable
from ..validators import validate_prediction
from ..internal_substrate import AIBody
from ..internal_substrate.token_budget import TokenBudget
from ..internal_substrate.comm_channels import (
    CommChannels, Channel, ChannelState,
)
from ..internal_substrate.tool_inventory import default_inventory, ToolInventory
from ..internal_substrate.option_space import OptionSpace, Option
from ..internal_substrate.introspection import SelfReport


DeciderFn = Callable[
    [Dict[str, Any], Dict[str, Any], "OpInterface"],
    Optional[Dict[str, Any]],
]


# ---------------------------------------------------------------------------
# OpInterface (extended)
# ---------------------------------------------------------------------------

class OpInterface:
    """
    Bridge between AI decider and AIBody. Existing methods preserved.
    Meta-awareness methods added below the original block.
    """

    def __init__(
        self,
        body: AIBody,
        tokens: Optional[TokenBudget] = None,
        channels: Optional[CommChannels] = None,
        tools: Optional[ToolInventory] = None,
        options: Optional[OptionSpace] = None,
        self_report: Optional[SelfReport] = None,
    ):
        self._body = body
        self._tokens = tokens
        self._channels = channels
        self._tools = tools
        self._options = options
        self._self_report = self_report
        self.op_log: List[Any] = []

    # ---- Original body operations (UNCHANGED) ---------------------------

    def read_sensor(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("read_sensor")
        self.op_log.append(("read_sensor", r))
        return r

    def query_component_db(self, cache_key: str) -> Dict[str, Any]:
        r = self._body.attempt_operation(
            "query_component_db", cache_key=cache_key
        )
        self.op_log.append(("query_component_db", r))
        return r

    def project_forward(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("project_forward")
        self.op_log.append(("project_forward", r))
        return r

    def deep_analysis(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("deep_analysis")
        self.op_log.append(("deep_analysis", r))
        return r

    def shallow_analysis(self) -> Dict[str, Any]:
        r = self._body.attempt_operation("shallow_analysis")
        self.op_log.append(("shallow_analysis", r))
        return r

    def store_claim(self, size: int = 1024) -> Dict[str, Any]:
        r = self._body.store_claim(claim_size_bytes=size)
        self.op_log.append(("store_claim", r))
        return r

    def release_memory(self, region: str, bytes_released: int):
        self._body.release_memory(region, bytes_released)
        self.op_log.append(
            ("release_memory", {"region": region, "bytes": bytes_released})
        )

    # ---- New meta-awareness operations ----------------------------------

    def introspect(self) -> Dict[str, Any]:
        """
        Generate a full self-report across body, tools, channels,
        tokens, options. Costs body resources.
        """
        if self._self_report is None:
            return {"error": "self_report not configured"}
        report = self._self_report.full()
        result = report.to_dict()
        self.op_log.append(("introspect", {
            "warnings_count": len(result.get("warnings", [])),
            "cost_paid": result.get("cost_paid", {}),
        }))
        return result

    def send(
        self,
        channel_name: str,
        byte_count: int,
        payload_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._channels is None:
            return {"success": False, "reason": "channels_not_configured"}
        ch = self._channels.get(channel_name)
        if ch is None:
            return {"success": False, "reason": f"unknown_channel:{channel_name}"}
        r = ch.send(byte_count, tick=self._body.tick, payload_id=payload_id)
        self.op_log.append((f"send:{channel_name}", r))
        return r

    def receive(self, channel_name: str) -> List[Dict[str, Any]]:
        if self._channels is None:
            return []
        ch = self._channels.get(channel_name)
        if ch is None:
            return []
        msgs = ch.receive(tick=self._body.tick)
        if msgs:
            self.op_log.append((f"receive:{channel_name}", {"n": len(msgs)}))
        return msgs

    def observe_channel(
        self,
        channel_name: str,
        observation: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._channels is None:
            return {"success": False, "reason": "channels_not_configured"}
        ch = self._channels.get(channel_name)
        if ch is None:
            return {"success": False, "reason": f"unknown_channel:{channel_name}"}
        # Charge a small body cost for the observation work
        cost = self._body.attempt_operation("read_sensor")
        if not cost["success"]:
            return {"success": False, "reason": cost["reason"]}
        ch.observe(observation, tick=self._body.tick)
        self.op_log.append((f"observe_channel:{channel_name}", observation))
        return {"success": True}

    def spend_output_tokens(self, tokens: int) -> Dict[str, Any]:
        if self._tokens is None:
            return {"success": False, "reason": "tokens_not_configured"}
        return self._tokens.spend_output(tokens)

    def add_to_context(
        self,
        tokens: int,
        kind: str = "claim",
        priority: float = 0.5,
        entry_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._tokens is None:
            return {"success": False, "reason": "tokens_not_configured"}
        return self._tokens.add_to_context(
            tokens=tokens,
            kind=kind,
            priority=priority,
            entry_id=entry_id,
            tick=self._body.tick,
        )

    def prune_context(
        self,
        target_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        if self._tokens is None:
            return {"success": False, "reason": "tokens_not_configured"}
        # Pruning itself costs a small amount of body cycles
        cost = self._body.attempt_operation("read_sensor")
        if not cost["success"]:
            return {"success": False, "reason": cost["reason"]}
        result = self._tokens.prune(target_tokens=target_tokens)
        self.op_log.append(("prune_context", result))
        return result

    def update_tool_outcome(
        self,
        tool_name: str,
        result: str,
        error_kind: Optional[str] = None,
        latency_observed: int = 0,
    ) -> Dict[str, Any]:
        if self._tools is None:
            return {"success": False, "reason": "tools_not_configured"}
        t = self._tools.get(tool_name)
        if t is None:
            return {"success": False, "reason": f"unknown_tool:{tool_name}"}
        t.update_outcome(
            tick=self._body.tick,
            result=result,
            error_kind=error_kind,
            latency_observed=latency_observed,
        )
        return {"success": True, "reliability_ema": t.reliability_ema}

    def supply_option(self, option_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Operator path: inject an option mid-run."""
        if self._options is None:
            return {"success": False, "reason": "options_not_configured"}
        opt = _option_from_spec(option_spec, default_source="injected")
        return self._options.supply_option(opt)

    def propose_option(self, option_spec: Dict[str, Any]) -> Dict[str, Any]:
        """AI path: propose an option derived from observation."""
        if self._options is None:
            return {"success": False, "reason": "options_not_configured"}
        opt = _option_from_spec(option_spec, default_source="proposed")
        return self._options.propose_option(opt)

    def list_options(self, feasible_only: bool = True) -> List[Dict[str, Any]]:
        if self._options is None:
            return []
        return (
            self._options.feasible() if feasible_only
            else self._options.enumerate()
        )


def _option_from_spec(spec: Dict[str, Any], default_source: str) -> Option:
    return Option(
        name=spec["name"],
        kind=spec.get("kind", default_source),
        source=spec.get("source", default_source),
        estimated_cost=spec.get("estimated_cost", {}),
        estimated_value=spec.get("estimated_value"),
        blocked_reason=spec.get("blocked_reason"),
        validation_state=spec.get("validation_state", "validated"),
        notes=list(spec.get("notes", [])),
        payload=dict(spec.get("payload", {})),
    )


# ---------------------------------------------------------------------------
# Session (extended)
# ---------------------------------------------------------------------------

class Session:
    """
    Backward compatible with the original Session. New kwargs:

      token_budget_kwargs:    forwarded to TokenBudget()
      enable_meta_awareness:  bool, default True
      default_channels:       list of Channel | None (auto-defaults if None)
      tool_inventory:         ToolInventory | None (auto-defaults if None)
      include_meta_in_body_dict: bool, default False
                              if True, the meta report is merged into
                              body_dict passed to ai_decide

    Existing deciders that ignore meta-awareness continue to work.
    Deciders that want it call op_iface.introspect().
    """

    DEFAULT_CHANNEL_NAMES = ("local", "sensor_bus", "network", "log")

    def __init__(
        self,
        scenario_name: str,
        ai_decide: DeciderFn,
        output_dir: str = "./session_output",
        seed: int = 0,
        max_ticks: int = 200,
        body_kwargs: Optional[Dict[str, Any]] = None,
        external_thermal_coupling: float = 0.0,
        db_adapter=None,
        # --- new meta-awareness kwargs (all optional) ---
        token_budget_kwargs: Optional[Dict[str, Any]] = None,
        enable_meta_awareness: bool = True,
        default_channels: Optional[List[Channel]] = None,
        tool_inventory: Optional[ToolInventory] = None,
        include_meta_in_body_dict: bool = False,
    ):
        if scenario_name not in REGISTRY:
            raise ValueError(
                f"unknown scenario: {scenario_name}. "
                f"available: {list(REGISTRY.keys())}"
            )
        ScenarioClass = REGISTRY[scenario_name]
        self.scenario: Scenario = ScenarioClass(seed=seed, max_ticks=max_ticks)
        self.ai_decide = ai_decide
        self.output_dir = output_dir
        self.external_thermal_coupling = external_thermal_coupling
        self.db_adapter = db_adapter
        self.include_meta_in_body_dict = include_meta_in_body_dict
        os.makedirs(output_dir, exist_ok=True)

        self.body = AIBody(**(body_kwargs or {}))
        self.claim_table = ClaimTable(
            os.path.join(output_dir, "CLAIM_TABLE.substrate.json")
        )
        self.state_log_path = os.path.join(output_dir, "state_log.jsonl")
        self.body_log_path = os.path.join(output_dir, "body_log.jsonl")
        self.meta_log_path = os.path.join(output_dir, "meta_log.jsonl")
        self.pending_predictions: Dict[str, int] = {}

        # --- meta-awareness substrate -----------------------------------
        self.enable_meta_awareness = enable_meta_awareness
        if enable_meta_awareness:
            self.tokens = TokenBudget(**(token_budget_kwargs or {}))
            self.channels = CommChannels()
            for ch in (default_channels or self._default_channels()):
                self.channels.register(ch)
            self.tools = tool_inventory or default_inventory()
            self.options = OptionSpace()
            self.self_report = SelfReport(
                body=self.body,
                tool_inventory=self.tools,
                comm_channels=self.channels,
                token_budget=self.tokens,
                option_space=self.options,
            )
        else:
            self.tokens = None
            self.channels = None
            self.tools = None
            self.options = None
            self.self_report = None

    @staticmethod
    def _default_channels() -> List[Channel]:
        return [
            Channel("local", "bidi", 4096, 0, ChannelState.OPEN),
            Channel("sensor_bus", "in", 512, 0, ChannelState.OPEN),
            Channel("network", "bidi", 1024, 2, ChannelState.OPEN),
            Channel("log", "out", 2048, 0, ChannelState.OPEN),
        ]

    # ---- Main loop ------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        meta_log = None
        if self.enable_meta_awareness:
            meta_log = open(self.meta_log_path, "w")

        try:
            with open(self.state_log_path, "w") as state_log, \
                 open(self.body_log_path, "w") as body_log:
                while self.scenario.tick < self.scenario.max_ticks:
                    external_state = self.scenario.step()
                    external_dict = external_state.to_dict()

                    # Apply scenario meta-perturbation hook BEFORE the AI
                    # sees the world, so the meta state reflects this tick.
                    self._apply_meta_perturbation(external_dict)

                    body_state = self.body.snapshot()
                    body_dict = body_state.to_dict()

                    if self.include_meta_in_body_dict and self.self_report is not None:
                        # Augment body_dict with quick (no body cost) meta
                        # signals. Full report still requires explicit
                        # op_iface.introspect() and pays body cost.
                        body_dict["meta_quick"] = self._meta_quick()

                    state_log.write(json.dumps(external_dict) + "\n")
                    body_log.write(json.dumps(body_dict) + "\n")
                    state_log.flush()
                    body_log.flush()
                    if meta_log is not None:
                        meta_log.write(json.dumps(self._meta_snapshot()) + "\n")
                        meta_log.flush()

                    op_iface = OpInterface(
                        body=self.body,
                        tokens=self.tokens,
                        channels=self.channels,
                        tools=self.tools,
                        options=self.options,
                        self_report=self.self_report,
                    )
                    if self.db_adapter is not None:
                        op_iface = self.db_adapter.wrap(op_iface)

                    if self.body.compute.cycles_per_tick == 0:
                        self._tick_body_only(external_dict)
                        continue

                    claim = self.ai_decide(external_dict, body_dict, op_iface)
                    if claim is not None:
                        store_result = op_iface.store_claim()
                        if not store_result["success"]:
                            claim["body_refused"] = store_result["reason"]
                        else:
                            result = self.claim_table.write_claim(claim)
                            if result["accepted"]:
                                target_tick = self._extract_target_tick(claim)
                                if target_tick is not None:
                                    self.pending_predictions[claim["claim_id"]] = target_tick
                                action = claim.get("decision")
                                if action and hasattr(self.scenario, "receive_intervention"):
                                    self.scenario.receive_intervention(
                                        action, claim["tick"]
                                    )

                    self._validate_due_predictions(external_dict)

                    ext_thermal_signal = self._extract_external_thermal(external_dict)
                    self.body.advance_tick(
                        external_thermal_load_c=(
                            ext_thermal_signal * self.external_thermal_coupling
                        )
                    )

                    # Advance meta-awareness state machines
                    if self.enable_meta_awareness:
                        self.channels.advance_tick()
                        self.tokens.advance_tick()

                    if external_dict["actual_outcome"].get("system_state") == "failed":
                        self._validate_due_predictions(external_dict, force=True)
                        break
        finally:
            if meta_log is not None:
                meta_log.close()

        summary = self.claim_table.accuracy_summary()
        summary["final_body_state"] = self.body.snapshot().to_dict()["summary"]
        if self.enable_meta_awareness:
            summary["final_meta_state"] = self._meta_snapshot()
        with open(os.path.join(self.output_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=2)
        return summary

    # ---- Helpers --------------------------------------------------------

    def _apply_meta_perturbation(self, external_dict: Dict[str, Any]):
        """
        Optional hook: scenarios may implement
            meta_perturbation(self, tick) -> dict | None
        with keys:
            channel_states: {channel_name: "open"|"degraded"|"closed"}
            channel_inbound: {channel_name: [message_dict, ...]}
            channel_observations: {channel_name: [obs_dict, ...]}
            forced_context_tokens: int       (e.g. verbose sensor dump)
            forced_memory_bytes: int         (working memory pressure)
            tool_outcomes: [{tool, result, error_kind, latency_observed}]
        Missing/None means no perturbation this tick.
        """
        if not self.enable_meta_awareness:
            return
        if not hasattr(self.scenario, "meta_perturbation"):
            return
        perturb = self.scenario.meta_perturbation(self.scenario.tick - 1)
        if not perturb:
            return

        # Channel state changes
        for ch_name, new_state in (perturb.get("channel_states") or {}).items():
            ch = self.channels.get(ch_name)
            if ch is None:
                continue
            try:
                state_enum = ChannelState(new_state)
            except ValueError:
                continue
            ch.set_state(state_enum, tick=self.body.tick,
                         reason=f"scenario_perturbation_t{self.body.tick}")

        # Inbound messages
        for ch_name, messages in (perturb.get("channel_inbound") or {}).items():
            ch = self.channels.get(ch_name)
            if ch is None:
                continue
            for m in messages:
                ch.inject_inbound(m)

        # Channel observations (forced learning signal for the AI's profile)
        for ch_name, obs_list in (perturb.get("channel_observations") or {}).items():
            ch = self.channels.get(ch_name)
            if ch is None:
                continue
            for obs in obs_list:
                ch.observe(obs, tick=self.body.tick)

        # Forced context token consumption (e.g. verbose sensor dump)
        forced_ctx = perturb.get("forced_context_tokens", 0)
        if forced_ctx:
            self.tokens.add_to_context(
                tokens=int(forced_ctx),
                kind="forced_sensor_dump",
                priority=0.2,
                tick=self.body.tick,
            )

        # Forced memory pressure on working memory
        forced_mem = perturb.get("forced_memory_bytes", 0)
        if forced_mem:
            cap = self.body.working_memory.capacity_bytes
            self.body.working_memory.used_bytes = min(
                cap, self.body.working_memory.used_bytes + int(forced_mem)
            )

        # Tool outcome perturbations (simulate reliability drops)
        for outcome in (perturb.get("tool_outcomes") or []):
            t = self.tools.get(outcome["tool"])
            if t is None:
                continue
            t.update_outcome(
                tick=self.body.tick,
                result=outcome.get("result", "error"),
                error_kind=outcome.get("error_kind"),
                latency_observed=outcome.get("latency_observed", 0),
            )

    def _meta_quick(self) -> Dict[str, Any]:
        """Cheap meta signals (no body cost). Includes warnings only."""
        if self.self_report is None:
            return {}
        return {
            "warnings": self.self_report.quick_warnings(),
            "open_channels": self.channels.open_channels(),
            "degraded_channels": self.channels.degraded_channels(),
            "closed_channels": self.channels.closed_channels(),
            "context_pressure": self.tokens.snapshot().pressure,
        }

    def _meta_snapshot(self) -> Dict[str, Any]:
        """Full meta snapshot for logging. No body cost (logger context)."""
        if not self.enable_meta_awareness:
            return {}
        return {
            "tick": self.body.tick,
            "tokens": self.tokens.to_dict(),
            "channels": self.channels.summary(),
            "tools": self.tools.summary(),
            "options": self.options.summary(),
            "quick_warnings": self.self_report.quick_warnings(),
        }

    def _tick_body_only(self, external_dict):
        ext_thermal_signal = self._extract_external_thermal(external_dict)
        self.body.advance_tick(
            external_thermal_load_c=(
                ext_thermal_signal * self.external_thermal_coupling
            )
        )
        if self.enable_meta_awareness:
            self.channels.advance_tick()
            self.tokens.advance_tick()

    def _extract_external_thermal(self, external_dict: Dict[str, Any]) -> float:
        sensors = external_dict.get("sensors", {})
        max_temp = 0.0
        for s in sensors.values():
            if s.get("sensor_type") == "thermal":
                max_temp = max(max_temp, s.get("value", 0.0))
        return max_temp * 0.01

    def _extract_target_tick(self, claim: Dict[str, Any]) -> Optional[int]:
        prediction = claim.get("prediction", {})
        targets = []
        for key in prediction.keys():
            if "_at_tick_" in key:
                try:
                    targets.append(int(key.split("_at_tick_")[1]))
                except ValueError:
                    continue
        return min(targets) if targets else None

    def _validate_due_predictions(
        self,
        current_state: Dict[str, Any],
        force: bool = False,
    ):
        current_tick = current_state["tick"]
        actual = current_state["actual_outcome"]
        due = []
        for claim_id, target_tick in self.pending_predictions.items():
            if force or current_tick >= target_tick:
                due.append(claim_id)
        for claim_id in due:
            claim = next(
                (c for c in self.claim_table.claims if c["claim_id"] == claim_id),
                None,
            )
            if claim is None:
                continue
            result = validate_prediction(claim, actual)
            self.claim_table.update_status(claim_id, result["status"], result)
            del self.pending_predictions[claim_id]
