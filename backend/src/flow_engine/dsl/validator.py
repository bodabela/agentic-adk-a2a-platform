"""Flow DSL Validator - validates structural integrity of parsed flows."""

from dataclasses import dataclass

from src.flow_engine.dsl.parser import ParsedFlow
from src.flow_engine.dsl.schema import (
    ParallelNode,
    TerminalNode,
)


@dataclass
class ValidationError:
    state: str
    message: str
    severity: str = "error"

    def __repr__(self):
        return f"[{self.severity}] {self.state}: {self.message}"


class FlowValidator:
    def validate(self, flow: ParsedFlow) -> list[ValidationError]:
        errors = []
        errors.extend(self._check_reachability(flow))
        errors.extend(self._check_transitions(flow))
        errors.extend(self._check_terminal_exists(flow))
        errors.extend(self._check_parallel_branches(flow))
        return errors

    def _check_transitions(self, flow: ParsedFlow) -> list[ValidationError]:
        """Ensure all transition targets reference existing states."""
        errors = []
        for name, node in flow.nodes.items():
            targets = self._get_transition_targets(node)
            for target in targets:
                if target and target not in flow.nodes:
                    # Allow dynamic targets (template expressions)
                    if "{{" not in target:
                        errors.append(
                            ValidationError(
                                name,
                                f"Transition target '{target}' does not exist",
                            )
                        )
        return errors

    def _check_reachability(self, flow: ParsedFlow) -> list[ValidationError]:
        """Check that all states are reachable from the initial state."""
        initial = flow.get_initial_state()
        visited: set[str] = set()
        self._visit(initial, flow, visited)
        errors = []
        for name in flow.nodes:
            if name not in visited:
                errors.append(
                    ValidationError(name, "State is unreachable", severity="warning")
                )
        return errors

    def _visit(self, state: str, flow: ParsedFlow, visited: set):
        if state in visited or state not in flow.nodes:
            return
        visited.add(state)
        node = flow.nodes[state]
        for target in self._get_transition_targets(node):
            if target and "{{" not in target:
                self._visit(target, flow, visited)

    def _check_terminal_exists(self, flow: ParsedFlow) -> list[ValidationError]:
        has_terminal = any(
            isinstance(n, TerminalNode) for n in flow.nodes.values()
        )
        if not has_terminal:
            return [
                ValidationError("flow", "No terminal state defined", "warning")
            ]
        return []

    def _check_parallel_branches(self, flow: ParsedFlow) -> list[ValidationError]:
        errors = []
        for name, node in flow.nodes.items():
            if isinstance(node, ParallelNode):
                if not node.branches:
                    errors.append(
                        ValidationError(name, "Parallel node has no branches")
                    )
        return errors

    def _get_transition_targets(self, node) -> list[str]:
        targets = []
        if hasattr(node, "on_complete") and node.on_complete:
            targets.append(node.on_complete)
        if hasattr(node, "on_error") and node.on_error:
            targets.append(node.on_error)
        if hasattr(node, "on_response") and node.on_response:
            targets.append(node.on_response)
        if hasattr(node, "on_event") and node.on_event:
            targets.append(node.on_event)
        if hasattr(node, "on_timeout") and node.on_timeout:
            targets.append(node.on_timeout)
        if hasattr(node, "transitions"):
            targets.extend(node.transitions.values())
        if hasattr(node, "if_true") and node.if_true:
            targets.append(node.if_true)
        if hasattr(node, "if_false") and node.if_false:
            targets.append(node.if_false)
        return [t for t in targets if t]
