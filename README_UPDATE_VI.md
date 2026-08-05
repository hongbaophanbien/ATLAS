# ATLAS Flow Radar — Classic Grouped Restore

Bản này phục hồi Flow Radar giống hình mẫu:

- Hiển thị từng contract riêng biệt.
- Các contract cùng ticker nằm liền nhau.
- Ticker chỉ hiện ở dòng đầu của mỗi nhóm.
- Trong mỗi ticker, Flow Score cao nhất đứng trước.
- Giữ các cột:
  - Ticker
  - Side
  - Contract
  - Flow Score
  - Alignment
  - Chart Bias
  - Overnight %
  - Overnight Bias
  - Overnight Confirm
  - Gap Risk
  - Premium Proxy
  - Volume
  - OI
  - Vol/OI
  - Spread %
  - IV %
  - Delta
  - DTE
  - Moneyness %
  - Interpretation
  - Trigger
  - Invalidation
  - Execution
- Không hiển thị Source.
- Giữ logic retry và khôi phục contract từ snapshot trước nếu Yahoo tạm thời trả rỗng.

## Cập nhật

Upload và thay thế 3 file trong thư mục gốc GitHub ATLAS:

1. app.py
2. background_scan.py
3. option_flow_radar.py

Sau đó commit vào main và chạy GitHub Action thủ công một lần.

Trên máy local, copy cùng 3 file và khởi động lại worker.
