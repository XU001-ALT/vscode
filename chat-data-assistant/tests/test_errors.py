"""api.errors 单元测试：错误消息 → 稳定错误码。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_errors.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.errors import classify_error


def test_server_busy_first():
    assert classify_error("QueuePool limit reached") == "server_busy"
    assert classify_error("连接池已满，请稍后重试") == "server_busy"


def test_llm_auth():
    assert classify_error("HTTP 401 Unauthorized") == "llm_auth"
    assert classify_error("Invalid API key provided") == "llm_auth"
    assert classify_error("authorization failed") == "llm_auth"


def test_db_unreachable():
    assert classify_error("could not connect to server") == "db_unreachable"
    assert classify_error("connection refused") == "db_unreachable"
    assert classify_error("SQL执行失败: relation does not exist") == "db_unreachable"


def test_llm_timeout():
    assert classify_error("read operation timed out") == "llm_timeout"


def test_no_valid_sql():
    assert classify_error("LLM 未生成合法 SQL") == "no_valid_sql"
    assert classify_error("model produced no valid sql") == "no_valid_sql"


def test_llm_conn():
    assert classify_error("无法连接到 LLM 服务") == "llm_conn"


def test_unknown():
    assert classify_error("") == "unknown"
    assert classify_error(None) == "unknown"
    assert classify_error("something odd") == "unknown"


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
