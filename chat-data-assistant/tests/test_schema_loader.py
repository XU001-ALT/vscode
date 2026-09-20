"""schema.loader 单元测试：三种格式解析、关系推断、回写文本。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_schema_loader.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema.loader import (
    Column, Table, load_from_text, schema_to_text,
    infer_relationships, format_relationships_text,
)


# ── 自定义文本格式 ──

def test_parse_text_format():
    tables = load_from_text("Table users:\n  id int\n  email text (nullable)")
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "users"
    assert [c.name for c in t.columns] == ["id", "email"]
    assert t.columns[0].dtype == "int" and not t.columns[0].nullable
    assert t.columns[1].nullable is True


def test_parse_text_multiple_tables():
    text = "Table a:\n  x int\n\nTable b:\n  y text"
    tables = load_from_text(text)
    assert [t.name for t in tables] == ["a", "b"]


def test_parse_garbage_returns_empty():
    assert load_from_text("this is not a schema") == []
    assert load_from_text("") == []
    assert load_from_text("   ") == []


# ── JSON 格式 ──

def test_parse_json_dict_of_lists():
    text = '{"users": [{"name": "id", "type": "int"}, ' \
           '{"name": "email", "type": "text", "nullable": true}]}'
    tables = load_from_text(text)
    assert len(tables) == 1
    assert tables[0].name == "users"
    assert tables[0].columns[1].nullable is True


def test_parse_json_dict_with_columns_key():
    text = '{"users": {"columns": [{"column": "id", "dtype": "int"}]}}'
    tables = load_from_text(text)
    assert tables[0].columns[0].name == "id"
    assert tables[0].columns[0].dtype == "int"


def test_parse_json_list_of_objects():
    text = '[{"table_name": "t", "fields": [{"field": "a", "data_type": "int"}]}]'
    tables = load_from_text(text)
    assert tables[0].name == "t"
    assert tables[0].columns[0].name == "a"


# ── Python ORM 格式 ──

def test_parse_orm_classic_column():
    text = (
        "class User(Base):\n"
        "    __tablename__ = 'users'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    email = Column(String(100), nullable=True)\n"
    )
    tables = load_from_text(text)
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "users"
    assert t.columns[0].name == "id" and t.columns[0].dtype == "Integer"
    assert t.columns[1].name == "email" and t.columns[1].nullable


def test_parse_orm_v2_mapped_column():
    text = (
        "class T(Base):\n"
        "    __tablename__ = 't'\n"
        "    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n"
        "    name: Mapped[str] = mapped_column(String)\n"
    )
    tables = load_from_text(text)
    assert tables[0].name == "t"
    assert [c.name for c in tables[0].columns] == ["id", "name"]
    assert tables[0].columns[1].dtype == "String"


def test_orm_without_tablename_returns_empty():
    assert load_from_text("x = Column(Integer)") == []


# ── schema_to_text ──

def test_schema_to_text_roundtrip():
    tables = [Table(name="t", description="说明",
                    columns=[Column("a", "int", True), Column("b", "text")])]
    out = schema_to_text(tables)
    assert "Table t: 说明" in out
    assert "  a int (nullable)" in out
    assert "  b text" in out


# ── 关系推断 ──

def _t(name, cols):
    return Table(name=name, columns=[Column(c, "integer") for c in cols])


def test_infer_relationships_basic_fk():
    tables = [_t("process", ["id", "process_type"]),
              _t("cycle", ["id", "process_id", "count"])]
    rels = infer_relationships(tables)
    assert len(rels) == 1
    r = rels[0]
    assert r["from_table"] == "cycle" and r["from_col"] == "process_id"
    assert r["to_table"] == "process" and r["to_col"] == "id"
    assert r["confidence"] == "high"


def test_infer_relationships_plural_target():
    tables = [_t("samples", ["id"]), _t("measurements", ["id", "sample_id"])]
    rels = infer_relationships(tables)
    assert rels and rels[0]["to_table"] == "samples"


def test_infer_relationships_ignores_plain_id_and_self():
    tables = [_t("only", ["id"])]
    assert infer_relationships(tables) == []


def test_infer_relationships_skips_missing_target():
    tables = [_t("a", ["id", "ghost_id"])]
    assert infer_relationships(tables) == []


def test_format_relationships_text():
    rels = infer_relationships([_t("process", ["id"]),
                                _t("cycle", ["id", "process_id"])])
    text = format_relationships_text(rels)
    assert "表关联关系" in text
    assert "cycle" in text and "process" in text


def test_format_relationships_text_empty():
    assert format_relationships_text([]) == ""


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
