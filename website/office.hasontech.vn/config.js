/* Cấu hình DUY NHẤT cho bản phát hành phía giao diện.
 * URL GitHub chỉ nằm trong .htaccess; giữ nguyên các đường dẫn /tai/*.
 * HTML là bản dự phòng không JS của bản phát hành hiện tại.
 */
window.HST_OFFICE_CONFIG = {
  version: "1.0.1",
  releaseLabel: "Bản chính thức",
  tag: "v1.0.1",
  platforms: {
    windows: { available: true, path: "/tai/windows", label: "Windows" },
    "macos-arm": { available: true, path: "/tai/macos-arm", label: "macOS Apple Silicon" },
    "macos-intel": { available: true, path: "/tai/macos-intel", label: "macOS Intel" },
    linux: { available: true, path: "/tai/linux", label: "Linux" },
    /* Từ 1.0.2: bật (available: true) khi tai/1.0.2/ đã có .rpm và .AppImage, cùng lúc đổi tag các dòng /tai/* trong .htaccess. */
    "linux-rpm": { available: false, path: "/tai/linux-rpm", label: "Linux (.rpm)" },
    "linux-appimage": { available: false, path: "/tai/linux-appimage", label: "Linux (AppImage)" }
  },
  checksum: { available: true, path: "/tai/sha256" },
  linuxArchive: "HSTOffice_1.0.1_Linux_x86-64.deb"
};

/* Khi ra bản mới:
 * Đổi tag ở trên, cập nhật nhãn phiên bản trong index.html (bản dự phòng không JS).
 * Đổi tag trong các RewriteRule /tai/* của .htaccess và thay tệp tai/SHA256SUMS.
 * Không đổi /tai/windows, /tai/macos-arm, /tai/macos-intel, /tai/linux, /tai/linux-rpm, /tai/linux-appimage, /tai/sha256.
 */
