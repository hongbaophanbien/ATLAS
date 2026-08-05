# ATLAS Trade Plan — Single Panel Update

## Thay đổi

- Gộp hai khung trong Trade Plan thành **một khung duy nhất**.
- Phần Signal Fusion nằm trên cùng bên trong cùng một panel.
- Phần kế hoạch cụ thể nằm ngay bên dưới:
  - Price Used / Session / Updated
  - Money In / Money Out
  - Trend Score / Entry Score
  - Entry / Trigger / Stop
  - TP1 / TP2 / Stretch
  - Plan A / B / C
- Giữ nguyên toàn bộ thông tin, chỉ bỏ khoảng trống và viền tách đôi.

## Cách cập nhật

Upload và thay thế 3 file:
- `app.py`
- `trade_plan_engine.py`
- `signal_brain.py`

Sau đó commit vào branch `main`.

Để đồng bộ máy local, copy cùng 3 file vào thư mục ATLAS trên máy.
Worker không cần khởi động lại vì đây chủ yếu là thay đổi giao diện Trade Plan.
