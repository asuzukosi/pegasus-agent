from collections import deque
from typing import Any

class LoopDetector:
    def __init__(self) -> None:
        self._max_repeats = 3
        self._max_cycle_length = 3
        self._history: deque = deque(maxlen=20)

    def record_action(self, action_type: str, **details: Any):
        output = [action_type]
        if action_type == "tool_call":
            output.append(details.get("tool_name", ""))
            args = details.get("args", {})

            if isinstance(args, dict):
                for k in sorted(args.keys()):
                    output.append(f"{k}={args[k]}")
        elif action_type == "response":
            output.append(details.get("text", ""))

        signature = "|".join(output)
        self._history.append(signature)
        return signature
    
    def check_for_loop(self) -> str | None:
        if len(self._history) < 2:
            return None
        if len(self._history) >= self._max_repeats:
            recent = list(self._history)[-self._max_repeats:]
            if len(set(recent)) == 1:
                return f"same action repeated {self._max_repeats} times"
        if len(self._history) >= self._max_cycle_length * 2:
            history = list(self._history)

            for cycle_len in range(2, min(self._max_cycle_length + 1, len(history) // 2 + 1)):
                recent = history[-cycle_len * 2]
                if recent[:cycle_len] == recent[cycle_len:]:
                    return f"loop detected: {recent[:cycle_len]}"
        return None
