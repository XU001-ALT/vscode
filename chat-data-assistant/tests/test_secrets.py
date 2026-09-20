"""core.secrets 单元测试：服务端私有 Key 存取、脱敏与错误清洗。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_secrets.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import secrets


def test_store_retrieve_remove_roundtrip():
    token = secrets.store("sk-test-1234567890abcdef")
    assert secrets.retrieve(token) == "sk-test-1234567890abcdef"
    secrets.remove(token)
    assert secrets.retrieve(token) == ""


def test_retrieve_invalid_token():
    assert secrets.retrieve(None) == ""
    assert secrets.retrieve("") == ""
    assert secrets.retrieve("no-such-token") == ""


def test_remove_invalid_token_noop():
    secrets.remove(None)
    secrets.remove("nope")


def test_tokens_are_unique():
    a = secrets.store("k1")
    b = secrets.store("k2")
    assert a != b and len(a) == 48
    secrets.remove(a)
    secrets.remove(b)


def test_mask_key():
    assert secrets.mask_key("sk-1234567890abcdef", visible=6) == "sk-123***abcdef"
    assert secrets.mask_key("short") == "short"  # 过短不脱敏
    assert secrets.mask_key("") == ""


def test_sanitize_error_redacts_sk_key():
    out = secrets.sanitize_error("auth failed for sk-abcdefghijklmnop1234")
    assert "sk-abcdefghijklmnop1234" not in out
    assert "[API_KEY_REDACTED]" in out


def test_sanitize_error_redacts_bearer():
    out = secrets.sanitize_error("header Bearer abcdefghijklmnopqrstuvwxyz")
    assert "abcdefghijklmnopqrstuvwxyz" not in out
    assert "Bearer [REDACTED]" in out


def test_sanitize_error_keeps_plain_text():
    assert secrets.sanitize_error("connection refused") == "connection refused"


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
