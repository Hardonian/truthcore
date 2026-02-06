"""Extended Invariant DSL with boolean composition and explain mode.

Provides rich rule composition:
- Boolean operators: all, any, not
- Thresholds and comparisons
- Aggregations: count, rate, avg, max, min
- Explain mode for debugging

Determinism guarantees:
- Rules are evaluated in declaration order (array position)
- Batch evaluation sorts rules by ID for stable ordering
- Filter specs iterate keys in sorted order
- Tie-breaking: alphabetical by rule_id, then by declaration order
- Each evaluation step has a stable sequence number
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any

# Operator mapping
OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


@dataclass
class RuleEvaluation:
    """Result of evaluating a rule with full evidence."""

    rule_id: str
    passed: bool
    operator: str
    left_value: Any
    right_value: Any
    sequence: int = 0  # Stable evaluation order counter
    context: dict[str, Any] = field(default_factory=dict)
    sub_evaluations: list[RuleEvaluation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert evaluation to dictionary."""
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "operator": self.operator,
            "left_value": self.left_value,
            "right_value": self.right_value,
            "sequence": self.sequence,
            "context": self.context,
            "sub_evaluations": [e.to_dict() for e in self.sub_evaluations],
        }


class InvariantDSL:
    """Domain-specific language for invariant rules.

    Determinism: evaluation order is stable. Rules within composite
    operators (all/any) are evaluated in array order. The batch
    evaluate_rules() method sorts by rule ID for predictable ordering.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize with data context.

        Args:
            data: Dictionary containing values to evaluate against
        """
        self.data = data
        self.explain_mode = False
        self.evaluations: list[RuleEvaluation] = []
        self._eval_sequence = 0  # Monotonic counter for evaluation order

    def set_explain_mode(self, enabled: bool = True) -> None:
        """Enable explain mode to capture intermediate values."""
        self.explain_mode = enabled

    def get_path(self, path: str) -> Any:
        """Get value from data by dot-separated path."""
        parts = path.split(".")
        value = self.data

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value

    def evaluate_rule(self, rule: dict[str, Any]) -> tuple[bool, RuleEvaluation | None]:
        """Evaluate a single rule.

        Rule format:
        {
            "id": "rule_name",
            "operator": "==",  # or >, <, >=, <=, !=
            "left": "path.to.value" or literal,
            "right": "path.to.value" or literal,
            "threshold": 5,  # optional
        }

        Or with aggregation:
        {
            "id": "count_rule",
            "aggregation": "count",
            "path": "findings",
            "filter": {"severity": "HIGH"},
            "operator": "==",
            "right": 0,
        }
        """
        rule_id = rule.get("id", "unknown")

        # Handle boolean composition
        if "all" in rule:
            return self._evaluate_all(rule["all"], rule_id)
        if "any" in rule:
            return self._evaluate_any(rule["any"], rule_id)
        if "not" in rule:
            return self._evaluate_not(rule["not"], rule_id)

        # Get values
        left = self._resolve_value(rule.get("left"))
        right = self._resolve_value(rule.get("right"))

        # Handle aggregations
        if "aggregation" in rule:
            left = self._apply_aggregation(
                rule["aggregation"],
                rule.get("path", ""),
                rule.get("filter"),
            )

        # Apply operator
        op_str = rule.get("operator", "==")
        op_func = OPS.get(op_str, operator.eq)

        try:
            result = op_func(left, right)
        except Exception as e:
            result = False
            if self.explain_mode:
                right = f"{right} (ERROR: {e})"

        evaluation = None
        if self.explain_mode:
            self._eval_sequence += 1
            evaluation = RuleEvaluation(
                rule_id=rule_id,
                passed=result,
                operator=op_str,
                left_value=left,
                right_value=right,
                sequence=self._eval_sequence,
                context={"rule": rule},
            )
            self.evaluations.append(evaluation)

        return result, evaluation

    def _resolve_value(self, value: Any) -> Any:
        """Resolve a value - either a path or literal."""
        if isinstance(value, str):
            # Try as a path (handles both "key" and "path.to.key")
            resolved = self.get_path(value)
            if resolved is not None:
                return resolved
        return value

    def _apply_aggregation(
        self,
        agg_type: str,
        path: str,
        filter_spec: dict[str, Any] | None,
    ) -> Any:
        """Apply aggregation function."""
        data = self.get_path(path)

        if not isinstance(data, list):
            return 0

        # Apply filter if specified (sorted keys for deterministic iteration)
        if filter_spec:
            data = [
                item for item in data
                if all(
                    self._get_nested(item, k) == v
                    for k, v in sorted(filter_spec.items())
                )
            ]

        # Apply aggregation
        if agg_type == "count":
            return len(data)
        elif agg_type == "rate":
            # Rate of true values
            if not data:
                return 0.0
            true_count = sum(1 for item in data if item)
            return true_count / len(data)
        elif agg_type == "avg":
            if not data:
                return 0.0
            return sum(float(x) for x in data if isinstance(x, (int, float))) / len(data)
        elif agg_type == "max":
            if not data:
                return 0
            return max(data)
        elif agg_type == "min":
            if not data:
                return 0
            return min(data)

        return 0

    def _get_nested(self, obj: Any, path: str) -> Any:
        """Get nested value from object."""
        parts = path.split(".")
        value = obj

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def evaluate_rules(self, rules: list[dict[str, Any]]) -> list[tuple[bool, RuleEvaluation | None]]:
        """Evaluate multiple rules in stable order.

        Rules are sorted by ID before evaluation to ensure deterministic
        ordering regardless of input order.

        Args:
            rules: List of rule dicts to evaluate

        Returns:
            List of (passed, evaluation) tuples in rule-ID-sorted order
        """
        # Sort by rule ID for deterministic evaluation order
        sorted_rules = sorted(rules, key=lambda r: r.get("id", ""))
        return [self.evaluate_rule(rule) for rule in sorted_rules]

    def _evaluate_all(self, rules: list[dict], rule_id: str) -> tuple[bool, RuleEvaluation]:
        """Evaluate all rules (AND). Rules evaluated in array order."""
        results = []
        sub_evals = []

        for rule in rules:
            result, eval_data = self.evaluate_rule(rule)
            results.append(result)
            if eval_data:
                sub_evals.append(eval_data)

        passed = all(results)

        self._eval_sequence += 1
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            passed=passed,
            operator="all",
            left_value=results,
            right_value=True,
            sequence=self._eval_sequence,
            sub_evaluations=sub_evals,
        )

        if self.explain_mode:
            self.evaluations.append(evaluation)

        return passed, evaluation

    def _evaluate_any(self, rules: list[dict], rule_id: str) -> tuple[bool, RuleEvaluation]:
        """Evaluate any rule (OR). Rules evaluated in array order."""
        results = []
        sub_evals = []

        for rule in rules:
            result, eval_data = self.evaluate_rule(rule)
            results.append(result)
            if eval_data:
                sub_evals.append(eval_data)

        passed = any(results)

        self._eval_sequence += 1
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            passed=passed,
            operator="any",
            left_value=results,
            right_value=True,
            sequence=self._eval_sequence,
            sub_evaluations=sub_evals,
        )

        if self.explain_mode:
            self.evaluations.append(evaluation)

        return passed, evaluation

    def _evaluate_not(self, rule: dict, rule_id: str) -> tuple[bool, RuleEvaluation]:
        """Evaluate negation."""
        result, eval_data = self.evaluate_rule(rule)
        passed = not result

        self._eval_sequence += 1
        evaluation = RuleEvaluation(
            rule_id=rule_id,
            passed=passed,
            operator="not",
            left_value=result,
            right_value=False,
            sequence=self._eval_sequence,
            sub_evaluations=[eval_data] if eval_data else [],
        )

        if self.explain_mode:
            self.evaluations.append(evaluation)

        return passed, evaluation

    def explain(self, rule: dict[str, Any]) -> str:
        """Generate human-readable explanation for a rule evaluation.

        Args:
            rule: Rule to explain

        Returns:
            Markdown-formatted explanation
        """
        self.set_explain_mode(True)
        self.evaluations = []

        passed, evaluation = self.evaluate_rule(rule)

        lines = [
            f"# Rule Explanation: {rule.get('id', 'unknown')}",
            "",
            f"**Result:** {'✅ PASSED' if passed else '❌ FAILED'}",
            "",
            "## Evaluation Tree",
            "",
        ]

        if evaluation:
            lines.extend(self._format_evaluation(evaluation, 0))

        return "\n".join(lines)

    def _format_evaluation(self, eval_data: RuleEvaluation, depth: int) -> list[str]:
        """Format evaluation tree."""
        indent = "  " * depth
        lines = []

        if eval_data.operator in ("all", "any", "not"):
            lines.append(f"{indent}- **{eval_data.operator.upper()}** → {'✅' if eval_data.passed else '❌'}")
            for sub in eval_data.sub_evaluations:
                lines.extend(self._format_evaluation(sub, depth + 1))
        else:
            lines.append(
                f"{indent}- `{eval_data.left_value}` {eval_data.operator} `{eval_data.right_value}` "
                f"→ {'✅' if eval_data.passed else '❌'}"
            )

        return lines


class InvariantExplainer:
    """CLI explainer for invariants."""

    def __init__(self, rules: list[dict[str, Any]], data: dict[str, Any]) -> None:
        self.rules = {r["id"]: r for r in rules if "id" in r}
        self.dsl = InvariantDSL(data)

    def explain_rule(self, rule_id: str) -> str:
        """Explain a specific rule."""
        if rule_id not in self.rules:
            return f"Rule not found: {rule_id}"

        rule = self.rules[rule_id]
        return self.dsl.explain(rule)

    def explain_all(self) -> str:
        """Explain all rules."""
        lines = ["# Invariant Explanation Report", ""]

        for _rule_id, rule in sorted(self.rules.items()):
            lines.append(self.dsl.explain(rule))
            lines.append("---")

        return "\n".join(lines)
