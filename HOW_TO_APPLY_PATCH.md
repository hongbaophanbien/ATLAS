
# ATLAS X 2.1 — Signal + 60s UI refresh patch

1. Upload `atlas_signal_refresh_hotfix.py` vào thư mục gốc GitHub.

2. Trong `app.py`, thêm:
```python
from atlas_signal_refresh_hotfix import (
    apply_decisions,
    fill_option_signals,
    snapshot_health,
    format_snapshot_age,
    compact_numbers,
)
```

3. Ngay sau `st.set_page_config(...)`, thêm:
```python
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60_000, key="atlas_60s_refresh")
except Exception:
    pass
```

4. Sau khi tạo Fast Picks/opportunities:
```python
opportunities = apply_decisions(opportunities)
st.session_state["opportunities"] = opportunities
```

5. Trước khi hiển thị Option Shortlist:
```python
option_shortlist = fill_option_signals(
    option_shortlist,
    st.session_state.get("opportunities", pd.DataFrame()),
)
option_shortlist = compact_numbers(option_shortlist)
```

6. Sửa System Health:
```python
updated_at = payload.get("_snapshot_updated_at_") or payload.get("updated_at")
health = snapshot_health(updated_at)

st.metric("Snapshot", health.label)
st.caption(format_snapshot_age(updated_at))

if health.label == "FRESH":
    st.success("Snapshot đang mới. iPhone có thể dùng dữ liệu đã tính sẵn.")
elif health.label == "WARNING":
    st.warning("Snapshot đang chậm hơn mục tiêu 60 giây.")
else:
    st.error("Snapshot đã quá 5 phút. Không dùng Flow/Overnight để vào lệnh.")
```

7. Thêm vào `requirements.txt`:
```text
streamlit-autorefresh>=1.0.1,<2
```

Lưu ý: patch này làm UI tự đọc lại mỗi 60 giây. GitHub Actions hiện vẫn tạo snapshot khoảng mỗi 5 phút. Render Worker sẽ là bước sau để dữ liệu nguồn thật sự cập nhật mỗi 60 giây.
