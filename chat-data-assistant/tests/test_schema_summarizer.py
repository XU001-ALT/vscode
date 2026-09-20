"""schema.summarizer 单元测试：描述注入、外键标注、token 预算裁剪。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_schema_summarizer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema.loader import Column, Table
from schema.summarizer import summarize_schema


def _t(name, cols):
    return Table(name=name, columns=[Column(c, "integer") for c in cols])


def test_empty_schema_returns_empty():
    assert summarize_schema([]) == ""


def test_relationship_block_and_fk_annotation():
    tables = [_t("process", ["id", "process_type"]),
              _t("cycle", ["id", "process_id", "count"])]
    out = summarize_schema(tables)
    assert "表关联关系" in out
    assert "cycle" in out and "process" in out
    assert "process_id integer ← FK" in out


def test_local_description_injected():
    # dsc 在 table_descriptions.json 中有中文说明
    out = summarize_schema([_t("dsc", ["id", "peak_temp"])])
    assert "DSC" in out


def test_compact_fallback_when_over_budget():
    big = [_t(f"table_{i}", [f"c{j}" for j in range(40)]) for i in range(10)]
    out = summarize_schema(big, max_tokens=50)
    assert out.strip()
    # 预算不足时应出现紧凑格式 "Table xxx: c0, c1, ..."
    assert "Table " in out


def test_full_format_under_budget():
    out = summarize_schema([_t("small", ["id", "name"])], max_tokens=2000)
    assert "Table small:" in out
    assert "  id integer" in out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
