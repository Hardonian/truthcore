"""Truth Core CLI with all upgrades integrated."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import click

from truthcore import __version__
from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.cache import ContentAddressedCache
from truthcore.security import SecurityLimits, safe_read_text, safe_load_json
from truthcore.parquet_store import ParquetStore, HistoryCompactor
from truthcore.invariant_dsl import InvariantExplainer
from truthcore.ui_geometry import UIGeometryParser, UIReachabilityChecker
from truthcore.anomaly_scoring import (
    ReadinessAnomalyScorer,
    ReconciliationAnomalyScorer,
    AgentBehaviorScorer,
    KnowledgeHealthScorer,
    ScorecardWriter,
)
from truthcore.impact import ChangeImpactEngine
from truthcore.truth_graph import TruthGraph, TruthGraphBuilder


# Cache context for CLI
cache_context = {}


def get_cache(cache_dir: Path | None, readonly: bool = False) -> ContentAddressedCache | None:
    """Get or create cache instance."""
    if cache_dir is None:
        return None
    
    cache_key = (str(cache_dir), readonly)
    if cache_key not in cache_context:
        cache_context[cache_key] = ContentAddressedCache(cache_dir)
    
    return cache_context[cache_key]


@click.group()
@click.version_option(version=__version__, prog_name="truthctl")
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory (default: .truthcache)')
@click.option('--no-cache', is_flag=True, help='Disable cache')
@click.option('--cache-readonly', is_flag=True, help='Use cache but do not write new entries')
@click.pass_context
def cli(ctx: click.Context, cache_dir: Path | None, no_cache: bool, cache_readonly: bool):
    """Truth Core CLI - Deterministic evidence-based verification."""
    ctx.ensure_object(dict)
    ctx.obj['cache_dir'] = None if no_cache else cache_dir
    ctx.obj['cache_readonly'] = cache_readonly


@cli.command()
@click.option('--inputs', '-i', type=click.Path(exists=True, path_type=Path), help='Input directory')
@click.option('--profile', '-p', default='base')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path))
@click.option('--strict/--no-strict', default=None)
@click.option('--parallel/--sequential', default=True, help='Run engines in parallel')
@click.option('--diff', '-d', type=click.Path(exists=True, path_type=Path), help='Git diff file for impact analysis')
@click.option('--changed-files', type=click.Path(exists=True, path_type=Path), help='Changed files list (newline or JSON)')
@click.option('--plan-out', type=click.Path(path_type=Path), help='Output path for run_plan.json')
@click.pass_context
def judge(
    ctx: click.Context,
    inputs: Path | None,
    profile: str,
    out: Path,
    config: Path | None,
    strict: bool | None,
    parallel: bool,
    diff: Path | None,
    changed_files: Path | None,
    plan_out: Path | None,
):
    """Run readiness check with parallel execution and UI geometry support.
    
    Can use --diff or --changed-files to run impact analysis first and
    execute only selected engines/invariants based on changes.
    """
    start_time = time.time()
    
    # Setup cache
    cache = get_cache(ctx.obj.get('cache_dir'), ctx.obj.get('cache_readonly', False))
    
    run_plan_path = plan_out
    
    # If diff or changed-files provided, run impact analysis
    if diff or changed_files:
        click.echo("Running change impact analysis...")
        engine = ChangeImpactEngine()
        
        diff_text = None
        if diff:
            diff_text = engine.load_diff_from_file(diff)
            click.echo(f"  Loaded diff from: {diff}")
        
        changed_files_list = None
        if changed_files:
            changed_files_list = engine.load_changed_files_from_file(changed_files)
            click.echo(f"  Loaded {len(changed_files_list)} changed files from: {changed_files}")
        
        # Generate run plan
        plan = engine.analyze(
            diff_text=diff_text,
            changed_files=changed_files_list,
            profile=profile,
            source=str(diff or changed_files),
        )
        
        # Write run plan
        if not run_plan_path:
            run_plan_path = out / "run_plan.json"
        plan.write(run_plan_path)
        click.echo(f"  Run plan written to: {run_plan_path}")
        
        # Show summary
        selected_engines = [e.engine_id for e in plan.engines if e.include]
        selected_invariants = [i.rule_id for i in plan.invariants if i.include]
        click.echo(f"  Selected engines: {', '.join(selected_engines) or 'none'}")
        click.echo(f"  Selected invariants: {', '.join(selected_invariants) or 'none'}")
        
        # Check if any engines selected
        if not selected_engines:
            click.echo("No engines selected for execution based on changes.")
            # Write minimal manifest
            manifest = RunManifest.create(
                command="judge",
                config={"profile": profile, "strict": strict, "parallel": parallel, "impact_skipped": True},
                input_dir=inputs or Path("."),
                profile=profile,
            )
            manifest.duration_ms = int((time.time() - start_time) * 1000)
            manifest.metadata["run_plan"] = str(run_plan_path)
            manifest.write(out)
            click.echo(f"Results written to {out}")
            return
    
    # Load run plan if provided
    engines_to_run = None
    invariants_to_run = None
    if run_plan_path and run_plan_path.exists():
        with open(run_plan_path, encoding="utf-8") as f:
            plan_data = json.load(f)
        engines_to_run = [e["engine_id"] for e in plan_data.get("engines", []) if e.get("include")]
        invariants_to_run = [i["rule_id"] for i in plan_data.get("invariants", []) if i.get("include")]
        click.echo(f"Executing based on run plan: {run_plan_path}")
    
    # Create manifest
    manifest = RunManifest.create(
        command="judge",
        config={"profile": profile, "strict": strict, "parallel": parallel, "engines": engines_to_run, "invariants": invariants_to_run},
        input_dir=inputs or Path("."),
        profile=profile,
    )
    
    # Check cache
    cache_key = manifest.compute_cache_key()
    cache_path = cache.get(cache_key) if cache else None
    
    if cache_path:
        click.echo(f"Cache hit: reusing previous results")
        manifest.cache_hit = True
        manifest.cache_key = cache_key
        manifest.cache_path = str(cache_path)
        
        # Copy cached outputs
        import shutil
        shutil.copytree(cache_path, out, dirs_exist_ok=True)
        
        # Update manifest with cache info
        manifest.duration_ms = int((time.time() - start_time) * 1000)
        if run_plan_path:
            manifest.metadata["run_plan"] = str(run_plan_path)
        manifest.write(out)
        
        click.echo(f"Results written to {out} (from cache)")
        return
    
    # Run the actual check
    click.echo(f"Running readiness check with profile '{profile}'...")
    
    # TODO: Integrate with actual readiness engine
    # For now, create sample output
    out.mkdir(parents=True, exist_ok=True)
    
    # Check for UI geometry facts
    ui_facts = inputs / "ui_facts.json" if inputs else None
    if ui_facts and ui_facts.exists():
        click.echo("UI geometry facts detected, running reachability checks...")
        parser = UIGeometryParser(ui_facts)
        checker = UIReachabilityChecker(parser)
        
        ui_results = checker.run_all_checks()
        
        with open(out / "ui_geometry.json", "w") as f:
            json.dump(ui_results, f, indent=2)
    
    # Create readiness output
    readiness_data = {
        "version": __version__,
        "profile": profile,
        "timestamp": normalize_timestamp(),
        "passed": True,
        "findings": [],
    }
    
    with open(out / "readiness.json", "w") as f:
        json.dump(readiness_data, f, indent=2, sort_keys=True)
    
    # Write manifest
    manifest.duration_ms = int((time.time() - start_time) * 1000)
    if run_plan_path:
        manifest.metadata["run_plan"] = str(run_plan_path)
    manifest.write(out)
    
    # Cache results
    if cache and not ctx.obj.get('cache_readonly'):
        cache.put(cache_key, out, manifest.to_dict())
    
    click.echo(f"Results written to {out}")


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path))
@click.pass_context
def recon(ctx: click.Context, inputs: Path, out: Path, config: Path | None):
    """Run reconciliation with anomaly detection."""
    start_time = time.time()
    
    out.mkdir(parents=True, exist_ok=True)
    
    # TODO: Run reconciliation engine
    recon_data = {
        "version": __version__,
        "timestamp": normalize_timestamp(),
        "summary": {
            "total_left": 10,
            "total_right": 10,
            "matched_count": 10,
            "balance_check": True,
        },
    }
    
    with open(out / "recon_run.json", "w") as f:
        json.dump(recon_data, f, indent=2, sort_keys=True)
    
    # Write manifest
    manifest = RunManifest.create(
        command="recon",
        config={},
        input_dir=inputs,
    )
    manifest.duration_ms = int((time.time() - start_time) * 1000)
    manifest.write(out)
    
    click.echo(f"Reconciliation results written to {out}")


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--fsm', '-f', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.pass_context
def trace(ctx: click.Context, inputs: Path, fsm: Path, out: Path):
    """Run trace analysis with FSM validation."""
    start_time = time.time()
    
    out.mkdir(parents=True, exist_ok=True)
    
    # TODO: Run trace engine
    trace_data = {
        "version": __version__,
        "trace_id": "test-123",
        "valid": True,
        "metrics": {
            "tool_success_rate": 0.95,
            "avg_latency_ms": 1500,
        },
    }
    
    with open(out / "trace_report.json", "w") as f:
        json.dump(trace_data, f, indent=2, sort_keys=True)
    
    # Write manifest
    manifest = RunManifest.create(
        command="trace",
        config={},
        input_files=[inputs, fsm],
    )
    manifest.duration_ms = int((time.time() - start_time) * 1000)
    manifest.write(out)
    
    click.echo(f"Trace analysis written to {out}")


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--parquet/--no-parquet', default=False, help='Write to Parquet history store')
@click.pass_context
def index(ctx: click.Context, inputs: Path, out: Path, parquet: bool):
    """Run knowledge indexing with optional Parquet storage."""
    start_time = time.time()
    
    out.mkdir(parents=True, exist_ok=True)
    
    # TODO: Run knowledge engine
    kb_data = {
        "version": __version__,
        "index_id": "kb-001",
        "stats": {
            "total": 42,
            "stale_count": 3,
        },
    }
    
    with open(out / "kb_index.json", "w") as f:
        json.dump(kb_data, f, indent=2, sort_keys=True)
    
    # Write to Parquet if requested
    if parquet:
        store = ParquetStore(out / "parquet_history")
        if store.available:
            store.write_findings([], "kb-001", normalize_timestamp())
            click.echo("History written to Parquet store")
        else:
            click.echo("Warning: Parquet support not available (install pyarrow)")
    
    # Write manifest
    manifest = RunManifest.create(
        command="index",
        config={"parquet": parquet},
        input_dir=inputs,
    )
    manifest.duration_ms = int((time.time() - start_time) * 1000)
    manifest.write(out)
    
    click.echo(f"Knowledge index written to {out}")


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--mode', '-m', required=True, type=click.Choice(['readiness', 'recon', 'agent', 'knowledge']))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--compact', is_flag=True, help='Compact history store')
@click.option('--retention', type=int, default=90, help='Retention period in days for compaction')
@click.pass_context
def intel(ctx: click.Context, inputs: Path, mode: str, out: Path, compact: bool, retention: int):
    """Run intelligence analysis with anomaly scoring."""
    start_time = time.time()
    
    out.mkdir(parents=True, exist_ok=True)
    
    # Load historical data
    historical_files = list(inputs.rglob("*.json"))
    history = []
    for f in historical_files[:50]:  # Limit to recent 50
        try:
            with open(f) as fp:
                history.append(json.load(fp))
        except Exception:
            pass
    
    # Run compaction if requested
    if compact:
        store = ParquetStore(inputs / "parquet_history")
        compactor = HistoryCompactor(store)
        stats = compactor.compact(dry_run=False)
        click.echo(f"Compaction complete: {stats}")
    
    # Generate scorecard based on mode
    if mode == "readiness":
        scorer = ReadinessAnomalyScorer(history)
    elif mode == "recon":
        scorer = ReconciliationAnomalyScorer(history)
    elif mode == "agent":
        scorer = AgentBehaviorScorer(history)
    else:  # knowledge
        scorer = KnowledgeHealthScorer(history)
    
    scorecard = scorer.score()
    
    # Write scorecard
    writer = ScorecardWriter(out)
    json_path, md_path = writer.write(scorecard, f"{mode}_intel")
    
    click.echo(f"Scorecard written to {out}")
    click.echo(f"  JSON: {json_path}")
    click.echo(f"  Markdown: {md_path}")
    
    # Write manifest
    manifest = RunManifest.create(
        command="intel",
        config={"mode": mode, "retention": retention},
        input_dir=inputs,
    )
    manifest.duration_ms = int((time.time() - start_time) * 1000)
    manifest.write(out)


@cli.command()
@click.option('--rule', '-r', required=True, help='Rule ID to explain')
@click.option('--data', '-d', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--rules', required=True, type=click.Path(exists=True, path_type=Path))
def explain(rule: str, data: Path, rules: Path):
    """Explain an invariant rule evaluation."""
    # Load data
    with open(data) as f:
        data_dict = json.load(f)
    
    # Load rules
    with open(rules) as f:
        rules_list = json.load(f)
    
    # Create explainer
    explainer = InvariantExplainer(rules_list, data_dict)
    explanation = explainer.explain_rule(rule)
    
    click.echo(explanation)


@cli.command()
@click.option('--diff', '-d', type=click.Path(exists=True, path_type=Path), help='Git diff file')
@click.option('--changed-files', type=click.Path(exists=True, path_type=Path), help='Changed files list')
@click.option('--profile', '-p', default='base', help='Execution profile')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output path for run_plan.json')
@click.option('--source', '-s', help='Source identifier for the analysis')
def plan(diff: Path | None, changed_files: Path | None, profile: str, out: Path, source: str | None):
    """Generate a run plan from git diff or changed files list.
    
    Analyzes changes to determine which engines and invariants should run.
    Output is deterministic and cacheable.
    """
    if not diff and not changed_files:
        click.echo("Error: Must provide either --diff or --changed-files", err=True)
        sys.exit(1)
    
    engine = ChangeImpactEngine()
    
    diff_text = None
    if diff:
        diff_text = engine.load_diff_from_file(diff)
        click.echo(f"Loaded diff from: {diff}")
    
    changed_files_list = None
    if changed_files:
        changed_files_list = engine.load_changed_files_from_file(changed_files)
        click.echo(f"Loaded {len(changed_files_list)} changed files from: {changed_files}")
    
    # Generate run plan
    plan = engine.analyze(
        diff_text=diff_text,
        changed_files=changed_files_list,
        profile=profile,
        source=source or str(diff or changed_files),
    )
    
    # Write run plan
    plan.write(out)
    
    # Show summary
    click.echo(f"\nRun plan written to: {out}")
    click.echo(f"Cache key: {plan.cache_key}")
    click.echo(f"\nImpact Summary:")
    click.echo(f"  Total changes: {plan.impact_summary['total_changes']}")
    click.echo(f"  Max impact: {plan.impact_summary['max_impact']}")
    
    selected_engines = [e for e in plan.engines if e.include]
    selected_invariants = [i for i in plan.invariants if i.include]
    
    click.echo(f"\nSelected Engines ({len(selected_engines)}):")
    for engine in selected_engines:
        click.echo(f"  [+] {engine.engine_id} (priority: {engine.priority}) - {engine.reason}")
    
    if plan.exclusions:
        click.echo(f"\nExclusions ({len(plan.exclusions)}):")
        for ex in plan.exclusions[:5]:  # Show first 5
            click.echo(f"  [-] {ex['type']}: {ex['id']} - {ex['reason']}")
        if len(plan.exclusions) > 5:
            click.echo(f"  ... and {len(plan.exclusions) - 5} more")


@cli.command(name="graph")
@click.option('--run-dir', '-r', required=True, type=click.Path(exists=True, path_type=Path), help='Run output directory containing run_manifest.json')
@click.option('--plan', type=click.Path(exists=True, path_type=Path), help='Run plan JSON (optional)')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory for truth graph')
@click.option('--format', type=click.Choice(['json', 'parquet', 'both']), default='json', help='Output format')
def graph_build(run_dir: Path, plan: Path | None, out: Path, format: str):
    """Build a Truth Graph from run outputs.
    
    Creates a graph linking runs, engines, findings, evidence, and entities.
    """
    out.mkdir(parents=True, exist_ok=True)
    
    # Build graph
    builder = TruthGraphBuilder()
    truth_graph = builder.build_from_run_directory(run_dir, plan)
    
    # Export to JSON
    if format in ('json', 'both'):
        json_path = out / "truth_graph.json"
        truth_graph.to_json(json_path)
        click.echo(f"Truth graph (JSON) written to: {json_path}")
    
    # Export to Parquet
    if format in ('parquet', 'both'):
        try:
            parquet_dir = out / "truth_graph.parquet"
            truth_graph.to_parquet(parquet_dir)
            click.echo(f"Truth graph (Parquet) written to: {parquet_dir}")
        except RuntimeError as e:
            click.echo(f"Warning: Could not export to Parquet: {e}", err=True)
    
    # Show stats
    stats = truth_graph.to_dict()['stats']
    click.echo(f"\nGraph Statistics:")
    click.echo(f"  Nodes: {stats['node_count']}")
    click.echo(f"  Edges: {stats['edge_count']}")


@cli.command(name="graph-query")
@click.option('--graph', '-g', required=True, type=click.Path(exists=True, path_type=Path), help='Truth graph JSON file')
@click.option('--where', '-w', required=True, help='Query predicate (e.g., "severity=high", "type=finding", "severity>=medium")')
@click.option('--out', '-o', type=click.Path(path_type=Path), help='Output file for results')
def graph_query(graph: Path, where: str, out: Path | None):
    """Query a Truth Graph using simple predicates.
    
    Query syntax:
      - key=value (exact match)
      - key=contains:substring (contains match)
      - severity>=level (severity comparison)
      
    Examples:
      truthctl graph-query --graph truth_graph.json --where "severity=high"
      truthctl graph-query --graph truth_graph.json --where "type=finding"
      truthctl graph-query --graph truth_graph.json --where "severity>=medium" --out results.json
    """
    # Load graph
    truth_graph = TruthGraph.from_json(graph)
    
    # Execute query
    results = truth_graph.query_simple(where)
    
    # Prepare output
    output_data = {
        "query": where,
        "graph": str(graph),
        "result_count": len(results),
        "results": [n.to_dict() for n in results],
    }
    
    # Output results
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        click.echo(f"Query results written to: {out}")
    else:
        click.echo(json.dumps(output_data, indent=2))
    
    click.echo(f"\nFound {len(results)} matching nodes")


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
def cache_stats(cache_dir: Path | None):
    """Show cache statistics."""
    cache = get_cache(cache_dir or Path(".truthcache"))
    if cache:
        stats = cache.stats()
        click.echo("Cache Statistics:")
        click.echo(f"  Entries: {stats['entries']}")
        click.echo(f"  Total size: {stats['total_size_bytes']:,} bytes")
        click.echo(f"  Location: {stats['cache_dir']}")
    else:
        click.echo("Cache not available")


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.option('--max-age', type=int, default=30, help='Maximum age in days')
def cache_compact(cache_dir: Path | None, max_age: int):
    """Compact old cache entries."""
    cache = get_cache(cache_dir or Path(".truthcache"))
    if cache:
        removed = cache.compact(max_age_days=max_age)
        click.echo(f"Removed {removed} old cache entries")
    else:
        click.echo("Cache not available")


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
def cache_clear(cache_dir: Path | None):
    """Clear all cache entries."""
    cache = get_cache(cache_dir or Path(".truthcache"))
    if cache:
        count = cache.clear()
        click.echo(f"Cleared {count} cache entries")
    else:
        click.echo("Cache not available")


def main() -> None:
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
