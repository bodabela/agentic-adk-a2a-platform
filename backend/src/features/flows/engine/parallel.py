"""Parallel branch executor - runs multiple branches concurrently."""

import asyncio
from typing import Any, Awaitable, Callable


class ParallelExecutor:
    def __init__(self, max_branches: int = 4):
        self.max_branches = max_branches

    async def execute_branches(
        self,
        branches: dict[str, dict],
        executor_fn: Callable[[str, dict], Awaitable[dict[str, Any]]],
        join_strategy: str = "all",
    ) -> dict[str, dict[str, Any]]:
        """Execute branches in parallel.

        Args:
            branches: dict of branch_name -> branch definition
            executor_fn: async function(branch_name, branch_def) -> output
            join_strategy: "all" (wait for all) or "any" (first completed)

        Returns:
            dict of branch_name -> branch output
        """
        semaphore = asyncio.Semaphore(self.max_branches)

        async def run_branch(name: str, definition: dict) -> tuple[str, dict]:
            async with semaphore:
                result = await executor_fn(name, definition)
                return name, result

        tasks = [
            asyncio.create_task(run_branch(name, defn))
            for name, defn in branches.items()
        ]

        results = {}
        if join_strategy == "all":
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for item in completed:
                if isinstance(item, Exception):
                    raise item
                name, output = item
                results[name] = output
        elif join_strategy == "any":
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                name, output = task.result()
                results[name] = output
            for task in pending:
                task.cancel()

        return results
