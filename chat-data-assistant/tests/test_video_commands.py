"""tools.video.cli 单元测试：退出码语义与「失败不留半成品」（contracts/cli.md §4/§7）。

外部依赖全部以替身隔离（不启动浏览器、不访问网络、不调用模型）。
无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_commands.py
"""
import contextlib
import functools
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import capture, cli, preflight, settings as S  # noqa: E402
from tools.video import ui_surface  # noqa: E402


def _check(cid: str, ok: bool = True, detail: str = "stub") -> preflight.PreflightCheck:
    return preflight.PreflightCheck(cid, ok, detail)


def _all_ok(*, failing: str | None = None):
    checks = [_check(cid, cid != failing) for cid in preflight.CHECK_IDS]
    return lambda **kwargs: (checks, ["t1", "t2"])


class _FakePage:
    """占位页面：只提供 open_app 用到的调用面，避免真的启动浏览器。"""

    def __init__(self):
        self.visited: list[str] = []

    def goto(self, url, **_kwargs):
        self.visited.append(url)

    def wait_for_selector(self, *_args, **_kwargs):
        return None

    def query_selector(self, *_args, **_kwargs):
        return None

    def evaluate(self, *_args, **_kwargs):
        return None

    def click(self, *_args, **_kwargs):
        return None


@contextlib.contextmanager
def _fake_browser(**_kwargs):
    yield None, None, _FakePage()


def _capture_output(argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        code = cli.main(argv)
    return code, buffer.getvalue()


def _probe_args(extra: tuple[str, ...] = ()):
    """用真实解析器构造 probe 参数（顺带覆盖 CLI 选项面）。"""
    return cli.build_parser().parse_args(["probe", *extra])


# apply_overrides() 会改写全局设置，且用例会用替身替换外部依赖；
# 不还原就会让「上一条用例的临时目录/替身」污染下一条用例。
_SETTING_KEYS = ("CONTENT_DIR", "RUNS_DIR", "FRONTEND_URL", "BACKEND_URL", "MIN_DATA_POINTS")
_PATCH_TARGETS = (
    (preflight, ("run_all", "failed_ids")),
    (capture, ("browser_session", "open_app", "ask_query", "capture_manual")),
    (ui_surface, ("check_page", "check_chart", "check_manual")),
)


@contextlib.contextmanager
def _isolated():
    saved = [(S, name, getattr(S, name)) for name in _SETTING_KEYS]
    for module, names in _PATCH_TARGETS:
        saved += [(module, name, getattr(module, name)) for name in names]
    try:
        yield
    finally:
        for module, name, value in reversed(saved):
            setattr(module, name, value)


def isolated(fn):
    """用例级隔离：结束后把设置与替身还原成原样。"""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _isolated():
            return fn(*args, **kwargs)

    return wrapper


@isolated
def test_doctor_passes_returns_zero():
    cli.preflight.run_all = _all_ok()
    cli.capture.browser_session = _fake_browser
    cli.ui_surface.check_page = lambda page: ({"A1": True}, [])
    code, out = _capture_output(["doctor"])
    assert code == S.EXIT_OK and "PASS 9/9" in out


@isolated
def test_doctor_failing_check_returns_preflight_code():
    cli.preflight.run_all = _all_ok(failing="credential")
    cli.capture.browser_session = _fake_browser
    cli.ui_surface.check_page = lambda page: ({"A1": True}, [])
    code, out = _capture_output(["doctor"])
    assert code == S.EXIT_PREFLIGHT and "credential" in out


@isolated
def test_doctor_ui_surface_drift_returns_four():
    cli.preflight.run_all = _all_ok()
    cli.capture.browser_session = _fake_browser

    def _drift(_page):
        raise ui_surface.UiSurfaceDrift(["A3"])

    cli.ui_surface.check_page = _drift
    code, out = _capture_output(["doctor"])
    assert code == S.EXIT_UI_SURFACE and "A3" in out


@isolated
def test_doctor_json_output_is_parseable():
    cli.preflight.run_all = _all_ok()
    cli.capture.browser_session = _fake_browser
    cli.ui_surface.check_page = lambda page: ({"A1": True}, [])
    code, out = _capture_output(["doctor", "--json"])
    assert code == S.EXIT_OK
    payload = json.loads(out)
    assert payload["passed"] == 9 and len(payload["checks"]) == 9


@isolated
def test_unknown_option_is_usage_error():
    try:
        cli.main(["doctor", "--api-key", "sk-should-be-rejected"])
    except SystemExit as exc:
        assert exc.code == S.EXIT_USAGE
    else:
        raise AssertionError("未知选项（如凭据参数）应当以用法错误退出")


@isolated
def test_probe_preflight_failure_leaves_no_video_artifacts():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        runs = tmp / "runs"
        cli.preflight.run_all = _all_ok(failing="frontend")
        code, _out = _capture_output(["probe", "--runs-dir", str(runs), "--json"])
        assert code == S.EXIT_PREFLIGHT
        run_dirs = list(runs.iterdir())
        assert len(run_dirs) == 1
        assert (run_dirs[0] / "report.json").is_file()
        assert not list(runs.rglob("demo-*.mp4"))
        assert not list(runs.rglob("segments/*.mp4"))
        assert not list(runs.rglob("manifest.json"))


@isolated
def test_build_refuses_to_overwrite_existing_manifest():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = tmp / "20260101-000000-aaaaaaa"
        run.mkdir(parents=True)
        (run / "report.json").write_text(json.dumps({
            "schema_version": "1.0.0", "run_id": run.name, "generated_at": "2026-01-01T00:00:00+08:00",
            "tool_versions": {}, "preflight": [], "candidates": [],
            "summary": {"total": 0, "chart_ok": 0, "table_only": 0, "failed": 0,
                        "recommended": 0, "manual_recommended": 0, "issues": []},
            "seeded_from": None,
        }, ensure_ascii=False), encoding="utf-8")
        (run / "manifest.json").write_text("{}", encoding="utf-8")
        code, _out = _capture_output(["build", "--runs-dir", str(tmp), "--run-id", run.name])
        assert code == S.EXIT_RENDER


@isolated
def test_verify_without_manifest_returns_verify_code():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = tmp / "20260101-000000-bbbbbbb"
        run.mkdir(parents=True)
        code, _out = _capture_output(["verify", "--runs-dir", str(tmp), "--run-id", run.name])
        assert code == S.EXIT_VERIFY


@isolated
def test_publish_without_runs_returns_publish_code():
    with tempfile.TemporaryDirectory() as raw:
        code, _out = _capture_output(["publish", "--runs-dir", str(Path(raw) / "nope")])
        assert code == S.EXIT_PUBLISH


@isolated
def test_content_error_returns_content_code():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / "scenes.toml").write_text("[meta]\n", encoding="utf-8")
        (tmp / "candidates.toml").write_text("[meta]\n", encoding="utf-8")
        code, _out = _capture_output(["probe", "--content-dir", str(tmp), "--runs-dir", str(tmp / "runs")])
        assert code == S.EXIT_CONTENT


@isolated
def test_probe_query_checks_chart_anchor_group():
    """问答出图后核对 A10/A11/A12（.chart-view 组），不得核对手动绘图锚点。"""
    snapshot = capture.CaptureSnapshot(
        has_plotly=True, traces=[{"type": "scatter", "points": 1000, "method": "plotly_points"}])
    calls: list[str] = []
    cli.capture.ask_query = lambda *a, **k: snapshot
    cli.ui_surface.check_chart = lambda page: calls.append("chart") or []

    def _boom(_page):
        raise AssertionError("问答采集不应核对手动绘图锚点组")

    cli.ui_surface.check_manual = _boom
    with tempfile.TemporaryDirectory() as raw:
        result = cli._probe_one(_FakePage(), item_id="demo_query", source="query",
                                prompt={"zh": "绘制分布图", "en": "Plot a chart"}, question="绘制分布图",
                                run_path=Path(raw), args=_probe_args())
    assert calls == ["chart"]
    assert result["verdict"] == "chart_ok" and result["data_points"] == 1000


@isolated
def test_probe_manual_checks_manual_anchor_group():
    """手动绘图出图后只核对 A16（.manual-plot-demo 组）——手动区没有 .chart-view。"""
    snapshot = capture.CaptureSnapshot(
        has_plotly=True, traces=[{"type": "scatter", "points": 31, "method": "plotly_points"}])
    calls: list[str] = []
    cli.capture.capture_manual = lambda *a, **k: snapshot
    cli.ui_surface.check_manual = lambda page: calls.append("manual") or []

    def _boom(_page):
        raise AssertionError("手动绘图不应核对 .chart-view 锚点组 A10/A11/A12")

    cli.ui_surface.check_chart = _boom
    manual = SimpleNamespace(chart_type="bubble")
    with tempfile.TemporaryDirectory() as raw:
        result = cli._probe_one(_FakePage(), item_id="manual_bubble", source="manual",
                                prompt={"zh": "气泡图", "en": "Bubble map"},
                                run_path=Path(raw), args=_probe_args(), manual=manual)
    assert calls == ["manual"]
    assert result["verdict"] == "chart_ok" and result["chart_type"] == "bubble"


@isolated
def test_probe_skips_anchor_checks_when_no_plot():
    """没出图（table_only）时不得核对任何「出图后才存在」的锚点。"""
    snapshot = capture.CaptureSnapshot(answer_text="该问题仅返回单行结论")
    reasons: list[str] = []
    cli.capture.ask_query = lambda *a, **k: snapshot
    cli.ui_surface.check_chart = lambda page: reasons.append("chart") or []

    def _boom(_page):
        raise AssertionError("无图时不应核对手动绘图锚点组")

    cli.ui_surface.check_manual = _boom
    with tempfile.TemporaryDirectory() as raw:
        result = cli._probe_one(_FakePage(), item_id="demo_table", source="query",
                                prompt={"zh": "一共有多少条记录", "en": "How many records"},
                                question="一共有多少条记录",
                                run_path=Path(raw), args=_probe_args())
    assert reasons == [] and result["verdict"] == "table_only"


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
