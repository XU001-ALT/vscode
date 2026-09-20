"""api.serializers 单元测试：DataFrame → JSON 安全的行/列序列化。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_serializers.py
"""
import datetime
import decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from api.serializers import _cell, df_to_json


def test_none_and_nan_become_none():
    assert _cell(None) is None
    assert _cell(float("nan")) is None
    assert _cell(float("inf")) is None
    assert _cell(np.nan) is None


def test_timestamp_isoformat():
    v = pd.Timestamp("2024-01-02 03:04:05")
    assert _cell(v) == "2024-01-02 03:04:05"


def test_date_isoformat():
    assert _cell(datetime.date(2024, 1, 2)) == "2024-01-02"


def test_decimal_to_float():
    assert _cell(decimal.Decimal("1.5")) == 1.5


def test_numpy_scalars():
    assert _cell(np.int64(7)) == 7 and isinstance(_cell(np.int64(7)), int)
    assert _cell(np.bool_(True)) is True
    assert _cell(np.float32(1.25)) == 1.25


def test_bytes_decoded():
    assert _cell(b"hi") == "hi"


def test_dict_and_list_passthrough():
    assert _cell({"a": 1}) == {"a": 1}
    assert _cell([1, 2]) == [1, 2]


def test_plain_values():
    assert _cell("s") == "s"
    assert _cell(3) == 3
    assert _cell(True) is True


def test_df_to_json_columns_and_rows():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    cols, rows = df_to_json(df)
    assert cols == ["a", "b"]
    assert rows == [[1, "x"], [2, "y"]]


def test_df_to_json_non_string_columns():
    df = pd.DataFrame({0: [1], "n": [None]})
    cols, rows = df_to_json(df)
    assert cols == ["0", "n"]
    assert rows == [[1, None]]


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
