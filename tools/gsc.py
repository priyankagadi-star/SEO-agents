"""parse_gsc_export — Google Search Console ZIP/CSV export parsing (BUILD-SPEC §7).

Computes: totals, CTR by position bucket, expected-clicks model (fixed CTR
curve), striking-distance list (pos 8–20 by impressions desc), and the
zero-click anomaly score used by a10's AIO rule (pos≤10 & CTR < 0.1%).
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

# simple CTR curve per BUILD-SPEC §7
CTR_CURVE = [(1, 1, 0.28), (2, 2, 0.15), (3, 3, 0.10), (4, 10, 0.05), (11, 20, 0.015)]

AIO_ZERO_CLICK_CTR = 0.001  # pos<=10 with CTR below this ⇒ likely AI-Overview citation


def expected_ctr(position: float) -> float:
    for lo, hi, ctr in CTR_CURVE:
        if lo <= position <= hi:
            return ctr
    return 0.005


def _num(s: str) -> float:
    return float(str(s).replace(",", "").replace("%", "").strip() or 0)


def _read_csv_rows(name: str, raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def export_page_filter(path: str | Path) -> str | None:
    """If a GSC export is filtered to one page, return that page URL (from its
    Filters.csv 'Page' row); None for a site-wide export. Lets an export
    self-identify which page it belongs to — drop it in, no naming needed."""
    path = Path(path)
    try:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                names = {Path(n).stem.lower(): n for n in zf.namelist()}
                if "filters" not in names:
                    return None
                rows = _read_csv_rows("Filters.csv", zf.read(names["filters"]))
        else:
            return None
    except Exception:
        return None
    for r in rows:
        vals = {k.lower().strip(): v for k, v in r.items()}
        if vals.get("filter", "").strip().lower() == "page":
            return (vals.get("value") or "").strip() or None
    return None


def parse_gsc_export(path: str | Path) -> dict:
    """Parse a GSC export (ZIP with Queries.csv/Pages.csv/Chart.csv/Countries.csv,
    or a single CSV treated as Queries)."""
    path = Path(path)
    tables: dict[str, list[dict]] = {}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                key = Path(name).stem.lower()
                tables[key] = _read_csv_rows(name, zf.read(name))
    else:
        tables["queries"] = _read_csv_rows(path.name, path.read_bytes())

    queries = _normalize_queries(tables.get("queries", []))
    return {
        "queries": queries,
        "pages": tables.get("pages", []),
        "chart": tables.get("chart", []),
        "countries": tables.get("countries", []),
        **analyze_queries(queries),
    }


def _normalize_queries(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        keymap = {k.lower().strip(): k for k in r}

        def col(*names, default="0"):
            for n in names:
                if n in keymap:
                    return r[keymap[n]]
            return default

        out.append({
            "query": col("top queries", "query", "queries", default=""),
            "clicks": _num(col("clicks")),
            "impressions": _num(col("impressions")),
            "ctr": _num(col("ctr")) / (100 if "%" in str(col("ctr")) else 1),
            "position": _num(col("position", "avg. position", "average position")),
        })
    return out


def analyze_queries(queries: list[dict]) -> dict:
    total_clicks = sum(q["clicks"] for q in queries)
    total_impr = sum(q["impressions"] for q in queries)
    expected_clicks = sum(q["impressions"] * expected_ctr(q["position"]) for q in queries)

    striking = sorted(
        (q for q in queries if 8 <= q["position"] <= 20),
        key=lambda q: -q["impressions"],
    )

    # AIO zero-click anomalies: ranking in top 10 but structurally unclicked
    anomalies = [
        q for q in queries
        if q["position"] <= 10 and q["impressions"] > 0
        and (q["clicks"] / q["impressions"]) < AIO_ZERO_CLICK_CTR
    ]
    anomaly_impr = sum(q["impressions"] for q in anomalies)
    zero_click_anomaly_score = (anomaly_impr / total_impr) if total_impr else 0.0

    return {
        "totals": {
            "clicks": total_clicks,
            "impressions": total_impr,
            "ctr": (total_clicks / total_impr) if total_impr else 0.0,
            "expected_clicks": round(expected_clicks, 1),
        },
        "striking_distance_queries": striking,
        "zero_click_anomalies": anomalies,
        "zero_click_anomaly_score": round(zero_click_anomaly_score, 4),
        "aio_flag": (
            "likely AI-Overview citations — CTR is structurally suppressed; "
            "judge on AI-citation share instead"
        ) if anomalies else None,
    }
