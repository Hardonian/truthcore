"""Verdict Aggregator v2 - CLI Integration (M6).

Adds truthctl verdict build command and integrates verdict generation
into truthctl judge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from truthcore.verdict.aggregator import aggregate_verdict


def register_verdict_commands(cli: click.Group) -> None:
    """Register verdict commands with the CLI.
    
    Args:
        cli: The Click CLI group to add commands to
    """

    @cli.command(name="verdict")
    @click.option(
        "--inputs", "-i",
        required=True,
        type=click.Path(exists=True, path_type=Path),
        help="Input directory containing engine outputs",
    )
    @click.option(
        "--profile", "-p",
        default="default",
        help="Profile name for the verdict",
    )
    @click.option(
        "--mode", "-m",
        type=click.Choice(["pr", "main", "release"]),
        default="pr",
        help="Execution mode (determines thresholds)",
    )
    @click.option(
        "--out", "-o",
        required=True,
        type=click.Path(path_type=Path),
        help="Output directory for verdict files",
    )
    @click.option(
        "--thresholds", "-t",
        type=click.Path(exists=True, path_type=Path),
        help="Custom thresholds JSON file (optional)",
    )
    @click.option(
        "--include", "-I",
        multiple=True,
        help="Include specific files (can be used multiple times)",
    )
    @click.option(
        "--compat",
        is_flag=True,
        help="Enable backward compatibility mode (v1 output format)",
    )
    @click.pass_context
    def verdict_build(
        ctx: click.Context,
        inputs: Path,
        profile: str,
        mode: str,
        out: Path,
        thresholds: Path | None,
        include: tuple[str, ...],
        compat: bool,
    ):
        """Build a verdict from engine outputs.
        
        Aggregates findings from multiple engines and produces a weighted
        ship/no-ship verdict based on configured thresholds.
        
        Inputs should contain:
        - readiness.json: Readiness engine output
        - invariants.json: Invariant violations
        - policy_findings.json: Policy findings
        - provenance verification results (optional)
        - intel scorecards (optional)
        
        Outputs:
        - verdict.json: Machine-readable verdict
        - verdict.md: Human-readable report
        
        Use --compat for v1 output format (backward compatible with truth-core < 0.2.0).
        """
        debug = ctx.obj.get("debug", False)

        try:
            # Collect input files
            input_files: list[Path] = []

            if include:
                # Use explicitly included files
                for pattern in include:
                    input_files.extend(inputs.glob(pattern))
            else:
                # Auto-discover known files
                known_files = [
                    "readiness.json",
                    "invariants.json",
                    "policy_findings.json",
                    "provenance_result.json",
                    "*intel*.json",
                    "*scorecard*.json",
                ]
                for pattern in known_files:
                    input_files.extend(inputs.glob(pattern))

            # Remove duplicates and sort
            input_files = sorted(set(input_files))

            if not input_files:
                click.echo("Warning: No input files found", err=True)
                click.echo(f"Searched in: {inputs}", err=True)
                # Create empty verdict
                input_files = []

            click.echo(f"Aggregating verdict from {len(input_files)} input(s)...")
            for f in input_files:
                click.echo(f"  - {f.name}")

            # Load custom thresholds if provided
            custom_thresholds: dict[str, Any] | None = None
            if thresholds:
                import json
                with open(thresholds, encoding="utf-8") as f:
                    custom_thresholds = json.load(f)
                click.echo(f"Loaded custom thresholds from: {thresholds}")

            # Aggregate verdict
            result = aggregate_verdict(
                input_paths=input_files,
                mode=mode,
                profile=profile,
                custom_thresholds=custom_thresholds,
            )

            # Write outputs
            out.mkdir(parents=True, exist_ok=True)

            # Handle compat mode for v1 output format
            if compat:
                from truthcore.compat import CompatOptions, write_compat_output
                opts = CompatOptions.from_flag(True)
                write_compat_output(result.to_dict(), out / "verdict.json", opts)
                click.echo(f"  Written: {out / 'verdict.json'} (v1 compat format)")
            else:
                result.write_json(out / "verdict.json")
                click.echo(f"  Written: {out / 'verdict.json'}")

            result.write_markdown(out / "verdict.md")
            click.echo(f"  Written: {out / 'verdict.md'}")

            # Print summary
            click.echo(f"\nVerdict: {result.verdict.value}")
            click.echo(f"  Total findings: {result.total_findings}")
            click.echo(f"  Blockers: {result.blockers}")
            click.echo(f"  Highs: {result.highs}")
            click.echo(f"  Total points: {result.total_points}")

            if result.no_ship_reasons:
                click.echo("\nNo-ship reasons:")
                for reason in result.no_ship_reasons:
                    click.echo(f"  - {reason}")

            # Exit with error code if no-ship
            if result.verdict.value == "NO_SHIP":
                ctx.exit(1)

        except Exception as e:
            if debug:
                raise
            click.echo(f"Error: {e}", err=True)
            ctx.exit(1)

    # Store the command for potential reference
    cli.commands["verdict"] = verdict_build


def generate_verdict_for_judge(
    inputs_dir: Path,
    output_dir: Path,
    mode: str = "pr",
    profile: str | None = None,
) -> Path | None:
    """Generate verdict as part of judge command.
    
    This is called by truthctl judge to produce verdict artifacts.
    
    Args:
        inputs_dir: Directory containing engine outputs
        output_dir: Directory to write verdict to
        mode: Execution mode
        profile: Profile name
        
    Returns:
        Path to verdict.json or None if generation failed
    """
    try:
        # Look for input files
        input_files: list[Path] = []

        # Readiness output
        readiness_json = output_dir / "readiness.json"
        if readiness_json.exists():
            input_files.append(readiness_json)

        # Policy findings
        policy_json = output_dir / "policy_findings.json"
        if policy_json.exists():
            input_files.append(policy_json)

        # Invariants results
        invariants_json = inputs_dir / "invariants.json"
        if invariants_json.exists():
            input_files.append(invariants_json)

        # If no files found, skip
        if not input_files:
            return None

        # Aggregate verdict
        result = aggregate_verdict(
            input_paths=input_files,
            mode=mode,
            profile=profile,
        )

        # Write outputs
        result.write_json(output_dir / "verdict.json")
        result.write_markdown(output_dir / "verdict.md")

        return output_dir / "verdict.json"

    except Exception:
        # Silently fail - verdict is optional for judge
        return None
