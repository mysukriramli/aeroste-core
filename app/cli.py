"""Standalone command-line interface for AeroSTE-Core."""

import argparse
import json
import sys
from pathlib import Path
from app.engine import evaluate_ste_metrics, generate_sarif_report


def main():
    parser = argparse.ArgumentParser(
        prog="aeroste",
        description="AeroSTE-Core CLI: Multi-tier text clarity, ASD-STE100 linter, and patch generator."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    check_parser = subparsers.add_parser("check", help="Audit text or file for compliance.")
    check_parser.add_argument("target", help="File path or '-' to read from stdin.")
    check_parser.add_argument(
        "--profile",
        choices=["general", "technical", "aerospace_ste"],
        default="aerospace_ste",
        help="Strictness profile (default: aerospace_ste)."
    )
    check_parser.add_argument("--json", action="store_true", help="Output raw JSON analysis.")
    check_parser.add_argument("--sarif", action="store_true", help="Output SARIF v2.1.0 schema.")
    check_parser.add_argument("--diff", action="store_true", help="Print unified diff patch.")

    # Subcommand: fix
    fix_parser = subparsers.add_parser("fix", help="Automatically transform document into compliant prose.")
    fix_parser.add_argument("file_path", help="Target file path.")
    fix_parser.add_argument(
        "--profile",
        choices=["general", "technical", "aerospace_ste"],
        default="aerospace_ste",
        help="Strictness profile."
    )
    fix_parser.add_argument("--in-place", action="store_true", help="Overwrite the file directly.")

    args = parser.parse_args()

    if args.command == "check":
        if args.target == "-":
            content = sys.stdin.read()
            filename = "stdin"
        else:
            p = Path(args.target)
            if not p.exists():
                print(f"Error: Target '{args.target}' does not exist.", file=sys.stderr)
                sys.exit(1)
            content = p.read_text(encoding="utf-8")
            filename = p.name

        eval_res = evaluate_ste_metrics({
            "profile": args.profile,
            "text_payload": content
        })

        if args.sarif:
            sarif = generate_sarif_report(eval_res, file_uri=filename)
            print(json.dumps(sarif, indent=2))
            sys.exit(0 if eval_res["classification"] != "CRITICAL" else 1)

        if args.json:
            print(json.dumps(eval_res, indent=2))
            sys.exit(0 if eval_res["classification"] != "CRITICAL" else 1)

        if args.diff:
            print(eval_res.get("patch", ""))
            sys.exit(0)

        # Human & Agent readable concise terminal table
        print(f"File: {filename} | Profile: {eval_res['profile']}")
        print(f"Score: {eval_res['primary_metric']}/100.0 | Status: {eval_res['classification']}")
        violations = eval_res.get("explainability", {}).get("violations", [])
        print(f"Violations Detected: {len(violations)}")
        for v in violations:
            print(f"  Line {v.get('line')}:{v.get('column')} - '{v.get('term')}' -> '{v.get('approved')}' [{v.get('rule')}]")

        sys.exit(0 if eval_res["classification"] != "CRITICAL" else 1)

    elif args.command == "fix":
        p = Path(args.file_path)
        if not p.exists():
            print(f"Error: Target '{args.file_path}' does not exist.", file=sys.stderr)
            sys.exit(1)

        raw = p.read_text(encoding="utf-8")
        eval_res = evaluate_ste_metrics({
            "profile": args.profile,
            "text_payload": raw
        })
        repaired = eval_res.get("transformed_text", raw)

        if args.in_place:
            p.write_text(repaired, encoding="utf-8")
            print(f"Repaired and saved to: {p} (New Score: {eval_res['primary_metric']})")
        else:
            print(repaired)


if __name__ == "__main__":
    main()
