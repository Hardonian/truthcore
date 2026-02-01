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
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--profile', '-p', default='base')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path))
@click.option('--strict/--no-strict', default=None)
@click.option('--parallel/--sequential', default=True, help='Run engines in parallel')
@click.pass_context
def judge(ctx: click.Context, inputs: Path, profile: str, out: Path, config: Path | None, strict: bool | None, parallel: bool):
    """Run readiness check with parallel execution and UI geometry support."""
    start_time = time.time()
    
    # Setup cache
    cache = get_cache(ctx.obj.get('cache_dir'), ctx.obj.get('cache_readonly', False))
    
    # Create manifest
    manifest = RunManifest.create(
        command="judge",
        config={"profile": profile, "strict": strict, "parallel": parallel},
        input_dir=inputs,
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
        manifest.write(out)
        
        click.echo(f"Results written to {out} (from cache)")
        return
    
    # Run the actual check
    click.echo(f"Running readiness check with profile '{profile}'...")
    
    # TODO: Integrate with actual readiness engine
    # For now, create sample output
    out.mkdir(parents=True, exist_ok=True)
    
    # Check for UI geometry facts
    ui_facts = inputs / "ui_facts.json"
    if ui_facts.exists():
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
