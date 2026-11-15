# SPDX-License-Identifier: AGPL-3.0-only
"""Generated Vietnamese-like words for the synthetic large-file fixtures (no user data)."""

WORDS = ("công ty", "hóa đơn", "khách hàng", "số lượng", "đơn giá", "thành tiền", "ngày", "tháng", "năm", "báo cáo",
         "doanh thu", "chi phí", "hợp đồng", "thanh toán", "nhân viên", "phòng ban", "kế toán", "tổng cộng", "ghi chú",
         "Hà Nội", "Đà Nẵng", "Hồ Chí Minh", "vật tư", "kho", "nhập", "xuất", "tồn", "mã hàng", "đơn vị", "chiếc")


def sentence(rnd, n):
    return " ".join(rnd.choice(WORDS) for _ in range(n)).capitalize()


def col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s
