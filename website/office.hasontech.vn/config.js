/* Cấu hình DUY NHẤT cho bản phát hành phía giao diện.
 * URL GitHub chỉ nằm trong .htaccess; giữ nguyên các đường dẫn /tai/*.
 * HTML là bản dự phòng không JS của bản phát hành hiện tại.
 */
window.HST_OFFICE_CONFIG = {
  version: "1.0.0",
  releaseLabel: "Bản thử nghiệm (beta)",
  tag: "v1.0.0-beta.2",
  platforms: {
    windows: { available: true, path: "/tai/windows", label: "Windows" },
    "macos-arm": { available: true, path: "/tai/macos-arm", label: "macOS Apple Silicon" },
    "macos-intel": { available: true, path: "/tai/macos-intel", label: "macOS Intel" },
    linux: { available: true, path: "/tai/linux", label: "Linux" }
  },
  checksum: { available: true, path: "/tai/sha256" },
  linuxArchive: "HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz"
};

/* Khi ra bản mới:
 * Đổi tag ở trên, cập nhật nhãn phiên bản trong index.html (bản dự phòng không JS).
 * Đổi tag trong các RewriteRule /tai/* của .htaccess và thay tệp tai/SHA256SUMS.
 * Không đổi /tai/windows, /tai/macos-arm, /tai/macos-intel, /tai/linux, /tai/sha256.
 */
