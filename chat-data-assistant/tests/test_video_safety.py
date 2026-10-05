"""tools.video.safety 单元测试：敏感信息扫描与脱敏（FR-018 / SC-012）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_safety.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import safety  # noqa: E402

FAKE_KEY = "sk-abcdefghijklmnopqrstuvwx1234"
FAKE_DSN = "postgresql://analyst:s3cretPwd@10.20.30.40:5432/hydrogen_db"


def test_detects_api_key():
    findings = safety.scan_text(f"auth failed for {FAKE_KEY}")
    assert any(f["kind"] == "api_key" for f in findings)
    out = safety.sanitize(f"auth failed for {FAKE_KEY}")
    assert FAKE_KEY not in out and "[API_KEY_REDACTED]" in out


def test_detects_bearer_token():
    token = "Bearer abcdefghijklmnopqrstuvwxyz012345"
    assert safety.count_findings(token) >= 1
    assert "abcdefghijklmnopqrstuvwxyz012345" not in safety.sanitize(token)


def test_detects_connection_string():
    assert any(f["kind"] == "conn_str" for f in safety.scan_text(FAKE_DSN))
    assert "s3cretPwd" not in safety.sanitize(FAKE_DSN)


def test_detects_private_ip():
    for ip in ("10.1.2.3", "192.168.100.7", "172.16.5.9", "172.31.255.1"):
        assert safety.count_findings(f"host {ip} unreachable") >= 1, ip
    assert "[PRIVATE_IP_REDACTED]" in safety.sanitize("host 10.1.2.3 unreachable")


def test_public_ip_not_flagged():
    assert safety.count_findings("host 8.8.8.8 and 172.32.0.1 are public") == 0


def test_detects_credential_assignment_and_env():
    assert safety.count_findings("password: hunter2hunter2") >= 1
    assert safety.count_findings("DB_PASSWORD=topsecret123") >= 1


def test_sanitize_is_idempotent():
    dirty = f"{FAKE_KEY} {FAKE_DSN} Bearer abcdefghijklmnopqrstuvwxyz012345"
    once = safety.sanitize(dirty)
    twice = safety.sanitize(once)
    assert once == twice
    assert safety.count_findings(once) == 0


def test_clean_text_untouched():
    clean = "对比全部 PCT 测试的平台压力与放氢容量分布"
    assert safety.scan_text(clean) == []
    assert safety.sanitize(clean) == clean


def test_empty_input():
    assert safety.scan_text("") == []
    assert safety.sanitize("") == ""


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
