"""Retry & Loop Manager - tracks retry loops and enforces limits."""

from src.features.flows.engine.context import FlowContext
from src.features.flows.engine.dsl.schema import FlowConfig


class RetryLimitExceeded(Exception):
    def __init__(self, loop_name: str, count: int, max_count: int):
        self.loop_name = loop_name
        self.count = count
        self.max_count = max_count
        super().__init__(f"Retry loop '{loop_name}' exceeded: {count}/{max_count}")


class RetryManager:
    def __init__(self, config: FlowConfig):
        self.max_retry_loops = config.max_retry_loops

    def check_and_increment(self, context: FlowContext, loop_name: str) -> int:
        """Increment retry counter. Raises RetryLimitExceeded if max is hit."""
        count = context.increment_retry(loop_name)
        if count > self.max_retry_loops:
            raise RetryLimitExceeded(loop_name, count, self.max_retry_loops)
        return count

    def get_count(self, context: FlowContext, loop_name: str) -> int:
        return context.get_retry_count(loop_name)
