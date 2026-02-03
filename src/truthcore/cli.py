"""Truth Core CLI with all upgrades integrated."""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import click

from truthcore import __version__
from truthcore.anomaly_scoring import (
    AgentBehaviorScorer,
    KnowledgeHealthScorer,
    ReadinessAnomalyScorer,
    ReconciliationAnomalyScorer,
    ScorecardWriter,
)
from truthcore.cache import ContentAddressedCache
from truthcore.impact import ChangeImpactEngine
from truthcore.invariant_dsl import InvariantExplainer
from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.parquet_store import HistoryCompactor, ParquetStore
from truthcore.replay import (
    BundleExporter,
    ReplayBundle,
    ReplayEngine,
    ReplayReporter,
    SimulationChanges,
    SimulationEngine,
    SimulationReporter,
)
from truthcore.truth_graph import TruthGraph, TruthGraphBuilder
from truthcore.ui_geometry import UIGeometryParser, UIReachabilityChecker
from truthcore.verdict.cli import generate_verdict_for_judge, register_verdict_commands


def register_spine_commands(cli: click.Group) -> None:
    """Register spine CLI commands."""
    try:
        from truthcore.spine.cli import register_spine_commands as _register
        _register(cli)
    except ImportError:
        # Spine module not available
        pass


def handle_error(error: Exception, debug: bool) -> None:
    """Handle errors with structured output.

    Args:
        error: The exception that occurred
        debug: Whether to show full traceback
    """
    if debug:
        traceback.print_exc()
    else:
        click.echo(f"Error: {error}", err=True)
    sys.exit(1)


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
@click.option('--debug', is_flag=True, help='Enable debug mode (show full tracebacks)')
@click.pass_context
def cli(ctx: click.Context, cache_dir: Path | None, no_cache: bool, cache_readonly: bool, debug: bool):
    """Truth Core CLI - Deterministic evidence-based verification."""
    ctx.ensure_object(dict)
    ctx.obj['cache_dir'] = None if no_cache else cache_dir
    ctx.obj['cache_readonly'] = cache_readonly
    ctx.obj['debug'] = debug


# Register verdict commands
register_verdict_commands(cli)

# Register spine commands (read-only truth spine)
register_spine_commands(cli)


@cli.command()
@click.option('--inputs', '-i', type=click.Path(exists=True, path_type=Path), help='Input directory')
@click.option('--profile', '-p', default='base')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path))
@click.option('--strict/--no-strict', default=None)
@click.option('--parallel/--sequential', default=True, help='Run engines in parallel')
@click.option('--diff', '-d', type=click.Path(exists=True, path_type=Path), help='Git diff file for impact analysis')
@click.option(
    '--changed-files',
    type=click.Path(exists=True, path_type=Path),
    help='Changed files list (newline or JSON)',
)
@click.option('--plan-out', type=click.Path(path_type=Path), help='Output path for run_plan.json')
@click.option('--policy-pack', type=str, help='Policy pack to run (built-in name or path)')
@click.option('--sign/--no-sign', default=False, help='Sign the evidence bundle (requires signing keys)')
@click.option('--manifest/--no-manifest', default=True, help='Generate evidence manifest')
@click.option('--compat', is_flag=True, help='Enable backward compatibility mode (legacy formats)')
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
    policy_pack: str | None,
    sign: bool,
    manifest: bool,
    compat: bool,
):
    """Run readiness check with parallel execution and UI geometry support.

    Can use --diff or --changed-files to run impact analysis first and
    execute only selected engines/invariants based on changes.

    Optionally runs policy pack (--policy-pack) and generates provenance
    (--sign, --manifest).

    Use --compat for backward compatibility with truth-core < 0.2.0.
    """
    start_time = time.time()
    debug = ctx.obj.get('debug', False)

    try:
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
                manifest_obj = RunManifest.create(
                    command="judge",
                    config={"profile": profile, "strict": strict, "parallel": parallel, "impact_skipped": True},
                    input_dir=inputs or Path("."),
                    profile=profile,
                )
                manifest_obj.duration_ms = int((time.time() - start_time) * 1000)
                manifest_obj.metadata["run_plan"] = str(run_plan_path)
                manifest_obj.write(out)
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
        run_manifest = RunManifest.create(
            command="judge",
            config={
                "profile": profile,
                "strict": strict,
                "parallel": parallel,
                "engines": engines_to_run,
                "invariants": invariants_to_run,
            },
            input_dir=inputs or Path("."),
            profile=profile,
        )

        # Check cache
        cache_key = run_manifest.compute_cache_key()
        cache_path = cache.get(cache_key) if cache else None

        if cache_path:
            click.echo("Cache hit: reusing previous results")
            run_manifest.cache_hit = True
            run_manifest.cache_key = cache_key
            run_manifest.cache_path = str(cache_path)

            # Copy cached outputs
            import shutil
            shutil.copytree(cache_path, out, dirs_exist_ok=True)

            # Update manifest with cache info
            run_manifest.duration_ms = int((time.time() - start_time) * 1000)
            if run_plan_path:
                run_manifest.metadata["run_plan"] = str(run_plan_path)
            run_manifest.write(out)

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

        # Run policy pack if specified
        if policy_pack:
            click.echo(f"Running policy pack: {policy_pack}...")
            from truthcore.policy.engine import PolicyEngine, PolicyPackLoader

            pack = PolicyPackLoader.load_pack(policy_pack)
            policy_engine = PolicyEngine(inputs or Path("."), out)
            policy_result = policy_engine.run_pack(pack)
            policy_engine.write_outputs(policy_result)

            click.echo(f"  Policy findings: {len(policy_result.findings)}")
            if policy_result.has_blocking():
                click.echo("  ⚠️  Blocking policy violations detected!")

        # Generate evidence manifest
        if manifest:
            click.echo("Generating evidence manifest...")
            from truthcore.provenance.manifest import EvidenceManifest
            from truthcore.security import SecurityLimits

            evidence_manifest = EvidenceManifest.generate(
                bundle_dir=out,
                run_manifest_hash=run_manifest.compute_cache_key(),
                config_hash=run_manifest.config_hash,
                limits=SecurityLimits(),
            )
            evidence_manifest.write_json(out / "evidence.manifest.json")
            click.echo(f"  Manifest: {out / 'evidence.manifest.json'}")

            # Sign if requested
            if sign:
                from truthcore.provenance.signing import Signer, SigningError

                signer = Signer()
                if signer.is_configured():
                    try:
                        manifest_path = out / "evidence.manifest.json"
                        signer.sign_file(manifest_path, out / "evidence.sig")
                        click.echo(f"  Signature: {out / 'evidence.sig'}")
                    except SigningError as e:
                        click.echo(f"  Warning: Signing failed: {e}", err=True)
                else:
                    click.echo(
                        "  Warning: Signing requested but no keys configured. "
                        "Set TRUTHCORE_SIGNING_PRIVATE_KEY env var.",
                        err=True,
                    )

        # Write manifest
        run_manifest.duration_ms = int((time.time() - start_time) * 1000)
        if run_plan_path:
            run_manifest.metadata["run_plan"] = str(run_plan_path)
        run_manifest.write(out)

        # Cache results
        if cache and not ctx.obj.get('cache_readonly'):
            cache.put(cache_key, out, run_manifest.to_dict())

        # Generate verdict
        click.echo("Generating verdict...")
        verdict_path = generate_verdict_for_judge(
            inputs_dir=inputs or Path("."),
            output_dir=out,
            mode="pr",
            profile=profile,
        )
        if verdict_path:
            click.echo(f"  Verdict: {verdict_path}")

        click.echo(f"Results written to {out}")
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path))
@click.pass_context
def recon(ctx: click.Context, inputs: Path, out: Path, config: Path | None):
    """Run reconciliation with anomaly detection."""
    start_time = time.time()
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--fsm', '-f', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.pass_context
def trace(ctx: click.Context, inputs: Path, fsm: Path, out: Path):
    """Run trace analysis with FSM validation."""
    start_time = time.time()
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--inputs', '-i', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path))
@click.option('--parquet/--no-parquet', default=False, help='Write to Parquet history store')
@click.pass_context
def index(ctx: click.Context, inputs: Path, out: Path, parquet: bool):
    """Run knowledge indexing with optional Parquet storage."""
    start_time = time.time()
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


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
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--rule', '-r', required=True, help='Rule ID to explain')
@click.option('--data', '-d', required=True, type=click.Path(exists=True, path_type=Path))
@click.option('--rules', required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def explain(ctx: click.Context, rule: str, data: Path, rules: Path):
    """Explain an invariant rule evaluation."""
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--diff', '-d', type=click.Path(exists=True, path_type=Path), help='Git diff file')
@click.option('--changed-files', type=click.Path(exists=True, path_type=Path), help='Changed files list')
@click.option('--profile', '-p', default='base', help='Execution profile')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output path for run_plan.json')
@click.option('--source', '-s', help='Source identifier for the analysis')
@click.pass_context
def plan(
    ctx: click.Context,
    diff: Path | None,
    changed_files: Path | None,
    profile: str,
    out: Path,
    source: str | None,
):
    """Generate a run plan from git diff or changed files list.

    Analyzes changes to determine which engines and invariants should run.
    Output is deterministic and cacheable.
    """
    debug = ctx.obj.get('debug', False)

    try:
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
        run_plan = engine.analyze(
            diff_text=diff_text,
            changed_files=changed_files_list,
            profile=profile,
            source=source or str(diff or changed_files),
        )

        # Write run plan
        run_plan.write(out)

        # Show summary
        click.echo(f"\nRun plan written to: {out}")
        click.echo(f"Cache key: {run_plan.cache_key}")
        click.echo("\nImpact Summary:")
        click.echo(f"  Total changes: {run_plan.impact_summary['total_changes']}")
        click.echo(f"  Max impact: {run_plan.impact_summary['max_impact']}")

        selected_engines = [e for e in run_plan.engines if e.include]

        click.echo(f"\nSelected Engines ({len(selected_engines)}):")
        for eng in selected_engines:
            click.echo(f"  [+] {eng.engine_id} (priority: {eng.priority}) - {eng.reason}")

        if run_plan.exclusions:
            click.echo(f"\nExclusions ({len(run_plan.exclusions)}):")
            for ex in run_plan.exclusions[:5]:  # Show first 5
                click.echo(f"  [-] {ex['type']}: {ex['id']} - {ex['reason']}")
            if len(run_plan.exclusions) > 5:
                click.echo(f"  ... and {len(run_plan.exclusions) - 5} more")
    except Exception as e:
        handle_error(e, debug)


@cli.command(name="graph")
@click.option(
    '--run-dir', '-r', required=True,
    type=click.Path(exists=True, path_type=Path),
    help='Run output directory containing run_manifest.json',
)
@click.option('--plan', type=click.Path(exists=True, path_type=Path), help='Run plan JSON (optional)')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory for truth graph')
@click.option('--format', type=click.Choice(['json', 'parquet', 'both']), default='json', help='Output format')
@click.pass_context
def graph_build(ctx: click.Context, run_dir: Path, plan: Path | None, out: Path, format: str):
    """Build a Truth Graph from run outputs.

    Creates a graph linking runs, engines, findings, evidence, and entities.
    """
    debug = ctx.obj.get('debug', False)

    try:
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
        click.echo("\nGraph Statistics:")
        click.echo(f"  Nodes: {stats['node_count']}")
        click.echo(f"  Edges: {stats['edge_count']}")
    except Exception as e:
        handle_error(e, debug)


@cli.command(name="graph-query")
@click.option(
    '--graph', '-g', required=True,
    type=click.Path(exists=True, path_type=Path),
    help='Truth graph JSON file',
)
@click.option(
    '--where', '-w', required=True,
    help='Query predicate (e.g., "severity=high")',
)
@click.option('--out', '-o', type=click.Path(path_type=Path), help='Output file for results')
@click.pass_context
def graph_query(ctx: click.Context, graph: Path, where: str, out: Path | None):
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
    debug = ctx.obj.get('debug', False)

    try:
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
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option(
    '--inputs', '-i', required=True,
    type=click.Path(exists=True, path_type=Path),
    help='Input directory to scan',
)
@click.option(
    '--pack', '-p', required=True,
    help='Policy pack name (built-in: base, security, privacy, '
         'logging, agent) or path to YAML file',
)
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory')
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path), help='Policy configuration file')
@click.option('--compat', is_flag=True, help='Enable backward compatibility mode (legacy formats, relaxed validation)')
@click.pass_context
def policy_run(ctx: click.Context, inputs: Path, pack: str, out: Path, config: Path | None, compat: bool):
    """Run policy-as-code scanner against inputs.

    Built-in packs: base, security, privacy, logging, agent

    Examples:
      truthctl policy run --inputs ./src --pack base --out ./policy-results
      truthctl policy run --inputs ./src --pack security --out ./security-report
      truthctl policy run --inputs ./src --pack /path/to/custom-policy.yaml --out ./results
    """
    import time

    from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
    from truthcore.policy.validator import PolicyValidator

    debug = ctx.obj.get('debug', False)

    try:
        start_time = time.time()

        click.echo(f"Loading policy pack: {pack}...")
        policy_pack = PolicyPackLoader.load_pack(pack)

        # Validate pack
        validator = PolicyValidator()
        errors = validator.validate_pack(policy_pack.to_dict())
        if errors:
            click.echo("Warning: Policy validation errors:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)

        click.echo(f"Running policy scan on: {inputs}...")
        engine = PolicyEngine(inputs, out)
        result = engine.run_pack(policy_pack)

        # Write outputs
        paths = engine.write_outputs(result, base_name="policy")

        duration_ms = int((time.time() - start_time) * 1000)

        click.echo(f"\nPolicy scan complete in {duration_ms}ms")
        click.echo(f"  Rules evaluated: {result.rules_evaluated}")
        click.echo(f"  Rules triggered: {result.rules_triggered}")
        click.echo(f"  Findings: {len(result.findings)}")

        if result.has_blocking():
            blocker_count = sum(1 for f in result.findings if f.severity.value == "BLOCKER")
            click.echo(f"  ⚠️  {blocker_count} BLOCKER findings detected!")

        click.echo(f"\nOutputs written to {out}:")
        click.echo(f"  - JSON:  {paths['json']}")
        click.echo(f"  - MD:    {paths['markdown']}")
        click.echo(f"  - CSV:   {paths['csv']}")
    except FileNotFoundError as e:
        handle_error(e, debug)
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--rule', '-r', required=True, help='Rule ID to explain')
@click.option('--pack', '-p', required=True, help='Policy pack name or path')
@click.pass_context
def policy_explain(ctx: click.Context, rule: str, pack: str):
    """Explain a policy rule.

    Shows the rule definition, matchers, thresholds, and suppressions.

    Example:
      truthctl policy explain --rule SECRET_API_KEY_DETECTED --pack security
    """
    from truthcore.policy.engine import PolicyEngine, PolicyPackLoader

    debug = ctx.obj.get('debug', False)

    try:
        policy_pack = PolicyPackLoader.load_pack(pack)
        policy_rule = policy_pack.get_rule(rule)

        if not policy_rule:
            click.echo(f"Rule not found: {rule}", err=True)
            available = [r.id for r in policy_pack.get_enabled_rules()]
            click.echo(f"Available rules: {', '.join(available)}", err=True)
            sys.exit(1)

        explanation = PolicyEngine.explain_rule(policy_rule)
        click.echo(explanation)
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option(
    '--bundle', '-b', required=True,
    type=click.Path(exists=True, path_type=Path),
    help='Bundle directory to verify',
)
@click.option(
    '--public-key', '-k',
    type=click.Path(exists=True, path_type=Path),
    help='Public key file for signature verification (optional)',
)
@click.option('--out', '-o', type=click.Path(path_type=Path), help='Output directory for verification reports')
@click.pass_context
def verify_bundle(ctx: click.Context, bundle: Path, public_key: Path | None, out: Path | None):
    """Verify an evidence bundle for tampering.

    Recomputes file hashes and compares against manifest.
    Optionally verifies signature if public key is provided.

    Examples:
      truthctl verify-bundle --bundle ./results
      truthctl verify-bundle --bundle ./results --public-key ./public.key
      truthctl verify-bundle --bundle ./results --out ./verification-report
    """
    from truthcore.provenance.signing import Signer
    from truthcore.provenance.verifier import BundleVerifier

    debug = ctx.obj.get('debug', False)

    try:
        click.echo(f"Verifying bundle: {bundle}...")

        # Load public key if provided
        pub_key = None
        if public_key:
            with open(public_key, "rb") as f:
                pub_key = f.read()
            click.echo(f"Using public key: {public_key}")
        else:
            # Try to load from environment
            signer = Signer()
            if signer._public_key:
                pub_key = signer._public_key
                click.echo("Using public key from TRUTHCORE_SIGNING_PUBLIC_KEY environment variable")

        # Verify
        verifier = BundleVerifier(public_key=pub_key)

        if out:
            result, paths = verifier.verify_and_report(bundle, out)
            click.echo("\nVerification reports written to:")
            click.echo(f"  - JSON: {paths['json']}")
            click.echo(f"  - MD:   {paths['markdown']}")
        else:
            result = verifier.verify(bundle)

        # Print summary
        click.echo(f"\nVerification Result: {'✅ VALID' if result.valid else '❌ INVALID'}")
        click.echo(f"  Files checked: {result.files_checked}")
        click.echo(f"  Files valid: {result.files_valid}")

        if result.files_tampered:
            click.echo(f"  ⚠️  Files tampered: {len(result.files_tampered)}")
            for item in result.files_tampered:
                click.echo(f"    - {item['path']}")

        if result.files_missing:
            click.echo(f"  ⚠️  Files missing: {len(result.files_missing)}")
            for path in result.files_missing:
                click.echo(f"    - {path}")

        if result.files_added:
            click.echo(f"  ℹ️  Files added (not in manifest): {len(result.files_added)}")

        if result.signature_valid is not None:
            click.echo(f"  Signature: {'✅ VALID' if result.signature_valid else '❌ INVALID'}")

        # Exit with error code if invalid
        if not result.valid:
            sys.exit(1)
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.pass_context
def cache_stats(ctx: click.Context, cache_dir: Path | None):
    """Show cache statistics."""
    debug = ctx.obj.get('debug', False)

    try:
        cache = get_cache(cache_dir or Path(".truthcache"))
        if cache:
            stats = cache.stats()
            click.echo("Cache Statistics:")
            click.echo(f"  Entries: {stats['entries']}")
            click.echo(f"  Total size: {stats['total_size_bytes']:,} bytes")
            click.echo(f"  Location: {stats['cache_dir']}")
        else:
            click.echo("Cache not available")
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.option('--max-age', type=int, default=30, help='Maximum age in days')
@click.pass_context
def cache_compact(ctx: click.Context, cache_dir: Path | None, max_age: int):
    """Compact old cache entries."""
    debug = ctx.obj.get('debug', False)

    try:
        cache = get_cache(cache_dir or Path(".truthcache"))
        if cache:
            removed = cache.compact(max_age_days=max_age)
            click.echo(f"Removed {removed} old cache entries")
        else:
            click.echo("Cache not available")
    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.confirmation_option(prompt='Are you sure you want to clear the cache?')
@click.pass_context
def cache_clear(ctx: click.Context, cache_dir: Path | None):
    """Clear all cache entries."""
    debug = ctx.obj.get('debug', False)

    try:
        cache = get_cache(cache_dir or Path(".truthcache"))
        if cache:
            count = cache.clear()
            click.echo(f"Cleared {count} cache entries")
        else:
            click.echo("Cache not available")
    except Exception as e:
        handle_error(e, debug)


@cli.command()
def policy_list():
    """List available built-in policy packs."""
    from truthcore.policy.engine import PolicyPackLoader

    packs = PolicyPackLoader.list_built_in()
    click.echo("Available built-in policy packs:")
    for pack in packs:
        click.echo(f"  - {pack}")
    click.echo("\nUsage: truthctl policy run --inputs <dir> --pack <pack_name> --out <dir>")


@cli.command()
def generate_keys():
    """Generate signing keys for evidence bundles.

    Outputs environment variable format for TRUTHCORE_SIGNING_PRIVATE_KEY
    and TRUTHCORE_SIGNING_PUBLIC_KEY.
    """
    from truthcore.provenance.signing import Signer

    click.echo("Generating new Ed25519 key pair...")
    private_key, public_key = Signer.generate_keys()
    priv_b64, pub_b64 = Signer.keys_to_env_format(private_key, public_key)

    click.echo("\nAdd these to your environment:")
    click.echo(f"export TRUTHCORE_SIGNING_PRIVATE_KEY={priv_b64}")
    click.echo(f"export TRUTHCORE_SIGNING_PUBLIC_KEY={pub_b64}")

    click.echo("\nOr save to a file (keep private key secure!):")
    click.echo(f"echo '{priv_b64}' > signing_key.private")
    click.echo(f"echo '{pub_b64}' > signing_key.public")


@cli.group(name="bundle")
def bundle_group():
    """Manage replay bundles for deterministic replay and simulation."""
    pass


@bundle_group.command(name="export")
@click.option(
    "--run-dir", "-r",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing run outputs (with run_manifest.json)",
)
@click.option(
    "--inputs", "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Original inputs directory (if separate from run_dir)",
)
@click.option(
    "--out", "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory for the bundle",
)
@click.option(
    "--profile", "-p",
    help="Profile used for the run",
)
@click.option(
    "--mode", "-m",
    type=click.Choice(["pr", "main", "release"]),
    help="Mode used for the run",
)
@click.pass_context
def bundle_export(
    ctx: click.Context,
    run_dir: Path,
    inputs: Path | None,
    out: Path,
    profile: str | None,
    mode: str | None,
):
    """Export a run into a replay bundle.

    Captures all inputs, configuration, and outputs needed for
    deterministic replay and counterfactual simulation.

    Examples:
      truthctl bundle export --run-dir ./results --out ./my-bundle
      truthctl bundle export --run-dir ./results --inputs ./test-data --out ./bundle --profile ui
    """
    debug = ctx.obj.get("debug", False)

    try:
        exporter = BundleExporter()
        bundle = exporter.export(
            run_dir=run_dir,
            original_inputs_dir=inputs,
            out_bundle_dir=out,
            profile=profile,
            mode=mode,
        )

        click.echo(f"✅ Bundle exported to: {out}")
        click.echo("\nBundle contents:")
        click.echo(f"  - Run ID: {bundle.manifest.run_id}")
        click.echo(f"  - Command: {bundle.manifest.command}")
        click.echo(f"  - Inputs: {bundle.get_input_files().__len__()} files")
        click.echo(f"  - Configs: {bundle.get_config_files().__len__()} files")
        click.echo(f"  - Outputs: {bundle.get_output_files().__len__()} files")

        if bundle.evidence_manifest:
            click.echo("  - Evidence manifest: ✓ (with provenance)")

    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option(
    "--bundle", "-b",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to replay bundle directory",
)
@click.option(
    "--out", "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory for replay results",
)
@click.option(
    "--mode", "-m",
    type=click.Choice(["pr", "main", "release"]),
    help="Override mode (uses bundle mode if not specified)",
)
@click.option(
    "--profile", "-p",
    help="Override profile (uses bundle profile if not specified)",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Fail if any differences found (even allowed fields)",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    help="Verify bundle integrity before replay",
)
@click.option(
    "--force",
    is_flag=True,
    help="Proceed even if bundle verification fails",
)
@click.pass_context
def replay(
    ctx: click.Context,
    bundle: Path,
    out: Path,
    mode: str | None,
    profile: str | None,
    strict: bool,
    verify: bool,
    force: bool,
):
    """Replay a bundle and verify deterministic behavior.

    Re-runs the verdict using stored inputs and configuration,
    then compares outputs to verify identical results.

    Examples:
      truthctl replay --bundle ./my-bundle --out ./replay-results
      truthctl replay --bundle ./my-bundle --out ./replay-results --strict
      truthctl replay --bundle ./my-bundle --out ./replay-results --mode main
    """
    debug = ctx.obj.get("debug", False)

    try:
        # Load bundle
        click.echo(f"Loading bundle: {bundle}")
        replay_bundle = ReplayBundle.load(bundle)

        # Verify bundle integrity if requested
        if verify and replay_bundle.evidence_manifest:
            click.echo("Verifying bundle integrity...")
            verification = replay_bundle.verify_integrity()

            if not verification.valid:
                click.echo("❌ Bundle verification failed!", err=True)
                click.echo(f"   Files tampered: {len(verification.files_tampered)}", err=True)
                click.echo(f"   Files missing: {len(verification.files_missing)}", err=True)

                if not force:
                    click.echo("\nUse --force to proceed anyway.", err=True)
                    sys.exit(1)
                else:
                    click.echo("⚠️  Proceeding with --force despite verification failure.", err=True)
            else:
                click.echo("✅ Bundle integrity verified")

        # Run replay
        click.echo(f"\nReplaying with mode={mode or replay_bundle.manifest.profile or 'pr'}...")
        engine = ReplayEngine(strict=strict)
        result = engine.replay(
            bundle=replay_bundle,
            output_dir=out,
            mode=mode,
            profile=profile,
        )

        # Write reports
        reporter = ReplayReporter()
        paths = reporter.write_reports(result, out)

        click.echo("\n✅ Replay complete")
        click.echo("\nReports:")
        click.echo(f"  - JSON: {paths['json']}")
        click.echo(f"  - Markdown: {paths['markdown']}")

        # Show summary
        click.echo("\nResults:")
        click.echo(f"  - Files compared: {len(result.file_diffs)}")
        click.echo(f"  - Identical: {sum(1 for d in result.file_diffs if d.diff.identical)}")
        click.echo(f"  - Different: {sum(1 for d in result.file_diffs if not d.diff.identical)}")

        if result.identical:
            click.echo("\n✅ Outputs are identical (content-wise)")
        else:
            if strict:
                click.echo("\n❌ Differences found (--strict mode)")
                sys.exit(1)
            else:
                content_diffs = sum(1 for d in result.file_diffs if d.diff.content_differences > 0)
                if content_diffs > 0:
                    click.echo(f"\n❌ Content differences found in {content_diffs} files")
                    sys.exit(1)
                else:
                    click.echo("\n✅ Content identical (allowed fields differ)")

    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option(
    "--bundle", "-b",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to replay bundle directory",
)
@click.option(
    "--out", "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory for simulation results",
)
@click.option(
    "--changes", "-c",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="YAML file with changes to apply",
)
@click.option(
    "--mode", "-m",
    type=click.Choice(["pr", "main", "release"]),
    help="Override mode (uses bundle mode if not specified)",
)
@click.option(
    "--profile", "-p",
    help="Override profile (uses bundle profile if not specified)",
)
@click.option(
    "--verify/--no-verify",
    default=True,
    help="Verify bundle integrity before simulation",
)
@click.option(
    "--force",
    is_flag=True,
    help="Proceed even if bundle verification fails",
)
@click.pass_context
def simulate(
    ctx: click.Context,
    bundle: Path,
    out: Path,
    changes: Path,
    mode: str | None,
    profile: str | None,
    verify: bool,
    force: bool,
):
    """Run counterfactual simulation with modified configuration.

    Applies changes to thresholds, weights, or rules and re-runs
    the verdict to see how results would differ.

    The changes YAML file can specify:
      - thresholds: Override threshold values
      - severity_weights: Override severity weights
      - category_weights: Override category weights
      - disabled_engines: List of engines to disable
      - disabled_rules: List of rules to disable
      - suppressions: Findings to suppress

    Examples:
      truthctl simulate --bundle ./my-bundle --out ./sim-results --changes ./changes.yaml

    Example changes.yaml:
      thresholds:
        max_highs: 10
        max_total_points: 200
      severity_weights:
        HIGH: 75.0
      disabled_engines:
        - "ui_geometry"
    """
    debug = ctx.obj.get("debug", False)

    try:
        # Load bundle
        click.echo(f"Loading bundle: {bundle}")
        replay_bundle = ReplayBundle.load(bundle)

        # Verify bundle integrity if requested
        if verify and replay_bundle.evidence_manifest:
            click.echo("Verifying bundle integrity...")
            verification = replay_bundle.verify_integrity()

            if not verification.valid:
                click.echo("❌ Bundle verification failed!", err=True)

                if not force:
                    click.echo("\nUse --force to proceed anyway.", err=True)
                    sys.exit(1)
                else:
                    click.echo("⚠️  Proceeding with --force despite verification failure.", err=True)
            else:
                click.echo("✅ Bundle integrity verified")

        # Load changes
        click.echo(f"Loading changes from: {changes}")
        sim_changes = SimulationChanges.from_yaml(changes)

        # Run simulation
        click.echo("\nRunning simulation...")
        engine = SimulationEngine()
        result = engine.simulate(
            bundle=replay_bundle,
            output_dir=out,
            changes=sim_changes,
            mode=mode,
            profile=profile,
        )

        # Write reports
        reporter = SimulationReporter()
        paths = reporter.write_reports(result, out)

        click.echo("\n✅ Simulation complete")
        click.echo("\nReports:")
        click.echo(f"  - JSON: {paths['json']}")
        click.echo(f"  - Markdown: {paths['markdown']}")
        if "diff" in paths:
            click.echo(f"  - Diff: {paths['diff']}")

        # Show comparison
        if result.original_verdict and result.simulated_verdict:
            orig = result.original_verdict
            sim = result.simulated_verdict

            click.echo("\nVerdict Comparison:")
            click.echo(
                f"  Original:  {orig.verdict.value} "
                f"({orig.total_findings} findings, {orig.total_points} points)"
            )
            click.echo(f"  Simulated: {sim.verdict.value} ({sim.total_findings} findings, {sim.total_points} points)")

            if orig.verdict != sim.verdict:
                click.echo(f"\n⚠️  VERDICT CHANGED: {orig.verdict.value} → {sim.verdict.value}")

        if result.errors:
            click.echo("\n⚠️  Errors encountered:")
            for error in result.errors:
                click.echo(f"  - {error}")

    except Exception as e:
        handle_error(e, debug)


@cli.command()
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to')
@click.option('--port', '-p', default=8000, help='Port to listen on')
@click.option('--cache-dir', type=click.Path(path_type=Path), help='Cache directory')
@click.option('--static-dir', type=click.Path(path_type=Path), help='Static files directory for GUI')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
@click.option('--workers', '-w', default=1, help='Number of worker processes')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.pass_context
def serve(
    ctx: click.Context,
    host: str,
    port: int,
    cache_dir: Path | None,
    static_dir: Path | None,
    reload: bool,
    workers: int,
    debug: bool,
):
    """Start the Truth Core HTTP server.

    Provides a REST API and optional HTML GUI for all Truth Core commands.

    Examples:
      truthctl serve                           # Start server on default port
      truthctl serve --port 8080               # Start on port 8080
      truthctl serve --host 0.0.0.0            # Bind to all interfaces
      truthctl serve --cache-dir ./cache       # Enable caching
      truthctl serve --static-dir ./gui        # Serve GUI static files
      truthctl serve --reload                  # Development mode with auto-reload
    """
    import uvicorn

    from truthcore.server import create_app

    # Use cache dir from context if not specified
    effective_cache_dir = cache_dir or ctx.obj.get('cache_dir')

    try:
        click.echo(f"Starting Truth Core server on http://{host}:{port}")
        click.echo(f"API documentation: http://{host}:{port}/docs")

        if effective_cache_dir:
            click.echo(f"Cache enabled: {effective_cache_dir}")
        if static_dir:
            click.echo(f"Static files: {static_dir}")
        if debug or reload:
            click.echo("Debug mode enabled")

        # Create the app with configuration
        app = create_app(
            cache_dir=effective_cache_dir,
            static_dir=static_dir,
            debug=debug or reload,
        )

        # Configure uvicorn
        config_kwargs = {
            "host": host,
            "port": port,
            "reload": reload,
        }

        # Only set workers if not reloading (reload implies single process)
        if not reload:
            config_kwargs["workers"] = workers

        if debug:
            config_kwargs["log_level"] = "debug"

        click.echo("\nPress Ctrl+C to stop the server\n")

        uvicorn.run(app, **config_kwargs)

    except ImportError as e:
        click.echo(f"Error: Server dependencies not installed: {e}", err=True)
        click.echo("Install with: pip install 'truth-core[server]'", err=True)
        sys.exit(1)
    except Exception as e:
        handle_error(e, debug or ctx.obj.get('debug', False))


@cli.group(name="dashboard")
def dashboard_group():
    """Build and serve the Truth Core dashboard."""
    pass


@dashboard_group.command(name="build")
@click.option('--runs', '-r', required=True, type=click.Path(exists=True, path_type=Path), help='Runs directory')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory')
@click.option('--embedded/--no-embedded', default=True, help='Embed run data in dashboard')
@click.pass_context
def dashboard_build(ctx: click.Context, runs: Path, out: Path, embedded: bool):
    """Build the dashboard as static files.

    Creates a production-ready static dashboard that can be hosted
    on GitHub Pages or any static hosting.

    Examples:
      truthctl dashboard build --runs ./my-runs --out ./dashboard-dist
      truthctl dashboard build --runs ./runs --out ./dist --no-embedded
    """
    import json
    import shutil
    import subprocess

    debug = ctx.obj.get('debug', False)

    try:
        dashboard_dir = Path(__file__).parent.parent.parent.parent / "dashboard"

        if not dashboard_dir.exists():
            click.echo(f"Error: Dashboard directory not found at {dashboard_dir}", err=True)
            sys.exit(1)

        click.echo(f"Building dashboard from {dashboard_dir}...")

        # Build the dashboard
        subprocess.run(
            ["npm", "run", "build"],
            cwd=dashboard_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        # Copy built files
        dist_dir = dashboard_dir / "dist"
        if not dist_dir.exists():
            click.echo("Error: Dashboard build failed - dist directory not created", err=True)
            sys.exit(1)

        out.mkdir(parents=True, exist_ok=True)

        # Copy dashboard files
        for item in dist_dir.iterdir():
            dest = out / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # If embedded mode, copy and embed runs
        if embedded:
            click.echo(f"Embedding run data from {runs}...")

            # Load all runs
            runs_data = []
            for run_dir in runs.iterdir():
                if run_dir.is_dir():
                    run_data = load_run_data(run_dir)
                    if run_data:
                        runs_data.append(run_data)

            # Create embedded data file
            embedded_js = f"window.__EMBEDDED_RUNS__ = {json.dumps(runs_data, indent=2)};"

            with open(out / "embedded-runs.js", "w") as f:
                f.write(embedded_js)

            # Inject into index.html
            index_path = out / "index.html"
            if index_path.exists():
                with open(index_path) as f:
                    html = f.read()

                # Add script tag before closing body
                html = html.replace(
                    "</body>",
                    '<script src="embedded-runs.js"></script>\n  </body>'
                )

                with open(index_path, "w") as f:
                    f.write(html)

            click.echo(f"  Embedded {len(runs_data)} runs")

        click.echo(f"Dashboard built successfully: {out}")
        click.echo(f"  Open {out / 'index.html'} in a browser")

    except subprocess.CalledProcessError as e:
        click.echo(f"Build failed: {e.stderr}", err=True)
        sys.exit(1)
    except Exception as e:
        handle_error(e, debug)


@dashboard_group.command(name="serve")
@click.option('--runs', '-r', required=True, type=click.Path(exists=True, path_type=Path), help='Runs directory')
@click.option('--port', '-p', default=8787, help='Port to serve on')
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to')
@click.option('--open/--no-open', default=True, help='Open browser automatically')
@click.pass_context
def dashboard_serve(ctx: click.Context, runs: Path, port: int, host: str, open: bool):
    """Serve the dashboard locally.

    Builds and serves the dashboard with hot-reload for development.

    Examples:
      truthctl dashboard serve --runs ./my-runs
      truthctl dashboard serve --runs ./runs --port 8080
    """
    import subprocess
    import time
    import webbrowser

    debug = ctx.obj.get('debug', False)

    # Warn if binding to all interfaces
    if host == '0.0.0.0':
        click.echo("⚠️  Warning: Binding to 0.0.0.0 exposes the dashboard on all network interfaces", err=True)

    try:
        dashboard_dir = Path(__file__).parent.parent.parent.parent / "dashboard"

        if not dashboard_dir.exists():
            click.echo(f"Error: Dashboard directory not found at {dashboard_dir}", err=True)
            sys.exit(1)

        click.echo(f"Starting dashboard server on http://{host}:{port}")
        click.echo(f"Using runs from: {runs}")
        click.echo("Press Ctrl+C to stop")

        # Open browser after a short delay
        if open and host == '127.0.0.1':
            url = f"http://{host}:{port}"
            time.sleep(1)
            webbrowser.open(url)

        # Start dev server
        env = {
            **subprocess.os.environ,
            'VITE_RUNS_DIR': str(runs),
        }

        subprocess.run(
            ["npm", "run", "dev"],
            cwd=dashboard_dir,
            env=env,
            check=True,
        )

    except subprocess.CalledProcessError:
        click.echo("Server stopped", err=True)
    except KeyboardInterrupt:
        click.echo("\nServer stopped")
    except Exception as e:
        handle_error(e, debug)


@dashboard_group.command(name="snapshot")
@click.option('--runs', '-r', required=True, type=click.Path(exists=True, path_type=Path), help='Runs directory')
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory')
@click.option('--name', '-n', help='Snapshot name (default: timestamp)')
@click.pass_context
def dashboard_snapshot(ctx: click.Context, runs: Path, out: Path, name: str | None):
    """Create a portable snapshot of runs + dashboard.

    Creates a self-contained directory with:
    - All run data (JSON files)
    - Dashboard (built with embedded data)
    - Can be hosted on GitHub Pages or shared as a ZIP

    Examples:
      truthctl dashboard snapshot --runs ./my-runs --out ./snapshot
      truthctl dashboard snapshot --runs ./runs --out ./export --name v1.0-results
    """
    import json
    import shutil
    import subprocess

    debug = ctx.obj.get('debug', False)

    try:
        snapshot_name = name or f"truthcore-snapshot-{int(time.time())}"
        snapshot_dir = out / snapshot_name

        click.echo(f"Creating snapshot: {snapshot_name}")

        # Create directories
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        runs_out = snapshot_dir / "runs"
        dashboard_out = snapshot_dir / "dashboard"
        runs_out.mkdir(exist_ok=True)
        dashboard_out.mkdir(exist_ok=True)

        # Copy runs
        click.echo(f"Copying runs from {runs}...")
        run_count = 0
        for run_dir in runs.iterdir():
            if run_dir.is_dir():
                dest = runs_out / run_dir.name
                shutil.copytree(run_dir, dest, dirs_exist_ok=True)
                run_count += 1

        click.echo(f"  Copied {run_count} runs")

        # Build dashboard
        dashboard_dir = Path(__file__).parent.parent.parent.parent / "dashboard"

        if dashboard_dir.exists():
            click.echo("Building dashboard...")

            # Build
            subprocess.run(
                ["npm", "run", "build"],
                cwd=dashboard_dir,
                capture_output=True,
                check=True,
            )

            # Copy built files
            dist_dir = dashboard_dir / "dist"
            for item in dist_dir.iterdir():
                dest = dashboard_out / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

            # Load and embed runs data
            runs_data = []
            for run_dir in runs.iterdir():
                if run_dir.is_dir():
                    run_data = load_run_data(run_dir)
                    if run_data:
                        runs_data.append(run_data)

            embedded_js = f"window.__EMBEDDED_RUNS__ = {json.dumps(runs_data, indent=2)};"
            with open(dashboard_out / "embedded-runs.js", "w") as f:
                f.write(embedded_js)

            # Inject into index.html
            index_path = dashboard_out / "index.html"
            if index_path.exists():
                with open(index_path) as f:
                    html = f.read()
                html = html.replace("</body>", '<script src="embedded-runs.js"></script>\n  </body>')
                with open(index_path, "w") as f:
                    f.write(html)

        # Create README
        readme_content = f"""# Truth Core Snapshot: {snapshot_name}

This is a self-contained snapshot of Truth Core verification results.

## Contents

- `runs/` - All verification run data (JSON)
- `dashboard/` - Static dashboard with embedded data

## Viewing

Open `dashboard/index.html` in any modern browser.

Or serve locally:
  python -m http.server 8000 --directory dashboard

Created: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        with open(snapshot_dir / "README.txt", "w") as f:
            f.write(readme_content)

        click.echo(f"Snapshot created: {snapshot_dir}")
        click.echo(f"  Runs: {run_count}")
        click.echo(f"  Dashboard: {dashboard_out / 'index.html'}")

    except Exception as e:
        handle_error(e, debug)


def load_run_data(run_dir: Path) -> dict | None:
    """Load run data from a directory."""
    import json

    run_id = run_dir.name
    run_data = {"run_id": run_id, "files": []}

    # Load manifest (required)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return None

    with open(manifest_path) as f:
        run_data["manifest"] = json.load(f)

    # Load optional files
    files_to_load = {
        "verdict": "verdict.json",
        "readiness": "readiness.json",
        "invariants": "invariants.json",
        "policy": "policy_findings.json",
        "provenance": "verification_report.json",
        "intel_scorecard": "intel_scorecard.json",
    }

    for key, filename in files_to_load.items():
        path = run_dir / filename
        if path.exists():
            with open(path) as f:
                run_data[key] = json.load(f)
            run_data["files"].append(filename)

    return run_data


@dashboard_group.command(name="demo")
@click.option('--out', '-o', required=True, type=click.Path(path_type=Path), help='Output directory')
@click.option('--open/--no-open', default=True, help='Open browser after building')
@click.pass_context
def dashboard_demo(ctx: click.Context, out: Path, open: bool):
    """Run demo and build dashboard.

    Creates a complete demo with:
    - Sample verification runs
    - All artifact types (verdict, policy, provenance)
    - Built dashboard

    Examples:
      truthctl dashboard demo --out ./demo-out
      truthctl dashboard demo --out ./demo --no-open
    """
    import json
    import shutil
    import subprocess
    import time
    import webbrowser

    debug = ctx.obj.get('debug', False)

    try:
        click.echo("Creating demo...")

        # Create runs directory
        runs_dir = out / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        # Create sample run
        run_id = f"demo-run-{int(time.time())}"
        run_dir = runs_dir / run_id
        run_dir.mkdir(exist_ok=True)

        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Create manifest
        manifest = {
            "version": "1.0.0",
            "run_id": run_id,
            "command": "judge",
            "timestamp": timestamp,
            "duration_ms": 1234,
            "profile": "demo",
            "config": {"strict": True},
            "input_hash": "sha256:demo",
            "config_hash": "sha256:demo",
            "metadata": {},
        }

        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        # Create verdict
        verdict = {
            "version": "2.0.0",
            "timestamp": timestamp,
            "run_id": run_id,
            "verdict": "CONDITIONAL",
            "score": 85,
            "threshold": 90,
            "total_findings": 3,
            "findings_by_severity": {
                "BLOCKER": 0,
                "CRITICAL": 0,
                "HIGH": 1,
                "MEDIUM": 2,
                "LOW": 0,
                "INFO": 0,
            },
            "findings": [
                {
                    "id": "demo-1",
                    "severity": "HIGH",
                    "category": "quality",
                    "engine": "demo",
                    "rule": "test_coverage",
                    "message": "Test coverage below threshold (75% < 80%)",
                },
                {
                    "id": "demo-2",
                    "severity": "MEDIUM",
                    "category": "style",
                    "engine": "demo",
                    "rule": "line_length",
                    "message": "3 lines exceed 100 characters",
                },
                {
                    "id": "demo-3",
                    "severity": "MEDIUM",
                    "category": "security",
                    "engine": "demo",
                    "rule": "dependency_check",
                    "message": "2 dependencies have known vulnerabilities",
                },
            ],
            "subscores": {
                "security": 90,
                "quality": 75,
                "performance": 95,
                "style": 85,
            },
        }

        with open(run_dir / "verdict.json", "w") as f:
            json.dump(verdict, f, indent=2)

        # Create invariants
        invariants = {
            "version": "1.0.0",
            "timestamp": timestamp,
            "results": [
                {
                    "rule_id": "no_blockers",
                    "name": "No Blocker Issues",
                    "passed": True,
                    "severity": "BLOCKER",
                },
                {
                    "rule_id": "tests_pass",
                    "name": "All Tests Pass",
                    "passed": True,
                    "severity": "CRITICAL",
                },
                {
                    "rule_id": "coverage_threshold",
                    "name": "Coverage >= 80%",
                    "passed": False,
                    "severity": "HIGH",
                    "message": "Current coverage: 75%",
                },
            ],
        }

        with open(run_dir / "invariants.json", "w") as f:
            json.dump(invariants, f, indent=2)

        # Create policy findings
        policy = {
            "version": "1.0.0",
            "timestamp": timestamp,
            "pack_name": "demo",
            "rules_evaluated": 10,
            "rules_triggered": 2,
            "findings": [
                {
                    "rule_id": "DEPRECATED_API",
                    "severity": "MEDIUM",
                    "message": "Using deprecated API: old_function()",
                    "file": "src/example.py",
                },
            ],
        }

        with open(run_dir / "policy_findings.json", "w") as f:
            json.dump(policy, f, indent=2)

        # Create provenance
        provenance = {
            "version": "1.0.0",
            "timestamp": timestamp,
            "bundle_hash": "sha256:demo-bundle",
            "files": [
                {"path": "verdict.json", "hash": "sha256:abc", "algorithm": "sha256", "size": 1234},
                {"path": "invariants.json", "hash": "sha256:def", "algorithm": "sha256", "size": 567},
            ],
        }

        with open(run_dir / "verification_report.json", "w") as f:
            json.dump(provenance, f, indent=2)

        click.echo(f"Created demo run: {run_id}")

        # Build dashboard
        dashboard_dir = Path(__file__).parent.parent.parent.parent / "dashboard"
        dashboard_out = out / "dashboard"

        if dashboard_dir.exists():
            click.echo("Building dashboard...")

            subprocess.run(
                ["npm", "run", "build"],
                cwd=dashboard_dir,
                capture_output=True,
                check=True,
            )

            # Copy built files
            dist_dir = dashboard_dir / "dist"
            dashboard_out.mkdir(exist_ok=True)

            for item in dist_dir.iterdir():
                dest = dashboard_out / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

            # Embed demo data
            run_data = load_run_data(run_dir)
            if run_data:
                embedded_js = f"window.__EMBEDDED_RUNS__ = {json.dumps([run_data], indent=2)};"
                with open(dashboard_out / "embedded-runs.js", "w") as f:
                    f.write(embedded_js)

                # Inject into index.html
                index_path = dashboard_out / "index.html"
                with open(index_path) as f:
                    html = f.read()
                html = html.replace("</body>", '<script src="embedded-runs.js"></script>\n  </body>')
                with open(index_path, "w") as f:
                    f.write(html)

            click.echo(f"Dashboard built: {dashboard_out / 'index.html'}")

            if open:
                url = f"file://{dashboard_out / 'index.html'}"
                webbrowser.open(url)

        click.echo(f"Demo created successfully in: {out}")
        click.echo(f"  Run: {run_dir}")
        click.echo(f"  Dashboard: {dashboard_out / 'index.html'}")

    except Exception as e:
        handle_error(e, debug)


def main() -> None:
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
