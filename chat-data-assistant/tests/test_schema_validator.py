"""schema.validator 单元测试。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_schema_validator.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema.loader import Column, Table
from schema.validator import validate_schema


def _table(name, cols=("id",)):
    return Table(name=name, columns=[Column(c, "int") for c in cols])


def test_valid_schema():
    ok, errors = validate_schema([_table("a"), _table("b")])
    assert ok and errors == []


def test_empty_schema_invalid():
    ok, errors = validate_schema([])
    assert not ok and errors


def test_duplicate_table_name():
    ok, errors = validate_schema([_table("a"), _table("a")])
    assert not ok
    assert any("重复" in e for e in errors)


def test_table_without_columns():
    ok, errors = validate_schema([Table(name="a", columns=[])])
    assert not ok
    assert any("列" in e for e in errors)


def test_empty_table_name():
    ok, errors = validate_schema([_table("")])
    assert not ok
    assert any("空表名" in e for e in errors)


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
