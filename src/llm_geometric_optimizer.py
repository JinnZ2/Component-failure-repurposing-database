#!/usr/bin/env python3
"""
LLM Geometric Optimizer
=======================
Provides a compact, token‑efficient protocol for LLMs to interact with
the Geometric Monitoring System.

Grammar:
  - Component: R(esistor), C(apacitor), D(iode), T(ransistor), S(sensor)
  - Token: vertex(0-7) + op(| = radial, / = tangential, = = nested) + symbol(O,I,X,Δ)
  - Health: integer 0-100 (optional)
  - Event: DEP @time comp1 comp2 ... -> action
  - Commands: ACT <comp> <action>, QUERY <comp>, RESET, SETPARAM <param> <value>
"""

import re
from typing import Dict, Optional, Tuple

# ----------------------------------------------------------------------
# 1. Compact Grammar Mappings
# ----------------------------------------------------------------------
COMPONENT_MAP = {
    "resistor": "R",
    "capacitor": "C",
    "diode": "D",
    "transistor": "T",
    "sensor": "S"
}
REVERSE_COMP_MAP = {v: k for k, v in COMPONENT_MAP.items()}

# Operator mapping: compact form -> full operator
OP_MAP = {
    "|": "radial",
    "/": "tangential",
    "=": "nested"   # for || 
}
REVERSE_OP_MAP = {v: k for k, v in OP_MAP.items()}

# Symbol mapping (already single char)
SYMBOLS = {"O", "I", "X", "Δ"}

# Action mapping for repurpose commands (short codes)
ACTION_MAP = {
    "RF": "rf_beacon",
    "OPT": "optical_fallback",
    "AC": "acoustic_alarm",
    "TH": "thermal_heater",
    "MG": "magnetic_coupling",
    "MV": "mechanical_vibration"
}
REVERSE_ACTION_MAP = {v: k for k, v in ACTION_MAP.items()}

# ----------------------------------------------------------------------
# 2. Compact Representation Functions
# ----------------------------------------------------------------------
def geometry_to_compact(geometry: dict) -> str:
    """
    Convert geometry dict (from HardwareBridgeEncoder) to compact string.
    Example: {"component_type":"resistor", "geometric_token":"001|O", "health_score":0.85}
    -> "R1|O 85"
    """
    comp_type = geometry.get("component_type", "").lower()
    comp = COMPONENT_MAP.get(comp_type, "?")
    token = geometry.get("geometric_token", "0|O")
    # token may have leading zeros like "001|O" -> strip to "1|O" but keep as is for consistency
    # Remove leading zeros from vertex part (optional, saves tokens)
    if token[0] == '0':
        # Strip leading zeros but keep at least one digit
        vertex_part = token.split('|')[0].lstrip('0') or '0'
        rest = token[len(token.split('|')[0]):]  # includes | and symbol
        token = vertex_part + rest
    health = int(geometry.get("health_score", 1.0) * 100)
    return f"{comp}{token} {health}"

def compact_to_geometry(compact: str) -> dict:
    """
    Parse compact string back to geometry dict.
    Input: "R1|O 85" -> {"component_type":"resistor", "geometric_token":"1|O", "health_score":0.85}
    """
    parts = compact.strip().split()
    if len(parts) < 1:
        return {}
    comp_token = parts[0]
    health = int(parts[1]) if len(parts) > 1 else 100
    # Extract component letter and token
    # Component is first character
    comp_letter = comp_token[0]
    token = comp_token[1:]
    # Reconstruct full token with 3-bit vertex if needed (optional)
    # Here we keep as is
    comp_type = REVERSE_COMP_MAP.get(comp_letter, "unknown")
    return {
        "component_type": comp_type,
        "geometric_token": token,
        "health_score": health / 100.0
    }

def dependency_to_compact(timestamp: float, components: list, action: str) -> str:
    """Format dependency event."""
    comp_str = " ".join(components)
    action_code = REVERSE_ACTION_MAP.get(action, action.upper())
    return f"DEP @{timestamp:.1f} {comp_str} -> {action_code}"

def command_to_compact(command: str, target: str = "", param: str = "", value: str = "") -> str:
    """Generate compact command string."""
    cmd = command.upper()
    if cmd == "ACT":
        return f"ACT {target} {param}"  # param = action code
    elif cmd == "QUERY":
        return f"QUERY {target}"
    elif cmd == "RESET":
        return "RESET"
    elif cmd == "SETPARAM":
        return f"SETPARAM {param} {value}"
    else:
        return ""

# ----------------------------------------------------------------------
# 3. LLM Prompt Template (compact & token‑efficient)
# ----------------------------------------------------------------------
LLM_PROMPT = """You are an interface to a geometric monitoring system. Use compact codes:

Components: R(esistor), C(apacitor), D(iode), T(ransistor), S(sensor)
Token: vertex(0-7) + op(|=radial, /=tangential, ==nested) + symbol(O,I,X,Δ)
Health: integer 0-100 after token
Event: DEP @time comp1 comp2 ... -> action (RF,OPT,AC,TH,MG,MV)
Commands: ACT <comp> <action>, QUERY <comp>, RESET, SETPARAM <param> <value>

Example input: "R1|O 85" -> resistor R1 token 1|O health 85%
Example dependency: "DEP 12.3 R1 C2 -> RF"
Respond with compact commands only. Keep responses under 20 tokens.

Now process:"""

# ----------------------------------------------------------------------
# 4. Natural Language to Compact Translator (for LLMs that don't follow prompt)
# ----------------------------------------------------------------------
def nl_to_compact(nl_text: str) -> str:
    """
    Convert natural language request to compact command.
    Simple keyword matching – can be extended with an LLM call.
    """
    text = nl_text.lower()
    if "repurpose" in text or "fallback" in text:
        # Find component like "resistor R1" or just "R1"
        comp_match = re.search(r'\b(r\d+|c\d+|d\d+|t\d+|s\d+)\b', text, re.IGNORECASE)
        if comp_match:
            comp = comp_match.group(1).upper()
        else:
            comp = "R1"  # default
        # Find action
        if "rf" in text or "radio" in text:
            action = "RF"
        elif "optical" in text or "led" in text:
            action = "OPT"
        elif "acoustic" in text or "buzzer" in text:
            action = "AC"
        elif "thermal" in text or "heat" in text:
            action = "TH"
        elif "magnetic" in text:
            action = "MG"
        elif "vibration" in text or "motor" in text:
            action = "MV"
        else:
            action = "RF"
        return f"ACT {comp} {action}"
    elif "status" in text or "health" in text:
        comp_match = re.search(r'\b(r\d+|c\d+|d\d+|t\d+|s\d+)\b', text, re.IGNORECASE)
        if comp_match:
            return f"QUERY {comp_match.group(1).upper()}"
        else:
            return "QUERY all"
    elif "reset" in text:
        return "RESET"
    else:
        return ""

# ----------------------------------------------------------------------
# 5. Integration with GeometricMonitoringSystem (example)
# ----------------------------------------------------------------------
class LLMGeometricBridge:
    """
    Bridges an LLM (e.g., via API or local inference) to the monitoring system.
    Uses compact commands to minimize token usage.
    """
    def __init__(self, monitoring_system):
        self.system = monitoring_system
        self.conversation_history = []  # store compact strings

    def process_llm_output(self, llm_output: str) -> str:
        """
        Parse LLM output (should be compact command). Execute and return response.
        """
        llm_output = llm_output.strip()
        if llm_output.startswith("QUERY"):
            parts = llm_output.split()
            if len(parts) > 1 and parts[1] != "all":
                comp = parts[1]
                # Retrieve health from system (simplified)
                # In real system, you'd query the component registry
                health = 85  # mock
                return f"{comp} 85"  # compact health response
            else:
                # Return all components
                return "SYS 3 2\nCOMPS: R1:85, C1:67"
        elif llm_output.startswith("ACT"):
            parts = llm_output.split()
            if len(parts) >= 3:
                comp = parts[1]
                action_code = parts[2]
                action = ACTION_MAP.get(action_code, action_code.lower())
                # Execute repurpose action
                self.system._execute_repurpose(comp, action)  # assume method exists
                return f"ACK {action_code}"
        elif llm_output == "RESET":
            # Reset system (clear history)
            return "RESET OK"
        elif llm_output.startswith("SETPARAM"):
            # Handle parameter setting
            return "OK"
        else:
            return "ERR unknown command"

    def get_prompt(self) -> str:
        """Return the system prompt to give to the LLM."""
        return LLM_PROMPT

# ----------------------------------------------------------------------
# 6. Demo
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("LLM Geometric Optimizer Demo")
    print("=" * 50)
    print("Prompt to give LLM:\n")
    print(LLM_PROMPT)
    print("\n" + "=" * 50)
    print("Example conversions:")
    geo = {"component_type": "resistor", "geometric_token": "001|O", "health_score": 0.85}
    compact = geometry_to_compact(geo)
    print(f"Geometry -> Compact: {compact}")
    back = compact_to_geometry(compact)
    print(f"Compact -> Geometry: {back}")
    print(f"Dependency event: {dependency_to_compact(12.34, ['R1','C2'], 'rf_beacon')}")
    print(f"NL to compact: {nl_to_compact('repurpose resistor R1 using RF')}")
    print("\nSimulated LLM interaction:")
    bridge = LLMGeometricBridge(None)
    print("User: What's the health of R1?")
    llm_out = "QUERY R1"
    resp = bridge.process_llm_output(llm_out)
    print(f"LLM output: {llm_out}\nSystem response: {resp}")
