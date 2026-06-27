"""Per-page GSC: exports self-identify via Filters.csv; the account auto-resolves
each page URL to its own export, falling back to the site-wide latest."""
import csv, io, zipfile
from pathlib import Path

from tools.gsc import export_page_filter


def _make_export(path: Path, page_url: str | None, queries=(("q", 10, 100),)):
    with zipfile.ZipFile(path, "w") as zf:
        q = "Top queries,Clicks,Impressions,CTR,Position\n" + "\n".join(
            f"{t},{c},{i},1%,5" for t, c, i in queries)
        zf.writestr("Queries.csv", q)
        flt = "Filter,Value\nSearch type,Web\nDate,Last 28 days"
        if page_url:
            flt += f"\nPage,{page_url}"
        zf.writestr("Filters.csv", flt)


def test_export_page_filter_reads_page(tmp_path):
    p = tmp_path / "cv.zip"
    _make_export(p, "https://siftly.ai/features/chatgpt-visibility")
    assert export_page_filter(p) == "https://siftly.ai/features/chatgpt-visibility"


def test_export_page_filter_none_for_sitewide(tmp_path):
    p = tmp_path / "site.zip"
    _make_export(p, None)
    assert export_page_filter(p) is None


def test_account_resolves_page_to_its_own_export(tmp_path, monkeypatch):
    from workspaces import Account
    gsc = tmp_path / "gsc"; (gsc / "by-page").mkdir(parents=True)
    _make_export(gsc / "site.zip", None)
    _make_export(gsc / "by-page" / "cv.zip", "https://siftly.ai/features/chatgpt-visibility")
    acc = Account(domain="siftly.ai", root=tmp_path)
    acc.gsc_dir = gsc
    # matching page -> its own export
    got = acc.gsc_export_for("/features/chatgpt-visibility")
    assert got and got.name == "cv.zip"
    # unmatched page -> falls back to a site-wide export
    fb = acc.gsc_export_for("/features/unknown-page")
    assert fb is not None and fb.name in ("site.zip", "cv.zip")
