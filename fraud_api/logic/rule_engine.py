from abc import ABC, abstractmethod
from typing import Dict, Generic, List, TypeVar

RuleType = TypeVar('RuleType')
ResultType = TypeVar('ResultType')


class RuleEngine(ABC, Generic[RuleType, ResultType]):
    def __init__(self):
        self.rules: List[RuleType] = []

    def add_rule(self, rule: RuleType) -> None:
        self.rules.append(rule)
        self._sort_rules()

    def _sort_rules(self) -> None:
        self.rules.sort(key=lambda r: getattr(r, 'priority', 0), reverse=True)

    @abstractmethod
    def evaluate(self, payload: Dict, context: Dict) -> List[ResultType]:
        raise NotImplementedError
