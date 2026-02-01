"""TruthCore Spine CLI commands.

Provides truthctl spine subcommands for querying the truth spine.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from truthcore.spine.query import SpineQueryClient
from truthcore.spine.graph import GraphStore
from truthcore.spine.belief import BeliefEngine


def register_spine_commands(cli: click.Group) -> None:
    """Register spine commands with the CLI."""
    
    @cli.group(name="spine")
    def spine_group():
        """Query the TruthCore Spine (read-only truth system)."""
        pass
    
    @spine_group.command(name="why")
    @click.argument("assertion-id")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def why_cmd(assertion_id: str, output_format: str, store: Path):
        """Explain why an assertion is believed.
        
        Shows lineage, evidence, and confidence computation.
        
        Examples:
          truthctl spine why assertion_abc123
          truthctl spine why assertion_abc123 --format json
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.why(assertion_id)
            
            if not result:
                click.echo(f"Assertion not found: {assertion_id}", err=True)
                sys.exit(1)
            
            if output_format == "json":
                click.echo(json.dumps({
                    "assertion": result.assertion.to_dict(),
                    "current_belief": result.current_belief.to_dict() if result.current_belief else None,
                    "confidence_explanation": result.confidence_explanation,
                    "evidence_count": result.evidence_count,
                    "upstream_dependencies": result.upstream_dependencies,
                    "formation_rationale": result.formation_rationale,
                }, indent=2))
            else:
                # Markdown format
                lines = [
                    f"# Belief: {assertion_id}",
                    "",
                    "## Claim",
                    result.assertion.claim,
                    "",
                    "## Confidence",
                    result.confidence_explanation,
                    "",
                    f"**Evidence Items:** {result.evidence_count}",
                    "",
                ]
                
                if result.current_belief:
                    current_conf = result.current_belief.current_confidence()
                    lines.extend([
                        f"**Current Confidence:** {current_conf:.2f}",
                        f"**Base Confidence:** {result.current_belief.confidence:.2f}",
                        f"**Method:** {result.current_belief.confidence_method}",
                        "",
                    ])
                
                if result.upstream_dependencies:
                    lines.extend(["## Dependencies", ""])
                    for dep in result.upstream_dependencies:
                        lines.append(f"- {dep}")
                    lines.append("")
                
                lines.extend(["## Rationale", result.formation_rationale])
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="evidence")
    @click.argument("assertion-id")
    @click.option("--type", "evidence_type", type=click.Choice(["supporting", "weakening", "stale", "all"]), default="all")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def evidence_cmd(assertion_id: str, evidence_type: str, output_format: str, store: Path):
        """Show evidence for an assertion.
        
        Examples:
          truthctl spine evidence assertion_abc123
          truthctl spine evidence assertion_abc123 --type supporting --format json
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.evidence(assertion_id, include_stale=(evidence_type in ["stale", "all"]))
            
            if not result:
                click.echo(f"Assertion not found: {assertion_id}", err=True)
                sys.exit(1)
            
            # Filter by type
            evidence_list = []
            if evidence_type in ["supporting", "all"]:
                evidence_list.extend(result.supporting_evidence)
            if evidence_type in ["weakening", "all"]:
                evidence_list.extend(result.weakening_evidence)
            if evidence_type in ["stale", "all"]:
                evidence_list.extend(result.stale_evidence)
            
            if output_format == "json":
                output = {
                    "assertion_id": result.assertion_id,
                    "evidence": [e.to_dict() for e in evidence_list],
                    "total_weight": result.total_weight,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                lines = [
                    f"# Evidence for {assertion_id}",
                    "",
                    f"**Total Weight:** {result.total_weight:.2f}",
                    f"**Supporting:** {len(result.supporting_evidence)}",
                    f"**Weakening:** {len(result.weakening_evidence)}",
                    f"**Stale:** {len(result.stale_evidence)}",
                    "",
                ]
                
                if evidence_list:
                    lines.extend(["## Evidence Items", ""])
                    for ev in evidence_list:
                        status = "⚠️ STALE" if ev.is_stale() else "✓"
                        lines.extend([
                            f"### {ev.evidence_id[:16]}... {status}",
                            f"- **Type:** {ev.evidence_type.value}",
                            f"- **Source:** {ev.source}",
                            f"- **Hash:** {ev.content_hash[:16]}...",
                            "",
                        ])
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="history")
    @click.argument("assertion-id")
    @click.option("--since", help="Show changes since date (YYYY-MM-DD)")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def history_cmd(assertion_id: str, since: str | None, output_format: str, store: Path):
        """Show belief version history.
        
        Examples:
          truthctl spine history assertion_abc123
          truthctl spine history assertion_abc123 --since 2026-01-01
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.history(assertion_id)
            
            if not result:
                click.echo(f"Assertion not found: {assertion_id}", err=True)
                sys.exit(1)
            
            # Filter by date if specified
            beliefs = result.beliefs
            if since:
                beliefs = [b for b in beliefs if b.formed_at >= since]
            
            if output_format == "json":
                output = {
                    "assertion_id": result.assertion_id,
                    "beliefs": [b.to_dict() for b in beliefs],
                    "change_summary": result.change_summary[-len(beliefs):] if beliefs else [],
                }
                click.echo(json.dumps(output, indent=2))
            else:
                lines = [
                    f"# Belief History: {assertion_id}",
                    "",
                ]
                
                if beliefs:
                    lines.extend([f"**Total Versions:** {len(beliefs)}", ""])
                    lines.extend(["## Timeline", ""])
                    
                    for belief in beliefs:
                        current_conf = belief.current_confidence()
                        status = "(superseded)" if belief.is_superseded() else "(current)"
                        lines.extend([
                            f"### Version {belief.version} {status}",
                            f"- **Confidence:** {belief.confidence:.2f} (current: {current_conf:.2f})",
                            f"- **Formed:** {belief.formed_at}",
                            f"- **Method:** {belief.confidence_method}",
                        ])
                        if belief.superseded_at:
                            lines.append(f"- **Superseded:** {belief.superseded_at}")
                        lines.append("")
                else:
                    lines.append("No belief history found.")
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="meaning")
    @click.argument("concept")
    @click.option("--version", help="Specific version to query")
    @click.option("--at", help="Query meaning at specific time (ISO8601)")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def meaning_cmd(concept: str, version: str | None, at: str | None, output_format: str, store: Path):
        """Query semantic meaning of a concept.
        
        Examples:
          truthctl spine meaning deployment_ready
          truthctl spine meaning deployment_ready --at 2026-01-15T00:00:00Z
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.meaning(concept, timestamp=at)
            
            if not result:
                click.echo(f"Error querying meaning for: {concept}", err=True)
                sys.exit(1)
            
            if output_format == "json":
                output = {
                    "concept": result.concept,
                    "current_version": result.current_version.to_dict() if result.current_version else None,
                    "all_versions": [v.to_dict() for v in result.all_versions],
                    "compatibility_warnings": result.compatibility_warnings,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                lines = [f"# Meaning: {concept}", ""]
                
                if result.current_version:
                    lines.extend([
                        "## Current Definition",
                        f"**Version:** {result.current_version.version}",
                        f"**Valid From:** {result.current_version.valid_from}",
                        "",
                        f"{result.current_version.definition}",
                        "",
                    ])
                    
                    if result.current_version.computation:
                        lines.extend([
                            "### Computation",
                            f"```\n{result.current_version.computation}\n```",
                            "",
                        ])
                else:
                    lines.extend(["## Current Definition", "*No current definition found*", ""])
                
                if result.all_versions:
                    lines.extend(["## All Versions", ""])
                    for v in result.all_versions:
                        current_marker = " ← current" if v == result.current_version else ""
                        lines.append(f"- **{v.version}**{current_marker}")
                
                if result.compatibility_warnings:
                    lines.extend(["", "## Warnings", ""])
                    for warning in result.compatibility_warnings:
                        lines.append(f"⚠️  {warning}")
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="dependencies")
    @click.argument("assertion-id")
    @click.option("--recursive", is_flag=True, help="Show transitive dependencies")
    @click.option("--depth", type=int, default=5, help="Maximum depth for recursive query")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def dependencies_cmd(assertion_id: str, recursive: bool, depth: int, output_format: str, store: Path):
        """Show dependencies for an assertion.
        
        Examples:
          truthctl spine dependencies assertion_abc123
          truthctl spine dependencies assertion_abc123 --recursive --depth 3
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.dependencies(assertion_id, recursive=recursive, max_depth=depth)
            
            if not result:
                click.echo(f"Assertion not found: {assertion_id}", err=True)
                sys.exit(1)
            
            if output_format == "json":
                output = {
                    "assertion_id": result.assertion_id,
                    "direct_dependencies": result.direct_dependencies,
                    "transitive_dependencies": result.transitive_dependencies,
                    "evidence_dependencies": result.evidence_dependencies,
                    "depth": result.depth,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                lines = [
                    f"# Dependencies: {assertion_id}",
                    "",
                    f"**Depth:** {result.depth}",
                    "",
                ]
                
                if result.evidence_dependencies:
                    lines.extend(["## Evidence", ""])
                    for ev in result.evidence_dependencies:
                        lines.append(f"- `{ev}`")
                    lines.append("")
                
                if result.direct_dependencies:
                    lines.extend(["## Direct Dependencies", ""])
                    for dep in result.direct_dependencies:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                
                if recursive and result.transitive_dependencies:
                    lines.extend(["## Transitive Dependencies", ""])
                    for dep in result.transitive_dependencies:
                        lines.append(f"- `{dep}`")
                    lines.append("")
                
                if not any([result.evidence_dependencies, result.direct_dependencies, result.transitive_dependencies]):
                    lines.append("*No dependencies found.*")
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="invalidate")
    @click.argument("assertion-id")
    @click.option("--format", "output_format", type=click.Choice(["json", "md"]), default="md")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def invalidate_cmd(assertion_id: str, output_format: str, store: Path):
        """Show what could invalidate a belief.
        
        Examples:
          truthctl spine invalidate assertion_abc123
        """
        try:
            client = SpineQueryClient(GraphStore(store))
            result = client.invalidate(assertion_id)
            
            if not result:
                click.echo(f"Assertion not found: {assertion_id}", err=True)
                sys.exit(1)
            
            if output_format == "json":
                output = {
                    "assertion_id": result.assertion_id,
                    "potential_counter_evidence": result.potential_counter_evidence,
                    "semantic_conflicts": result.semantic_conflicts,
                    "dependency_failures": result.dependency_failures,
                    "invalidation_scenarios": result.invalidation_scenarios,
                }
                click.echo(json.dumps(output, indent=2))
            else:
                lines = [
                    f"# Invalidation Scenarios: {assertion_id}",
                    "",
                    "## Potential Counter-Evidence",
                    "",
                ]
                
                for item in result.potential_counter_evidence:
                    lines.append(f"- {item}")
                
                if result.semantic_conflicts:
                    lines.extend(["", "## Semantic Conflicts", ""])
                    for item in result.semantic_conflicts:
                        lines.append(f"⚠️  {item}")
                
                if result.dependency_failures:
                    lines.extend(["", "## Dependency Failures", ""])
                    for item in result.dependency_failures:
                        lines.append(f"❌ {item}")
                
                lines.extend(["", "## Invalidation Scenarios", ""])
                for i, scenario in enumerate(result.invalidation_scenarios, 1):
                    lines.append(f"{i}. {scenario}")
                
                click.echo("\n".join(lines))
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="stats")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    @click.option("--since", help="Show stats since date (YYYY-MM-DD)")
    def stats_cmd(store: Path, since: str | None):
        """Show spine statistics."""
        try:
            store_obj = GraphStore(store)
            belief_engine = BeliefEngine(store_obj)
            
            storage_stats = store_obj.get_stats()
            belief_stats = belief_engine.compute_belief_stats()
            
            lines = [
                "# TruthCore Spine Statistics",
                "",
                "## Storage",
                f"- **Location:** {storage_stats['base_path']}",
                f"- **Total Size:** {storage_stats['total_size_bytes']:,} bytes",
                "",
                "## Assertions",
                f"- **Total:** {storage_stats.get('assertions', 0)}",
                f"- **Evidence Items:** {storage_stats.get('evidence', 0)}",
                "",
                "## Beliefs",
                f"- **Total Beliefs:** {belief_stats['total_beliefs']}",
                f"- **High Confidence (≥0.8):** {belief_stats['high_confidence']}",
                f"- **Medium Confidence (0.5-0.8):** {belief_stats['medium_confidence']}",
                f"- **Low Confidence (<0.5):** {belief_stats['low_confidence']}",
                f"- **Superseded:** {belief_stats['superseded_beliefs']}",
                f"- **Average Confidence:** {belief_stats['average_confidence']:.2f}",
            ]
            
            click.echo("\n".join(lines))
            
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    
    @spine_group.command(name="health")
    @click.option("--store", type=click.Path(path_type=Path), default=Path(".truthcore/spine"))
    def health_cmd(store: Path):
        """Check spine health."""
        try:
            store_obj = GraphStore(store)
            
            # Basic health checks
            checks = {
                "storage_accessible": store.exists(),
                "can_read": False,
                "can_write": False,
            }
            
            try:
                # Test read
                store_obj.list_assertions()
                checks["can_read"] = True
            except:
                pass
            
            try:
                # Test write (create and remove temp file)
                test_path = store / ".health_test"
                test_path.touch()
                test_path.unlink()
                checks["can_write"] = True
            except:
                pass
            
            all_healthy = all(checks.values())
            
            lines = [
                f"# Spine Health: {'✅ HEALTHY' if all_healthy else '❌ UNHEALTHY'}",
                "",
                "## Checks",
            ]
            
            for check, status in checks.items():
                symbol = "✅" if status else "❌"
                lines.append(f"- {symbol} {check}")
            
            click.echo("\n".join(lines))
            
            if not all_healthy:
                sys.exit(1)
                
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
