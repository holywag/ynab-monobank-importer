"""Pipeline: composable transaction processing via chained steps."""

from collections.abc import Callable, Iterable

from model.transaction import YnabTransaction
from model.configuration import PipelineContext

# Each step is a callable: Iterable[YnabTransaction] -> Iterable[YnabTransaction]
Step = Callable[[Iterable[YnabTransaction]], Iterable[YnabTransaction]]


class Pipeline:
    """Runs a sequence of steps over a transaction stream.

    Each step receives and returns an iterable of YnabTransactions.
    Steps are lazy (generator-based) except write_to steps which materialize.
    """

    def __init__(self, steps: list[Step]):
        self.steps = steps

    @classmethod
    def from_config(cls, step_dicts: list[dict], ctx: PipelineContext) -> 'Pipeline':
        from .steps import build_steps
        return cls(build_steps(step_dicts, ctx))

    def run(self) -> list[YnabTransaction]:
        stream: Iterable[YnabTransaction] = iter([])
        for step in self.steps:
            stream = step(stream)
        return list(stream)
