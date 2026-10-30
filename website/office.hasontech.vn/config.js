/* Cấu hình DUY NHẤT cho bản phát hành phía giao diện.
 * URL GitHub chỉ nằm trong .htaccess; giữ nguyên các đường dẫn /tai/*.
 * HTML là bản dự phòng không JS của bản phát hành hiện tại.
 */
window.HST_OFFICE_CONFIG = {
  version: "1.0.0",
  releaseLabel: "Bản thử nghiệm (beta)",
  tag: "v1.0.0-beta.1",
  platforms: {
    windows: { available: true, path: "/tai/windows", label: "Windows" },
    "macos-arm": { available: false, path: "/tai/macos-arm", label: "macOS Apple Silicon" },
    "macos-intel": { available: false, path: "/tai/macos-intel", label: "macOS Intel" },
    linux: { available: true, path: "/tai/linux", label: "Linux" }
  },
  checksum: { available: true, path: "/tai/sha256" },
  linuxArchive: "HSTOffice_1.0.0_Linux_x86-64_deb.tar.gz"
};

/* Khi v1.0.0-beta.2 đã được phát hành:
 * tag: "v1.0.0-beta.2"
 * Bật available: true cho macos-arm và macos-intel sau khi kiểm tra file.
 * Các RewriteRule beta.2 và tên file .dmg đã ghi sẵn trong .htaccess.
 * Không đổi /tai/windows, /tai/macos-arm, /tai/macos-intel, /tai/linux, /tai/sha256.
 */
