"""Batch runner — processes multiple demo + onboarding transcript pairs end-to-end."""

import argparse
import glob
import json
import os
import re
import sys

from engine.change_logger import reset_change_log, get_change_log
from engine.changelog_generator import save_changelog
from pipeline.demo_processor import process_demo
from pipeline.onboarding_processor import process_onboarding
from prompt.prompt_builder import build_prompt
from prompt.agent_spec_builder import build_agent_spec, save_agent_spec
from versioning.version_manager import save_version, load_version


def _find_pairs(demo_dir: str, onboarding_dir: str) -> list[dict]:
    """Match demo and onboarding files by numeric suffix."""
    pairs = []
    demo_files = sorted(glob.glob(os.path.join(demo_dir, "demo_*.txt")))
    for demo_path in demo_files:
        basename = os.path.basename(demo_path)
        match = re.search(r"demo_(\d+)", basename)
        if not match:
            continue
        num = match.group(1)
        account_id = f"account_{num}"
        onboarding_path = os.path.join(onboarding_dir, f"onboarding_{num}.txt")
        form_path = os.path.join(onboarding_dir, f"form_{num}.json")
        pairs.append({
            "account_id": account_id,
            "demo_path": demo_path,
            "onboarding_path": onboarding_path if os.path.exists(onboarding_path) else None,
            "form_path": form_path if os.path.exists(form_path) else None,
        })
    return pairs


def run_batch(
    demo_dir: str = "data/demo",
    onboarding_dir: str = "data/onboarding",
    output_dir: str = "output",
    versions_dir: str = "versions",
) -> dict:
    """Run the full pipeline for all matched demo/onboarding pairs.

    Returns a summary dictionary.
    """
    pairs = _find_pairs(demo_dir, onboarding_dir)
    if not pairs:
        print(f"No demo files found in {demo_dir}")
        return {"accounts_processed": 0, "accounts": []}

    summary = {
        "accounts_processed": 0,
        "total_unknowns_remaining": 0,
        "accounts": [],
    }

    for pair in pairs:
        account_id = pair["account_id"]
        account_output_dir = os.path.join(output_dir, "accounts", account_id)
        print(f"\n{'='*60}")
        print(f"Processing {account_id}")
        print(f"{'='*60}")

        try:
            # --- Pipeline A: Demo → v1 ---
            reset_change_log()
            print(f"  [Pipeline A] Reading demo: {pair['demo_path']}")
            with open(pair["demo_path"], "r", encoding="utf-8") as f:
                demo_text = f.read()

            v1 = process_demo(client_id=account_id, transcript=demo_text)
            save_version(v1, versions_dir)

            # Save v1 agent spec
            v1_dir = os.path.join(account_output_dir, "v1")
            os.makedirs(v1_dir, exist_ok=True)
            save_agent_spec(v1, v1_dir)

            # Save v1 config
            v1_config_path = os.path.join(v1_dir, "config.json")
            with open(v1_config_path, "w", encoding="utf-8") as f:
                f.write(v1.model_dump_json(indent=2))

            print(f"  [Pipeline A] v1 created — {len(v1.questions_or_unknowns)} unknowns")

            account_result = {
                "account_id": account_id,
                "company_name": v1.client_info.company_name,
                "v1_unknowns": len(v1.questions_or_unknowns),
                "v2_created": False,
                "v2_unknowns": None,
                "changes_count": 0,
            }

            # --- Pipeline B: Onboarding → v2 ---
            if pair["onboarding_path"]:
                reset_change_log()
                print(f"  [Pipeline B] Reading onboarding: {pair['onboarding_path']}")
                with open(pair["onboarding_path"], "r", encoding="utf-8") as f:
                    onboarding_text = f.read()

                form_data = None
                if pair["form_path"]:
                    print(f"  [Pipeline B] Reading form: {pair['form_path']}")
                    with open(pair["form_path"], "r", encoding="utf-8") as f:
                        form_data = json.load(f)

                loaded_v1 = load_version(account_id, "v1", versions_dir)
                v2 = process_onboarding(
                    existing_config=loaded_v1,
                    transcript=onboarding_text,
                    form_data=form_data,
                )
                save_version(v2, versions_dir)

                # Save v2 agent spec
                v2_dir = os.path.join(account_output_dir, "v2")
                os.makedirs(v2_dir, exist_ok=True)
                save_agent_spec(v2, v2_dir)

                # Save v2 config
                v2_config_path = os.path.join(v2_dir, "config.json")
                with open(v2_config_path, "w", encoding="utf-8") as f:
                    f.write(v2.model_dump_json(indent=2))

                # Generate changelog
                change_log = get_change_log()
                save_changelog(loaded_v1, v2, change_log, account_output_dir)

                print(f"  [Pipeline B] v2 created — {len(v2.questions_or_unknowns)} unknowns, {len(change_log)} changes")

                account_result["v2_created"] = True
                account_result["v2_unknowns"] = len(v2.questions_or_unknowns)
                account_result["changes_count"] = len(change_log)
                summary["total_unknowns_remaining"] += len(v2.questions_or_unknowns)
            else:
                print(f"  [Pipeline B] Skipped — no onboarding transcript found")
                summary["total_unknowns_remaining"] += len(v1.questions_or_unknowns)

            summary["accounts"].append(account_result)
            summary["accounts_processed"] += 1

        except Exception as exc:
            print(f"  ERROR processing {account_id}: {exc}")
            summary["accounts"].append({
                "account_id": account_id,
                "error": str(exc),
            })

    # Save batch summary
    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "batch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Print summary table
    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")
    print(f"{'Account':<20} {'Company':<30} {'v1 Unk':>8} {'v2 Unk':>8} {'Changes':>8}")
    print("-" * 74)
    for acct in summary["accounts"]:
        if "error" in acct:
            print(f"{acct['account_id']:<20} ERROR: {acct['error']}")
        else:
            v2_unk = str(acct.get("v2_unknowns", "—"))
            print(
                f"{acct['account_id']:<20} "
                f"{(acct.get('company_name') or 'Unknown'):<30} "
                f"{acct['v1_unknowns']:>8} "
                f"{v2_unk:>8} "
                f"{acct.get('changes_count', 0):>8}"
            )
    print(f"\nTotal accounts: {summary['accounts_processed']}")
    print(f"Total remaining unknowns: {summary['total_unknowns_remaining']}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Clara Agent System — Batch Runner")
    parser.add_argument("--demo_dir", default="data/demo", help="Directory with demo_NNN.txt files")
    parser.add_argument("--onboarding_dir", default="data/onboarding", help="Directory with onboarding_NNN.txt files")
    parser.add_argument("--output_dir", default="output", help="Output directory")
    parser.add_argument("--versions_dir", default="versions", help="Versions directory")
    parser.add_argument("--no-llm", action="store_true", help="Force rule-based extraction (no LLM)")
    args = parser.parse_args()

    if args.no_llm:
        os.environ["LLM_BACKEND"] = "rule_based"

    run_batch(
        demo_dir=args.demo_dir,
        onboarding_dir=args.onboarding_dir,
        output_dir=args.output_dir,
        versions_dir=args.versions_dir,
    )


if __name__ == "__main__":
    main()
