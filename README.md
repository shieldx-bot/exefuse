# ExeFuse — Gộp 2 file EXE thành 1 file duy nhất

> Một app chạy **ngầm (ẩn cửa sổ)**, một app **hiển thị giao diện** — tất cả trong **1 file .exe** duy nhất.
> Không còn cảnh 2 cửa sổ cùng bật lên lúc khởi động, chỉ hiện đúng cửa sổ bạn cần.

## Tính năng

- Web UI chạy local (Flask) — kéo thả 2 file EXE, bấm build là xong
- Xuất **1 file .exe duy nhất**, chạy được trên máy **không cần cài Python**
- App ẩn: không cửa sổ, không taskbar, không Alt-Tab (`SW_HIDE` + `CREATE_NO_WINDOW` + watcher ép ẩn liên tục)
- **Auto-token Traffmonetizer**: dán token 1 lần — file exe khi chạy tự đăng nhập + tự kết nối, không cần nhập tay (đã reverse-engineer binary để xác định chính xác file settings)
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

### Bước 0 — Đặt app ẩn mặc định (Traffmonetizer.exe)

Tool đã được cấu hình sẵn: **Traffmonetizer.exe là file chạy ngầm mặc định** (chạy hoàn toàn không có cửa sổ).

- Copy `Traffmonetizer.exe` vào thư mục `defaults/` trong repo (bên cạnh `app.py`), hoặc
- Đặt `Traffmonetizer.exe` cạnh `run.bat` rồi chạy **`setup_default.bat`** một lần
- Web UI sẽ tự nhận: thấy dòng xanh **"App ẩn mặc định: Traffmonetizer.exe (3.0 MB)"** là OK
- Lần build sau **không cần chọn lại file ẩn** nữa — chỉ cần chọn app hiển thị (nếu có)
- Muốn dùng app ẩn khác? Chọn/kéo thả file .exe vào ô 1 là tự động thay thế

### Bước 1 — Build

1. Ô trái: file EXE sẽ **chạy ngầm (bị ẩn)** — mặc định tự dùng `defaults/Traffmonetizer.exe`
2. Ô phải: file EXE **hiển thị giao diện** (app chính) — hoặc bật **"Chỉ chạy app ẩn"** nếu không cần app hiển thị
3. Đặt tên file output (tùy chọn) + icon .ico (tùy chọn)
4. Bấm **Ghép & Build EXE** → chờ 30–120 giây → **Tải file EXE**
5. Chạy file output: app ẩn chạy nền **không một cửa sổ nào**, app chính hiện cửa sổ — chỉ 1 cửa sổ duy nhất!

### Token Traffmonetizer tự động (auto-login + auto-connect)

ExeFuse đã phân tích trực tiếp binary Traffmonetizer (IL disassembly) và xác định:

- App lưu cấu hình tại **`%APPDATA%\traffmonetizer\settings.json`**
- Schema JSON (DataContractJsonSerializer): `Token`, `Accepting`, `StartWithWindows`
- App đọc file này lúc khởi động: có `Token` → **bỏ qua màn hình đăng nhập**; `Accepting: true` → **tự động chấp nhận chia sẻ traffic (tự kết nối)**

Cách dùng:

1. Dán application token (lấy từ dashboard Traffmonetizer) vào ô **"Token Traffmonetizer"**
2. Tick **"Ghi nhớ token trên máy này"** để không phải dán lại lần sau (lưu localStorage)
3. Build — token được nhúng vào launcher; khi chạy file exe:
   - Launcher ghi `settings.json` với Token + `Accepting: true` (nếu file đã tồn tại sẽ giữ lại các giá trị khác)
   - App Traffmonetizer khởi động im lặng (không truyền `/show`) → chạy nền, tự đăng nhập, tự kết nối
4. Tùy chọn **"Cho phép app tự chạy cùng Windows"** mặc định TẮT — vì app chạy từ thư mục tạm của bundle, nếu bật autorun registry sẽ trỏ vào path tạm đã bị xóa (không hợp lệ)

> Bảo mật: token được nhúng thẳng vào file exe. **Không chia sẻ file exe đã build** — ai có file đều dùng được tài khoản Traffmonetizer của bạn. Muốn thu hồi, đổi token trong dashboard.

### Chế độ SOLO (chỉ chạy app ẩn)

Không cần app hiển thị? Bật **"Chỉ chạy app ẩn — không cần app hiển thị"**: file output sẽ chỉ nhúng và chạy duy nhất app ẩn (vd: Traffmonetizer chạy nền vô hình, không mở gì cả). File output nhẹ hơn, launcher tự thoát khi app ẩn kết thúc.

### Tùy chọn build

| Tùy chọn | Ý nghĩa |
|---|---|
| Tắt tiến trình ẩn khi app chính đóng | Khi bạn thoát app chính, tiến trình ẩn bị `taskkill /T /F` — không để process "ma" ngốn RAM |
| Ép ẩn cửa sổ liên tục | Nếu app ẩn "cố tình" mở lại cửa sổ, watcher sẽ ẩn lại ngay (quét mỗi 0.4 giây) |
| Chỉ chạy app ẩn | Chế độ SOLO: file output chỉ chạy app ẩn, không cần app hiển thị |
| Icon | Gắn icon .ico vào file output |

> Lưu ý với Traffmonetizer: cửa sổ chính sẽ bị ẩn hoàn toàn, nhưng **icon khay hệ thống (system tray)** của nó vẫn có thể xuất hiện — đây là giới hạn của Windows, icon tray không thuộc cửa sổ nào để ẩn.

## Cách hoạt động

1. Web UI nhận file EXE (upload hoặc mặc định từ `defaults/`), lưu vào thư mục tạm **trên chính máy bạn**
2. ExeFuse sinh file `launcher.py` từ template và gọi PyInstaller `--onefile --noconsole` để nhúng vào 1 file
3. Khi chạy file output:
   - (Nếu bật auto-token) Launcher ghi Token vào `%APPDATA%\traffmonetizer\settings.json`
   - Launcher giải nén app vào `%TEMP%\_MEIxxxx`
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
├── defaults/                   # Đặt Traffmonetizer.exe vào đây (app ẩn mặc định)
│   └── README.txt
├── setup_default.bat           # Copy Traffmonetizer.exe vào defaults/ tự động
├── requirements.txt
├── run.bat                     # Chạy 1 click trên Windows
└── README.md
```

> **Vì sao `Traffmonetizer.exe` không có sẵn trong repo?** Đó là phần mềm của bên thứ ba, không thể re-host công khai. Hãy tự tải từ trang chủ Traffmonetizer và đặt vào `defaults/`.

## Yêu cầu hệ thống

- **Máy build:** Windows 10/11 + Python 3.10+ (hoặc Linux/macOS để test UI)
- **Máy chạy file output:** Windows 7+ (không cần cài gì thêm)

## License

MIT
