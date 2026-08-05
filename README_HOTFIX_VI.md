# ATLAS — HOME Summary Top + Flow Contract Restore

## Đã sửa

### HOME
- Dòng Market Summary màu xanh được chuyển lên ngay dưới tiêu đề HOME.
- Nó xuất hiện trước Option Shortlist và Top Opportunities.
- Xóa bản lặp lại ở cuối HOME.

### FLOW RADAR
- Retry option-chain 2 lần cho nhóm Primary.
- Retry option-chain 2 lần cho nhóm Fallback.
- Nới bộ lọc vừa phải để Yahoo extended-hours không làm mất toàn bộ contract:
  - spread tối đa 55%
  - OI tối thiểu 5
  - premium proxy tối thiểu $10,000
- Quét tối đa 4 expiration và 3 contract mỗi phía.
- Nếu Yahoo tạm thời trả rỗng, ATLAS giữ lại Flow Radar hợp lệ của snapshot trước,
  thay vì ghi đè thành Contracts found = 0.

## File cần upload

1. `app.py`
2. `background_scan.py`
3. `option_flow_radar.py`

Upload vào thư mục gốc GitHub ATLAS và Replace file cũ.

## Sau khi upload

1. Commit vào `main`.
2. Chạy GitHub Action thủ công một lần.
3. Trên máy local, copy cùng 3 file rồi khởi động lại worker để worker dùng logic mới.
