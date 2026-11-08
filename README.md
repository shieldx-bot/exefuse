# ExeFuse — Gộp 2 file EXE thành 1 file duy nhất

> Một app chạy **ngầm (ẩn cửa sổ)**, một app **hiển thị giao diện** — tất cả trong **1 file .exe** duy nhất.
> Không còn cảnh 2 cửa sổ cùng bật lên lúc khởi động, chỉ hiện đúng cửa sổ bạn cần.

## Tính năng

- Web UI chạy local (Flask) — kéo thả 2 file EXE, bấm build là xong
- Xuất **1 file .exe duy nhất**, chạy được trên máy **không cần cài Python**
- App ẩn: không cửa sổ, không taskbar, không Alt-Tab (`SW_HIDE` + `CREATE_NO_WINDOW` + watcher ép ẩn liên tục)
- Tùy chọn tự tắt tiến trình ẩn khi app chính đóng (dọn tài nguyên sạch sẽ, tránh lãng phí RAM)
- Icon `.ico` tùy chỉnh cho file output
- Log build trực tiếp trên web, tải file kết quả ngay tại chỗ
- Chạy 100% trên máy bạn — file EXE không bị gửi ra ngoài

## Cài đặt (Windows)

1. Cài [Python 3.10+](https://www.python.org/downloads/) — nhớ tick **Add python.exe to PATH**
2. Tải repo này về: nút **Code → Download ZIP**, hoặc:
   ```
   git clone https://github.com/shieldx-bot/exefuse.git
   ```
3. Double-click **`run.bat`** — nó sẽ tự:
   - Cài Flask + PyInstaller (lần đầu tiên)
   - Mở trình duyệt tại `http://127.0.0.1:5000`

Cách thủ công (nếu muốn):

```
pip install -r requirements.txt
python app.py
```

## Cách dùng

1. Ô trái: chọn file EXE sẽ **chạy ngầm (bị ẩn)**
2. Ô phải: chọn file EXE **hiển thị giao diện** (app chính)
3. Đặt tên file output (tùy chọn) + icon .ico (tùy chọn)
4. Bấm **Ghép & Build EXE** → chờ 30–120 giây → **Tải file EXE**
5. Chạy file output: app ẩn chạy nền, app chính hiện cửa sổ — chỉ 1 cửa sổ duy nhất!

### Tùy chọn build

| Tùy chọn | Ý nghĩa |
|---|---|
| Tắt tiến trình ẩn khi app chính đóng | Khi bạn thoát app chính, tiến trình ẩn bị `taskkill /T /F` — không để process "ma" ngốn RAM |
| Ép ẩn cửa sổ liên tục | Nếu app ẩn "cố tình" mở lại cửa sổ, watcher sẽ ẩn lại ngay (quét mỗi 0.4 giây) |
| Icon | Gắn icon .ico vào file output |

## Cách hoạt động

1. Web UI nhận 2 file EXE, lưu vào thư mục tạm **trên chính máy bạn**
2. ExeFuse sinh file `launcher.py` từ template và gọi PyInstaller `--onefile --noconsole` để nhúng cả 2 EXE vào 1 file
3. Khi chạy file output:
   - Launcher giải nén 2 app vào `%TEMP%\_MEIxxxx`
   - App ẩn được khởi động với `STARTF_USESHOWWINDOW + SW_HIDE + CREATE_NO_WINDOW`
   - App chính khởi động bình thường
4. Watcher (WinAPI `EnumWindows`) quét cửa sổ theo PID của app ẩn, gọi `ShowWindow(SW_HIDE)` và thêm cờ `WS_EX_TOOLWINDOW` để cửa sổ không lọt vào Alt-Tab
5. Khi app chính đóng → dọn tiến trình ẩn (nếu bật tùy chọn)

## Lưu ý quan trọng

- **Build phải chạy trên Windows** để ra file `.exe` (PyInstaller không cross-compile). Trên Linux/macOS bạn vẫn test được UI nhưng output không phải exe.
- Vẫn có **2 dòng tiến trình** trong Task Manager — công cụ này gộp **cách khởi động + ẩn cửa sổ**, không gộp code của 2 app.
- Antivirus/SmartScreen có thể cảnh báo nhầm file PyInstaller onefile (đặc thù của mọi tool đóng gói Python) — nếu bạn tin nguồn gốc 2 app thì chỉ cần add exclusion.
- File output nặng ≈ tổng dung lượng 2 EXE + ~2 MB; lần chạy đầu chậm hơn một chút do giải nén.
- Đừng chọn app cần tương tác (nhập mật khẩu, bấm OK...) làm **app ẩn** — cửa sổ bị ẩn thì bạn không bấm được.
- Nếu app ẩn spawn tiến trình con có cửa sổ riêng, watcher (quét theo PID chính) có thể không ẩn được cửa sổ con đó.

## Cấu trúc dự án

```
exefuse/
├── app.py                      # Flask web server + API (build, status, download)
├── builder/
│   ├── build.py                # Điều phối PyInstaller, quản lý job build
│   └── launcher_template.py    # Launcher runtime: chạy 1 app ẩn + 1 app hiện
├── templates/
│   └── index.html              # Web UI (kéo thả, log trực tiếp, tải kết quả)
├── requirements.txt
├── run.bat                     # Chạy 1 click trên Windows
└── README.md
```

## Yêu cầu hệ thống

- **Máy build:** Windows 10/11 + Python 3.10+ (hoặc Linux/macOS để test UI)
- **Máy chạy file output:** Windows 7+ (không cần cài gì thêm)

## License

MIT
