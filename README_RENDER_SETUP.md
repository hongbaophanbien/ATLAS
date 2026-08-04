
# ATLAS — Render Worker 60 giây

## File cần upload lên GitHub

1. `worker_60s.py`
2. `render.yaml`

Đặt cả hai ở thư mục gốc, cùng cấp với:

- `app.py`
- `background_scan.py`
- `requirements.txt`

Nếu repository đã có `render.yaml`, thay file cũ bằng file trong gói này.

## Tạo Background Worker trên Render

1. Đăng nhập Render.
2. Chọn **New → Blueprint**.
3. Kết nối GitHub và chọn repository `ATLAS`.
4. Render đọc `render.yaml`.
5. Xác nhận tạo service `atlas-60s-worker`.
6. Chọn gói **Starter**. Background Worker không hỗ trợ gói Free.
7. Nhập các biến bí mật khi Render yêu cầu:

- `SUPABASE_URL` = URL Supabase không có `/rest/v1/`
- `SUPABASE_KEY` = backend secret key đang hoạt động trên GitHub
- `SUPABASE_WRITE_KEY` = backend secret key
- `ATLAS_INTERVAL_SECONDS` đã đặt sẵn là `60`

## Dấu hiệu chạy đúng trong Logs

```text
[worker] ATLAS 60s worker online
[worker] Starting ATLAS scan
[worker] Scan finished with exit code 0
[worker] Next scan in ...
```

Worker dùng chu kỳ **start-to-start 60 giây**. Ví dụ scan mất 29 giây thì worker chờ khoảng 31 giây rồi bắt đầu scan kế tiếp.

## Sau khi Render chạy ổn

Giữ GitHub Actions làm backup 5 phút. Không xóa workflow hiện tại.
