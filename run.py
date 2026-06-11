"""CLI entrypoint (BUILD-SPEC §10).

  python run.py audit   --url https://… [--gsc path.zip] [--keyword "…"] [--out runs/<ts>/]
  python run.py content --mode rebuild --diagnosis runs/<ts>/diagnosis.json --inputs inputs.json
  python run.py content --mode net_new --inputs inputs.json
  python run.py eval
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

console = Console()

NET_NEW_REQUIRED = [
    "seed_keyword", "business_context", "page_type", "audience",
    "canonical_sources", "brand_assets",
]


def load_inputs(path: str, required: list[str]) -> dict:
    """Validate inputs.json; missing required field → print exactly which and exit 2."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]inputs file not found: {path}[/red]")
        sys.exit(2)
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]inputs file is not valid JSON: {path} ({e})[/red]")
        sys.exit(2)
    missing = [f for f in required if f not in data or data[f] in (None, "", [])]
    if missing:
        for f in missing:
            console.print(f"[red]missing required input field: {f}[/red]")
        sys.exit(2)
    return data


def new_run_dir(base: str | None = None) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = Path(base) if base else Path("runs") / ts
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_audit(args) -> int:
    from graphs.audit_graph import build_audit_graph
    run_dir = new_run_dir(args.out)
    try:
        graph = build_audit_graph()
    except NotImplementedError as e:
        console.print(f"[yellow]{e}[/yellow]")
        console.print("[yellow]Audit pipeline lands in Phase 3 (see BUILD-SPEC §11 / CLAUDE.md phase status).[/yellow]")
        return 1
    state = {"url": args.url}
    if args.gsc:
        state["gsc_path"] = args.gsc
    if args.keyword:
        state["primary_query"] = args.keyword
    result = graph.invoke(state)
    (run_dir / "diagnosis.json").write_text(json.dumps(result.get("diagnosis"), indent=2))
    (run_dir / "master_report.md").write_text(result.get("master_report_md", ""))
    console.print(f"[green]audit complete → {run_dir}[/green]")
    return 0


def cmd_content(args) -> int:
    from graphs.content_graph import build_content_graph
    from state import new_content_state, validate_diagnosis

    run_dir = new_run_dir(args.out)
    if args.mode == "net_new":
        inputs = load_inputs(args.inputs, NET_NEW_REQUIRED)
        state = new_content_state(
            mode="net_new",
            page_type=inputs["page_type"],
            primary_keyword=inputs["seed_keyword"],
            research_dossier=inputs.get("research_dossier", {}),
            brand_assets=inputs["brand_assets"],
            audience=inputs["audience"],
            canonical_sources=inputs["canonical_sources"],
        )
    else:
        if not args.diagnosis:
            console.print("[red]--diagnosis is required for --mode rebuild[/red]")
            return 2
        diagnosis = json.loads(Path(args.diagnosis).read_text())
        validate_diagnosis(diagnosis)
        inputs = load_inputs(args.inputs, ["canonical_sources", "brand_assets", "audience"]) if args.inputs else {}
        state = new_content_state(
            mode="rebuild",
            page_type=diagnosis["page_type"],
            target_url=diagnosis["url"],
            primary_keyword=diagnosis["primary_query"],
            research_dossier=inputs.get("research_dossier", {}),
            brand_assets=inputs.get("brand_assets", {}),
            audience=inputs.get("audience", ""),
            canonical_sources=inputs.get("canonical_sources", []),
            gap_entity_matrix=diagnosis["gap_entity_matrix"],
            keep_list=diagnosis["keep_list"],
            failure_modes=[d["description"] for d in diagnosis["defects"]],
        )
    try:
        graph = build_content_graph()
    except NotImplementedError as e:
        console.print(f"[yellow]{e}[/yellow]")
        console.print("[yellow]Content walking skeleton lands in Phase 1 (see BUILD-SPEC §11 / CLAUDE.md phase status).[/yellow]")
        return 1
    result = graph.invoke(state)
    (run_dir / "ledger.json").write_text(json.dumps(result.get("facts_ledger", []), indent=2))
    (run_dir / "package_out.json").write_text(json.dumps(result.get("package_out", {}), indent=2))
    console.print(f"[green]content run complete → {run_dir}[/green]")
    return 0


def cmd_eval(_args) -> int:
    from eval.run_eval import main as eval_main
    return eval_main()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="run.py", description="SEO/GEO agentic platform")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="Pipeline A: audit a live URL")
    p_audit.add_argument("--url", required=True)
    p_audit.add_argument("--gsc")
    p_audit.add_argument("--keyword")
    p_audit.add_argument("--out")
    p_audit.set_defaults(fn=cmd_audit)

    p_content = sub.add_parser("content", help="Pipeline B: generate content")
    p_content.add_argument("--mode", choices=["rebuild", "net_new"], required=True)
    p_content.add_argument("--diagnosis")
    p_content.add_argument("--inputs")
    p_content.add_argument("--out")
    p_content.set_defaults(fn=cmd_content)

    p_eval = sub.add_parser("eval", help="GO/KILL eval gate (rubric + seeded errors)")
    p_eval.set_defaults(fn=cmd_eval)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
