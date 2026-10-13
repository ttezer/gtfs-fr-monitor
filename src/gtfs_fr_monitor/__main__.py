"""Command line entry point: `python -m gtfs_fr_monitor <command>`.

The stages of gtfs-jp-monitor, run with the French source, downloads and profile. Installing the
analyzer, recording storage and building the site use gtfs-jp-monitor's own commands
(`python -m gtfs_jp_monitor install-analyzer | record-storage | check-storage | export-web`).
"""

from __future__ import annotations

import argparse
import collections
import functools
import json
import sys
from pathlib import Path

from gtfs_jp_monitor.analyzer import AnalyzerBinary, Lock, pinned_release_for
from gtfs_jp_monitor.catalog import sync_catalog
from gtfs_jp_monitor.download import download_zip, urllib_opener
from gtfs_jp_monitor.ids import is_path_id
from gtfs_jp_monitor.pipeline import run_analysis
from gtfs_jp_monitor.store import analysis_key

from .frsource import FrSource, Settings
from .profile import AREAS, HOLIDAYS_FILE, engine_config
from .site import profile as site_profile
from .tdg import USER_AGENT, is_history_url

DEFAULT_LOCK = Path(__file__).resolve().parents[2] / "analyzer.lock.json"
PROFILE = "auto"  # GTFS-JP rules run only on feeds with GTFS-JP signals; French feeds get the GTFS rules

# Every ZIP the pipeline downloads is an archived file on transport.data.gouv.fr's history host.
download = functools.partial(download_zip, allowed=is_history_url, opener=functools.partial(urllib_opener, user_agent=USER_AGENT))


def _feed_key(text: str) -> tuple[str, str]:
    org_id, sep, feed_id = text.partition("/")
    if not sep or not (is_path_id(org_id) and is_path_id(feed_id)):
        raise argparse.ArgumentTypeError(f"expected ORG_ID/FEED_ID, got {text!r}")
    return org_id, feed_id


def _cmd_sync_catalog(args: argparse.Namespace) -> int:
    source = FrSource(Settings(Path(args.data_dir), Path(args.work_dir), download_budget=args.download_budget))
    result = sync_catalog(source, Path(args.data_dir), only=set(args.only) if args.only else None)
    print(json.dumps({
        "feeds_scanned": result.feeds_scanned, "generations_seen": result.generations_seen,
        "new_generations": len(result.new_generations), "changed_files": len(result.changed_files),
        "changed_states": len(source.changed_states), "downloads": source.downloads, "requests": source.client.request_count,
        "warnings_by_code": dict(sorted(collections.Counter(w["code"] for w in result.warnings).items())),
    }, ensure_ascii=False, indent=2))
    if args.events_out:
        Path(args.events_out).write_text(json.dumps(result.events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    lock = Lock.load(Path(args.lock))
    binary = AnalyzerBinary.inspect(Path(args.analyzer), pinned_release=pinned_release_for(Path(args.analyzer), lock))
    if binary.is_pinned and f"{binary.arch}-{binary.os}" != lock.production_platform and not args.allow_non_production_platform:
        raise SystemExit(f"pinned binary runs on {binary.arch}-{binary.os}; data-repository results must come from "
                         f"{lock.production_platform}. Use --allow-non-production-platform only for scratch data.")
    extra = json.loads(Path(args.extra_warnings).read_text(encoding="utf-8")) if args.extra_warnings else None
    report = run_analysis(Path(args.data_dir), binary, PROFILE, trigger=args.trigger, limit=args.limit,
                          only=set(args.only) if args.only else None, timeout=args.timeout, downloader=download,
                          extra_warnings=extra, canonical_key=analysis_key(lock.release_tag, PROFILE), areas=AREAS)
    print(json.dumps({
        "run_id": report.run_id, "pinned": binary.is_pinned, "counts": report.counts, "processed": len(report.items),
        "changed_files": len(report.changed_files), "run_file": report.run_file,
        "warnings_by_code": dict(sorted(collections.Counter(w["code"] for w in report.warnings).items())),
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_semantic_reports(args: argparse.Namespace) -> int:
    from gtfs_jp_monitor.changes import run_reports

    key = analysis_key(Lock.load(Path(args.lock)).release_tag, PROFILE)
    run = run_reports(Path(args.data_dir), key, limit=args.limit, only=set(args.only) if args.only else None,
                      downloader=download, max_seconds=args.max_minutes * 60 if args.max_minutes else None,
                      config=engine_config(), holidays_path=HOLIDAYS_FILE)
    print(json.dumps({"analysis_key": key, "counts": dict(sorted(run.counts.items())),
                      "failed": [i for i in run.items if i["action"] == "failed"][:50]}, ensure_ascii=False, indent=2))
    return 0


def _cmd_site_profile(args: argparse.Namespace) -> int:
    Path(args.output).write_text(json.dumps(site_profile(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtfs_fr_monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync-catalog", help="refresh the catalog and the versions of each feed")
    sync.add_argument("--data-dir", required=True)
    sync.add_argument("--work-dir", required=True, help="scratch directory for downloads (removed files)")
    sync.add_argument("--only", type=_feed_key, action="append", metavar="ORG_ID/FEED_ID")
    sync.add_argument("--download-budget", type=int, default=300, help="downloads in this run (default 300)")
    sync.add_argument("--events-out", help="write the catalog events of this run (JSON) here")
    sync.set_defaults(func=_cmd_sync_catalog)

    analyze = sub.add_parser("analyze", help="analyze versions that have no record for the pinned analyzer")
    analyze.add_argument("--data-dir", required=True)
    analyze.add_argument("--analyzer", required=True, help="path to the gtfs-analyzer binary")
    analyze.add_argument("--lock", default=str(DEFAULT_LOCK))
    analyze.add_argument("--limit", type=int)
    analyze.add_argument("--only", type=_feed_key, action="append", metavar="ORG_ID/FEED_ID")
    analyze.add_argument("--timeout", type=float, default=600)
    analyze.add_argument("--trigger", choices=("schedule", "workflow_dispatch", "local"), default="local")
    analyze.add_argument("--allow-non-production-platform", action="store_true")
    analyze.add_argument("--extra-warnings", help="JSON list of catalog events to include in the run record")
    analyze.set_defaults(func=_cmd_analyze)

    reps = sub.add_parser("semantic-reports", help="build missing change reports with the French profile")
    reps.add_argument("--data-dir", required=True)
    reps.add_argument("--lock", default=str(DEFAULT_LOCK))
    reps.add_argument("--limit", type=int)
    reps.add_argument("--only", type=_feed_key, action="append", metavar="ORG_ID/FEED_ID")
    reps.add_argument("--max-minutes", type=float)
    reps.set_defaults(func=_cmd_semantic_reports)

    prof = sub.add_parser("site-profile", help="write the site profile for gtfs_jp_monitor export-web --site-profile")
    prof.add_argument("-o", "--output", required=True)
    prof.set_defaults(func=_cmd_site_profile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
