"""Context Accumulator - tracks state outputs and resolves template expressions."""

import re
from typing import Any

TEMPLATE_PATTERN = re.compile(r"\{\{\s*(.+?)\s*\}\}")


class FlowContext:
    """Accumulates state outputs and flow variables, resolves template expressions."""

    def __init__(self, trigger_input: dict[str, Any] | None = None):
        self.trigger = trigger_input or {}
        self.states: dict[str, dict[str, Any]] = {}
        self.flow_vars: dict[str, Any] = {
            "current_phase": "build",
            "current_source_files": None,
            "current_dependency_manifest": None,
        }
        self.retry_counts: dict[str, int] = {}
        self.history: dict[str, list[dict]] = {}
        self.cost_report: dict[str, Any] = {"total_usd": 0.0}

    def set_state_output(self, state_name: str, output: dict[str, Any]) -> None:
        """Record the output of a completed state."""
        if state_name in self.history:
            self.history[state_name].append(output)
        else:
            self.history[state_name] = [output]
        self.states[state_name] = {"output": output}

    def increment_retry(self, loop_name: str) -> int:
        """Increment and return retry count for a named loop."""
        self.retry_counts[loop_name] = self.retry_counts.get(loop_name, 0) + 1
        return self.retry_counts[loop_name]

    def get_retry_count(self, loop_name: str) -> int:
        return self.retry_counts.get(loop_name, 0)

    def set_flow_var(self, key: str, value: Any) -> None:
        """Set a flow-level variable (e.g., flow.current_source_files)."""
        if key.startswith("flow."):
            key = key[5:]
        self.flow_vars[key] = value

    def resolve(self, template: str) -> Any:
        """Resolve a template expression like '{{ states.X.output.Y }}'."""
        if not isinstance(template, str):
            return template

        match = TEMPLATE_PATTERN.fullmatch(template.strip())
        if match:
            expr = match.group(1).strip()
            return self._evaluate_expression(expr)

        # Handle inline templates within larger strings
        def replacer(m):
            result = self._evaluate_expression(m.group(1).strip())
            return str(result) if result is not None else ""

        result = TEMPLATE_PATTERN.sub(replacer, template)
        return result

    def resolve_dict(self, d: dict[str, str]) -> dict[str, Any]:
        """Resolve all template expressions in a dictionary."""
        return {k: self.resolve(v) if isinstance(v, str) else v for k, v in d.items()}

    def _evaluate_expression(self, expr: str) -> Any:
        """Evaluate a dot-notation expression against the context."""
        # Handle pipe expressions (e.g., "X | default('')")
        if "|" in expr:
            parts = expr.split("|", 1)
            main_expr = parts[0].strip()
            filter_expr = parts[1].strip()
            result = self._evaluate_expression(main_expr)
            if (result is None or result == "") and filter_expr.startswith("default("):
                default_val = filter_expr[8:-1].strip("'\"")
                return default_val
            return result

        # Handle comparison expressions (e.g., "flow.current_phase == 'operate'")
        if "==" in expr:
            left, right = expr.split("==", 1)
            left_val = self._evaluate_expression(left.strip())
            right_val = right.strip().strip("'\"")
            return left_val == right_val

        parts = expr.split(".")
        if parts[0] == "trigger":
            return self._traverse(self.trigger, parts[1:])
        elif parts[0] == "states":
            state_name = parts[1] if len(parts) > 1 else None
            if state_name and state_name in self.states:
                return self._traverse(self.states[state_name], parts[2:])
        elif parts[0] == "flow":
            key = parts[1] if len(parts) > 1 else None
            if key == "retry_count" and len(parts) > 2:
                return self.get_retry_count(parts[2])
            elif key == "history" and len(parts) > 2:
                return self.history.get(parts[2], [])
            elif key == "cost_report":
                return self.cost_report
            elif key == "config":
                return self.flow_vars.get("_config", {})
            elif key and key in self.flow_vars:
                if len(parts) > 2:
                    return self._traverse(self.flow_vars[key], parts[2:])
                return self.flow_vars[key]
        elif parts[0] == "error":
            return self.flow_vars.get("_last_error")
        elif parts[0] == "output" and len(parts) > 1:
            # Used in side_effect: "{{ output.fixed_files }}"
            last_output = self.flow_vars.get("_current_output", {})
            return self._traverse(last_output, parts[1:])
        return None

    def _traverse(self, obj: Any, path: list[str]) -> Any:
        """Navigate into a nested dict/object by dot path."""
        for key in path:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif hasattr(obj, key):
                obj = getattr(obj, key)
            else:
                return None
        return obj
