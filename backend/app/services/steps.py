from collections.abc import Callable

from app.schemas import AgentStep


class StepLog:
    """Collects the agent steps of one answer and reports each one immediately (for live streaming)."""

    def __init__(self, on_step: Callable[[AgentStep], None] | None = None):
        self.steps: list[AgentStep] = []
        self._on_step = on_step

    def add(self, agent: str, label: str) -> None:
        step = AgentStep(agent=agent, label=label)
        self.steps.append(step)
        if self._on_step:
            self._on_step(step)
