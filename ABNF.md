compID = letter digit digit*
letter = "R" / "C" / "D" / "T" / "S"
digit = "0" / "1" / "2" / "3" / "4" / "5" / "6" / "7" / "8" / "9"

token = vertex operator symbol
vertex = "0" / "1" / "2" / "3" / "4" / "5" / "6" / "7"
operator = "|" / "/" / "="
symbol = "O" / "I" / "X" / "Δ"

health = ["@" time] SP integer
time = 1*DIGIT ["." 1*DIGIT]
integer = 1*DIGIT

statusLine = compID SP token SP health
statusLines = statusLine *( ";" SP statusLine )

event = "DEP" SP "@" time SP compID *( "," compID ) SP "->" SP actionCode

command = queryCmd / actCmd / resetCmd / setParamCmd / helpCmd
queryCmd = "QUERY" SP ( compID / "all" )
actCmd = "ACT" SP compID SP actionCode
resetCmd = "RESET"
setParamCmd = "SETPARAM" SP paramName SP value
helpCmd = "HELP"

actionCode = "RF" / "OPT" / "AC" / "TH" / "MG" / "MV"
paramName = "thresh" / "interval" / "token_side"
value = integer

response = ackResp / dataResp / errorResp
ackResp = "ACK" SP commandWord
dataResp = statusLines
errorResp = "ERR" SP errorCode SP message

errorCode = "1" / "2" / "3" / "4"
message = *VCHAR



parser:

import re
from typing import List, Dict, Tuple, Optional

class CompactGrammarV2:
    @staticmethod
    def parse_command(line: str) -> Tuple[str, dict]:
        """Return (command_type, args_dict)."""
        line = line.strip()
        if line.startswith("QUERY"):
            parts = line.split()
            if len(parts) == 2 and (parts[1] == "all" or re.match(r'^[A-Z]\d+$', parts[1])):
                return ("QUERY", {"target": parts[1]})
        elif line.startswith("ACT"):
            parts = line.split()
            if len(parts) == 3 and re.match(r'^[A-Z]\d+$', parts[1]) and parts[2] in ("RF","OPT","AC","TH","MG","MV"):
                return ("ACT", {"comp": parts[1], "action": parts[2]})
        elif line == "RESET":
            return ("RESET", {})
        elif line.startswith("SETPARAM"):
            parts = line.split()
            if len(parts) == 3:
                return ("SETPARAM", {"param": parts[1], "value": parts[2]})
        elif line == "HELP":
            return ("HELP", {})
        return ("ERROR", {"code": "4", "message": "syntax error"})

    @staticmethod
    def format_status(comp: str, token: str, health: int, timestamp: float = None) -> str:
        """Format a status line for response."""
        ts = f"@{timestamp:.1f} " if timestamp is not None else ""
        return f"{comp} {token} {ts}{health}"

    @staticmethod
    def format_event(timestamp: float, comps: List[str], action: str) -> str:
        return f"DEP @{timestamp:.1f} {','.join(comps)} -> {action}"

    @staticmethod
    def format_ack(cmd: str) -> str:
        return f"ACK {cmd}"

    @staticmethod
    def format_error(code: str, msg: str) -> str:
        return f"ERR {code} {msg}"
