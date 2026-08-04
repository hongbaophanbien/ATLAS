# ATLAS X 2.1 — BẢN ĐỒNG BỘ GITHUB + MÁY WINDOWS

Gói này dùng cho cả hai việc:

1. Upload toàn bộ nội dung lên GitHub.
2. Giải nén trên máy Windows để chạy worker cập nhật snapshot mỗi 60 giây.

## A. Upload GitHub

Upload tất cả file và thư mục trong gói này vào thư mục gốc repository `ATLAS`.

Không upload các file sau nếu chúng xuất hiện sau khi bạn chạy trên máy:

- `.venv`
- `atlas_local_secrets.bat`
- `__pycache__`

File `.gitignore` đã được thêm để giúp ngăn upload nhầm.

## B. Chạy local worker trên Windows

### Lần đầu tiên

1. Giải nén gói vào một thư mục dễ tìm, ví dụ:
   `C:\ATLAS`
2. Nhấp đúp `INSTALL_ONCE.bat`.
3. Đợi đến khi thấy `INSTALLATION COMPLETE`.
4. Copy `atlas_local_secrets_TEMPLATE.bat`.
5. Đổi tên bản copy thành:
   `atlas_local_secrets.bat`
6. Mở file đó bằng Notepad và điền:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_WRITE_KEY`

Không đăng file `atlas_local_secrets.bat` lên GitHub công khai.

### Chạy mỗi ngày

Nhấp đúp:

`START_ATLAS_WORKER.bat`

Giữ cửa sổ đó mở. Máy phải bật, có Internet và không được Sleep.

### Kiểm tra một lần trước

Có thể nhấp đúp:

`RUN_ONE_SCAN_TEST.bat`

Nếu kết thúc không có lỗi và Supabase `updated_at` thay đổi, cấu hình đã đúng.

## C. Những thay đổi có trong bản này

- Bản đầy đủ ATLAS X 2.1.
- FAST PICKS Decision và Option Signal đã được nối với hotfix mới.
- Worker local chu kỳ 60 giây.
- Xóa tab Journal.
- Giữ GitHub Actions làm backup.
- Giữ các module Home, Fast Picks, ATLAS Bot, Rotation, Theme Rooms,
  Signal Fusion, Trade Plan, CALL/PUT, Flow Radar, Watch Engine,
  AI Semi, System Health và Earnings 14D.
