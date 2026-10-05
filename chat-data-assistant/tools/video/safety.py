"""敏感信息扫描与脱敏（FR-018、SC-012、Constitution II）。

所有落盘文本（report.json / manifest.json / 日志 / 字幕）必须先经本模块。
模式在既有 ``core/secrets.py`` 的基础上扩展：密钥、Bearer token、数据库连接串、
真实库名或账号、内网地址。
"""
from __future__ import annotations

import re

# 与 core/secrets.py 保持一致的两条基础模式
API_KEY_RE = re.compile(r"sk-[a-zA-Z0-9_\-]{16,}")
BEARER_RE = re.compile(r"Bearer\s+[a-zA-Z0-9\-_=+./]{16,}")

# 连接串：postgres/mysql/sqlite 等，含用户名口令
CONN_STR_RE = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|mssql)://[^\s\"']+",
    re.IGNORECASE,
)
# 内网地址（IPv4 私有段 + 本机回环以外的内网主机名）
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
# 账号/口令赋值形式
CRED_ASSIGN_RE = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|api_?key|access_?key|token)\s*[:=]\s*[^\s,;\"']{6,}"
)
# .env 风格的 DB 变量
DB_ENV_RE = re.compile(
    r"(?i)\b(?:DB|POSTGRES|PG|DATABASE)_(?:HOST|USER|PASSWORD|NAME|PORT|DSN|URL)\s*=\s*[^\s]+"
)

_SCAN_PATTERNS = (
    ("api_key", API_KEY_RE),
    ("bearer", BEARER_RE),
    ("conn_str", CONN_STR_RE),
    ("private_ip", PRIVATE_IP_RE),
    ("credential", CRED_ASSIGN_RE),
    ("db_env", DB_ENV_RE),
)


def scan_text(text: str) -> list[dict]:
    """返回检出项列表（每项含 kind / match 片段 / 位置）。空列表表示干净。"""
    if not text:
        return []
    findings: list[dict] = []
    for kind, pattern in _SCAN_PATTERNS:
        for m in pattern.finditer(text):
            findings.append({"kind": kind, "excerpt": _excerpt(m.group(0)), "start": m.start()})
    return findings


def sanitize(text: str) -> str:
    """把敏感片段替换为占位符；幂等（重复调用不会再变化）。"""
    if not text:
        return text
    out = API_KEY_RE.sub("[API_KEY_REDACTED]", text)
    out = BEARER_RE.sub("Bearer [REDACTED]", out)
    out = CONN_STR_RE.sub("[CONN_STR_REDACTED]", out)
    out = PRIVATE_IP_RE.sub("[PRIVATE_IP_REDACTED]", out)
    out = CRED_ASSIGN_RE.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]", out)
    out = DB_ENV_RE.sub("[DB_ENV_REDACTED]", out)
    return out


def _excerpt(value: str, limit: int = 48) -> str:
    head = value[:limit]
    return head + ("…" if len(value) > limit else "")


def count_findings(text: str) -> int:
    """计数值，供 manifest 的 sensitive_findings 使用。"""
    return len(scan_text(text))


def sanitize_mapping(text: str) -> str:
    """别名：语义上强调「用于写入 mapping 前」。"""
    return sanitize(text)
