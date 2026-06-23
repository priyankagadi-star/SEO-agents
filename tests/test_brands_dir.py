"""brands/<domain>/ is the per-brand home; each brand is fully isolated."""
import json

import pytest

from workspaces import add_account, list_accounts, load_account, workspaces_dir


def test_default_dir_is_brands(monkeypatch):
    monkeypatch.delenv("SEO_BRANDS_DIR", raising=False)
    monkeypatch.delenv("SEO_WORKSPACES_DIR", raising=False)
    assert workspaces_dir().name == "brands"


def test_brands_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SEO_BRANDS_DIR", str(tmp_path / "brands"))
    monkeypatch.delenv("SEO_WORKSPACES_DIR", raising=False)
    assert workspaces_dir() == tmp_path / "brands"


def test_each_brand_is_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("SEO_BRANDS_DIR", str(tmp_path / "brands"))
    add_account("one.com")
    add_account("two.com")
    one = load_account("one.com")
    (one.root / "brand_profile.json").write_text(json.dumps({"name": "One", "value_props": ["a"]}))
    # two's profile is untouched by writing one's
    assert load_account("one.com").brand_profile["name"] == "One"
    assert load_account("two.com").brand_profile.get("name") in (None, "")
    assert sorted(list_accounts()) == ["one.com", "two.com"]
    # data physically lives in separate subfolders
    assert one.root.name == "one.com" and one.root.parent.name == "brands"
