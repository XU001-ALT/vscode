"""前置条件探测（FR-023、research R9）：9 项检查，任一失败即点名缺失项。"""
from __future__ import annotations

import asyncio
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from . import ffmpeg, safety, settings as S

CHECK_IDS = ("backend", "frontend", "schema", "credential", "browser", "ffmpeg", "font", "tts", "disk")

_EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
_CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


@dataclass
class PreflightCheck:
    id: str
    ok: bool
    detail: str
    blocking: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _http_get(url: str, timeout: int = 15) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:                       # noqa: BLE001 - 统一转成检查失败
        return 0, str(exc)


def _http_post_json(url: str, payload: dict, timeout: int = 120) -> tuple[int, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:                       # noqa: BLE001
        return 0, {"_error": str(exc)}


def find_browser() -> tuple[str, str]:
    for path in _EDGE_CANDIDATES:
        if Path(path).is_file():
            return "msedge", path
    for path in _CHROME_CANDIDATES:
        if Path(path).is_file():
            return "chrome", path
    return "", ""


def check_backend(url: str | None = None) -> PreflightCheck:
    base = (url or S.BACKEND_URL).rstrip("/")
    status, body = _http_get(f"{base}/api/health")
    if status == 200:
        return PreflightCheck("backend", True, f"HTTP 200 {base}/api/health")
    return PreflightCheck("backend", False, f"后端不可达（status={status}）：{base} {body[:80]}")


def check_frontend(url: str | None = None) -> PreflightCheck:
    base = (url or S.FRONTEND_URL).rstrip("/")
    status, body = _http_get(base + "/")
    if status == 200:
        return PreflightCheck("frontend", True, f"HTTP 200 {base}/")
    return PreflightCheck("frontend", False, f"前端不可达（status={status}）：{base} {body[:80]}")


def check_schema(url: str | None = None) -> tuple[PreflightCheck, list[str]]:
    base = (url or S.BACKEND_URL).rstrip("/")
    status, body = _http_get(f"{base}/api/bootstrap")
    if status != 200:
        return PreflightCheck("schema", False, f"无法读取 /api/bootstrap（status={status}）"), []
    try:
        payload = json.loads(body)
        tables = list((payload.get("schema") or {}).get("tables") or [])
    except Exception as exc:                       # noqa: BLE001
        return PreflightCheck("schema", False, f"/api/bootstrap 解析失败：{exc}"), []
    if tables:
        return PreflightCheck("schema", True, f"tables={len(tables)}"), tables
    return PreflightCheck("schema", False, "数据库表结构尚未就绪（schema.tables 为空）"), []


def check_credential(url: str | None = None, probe_question: str = "列出所有表的名称") -> PreflightCheck:
    """用一次最小代价的提问确认服务端凭据可用（不接受任何 Key 参数）。"""
    base = (url or S.BACKEND_URL).rstrip("/")
    status, payload = _http_post_json(f"{base}/api/query", {"question": probe_question, "lang": "zh"})
    if status != 200:
        return PreflightCheck("credential", False, f"/api/query 不可用（status={status}）")
    code = payload.get("error_code")
    if code in ("llm_auth", "llm_conn", "llm_timeout"):
        return PreflightCheck("credential", False,
                              f"模型凭据不可用（error_code={code}）；请在服务端配置一份新的有效凭据")
    detail = "probe query ok" if payload.get("ok") else f"probe query 返回 error_code={code}"
    return PreflightCheck("credential", True, safety.sanitize(detail))


def check_browser() -> PreflightCheck:
    channel, path = find_browser()
    if channel:
        return PreflightCheck("browser", True, f"{channel} 已找到：{path}")
    return PreflightCheck("browser", False, "未找到系统 Edge/Chrome（需要其一以驱动真实界面）")


def check_ffmpeg() -> PreflightCheck:
    try:
        ver = ffmpeg.version()
        caps = ffmpeg.capabilities()
    except Exception as exc:                       # noqa: BLE001
        return PreflightCheck("ffmpeg", False, f"ffmpeg 不可用：{exc}")
    missing = [k for k in ("libx264", "zoompan", "xfade", "subtitles") if not caps.get(k)]
    detail = (f"{ver.split(' Copyright')[0]} | libx264={caps.get('libx264')} "
              f"zoompan={caps.get('zoompan')} xfade={caps.get('xfade')} subtitles={caps.get('subtitles')}")
    if missing:
        return PreflightCheck("ffmpeg", False, f"缺少能力：{missing} | {detail}")
    return PreflightCheck("ffmpeg", True, detail)


def check_font() -> PreflightCheck:
    if S.FONT_PATH.is_file():
        return PreflightCheck("font", True, str(S.FONT_PATH))
    return PreflightCheck("font", False, f"缺少中文字体：{S.FONT_PATH}")


def check_tts(timeout: int | None = None) -> PreflightCheck:
    from . import tts
    limit = timeout or S.TTS_PROBE_TIMEOUT_SEC
    try:
        result = asyncio.run(asyncio.wait_for(tts.synthesize("测试", S.TTS_VOICES["zh"], rate="+0%"), timeout=limit))
        return PreflightCheck("tts", True,
                              f"{S.TTS_VOICES['zh']} 合成 {len(result.audio)} 字节 / {len(result.words)} 词边界")
    except Exception as exc:                       # noqa: BLE001
        return PreflightCheck("tts", False, f"TTS 不可用（{type(exc).__name__}: {str(exc)[:100]}）")


def check_disk(runs_dir: Path | None = None) -> PreflightCheck:
    root = Path(runs_dir or S.RUNS_DIR)
    probe = root if root.exists() else Path(root.anchor or ".")
    try:
        usage = shutil.disk_usage(str(probe))
    except OSError as exc:
        return PreflightCheck("disk", False, f"无法读取磁盘余量：{exc}")
    free_gb = usage.free / (1024 ** 3)
    if free_gb < S.MIN_FREE_DISK_GB:
        return PreflightCheck("disk", False, f"可用空间不足：{free_gb:.2f} GB < {S.MIN_FREE_DISK_GB} GB")
    return PreflightCheck("disk", True, f"{free_gb:.1f} GB 可用")


def run_all(*, frontend_url: str | None = None, backend_url: str | None = None,
            with_tts: bool = True) -> tuple[list[PreflightCheck], list[str]]:
    """返回（检查结果, 数据库表名）。全部检查都会跑完，便于一次性看到所有缺失项。"""
    backend = check_backend(backend_url)
    frontend = check_frontend(frontend_url)
    schema_check, tables = check_schema(backend_url)

    if backend.ok and schema_check.ok:
        credential = check_credential(backend_url)
    else:
        credential = PreflightCheck("credential", False, "跳过：后端或 schema 不可用")

    checks = [
        backend, frontend, schema_check, credential, check_browser(),
        check_ffmpeg(), check_font(),
        check_tts() if with_tts else PreflightCheck("tts", False, "跳过：--no-tts-probe"),
        check_disk(),
    ]
    checks.sort(key=lambda c: CHECK_IDS.index(c.id))
    return checks, tables


def failed_ids(checks: list[PreflightCheck]) -> list[str]:
    return [c.id for c in checks if c.blocking and not c.ok]

