"""sql_guard 单元测试。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_sql_guard.py
也兼容 pytest：
    venv\\Scripts\\python.exe -m pytest tests\\test_sql_guard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.sql_guard import validate_sql


def test_select_ok():
    ok, err = validate_sql("SELECT * FROM t")
    assert ok, err


def test_with_cte_ok():
    ok, err = validate_sql("WITH x AS (SELECT 1 AS a) SELECT a FROM x")
    assert ok, err


def test_explain_ok():
    ok, err = validate_sql("EXPLAIN SELECT 1")
    assert ok, err


def test_lowercase_ok():
    ok, err = validate_sql("  select 1  ")
    assert ok, err


def test_empty_rejected():
    assert not validate_sql("")[0]
    assert not validate_sql("   ")[0]
    assert not validate_sql(None)[0]


def test_drop_rejected():
    ok, _ = validate_sql("DROP TABLE users")
    assert not ok


def test_delete_rejected():
    ok, _ = validate_sql("DELETE FROM users")
    assert not ok


def test_insert_update_rejected():
    assert not validate_sql("INSERT INTO t VALUES (1)")[0]
    assert not validate_sql("UPDATE t SET a = 1")[0]


def test_leading_comment_still_rejected():
    # 前置注释不能绕过只读前缀检查
    ok, _ = validate_sql("-- comment\nDROP TABLE users")
    assert not ok


def test_multi_statement_rejected():
    ok, err = validate_sql("SELECT 1; DROP TABLE x")
    assert not ok
    assert "多" in err or "multiple" in err.lower()


def test_trailing_semicolon_allowed():
    ok, err = validate_sql("SELECT 1;")
    assert ok, err


def test_semicolon_inside_string_allowed():
    ok, err = validate_sql("SELECT 'a;b' FROM t")
    assert ok, err


def test_semicolon_in_string_not_split():
    # 字符串里的分号 + 真实第二条语句：必须拦下
    ok, _ = validate_sql("SELECT 'a;b'; DROP TABLE x")
    assert not ok


def test_escaped_quote_in_string():
    ok, err = validate_sql("SELECT 'it''s; fine' FROM t")
    assert ok, err


def test_block_comment_hides_semicolon():
    ok, err = validate_sql("SELECT /* a;b */ 1")
    assert ok, err


def test_quoted_identifier_semicolon():
    ok, err = validate_sql('SELECT "col;x" FROM t')
    assert ok, err


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
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
