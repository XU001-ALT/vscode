"""Offline regression checks for the unchanged original website."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from ingest_extraction import append_to_parquet

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "📊 平台数据总览",
    "📥 论文自动下载",
    "🔬 数据自动提取",
    "📈 数据可视化分析",
    "📖 使用说明",
]


@pytest.mark.parametrize("page", PAGES)
def test_five_original_pages(page):
    app = AppTest.from_file(str(ROOT / "app27.py"), default_timeout=60)
    app.session_state["page"] = page
    app.run()
    assert not app.exception and not app.error
    navigation = [b for b in app.button if b.key and b.key.startswith("nav_btn_")]
    assert [b.label for b in navigation] == PAGES


def test_merged_overview_and_navigation():
    app = AppTest.from_file(str(ROOT / "app27.py"), default_timeout=60).run()
    assert app.multiselect(key="db_family")
    assert len(app.get("plotly_chart")) >= 2
    app.multiselect(key="db_metal").set_value(["Co"]).run()
    assert not app.exception and len(app.get("plotly_chart")) >= 2
    app.button(key="nav_btn_3").click().run()
    assert app.session_state["page"] == PAGES[3]
    assert not app.exception and len(app.get("plotly_chart")) >= 4
    app.radio(key="viz_data_source").set_value("论文信息（年份/期刊/工艺路线）").run()
    assert not app.exception and not app.error


def test_original_source_hashes_and_no_model_module():
    manifest = json.loads((ROOT / "docs/upstream-manifest.json").read_text(encoding="utf-8-sig"))
    for name, info in manifest["files"].items():
        if not name.startswith("outputs/"):
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == info["sha256"], name
    for name in ("model_service.py", "prediction_ui.py", "model_bundle"):
        assert not (ROOT / name).exists()


def test_ingestion_preserves_existing_record(tmp_path):
    destination = tmp_path / "test.parquet"
    pd.DataFrame({"paper_id": ["existing"], "CO_conversion_pct": [42.0]}).to_parquet(destination)
    result = append_to_parquet(
        "test-paper", "test-sha", "test.pdf", 100, 1,
        {"metadata": {"metadata": {"title": "Offline test"}}}, destination,
    )
    assert result["appended"] == 1
    after = pd.read_parquet(destination)
    assert len(after) == 2
    assert after.loc[after.paper_id == "existing", "CO_conversion_pct"].iloc[0] == 42.0
