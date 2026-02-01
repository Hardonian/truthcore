"""Compatibility layer for backward compatibility with older CLI versions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click


@dataclass
class CompatOptions:
    """Compatibility options for backward compatibility.
    
    Attributes:
        legacy_format: Use legacy output format
        v1_output: Use v1 output format for verdicts
        skip_normalization: Skip input normalization (legacy behavior)
        relaxed_paths: Allow relative paths without validation (legacy)
        no_provenance: Skip provenance generation even when signing enabled
    """
    legacy_format: bool = False
    v1_output: bool = False
    skip_normalization: bool = False
    relaxed_paths: bool = False
    no_provenance: bool = False
    
    @classmethod
    def from_flag(cls, enabled: bool) -> "CompatOptions":
        """Create compatibility options from a single flag.
        
        When --compat is enabled, all compatibility options are enabled
        for maximum backward compatibility.
        """
        return cls(
            legacy_format=enabled,
            v1_output=enabled,
            skip_normalization=enabled,
            relaxed_paths=enabled,
            no_provenance=enabled,
        )


def apply_compat_decorator(cmd):
    """Apply compatibility option decorator to a command.
    
    Usage:
        @cli.command()
        @click.option(...)
        @apply_compat_decorator
        def my_command(ctx, compat, ...):
            opts = CompatOptions.from_flag(compat)
    """
    return click.option(
        "--compat",
        is_flag=True,
        default=False,
        help="Enable backward compatibility mode (legacy formats, relaxed validation)",
    )(cmd)


def transform_output_for_compat(data: dict[str, Any], opts: CompatOptions) -> dict[str, Any]:
    """Transform output data for compatibility mode.
    
    Args:
        data: Output data dict
        opts: Compatibility options
        
    Returns:
        Transformed data for backward compatibility
    """
    if not opts.legacy_format:
        return data
    
    result = dict(data)
    
    # Legacy format modifications
    if "verdict" in result and opts.v1_output:
        # Convert v2 format to v1 format
        result = _convert_verdict_v2_to_v1(result)
    
    # Remove newer fields for legacy compatibility
    newer_fields = ["version", "engines", "categories", "top_findings", "reasoning"]
    for field in newer_fields:
        if field in result:
            del result[field]
    
    return result


def _convert_verdict_v2_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Convert v2 verdict format to v1 format."""
    summary = data.get("summary", {})
    
    return {
        "verdict": data.get("verdict", "NO_SHIP"),
        "mode": data.get("mode", "pr"),
        "profile": data.get("profile"),
        "timestamp": data.get("timestamp", ""),
        "passed": data.get("verdict") == "SHIP",
        "total_findings": summary.get("total_findings", 0),
        "blockers": summary.get("blockers", 0),
        "highs": summary.get("highs", 0),
        "mediums": summary.get("mediums", 0),
        "lows": summary.get("lows", 0),
        "total_points": summary.get("total_points", 0),
    }


def write_compat_output(
    data: dict[str, Any],
    output_path: Path,
    opts: CompatOptions,
) -> None:
    """Write output file with compatibility transformations.
    
    Args:
        data: Data to write
        output_path: Path to write to
        opts: Compatibility options
    """
    transformed = transform_output_for_compat(data, opts)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed, f, indent=2, sort_keys=True)


def get_compat_help_text(command_name: str) -> str:
    """Get help text for compatibility mode for a specific command.
    
    Args:
        command_name: Name of the command
        
    Returns:
        Help text describing compat mode effects
    """
    help_texts = {
        "judge": """
Compatibility mode (--compat) affects the judge command:
  - Uses legacy output format (v1 style)
  - Relaxes path validation for legacy setups
  - Disables automatic provenance generation
  - Maintains output compatible with truth-core < 0.2.0
""",
        "verdict": """
Compatibility mode (--compat) affects the verdict command:
  - Outputs v1 format verdict (simpler structure)
  - Removes engine/category breakdowns
  - Uses legacy field names
  - Compatible with truth-core < 0.2.0 consumers
""",
        "policy": """
Compatibility mode (--compat) affects the policy command:
  - Uses legacy output format for findings
  - Relaxes validation rules for policy packs
  - Maintains output compatible with truth-core < 0.2.0
""",
    }
    
    return help_texts.get(command_name, "")
