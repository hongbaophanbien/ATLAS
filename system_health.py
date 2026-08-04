from __future__ import annotations
import pandas as pd

def health_report(data_online, scan, signals, contracts, scan_time):
    scanned = 0 if scan is None else len(scan)
    signal_count = 0 if signals is None else len(signals)
    contract_count = 0 if contracts is None else len(contracts)
    return [
        {
            "Status": "READY" if data_online else "STOP",
            "Area": "Dữ liệu thị trường",
            "Meaning": "Giá và volume đang tải được." if data_online else "Không có dữ liệu online; tín hiệu không đáng tin.",
            "Action": "Có thể tiếp tục." if data_online else "Không vào lệnh; refresh sau.",
        },
        {
            "Status": "READY" if scanned >= 8 else "LIMITED",
            "Area": "Phạm vi quét",
            "Meaning": f"ATLAS đã phân tích {scanned} mã.",
            "Action": "Đủ để so sánh setup." if scanned >= 8 else "Chạy lại scan hoặc thêm ticker.",
        },
        {
            "Status": "READY" if signal_count > 0 else "NO TRADE",
            "Area": "Tín hiệu",
            "Meaning": f"Có {signal_count} mã vượt bộ lọc." if signal_count > 0 else "Không có mã đủ chuẩn; đây không phải lỗi.",
            "Action": "Chỉ xem các mã đang hiện." if signal_count > 0 else "Không ép giao dịch.",
        },
        {
            "Status": "READY" if contract_count > 0 else "CHECK",
            "Area": "Option chain",
            "Meaning": f"Đã shortlist {contract_count} contract." if contract_count > 0 else "Chưa tìm được contract đủ thanh khoản/ngân sách.",
            "Action": "Xác nhận bid/ask live trên Robinhood." if contract_count > 0 else "Không mua OTM xa chỉ vì rẻ.",
        },
        {
            "Status": "READY" if scan_time and scan_time != "Never" else "STALE",
            "Area": "Độ mới",
            "Meaning": f"Lần quét gần nhất: {scan_time or 'Never'}.",
            "Action": "Quét lại nếu market vừa gap, mất VWAP hoặc sector xoay.",
        },
    ]
