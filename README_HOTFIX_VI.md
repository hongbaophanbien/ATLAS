# ATLAS Flow Radar Tab Index Hotfix

## Nguyên nhân

Sau khi gộp `Signal Fusion` và `Trade Plan`, việc giảm số thứ tự tab đã bị áp dụng lặp.
Kết quả là nhiều module cùng bị gán vào `tabs[7]`:

- FLOW RADAR
- Watch Engine
- AI SEMI ONLY
- System Health
- Earnings 14D

Vì vậy toàn bộ nội dung bị dồn vào FLOW RADAR.

## Đã sửa

Khôi phục đúng thứ tự:

0. HOME
1. FAST PICKS
2. ATLAS BOT
3. Sector Rotation
4. Theme Rooms
5. Trade Plan
6. Top CALL / PUT
7. FLOW RADAR
8. Watch Engine
9. AI SEMI ONLY
10. System Health
11. Earnings 14D

## Cập nhật

Chỉ cần upload và thay thế `app.py` trong thư mục gốc GitHub ATLAS, rồi commit vào `main`.

Worker 60 giây không cần khởi động lại.
