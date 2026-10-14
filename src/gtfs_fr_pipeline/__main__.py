"""Command line entry point: `python -m gtfs_fr_pipeline <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import PROFILES, Lock, install_release, sha256_file
from .http import USER_AGENT
from .ids import is_path_id

DEFAULT_LOCK = Path(__file__).resolve().parents[2] / "analyzer.lock.json"


def _feed_key(text: str) -> tuple[str, str]:
    org_id, sep, feed_id = text.partition("/")
    if not sep or not (is_path_id(org_id) and is_path_id(feed_id)):
        raise argparse.ArgumentTypeError(f"expected ORG_ID/FEED_ID, got {text!r}")
    return org_id, feed_id


def _fetch_release_archive(url: str, dest: Path, max_bytes: int = 64 * 1024 * 1024) -> None:
    import urllib.request

    from .download import _HttpsOnlyRedirects

    opener = urllib.request.build_opener(_HttpsOnlyRedirects())
    with opener.open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise SystemExit(f"release archive larger than {max_bytes} bytes")
    dest.write_bytes(data)


def _cmd_install_analyzer(args: argparse.Namespace) -> int:
    lock = Lock.load_next(Path(args.lock)) if args.next else Lock.load(Path(args.lock))
    if lock is None:  # no upgrade under way: nothing to install
        print(json.dumps({"binary": None, "release_tag": None}, indent=2))
        return 0
    binary = install_release(lock, Path(args.dest), _fetch_release_archive)
    print(json.dumps({"binary": str(binary), "release_tag": lock.release_tag, "sha256": sha256_file(binary)}, indent=2))
    return 0


def _cmd_rawdiff(args: argparse.Namespace) -> int:
    from gtfs_fr_semantic.rawdiff import diff_zips, gzip_bytes

    doc = diff_zips(Path(args.old), Path(args.new))
    Path(args.output).write_bytes(gzip_bytes(doc))
    print(json.dumps({
        "changes": len(doc["changes"]),
        "files": {name: meta["counts"] for name, meta in doc["files"].items() if meta["counts"]},
        "archive_warnings": len(doc["archive_warnings"]),
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_semantic_report(args: argparse.Namespace) -> int:
    from gtfs_fr_semantic.rawdiff import gzip_bytes
    from gtfs_fr_semantic.report import build_report

    from .canonical import write_json
    from .catalog import load_catalog
    from .store import diff_path

    root = Path(args.data_dir)
    org_id, feed_id = args.feed
    entries = load_catalog(root)[1].get((org_id, feed_id), {})
    pubs = []
    for uid in (args.old_uid, args.new_uid):
        if uid not in entries:
            raise SystemExit(f"{uid} is not a generation of {org_id}/{feed_id} in the catalog")
        pubs.append({k: entries[uid].get(k) for k in ("uid", "from_date", "to_date", "published_at", "memo")})
    quality, key = None, None
    if args.analysis_key:
        path = diff_path(root, org_id, feed_id, args.analysis_key, args.old_uid, args.new_uid)
        if path.exists():
            scores = json.loads(path.read_text(encoding="utf-8"))["scores"]
            if scores:
                quality, key = {"publish": scores["publish"], "overall": scores["overall"]}, args.analysis_key
    report, _ = build_report(Path(args.old), Path(args.new), feed={"org_id": org_id, "feed_id": feed_id},
                             old_pub=pubs[0], new_pub=pubs[1], summary_quality=quality, analysis_key=key)
    out = Path(args.output)
    if out.name.endswith(".gz"):
        out.write_bytes(gzip_bytes(report))
    else:
        write_json(out, report)
    print(json.dumps({"coverage": report["header"]["coverage"], "lines": report["summary"]["lines"],
                      "places": report["summary"]["places"]}, ensure_ascii=False, indent=2))
    return 0


DEFAULT_TEMPLATE = Path(__file__).resolve().parents[2] / "web" / "prototype" / "index.html"


def _cmd_export_web(args: argparse.Namespace) -> int:
    from .webexport import build_export

    key = f"{args.release_tag}__{args.profile}"
    next_key = f"{args.next_release_tag}__{args.profile}" if args.next_release_tag else None
    # Another source's site (data-model §10.4): {"site": page profile, "head": <head> block, "atom": {...}}.
    profile = json.loads(Path(args.site_profile).read_text(encoding="utf-8")) if args.site_profile else {}
    langs = tuple((profile.get("site") or {}).get("langs") or ()) or None
    export, files = build_export(Path(args.data_dir), key, Path(args.analyzer) if args.analyzer else None, next_key,
                                 **({"langs": langs} if langs else {}))
    ext = ".json.gz" if args.bundle_format == "gz" else ".json"
    export["report_bundle_ext"] = ext
    if profile.get("site"):
        export["site"] = profile["site"]
    if args.json:
        from .canonical import write_json
        write_json(Path(args.json), export)
    if args.html:
        # The report index is written next to the page and loaded after it, which keeps the page small.
        page = {k: v for k, v in export.items() if k not in ("report_index", "metrics", "fields", "determinism")}
        payload = json.dumps(page, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        template = Path(args.template).read_text(encoding="utf-8")
        if template.count("/*__EXPORT__*/") != 1:
            raise SystemExit("template must contain exactly one /*__EXPORT__*/ placeholder")
        if profile.get("head") is not None:
            from .webexport import apply_site_head
            try:
                template = apply_site_head(template, profile["head"])
            except ValueError as err:
                raise SystemExit(str(err)) from None
        Path(args.html).parent.mkdir(parents=True, exist_ok=True)
        Path(args.html).write_text(template.replace("/*__EXPORT__*/", payload), encoding="utf-8")
        from gtfs_fr_semantic.rawdiff import gzip_bytes

        from .canonical import dumps

        out = Path(args.html).parent / "reports"
        out.mkdir(parents=True, exist_ok=True)
        for old in [*out.rglob("*.json.gz"), *out.rglob("*.json")]:  # reports of an earlier export
            old.unlink()
        index = export["report_index"]
        (out / f"index{ext}").write_bytes(gzip_bytes(index) if ext == ".json.gz" else dumps(index).encode("utf-8"))
        for name, doc in files.items():  # reports/<org_id>/<feed_id>/<old_uid>__<new_uid><ext>
            path = out / f"{name}{ext}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip_bytes(doc) if ext == ".json.gz" else dumps(doc).encode("utf-8"))
        (Path(args.html).parent / "metrics.json").write_text(dumps(export["metrics"]) + "\n", encoding="utf-8")
        from .atom import build_atom

        atom_dir = Path(args.html).parent / "atom"
        for old in atom_dir.rglob("*.xml"):  # feeds of an earlier export
            old.unlink()
        atom = profile.get("atom") or {}
        for name, body in build_atom(export["feeds"], files, args.site_url, langs=atom.get("langs"), titles=atom.get("titles"),
                                     author=atom.get("author", "GTFS-JP Monitor"), tag=atom.get("tag", "gtfs-jp-monitor")).items():
            path = Path(args.html).parent / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        fields = gzip_bytes(export["fields"]) if ext == ".json.gz" else dumps(export["fields"]).encode("utf-8")
        (Path(args.html).parent / f"fields{ext}").write_bytes(fields)
        # Operational status for monitoring (watchdog, storage check): the export's status plus the
        # size of the site just written.
        site = Path(args.html).parent
        status = dict(export["status"], site_bytes=sum(p.stat().st_size for p in site.rglob("*") if p.is_file()),
                      determinism=export["determinism"])
        if args.stages and Path(args.stages).is_file():
            from .webexport import read_stages
            status["stages"] = read_stages(Path(args.stages))
        (site / "status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"feeds": len(export["feeds"]),
                      "generations": sum(len(f["generations"]) for f in export["feeds"]),
                      "reports": len(export["report_index"]), "report_files": len(files)}, indent=2))
    return 0


def _cmd_check_storage(args: argparse.Namespace) -> int:
    from .webexport import storage_warnings

    status = json.loads(Path(args.status).read_text(encoding="utf-8"))
    repo = args.repo_kb * 1024 if args.repo_kb is not None else None
    st = status["storage"]
    mib = lambda b: f"{b / 2**20:.1f} MiB" if b is not None else "unknown"
    lines = [f"| data repository (with history) | {mib(repo)} |", f"| data working tree | {mib(st['data_bytes'])} |",
             f"| reports ({st['reports']['count']}, avg {st['reports']['avg_bytes'] // 1024} KiB, "
             f"max {st['reports']['max_bytes'] // 1024} KiB) | {mib(st['reports']['bytes'])} |",
             f"| web site | {mib(status.get('site_bytes'))} |"]
    g = st.get("growth")
    if g:
        rate = lambda x: f"{x:+.2f} MiB/day" if x is not None else "unknown"
        lines += [f"| growth {g['from']} – {g['to']}: repository | {rate(g['repo_mb_per_day'])} |",
                  f"| growth: data working tree / reports | {rate(g['data_mb_per_day'])} / {rate(g['reports_mb_per_day'])} |"]
    d = status.get("determinism")
    if d:
        lines.append(f"| same content, other analysis result | {d['different_results']} of {d['same_content_pairs']} pairs |")
    for name, v in (status.get("stages") or {}).items():
        lines.append(f"| stage {name} | {v.get('minutes', '?')} min |")
    print("| Storage | Size |\n|---|---|\n" + "\n".join(lines))
    for w in storage_warnings(status, repo):
        print(f"::warning::{w}")
    return 0


def _cmd_record_storage(args: argparse.Namespace) -> int:
    import datetime as _dt

    from .webexport import record_storage

    entry = record_storage(Path(args.data_dir), args.repo_kb, _dt.datetime.now(_dt.timezone.utc).date())
    print(json.dumps(entry))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtfs_fr_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install-analyzer", help="download, verify and install the pinned analyzer release")
    install.add_argument("--dest", required=True, help="directory for the gtfs-analyzer binary")
    install.add_argument("--lock", default=str(DEFAULT_LOCK))
    install.add_argument("--next", action="store_true",
                         help="install the lock's next release instead (data-model §8.1); does nothing when there is none")
    install.set_defaults(func=_cmd_install_analyzer)

    raw = sub.add_parser("rawdiff", help="list every difference between two GTFS ZIP files (semantic engine, part 1)")
    raw.add_argument("--old", required=True)
    raw.add_argument("--new", required=True)
    raw.add_argument("-o", "--output", required=True, help="output .json.gz (gtfs-fr-semantic-rawdiff/1)")
    raw.set_defaults(func=_cmd_rawdiff)

    rep = sub.add_parser("semantic-report", help="planner change report for two publications (semantic engine, part 3)")
    rep.add_argument("--data-dir", required=True, help="data repository checkout (catalog and validation diffs)")
    rep.add_argument("--feed", required=True, type=_feed_key, metavar="ORG_ID/FEED_ID")
    rep.add_argument("--old", required=True, help="old GTFS ZIP")
    rep.add_argument("--new", required=True, help="new GTFS ZIP")
    rep.add_argument("--old-uid", required=True)
    rep.add_argument("--new-uid", required=True)
    rep.add_argument("--analysis-key", help="e.g. v0.14.0__auto; links the validation diff when it exists")
    rep.add_argument("-o", "--output", required=True, help="output .report.json or .report.json.gz")
    rep.set_defaults(func=_cmd_semantic_report)

    web = sub.add_parser("export-web", help="export data for the web page (prototype)")
    web.add_argument("--data-dir", required=True)
    web.add_argument("--release-tag", required=True, help="analysis release, e.g. v0.14.0")
    web.add_argument("--profile", default="auto", choices=PROFILES)
    web.add_argument("--next-release-tag", help="release being filled in the background; status.json reports its coverage")
    web.add_argument("--analyzer", help="gtfs-analyzer binary, used only to read rule titles (tr/en/ja)")
    web.add_argument("--json", help="write the export JSON here")
    web.add_argument("--html", help="write a self-contained page here")
    web.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    web.add_argument("--bundle-format", choices=("gz", "json"), default="gz",
                     help="report files next to the page: gzip (default) or plain JSON for hosts that do not serve .gz")
    web.add_argument("--stages", help="stage times written by the workflow, added to status.json")
    web.add_argument("--site-profile", help="JSON with another source's page profile, <head> block and Atom settings")
    web.add_argument("--site-url", default="https://ttezer.github.io/gtfs-jp-monitor/",
                     help="address the site is published at, for the links of the Atom feeds")
    web.set_defaults(func=_cmd_export_web)

    rec = sub.add_parser("record-storage", help="add today's sizes to status/storage-history.json (data-model §10.2)")
    rec.add_argument("--data-dir", required=True)
    rec.add_argument("--repo-kb", type=int, help="size of the data repository with history, in KiB (GitHub API)")
    rec.set_defaults(func=_cmd_record_storage)

    chk = sub.add_parser("check-storage", help="print storage sizes and warn past 75%% of a budget (data-model §10.2)")
    chk.add_argument("--status", required=True, help="status.json written by export-web")
    chk.add_argument("--repo-kb", type=int, help="size of the data repository with history, in KiB (GitHub API)")
    chk.set_defaults(func=_cmd_check_storage)

    args = parser.parse_args(argv)
    if getattr(args, "min_interval", 1.0) < 0.5:
        parser.error("--min-interval below 0.5 s is not allowed (be polite to gtfs-data.jp)")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
