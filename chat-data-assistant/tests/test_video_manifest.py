"""tools.video.manifest 单元测试：run_id、sha256、不可覆盖保护与发布备份（FR-022 / SC-010）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_manifest.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import manifest  # noqa: E402
from tools.video import settings as S  # noqa: E402


def _redirect_runs(tmp: Path) -> Path:
    S.RUNS_DIR = tmp
    return tmp


def test_run_id_shape_and_short_sha():
    run_id = manifest.new_run_id("cd3ef34")
    assert re.match(S.RUN_ID_RE, run_id), run_id
    assert run_id.endswith("-cd3ef34")


def test_ensure_run_dir_creates_subdirs():
    with tempfile.TemporaryDirectory() as raw:
        root = _redirect_runs(Path(raw))
        path = manifest.ensure_run_dir(manifest.new_run_id("abc1234"))
        for name in manifest.SUBDIRS:
            assert (path / name).is_dir()
        assert path.parent == root


def test_write_json_refuses_overwrite():
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "report.json"
        manifest.write_json(path, {"a": 1})
        assert json.loads(path.read_text(encoding="utf-8"))["a"] == 1
        try:
            manifest.write_json(path, {"a": 2})
        except manifest.ManifestError as exc:
            assert exc.code == "path_exists"
        else:
            raise AssertionError("重复写入应当失败")


def test_write_json_rejects_sensitive_payload():
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "report.json"
        try:
            manifest.write_json(path, {"error_excerpt": "sk-abcdefghijklmnopqrstuvwx1234"})
        except manifest.ManifestError as exc:
            assert exc.code == "sensitive_in_report"
        else:
            raise AssertionError("含敏感信息的内容不应落盘")


def test_update_json_allows_in_place_update():
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "manifest.json"
        manifest.write_json(path, {"verification_passed": False})
        manifest.update_json(path, {"verification_passed": True})
        assert json.loads(path.read_text(encoding="utf-8"))["verification_passed"] is True


def test_sha256_matches_file_content():
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "x.bin"
        path.write_bytes(b"hello")
        assert manifest.sha256_file(path) == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")


def test_existing_video_hashes_scans_all_runs():
    with tempfile.TemporaryDirectory() as raw:
        root = _redirect_runs(Path(raw))
        old = root / "20260101-000000-aaaaaaa"
        old.mkdir(parents=True)
        (old / "demo-zh.mp4").write_bytes(b"OLD-VIDEO")
        new = root / "20260102-000000-bbbbbbb"
        new.mkdir(parents=True)
        (new / "demo-zh.mp4").write_bytes(b"NEW-VIDEO")
        hashes = manifest.existing_video_hashes()
        assert set(hashes) == {f"{old.name}/demo-zh.mp4", f"{new.name}/demo-zh.mp4"}
        only_old = manifest.existing_video_hashes(exclude_run=new.name)
        assert set(only_old) == {f"{old.name}/demo-zh.mp4"}


def test_resolve_latest_run_dir():
    with tempfile.TemporaryDirectory() as raw:
        root = _redirect_runs(Path(raw))
        (root / "20260101-000000-aaaaaaa").mkdir(parents=True)
        last = root / "20260102-000000-bbbbbbb"
        last.mkdir(parents=True)
        assert manifest.resolve_run_dir(None) == last
        assert manifest.resolve_run_dir(last.name) == last


def test_resolve_run_dir_without_runs_fails():
    with tempfile.TemporaryDirectory() as raw:
        _redirect_runs(Path(raw) / "missing")
        try:
            manifest.resolve_run_dir(None)
        except manifest.ManifestError as exc:
            assert exc.code == "run_not_found"
        else:
            raise AssertionError("没有运行目录时应当报错")


def test_publish_dry_run_does_not_touch_files():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = tmp / "run"
        run.mkdir()
        (run / "demo-zh.mp4").write_bytes(b"ZH")
        (run / "demo-en.mp4").write_bytes(b"EN")
        target = tmp / "public"
        target.mkdir()
        (target / "demo.mp4").write_bytes(b"OLD")
        result = manifest.publish(run, apply=False, target_dir=target)
        assert result["applied"] is False and result["targets"] == []
        assert (target / "demo.mp4").read_bytes() == b"OLD"


def test_publish_apply_backs_up_then_copies():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = tmp / "run"
        run.mkdir()
        (run / "demo-zh.mp4").write_bytes(b"ZH")
        (run / "demo-en.mp4").write_bytes(b"EN")
        target = tmp / "public"
        target.mkdir()
        (target / "demo.mp4").write_bytes(b"OLD")
        result = manifest.publish(run, apply=True, target_dir=target)
        assert result["applied"] is True and len(result["targets"]) == 2
        assert (target / "demo.mp4").read_bytes() == b"ZH"
        assert (target / "demo-en.mp4").read_bytes() == b"EN"
        assert len(result["backups"]) == 1
        backup = Path(result["backups"][0])
        assert backup.is_file() and backup.read_bytes() == b"OLD"
        assert re.search(r"demo\.\d{8}-\d{6}\.bak\.mp4$", backup.name)


def test_publish_without_videos_fails():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        run = tmp / "run"
        run.mkdir()
        try:
            manifest.publish(run, apply=False, target_dir=tmp)
        except manifest.ManifestError as exc:
            assert exc.code == "publish_nothing"
        else:
            raise AssertionError("没有成片时应当报错")


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

