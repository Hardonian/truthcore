"""JSON Schema validation for policy YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from truthcore.security import safe_read_text

# JSON Schema for policy rules
POLICY_RULE_SCHEMA = {
    "type": "object",
    "required": ["id", "description", "severity", "category", "target"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "severity": {
            "type": "string",
            "enum": ["BLOCKER", "HIGH", "MEDIUM", "LOW"],
        },
        "category": {"type": "string", "minLength": 1},
        "target": {
            "type": "string",
            "enum": ["files", "logs", "json_fields", "findings", "traces"],
        },
        "enabled": {"type": "boolean"},
        "suggestion": {"type": "string"},
        "metadata": {"type": "object"},
        "matchers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "pattern"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["regex", "contains", "equals", "glob"],
                    },
                    "pattern": {"type": "string"},
                    "flags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "threshold": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 0},
                "rate": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "distinct": {"type": "integer", "minimum": 0},
            },
        },
        "suppressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pattern", "reason"],
                "properties": {
                    "pattern": {"type": "string"},
                    "reason": {"type": "string"},
                    "expiry": {"type": "string"},  # ISO date
                    "author": {"type": "string"},
                },
            },
        },
        "all_of": {"type": "array", "items": {"$ref": "#"}},
        "any_of": {"type": "array", "items": {"$ref": "#"}},
        "not_match": {"$ref": "#"},
    },
}

# JSON Schema for policy packs
POLICY_PACK_SCHEMA = {
    "type": "object",
    "required": ["name", "description", "version"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+"},
        "metadata": {"type": "object"},
        "rules": {
            "type": "array",
            "items": POLICY_RULE_SCHEMA,
        },
    },
}


class PolicyValidationError(Exception):
    """Policy validation error."""

    def __init__(self, message: str, path: str | None = None):
        self.message = message
        self.path = path
        super().__init__(f"Validation error{f' at {path}' if path else ''}: {message}")


class PolicyValidator:
    """Validator for policy YAML files."""

    def __init__(self) -> None:
        self.errors: list[PolicyValidationError] = []

    def validate_pack(self, data: dict[str, Any]) -> list[PolicyValidationError]:
        """Validate a policy pack against schema.

        Returns:
            List of validation errors (empty if valid)
        """
        self.errors = []
        self._validate_pack_schema(data, "")
        return self.errors

    def _validate_pack_schema(self, data: Any, path: str) -> None:
        """Recursively validate pack schema."""
        schema = POLICY_PACK_SCHEMA

        # Check type
        if schema.get("type") == "object":
            if not isinstance(data, dict):
                self.errors.append(
                    PolicyValidationError(f"Expected object, got {type(data).__name__}", path)
                )
                return

            # Check required fields
            for req in schema.get("required", []):
                if req not in data:
                    self.errors.append(
                        PolicyValidationError(f"Missing required field: {req}", path)
                    )

            # Validate properties
            for key, value in data.items():
                prop_schema = schema.get("properties", {}).get(key)
                if prop_schema:
                    self._validate_value(value, prop_schema, f"{path}.{key}" if path else key)

            # Validate rules array specially
            if "rules" in data and isinstance(data["rules"], list):
                for i, rule in enumerate(data["rules"]):
                    self._validate_rule(rule, f"{path}.rules[{i}]" if path else f"rules[{i}]")

    def _validate_rule(self, data: Any, path: str) -> None:
        """Validate a policy rule."""
        if not isinstance(data, dict):
            self.errors.append(
                PolicyValidationError(f"Expected object, got {type(data).__name__}", path)
            )
            return

        schema = POLICY_RULE_SCHEMA

        # Check required fields
        for req in schema.get("required", []):
            if req not in data:
                self.errors.append(
                    PolicyValidationError(f"Missing required field: {req}", path)
                )

        # Validate severity enum
        if "severity" in data:
            allowed = ["BLOCKER", "HIGH", "MEDIUM", "LOW"]
            if data["severity"] not in allowed:
                self.errors.append(
                    PolicyValidationError(
                        f"Invalid severity: {data['severity']}. Must be one of: {allowed}",
                        f"{path}.severity",
                    )
                )

        # Validate target enum
        if "target" in data:
            allowed = ["files", "logs", "json_fields", "findings", "traces"]
            if data["target"] not in allowed:
                self.errors.append(
                    PolicyValidationError(
                        f"Invalid target: {data['target']}. Must be one of: {allowed}",
                        f"{path}.target",
                    )
                )

        # Validate matchers
        if "matchers" in data and isinstance(data["matchers"], list):
            for i, matcher in enumerate(data["matchers"]):
                self._validate_matcher(
                    matcher, f"{path}.matchers[{i}]"
                )

        # Validate threshold
        if "threshold" in data and isinstance(data["threshold"], dict):
            thresh = data["threshold"]
            if "count" in thresh and not isinstance(thresh["count"], int):
                self.errors.append(
                    PolicyValidationError("threshold.count must be an integer", path)
                )
            if "rate" in thresh:
                rate = thresh["rate"]
                if not isinstance(rate, (int, float)) or rate < 0 or rate > 1:
                    self.errors.append(
                        PolicyValidationError(
                            "threshold.rate must be a number between 0.0 and 1.0", path
                        )
                    )
            if "distinct" in thresh and not isinstance(thresh["distinct"], int):
                self.errors.append(
                    PolicyValidationError("threshold.distinct must be an integer", path)
                )

        # Validate suppressions
        if "suppressions" in data and isinstance(data["suppressions"], list):
            for i, sup in enumerate(data["suppressions"]):
                self._validate_suppression(
                    sup, f"{path}.suppressions[{i}]"
                )

        # Recursively validate boolean composition
        for key in ["all_of", "any_of"]:
            if key in data and isinstance(data[key], list):
                for i, subrule in enumerate(data[key]):
                    self._validate_rule(subrule, f"{path}.{key}[{i}]")

        if "not_match" in data and isinstance(data["not_match"], dict):
            self._validate_rule(data["not_match"], f"{path}.not_match")

    def _validate_matcher(self, data: Any, path: str) -> None:
        """Validate a matcher."""
        if not isinstance(data, dict):
            self.errors.append(
                PolicyValidationError(f"Expected object, got {type(data).__name__}", path)
            )
            return

        if "type" not in data:
            self.errors.append(PolicyValidationError("Missing required field: type", path))
        elif data["type"] not in ["regex", "contains", "equals", "glob"]:
            self.errors.append(
                PolicyValidationError(
                    f"Invalid matcher type: {data['type']}", f"{path}.type"
                )
            )

        if "pattern" not in data:
            self.errors.append(PolicyValidationError("Missing required field: pattern", path))

        # Try to compile regex
        if data.get("type") == "regex":
            import re

            try:
                re.compile(data["pattern"])
            except re.error as e:
                self.errors.append(
                    PolicyValidationError(f"Invalid regex pattern: {e}", f"{path}.pattern")
                )

    def _validate_suppression(self, data: Any, path: str) -> None:
        """Validate a suppression."""
        if not isinstance(data, dict):
            self.errors.append(
                PolicyValidationError(f"Expected object, got {type(data).__name__}", path)
            )
            return

        if "pattern" not in data:
            self.errors.append(PolicyValidationError("Missing required field: pattern", path))

        if "reason" not in data:
            self.errors.append(PolicyValidationError("Missing required field: reason", path))

        # Validate expiry date format if present
        if "expiry" in data and data["expiry"]:
            from datetime import datetime

            try:
                datetime.fromisoformat(data["expiry"])
            except ValueError:
                self.errors.append(
                    PolicyValidationError(
                        "Invalid expiry date format (use ISO format)", f"{path}.expiry"
                    )
                )

    def _validate_value(self, value: Any, schema: dict[str, Any], path: str) -> None:
        """Validate a value against schema."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_type = schema.get("type")
        if expected_type and expected_type in type_map:
            python_type = type_map[expected_type]
            if expected_type == "number":
                if not isinstance(value, python_type):
                    self.errors.append(
                        PolicyValidationError(
                            f"Expected {expected_type}, got {type(value).__name__}", path
                        )
                    )
            elif not isinstance(value, python_type):
                self.errors.append(
                    PolicyValidationError(
                        f"Expected {expected_type}, got {type(value).__name__}", path
                    )
                )

        # Validate array items
        if expected_type == "array" and "items" in schema and isinstance(value, list):
            for i, item in enumerate(value):
                self._validate_value(item, schema["items"], f"{path}[{i}]")

    def validate_file(self, path: Path) -> list[PolicyValidationError]:
        """Validate a policy pack file.

        Args:
            path: Path to YAML file

        Returns:
            List of validation errors
        """
        try:
            text = safe_read_text(path)
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                return [
                    PolicyValidationError(f"File must contain a YAML object, got {type(data).__name__}")
                ]
            return self.validate_pack(data)
        except yaml.YAMLError as e:
            return [PolicyValidationError(f"Invalid YAML: {e}")]
        except Exception as e:
            return [PolicyValidationError(f"Error reading file: {e}")]
