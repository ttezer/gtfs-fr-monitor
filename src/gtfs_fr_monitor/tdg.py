"""transport.data.gouv.fr client: the French feed source (notes/DESIGN.md).

Every response is untrusted: identifiers are validated before they become paths, contact
fields are not kept. A feed is one GTFS resource of a public-transit dataset:
org_id = the dataset's datagouv_id, feed_id = the resource id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gtfs_fr_pipeline.download import HISTORY_HOST, is_history_url  # noqa: F401 (re-exported)
from gtfs_fr_pipeline.http import USER_AGENT, JsonClient, Transport, urllib_transport  # noqa: F401 (USER_AGENT re-exported)
from gtfs_fr_pipeline.ids import is_path_id
from gtfs_fr_pipeline.source import ApiError, FeedRecord, Rejected

from .regions import dataset_region

BASE_URL = "https://transport.data.gouv.fr"


@dataclass(frozen=True)
class Scope:
    """Which datasets and resources are monitored (notes/DESIGN.md, Kapsam)."""

    dataset_type: str = "public-transit"
    excluded_title_prefixes: tuple[str, ...] = ("Agrégat",)  # regional aggregates repeat local feeds
    excluded_resource_titles: tuple[str, ...] = ("Référentiel complet",)  # all networks in one file

    def dataset_excluded(self, title: str) -> bool:
        return any(title.casefold().startswith(p.casefold()) for p in self.excluded_title_prefixes)

    def resource_excluded(self, title: str) -> bool:
        return any(t.casefold() in title.casefold() for t in self.excluded_resource_titles)


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value != "" else None


def _is_gtfs(resource: dict) -> bool:
    return isinstance(resource, dict) and _str(resource.get("format")).upper() == "GTFS"


def _region(dataset: dict) -> int | None:
    """INSEE region code when every covered area lies in one region (regions.py)."""
    return dataset_region(dataset.get("covered_area") or [])


class TdgClient:
    def __init__(self, transport: Transport = urllib_transport, scope: Scope = Scope(),
                 sleep: Callable[[float], None] | None = None, **http_options) -> None:
        if sleep is not None:
            http_options["sleep"] = sleep
        self._http = JsonClient(BASE_URL, transport=transport, **http_options)
        self.scope = scope

    @property
    def request_count(self) -> int:
        return self._http.request_count

    def list_feeds(self) -> tuple[list[FeedRecord], list[Rejected]]:
        body = self._http.get_json("/api/datasets")
        if not isinstance(body, list):
            raise ApiError("/api/datasets is not a list")
        feeds: list[FeedRecord] = []
        rejected: list[Rejected] = []
        for ds in body:
            if not isinstance(ds, dict) or ds.get("type") != self.scope.dataset_type:
                continue
            title = " ".join(_str(ds.get("title")).split())
            gtfs = [r for r in ds.get("resources") or [] if _is_gtfs(r)]
            if not gtfs or self.scope.dataset_excluded(title):
                continue
            org_id = ds.get("datagouv_id")
            if not is_path_id(org_id):
                rejected.append(Rejected("INVALID_FEED_ID", _opt_str(org_id), None, None, "datagouv_id does not match the path pattern"))
                continue
            kept = [r for r in gtfs if not self.scope.resource_excluded(_str(r.get("title")))]
            for res in kept:
                rid = res.get("id")
                feed_id = str(rid) if isinstance(rid, int) and not isinstance(rid, bool) else None
                if not is_path_id(feed_id):
                    rejected.append(Rejected("INVALID_FEED_ID", org_id, None, None, f"resource id {rid!r}"))
                    continue
                meta = res.get("metadata") if isinstance(res.get("metadata"), dict) else {}
                name = title if len(kept) == 1 else f"{title} — {' '.join(_str(res.get('title')).split())}"
                feeds.append(FeedRecord(
                    org_id=org_id,
                    feed_id=feed_id,
                    feed_name=name,
                    organization_name=_str((ds.get("publisher") or {}).get("name")),
                    feed_pref_id=_region(ds),
                    license_raw=_str(ds.get("licence")),
                    license_url=None,
                    is_discontinued=False,  # is_available is the URL's state at the last check, not an end of service
                    discontinued_date=None,
                    last_published_at=_opt_str(res.get("updated")),
                    latest_feed_start_date=_opt_str(meta.get("start_date")),
                    latest_feed_end_date=_opt_str(meta.get("end_date")),
                    memo="",
                ))
        return feeds, rejected

    def get_dataset(self, org_id: str) -> dict:
        """Details of one dataset, with the last entries of its archived files (`history`)."""
        if not is_path_id(org_id):
            raise ApiError(f"invalid dataset id {org_id!r}")
        body = self._http.get_json(f"/api/datasets/{org_id}")
        if not isinstance(body, dict):
            raise ApiError(f"/api/datasets/{org_id} is not an object")
        return body
