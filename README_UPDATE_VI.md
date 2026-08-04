# ATLAS Flow Radar — Grouped Tickers Update

## Thay đổi

- Bỏ cột `Source` khỏi bảng Flow Radar.
- Giữ nguyên toàn bộ các cột còn lại.
- Giữ nguyên từng contract riêng lẻ.
- Sắp xếp các contract cùng ticker nằm cạnh nhau.
- Tên ticker chỉ hiển thị ở dòng đầu của mỗi nhóm để NVDA, SPY, AVGO, CRM... dễ đọc hơn.
- Trong mỗi ticker, contract có Flow Score cao hơn nằm trước.

## Cách upload

1. Giải nén ZIP.
2. Upload `app.py` vào thư mục gốc repository GitHub `ATLAS`.
3. Chọn thay thế file cũ.
4. Commit vào branch `main`.
5. Đợi Streamlit redeploy.

Có thể copy cùng `app.py` vào thư mục ATLAS trên máy để đồng bộ source.
Worker 60 giây không cần khởi động lại vì thay đổi này chỉ liên quan giao diện.
