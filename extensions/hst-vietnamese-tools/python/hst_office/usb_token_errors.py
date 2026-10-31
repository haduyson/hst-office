# SPDX-License-Identifier: AGPL-3.0-only
"""Only explicitly authored Vietnamese messages may reach the setup dialog."""
import configparser


class SetupError(ValueError):
    """An intentionally user-facing Vietnamese explanation."""


class RecoveryError(SetupError):
    """Keep the recovery copy if storage also refuses rollback."""


def vietnamese_error(exc):
    if isinstance(exc, SetupError):
        return str(exc)
    if isinstance(exc, PermissionError):
        return "Không có quyền ghi kho chứng thư. Hãy chọn kho thuộc tài khoản đang sử dụng."
    if isinstance(exc, BlockingIOError):
        return "Kho chứng thư đang được sử dụng. Đóng ứng dụng dùng kho rồi thử lại."
    if isinstance(exc, configparser.Error):
        return "Cấu hình kho chứng thư không hợp lệ. Hãy kiểm tra lại cấu hình hồ sơ trình duyệt."
    if isinstance(exc, OSError):
        return "Không thể đọc hoặc ghi kho chứng thư. Kiểm tra quyền truy cập và dung lượng đĩa rồi thử lại."
    return "Không thể hoàn tất thiết lập USB Token. Đóng ứng dụng dùng token rồi thử lại."
