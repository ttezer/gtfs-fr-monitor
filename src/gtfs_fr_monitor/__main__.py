"""Command line entry point: `python -m gtfs_fr_monitor <command>`.

The pipeline's stages (gtfs_fr_pipeline), run with the French source, downloads and profile. Installing
the analyzer, recording storage and building the site use the pipeline's own commands
(`python -m gtfs_fr_pipeline install-analyzer | record-storage | check-storage | export-web`).
"""

from __future__ import annotations

import argparse
import collections
import functools
import json
import sys
from pathlib import Path

from gtfs_fr_pipeline.analyzer import AnalyzerBinary, Lock, pinned_release_for
from gtfs_fr_pipeline.catalog import sync_catalog
from gtfs_fr_pipeline.download import download_zip, urllib_opener
from gtfs_fr_pipeline.ids import is_path_id
from gtfs_fr_pipeline.pipeline import run_analysis
from gtfs_fr_pipeline.store import analysis_key

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
    import time

    source = FrSource(Settings(Path(args.data_dir), Path(args.work_dir), download_budget=args.download_budget,
                               max_seconds=args.max_minutes * 60 if args.max_minutes else None))
    started = time.monotonic()

    def progress(index: int, total: int, key: tuple[str, str]) -> None:
        if index % 25 == 0:
            print(f"[{index}/{total}] {time.monotonic() - started:.0f} s, {source.downloads} downloads, "
                  f"{len(source.changed_states)} states written{' (time budget spent)' if source.out_of_time() else ''}",
                  file=sys.stderr, flush=True)

    result = sync_catalog(source, Path(args.data_dir), only=set(args.only) if args.only else None, progress=progress)
    print(json.dumps({
        "feeds_scanned": result.feeds_scanned, "generations_seen": result.generations_seen,
        "new_generations": len(result.new_generations), "changed_files": len(result.changed_files),
        "changed_states": len(source.changed_states), "downloads": source.downloads, "requests": source.client.request_count,
        "unreadable_files": len(source.unreadable),
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
                          extra_warnings=extra, canonical_key=analysis_key(lock.release_tag, PROFILE), areas=AREAS,
                          retry_fatal=args.retry_fatal)
    print(json.dumps({
        "run_id": report.run_id, "pinned": binary.is_pinned, "counts": report.counts, "processed": len(report.items),
        "changed_files": len(report.changed_files), "run_file": report.run_file,
        "warnings_by_code": dict(sorted(collections.Counter(w["code"] for w in report.warnings).items())),
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_semantic_reports(args: argparse.Namespace) -> int:
    from gtfs_fr_pipeline.changes import run_reports

    key = analysis_key(Lock.load(Path(args.lock)).release_tag, PROFILE)
    run = run_reports(Path(args.data_dir), key, limit=args.limit, only=set(args.only) if args.only else None,
                      downloader=download, max_seconds=args.max_minutes * 60 if args.max_minutes else None,
                      config=engine_config(), holidays_path=HOLIDAYS_FILE)
    print(json.dumps({"analysis_key": key, "counts": dict(sorted(run.counts.items())),
                      "failed": [i for i in run.items if i["action"] == "failed"][:50]}, ensure_ascii=False, indent=2))
    return 0


def _mdb_links() -> dict[str, str]:
    """Mobility Database ids of the feeds; links are a convenience, so a failure leaves them out."""
    import urllib.request

    from .mobilitydb import CATALOGUE, feed_ids
    from .tdg import TdgClient
    try:
        request = urllib.request.Request(CATALOGUE, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            catalogue = response.read(64 * 1024 * 1024).decode("utf-8")
        datasets = TdgClient()._http.get_json("/api/datasets")
        return feed_ids(catalogue, datasets if isinstance(datasets, list) else [])
    except Exception as err:  # noqa: BLE001 - any failure only drops the links
        print(f"Mobility Database links left out: {type(err).__name__}: {err}", file=sys.stderr)
        return {}


def _cmd_site_profile(args: argparse.Namespace) -> int:
    mdb = {} if args.no_mdb else _mdb_links()
    Path(args.output).write_text(json.dumps(site_profile(mdb), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"mobility_database_links": len(mdb)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtfs_fr_monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync-catalog", help="refresh the catalog and the versions of each feed")
    sync.add_argument("--data-dir", required=True)
    sync.add_argument("--work-dir", required=True, help="scratch directory for downloads (removed files)")
    sync.add_argument("--only", type=_feed_key, action="append", metavar="ORG_ID/FEED_ID")
    sync.add_argument("--download-budget", type=int, default=300, help="downloads in this run (default 300)")
    sync.add_argument("--max-minutes", type=float, help="time budget: no download starts after this many minutes")
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
    analyze.add_argument("--retry-fatal", action="store_true", help="re-analyze existing FATAL generation records")
    analyze.set_defaults(func=_cmd_analyze)

    reps = sub.add_parser("semantic-reports", help="build missing change reports with the French profile")
    reps.add_argument("--data-dir", required=True)
    reps.add_argument("--lock", default=str(DEFAULT_LOCK))
    reps.add_argument("--limit", type=int)
    reps.add_argument("--only", type=_feed_key, action="append", metavar="ORG_ID/FEED_ID")
    reps.add_argument("--max-minutes", type=float)
    reps.set_defaults(func=_cmd_semantic_reports)

    prof = sub.add_parser("site-profile", help="write the site profile for gtfs_fr_pipeline export-web --site-profile")
    prof.add_argument("-o", "--output", required=True)
    prof.add_argument("--no-mdb", action="store_true", help="leave out the Mobility Database links (no download)")
    prof.set_defaults(func=_cmd_site_profile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
