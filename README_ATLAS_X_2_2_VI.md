# ATLAS X 2.2 — Session Price + Unified Trade Plan

## Thay đổi chính

### 1. Gộp Signal Fusion và Trade Plan
- Chỉ còn một tab `Trade Plan`.
- Giữ toàn bộ phần xác nhận của Signal Fusion.
- Hiển thị kế hoạch cụ thể: Entry, Trigger, Stop, TP1, TP2, Stretch và Plan A/B/C.

### 2. Money In / Money Out
- Làm nổi bật hai ô Money In và Money Out.
- Không thêm Net Flow vào Trade Plan.

### 3. Horizon mới
- Thêm `Swing 2–3 tháng`.
- Dùng lookback và ATR target rộng hơn so với swing ngắn.

### 4. Session-aware Price
ATLAS thử lấy giá mới nhất theo:
- PRE-MARKET
- REGULAR MARKET
- AFTER-HOURS
- OVERNIGHT

Mỗi plan hiển thị:
- Price Used
- Session
- Updated
- Fresh/Stale status

### 5. Quy tắc an toàn
- Regular: quá 2 phút → stale
- Pre-market/After-hours: quá 3 phút → stale
- Overnight: quá 5 phút → stale
- Khi stale, ATLAS hiện `PRICE STALE — KHÔNG PHÁT PLAN MỚI`.

## Giới hạn nguồn miễn phí

Yahoo thường hỗ trợ regular, pre-market và after-hours. Yahoo không đảm bảo
tape overnight đầy đủ như broker. Vì vậy ATLAS không giả lập giá overnight:
nếu không có timestamp đủ mới, hệ thống đánh dấu stale thay vì dùng giá cũ.

## Cách cập nhật GitHub

Upload các file sau vào repository và thay thế file cũ:
- app.py
- data_provider.py
- atlas_brain.py
- trade_plan_engine.py
- background_scan.py

Sau đó commit vào `main`.

## Cách cập nhật máy local

Copy 5 file trên vào thư mục ATLAS local, chọn Replace. Sau đó:
1. Dừng worker bằng Ctrl+C.
2. Chạy RUN_ONE_SCAN_TEST.bat.
3. Nếu thành công, chạy START_ATLAS_WORKER.bat.
