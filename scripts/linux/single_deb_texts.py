# SPDX-License-Identifier: AGPL-3.0-only
"""Texts that scripts/linux/make-single-deb.py writes into the single HST Office .deb: the package
description, the DEP-5 copyright file, lintian overrides, the postrm cleanup and the AppStream metainfo."""

DESCRIPTION = """\
Description: Bộ ứng dụng văn phòng HST Office của HASON TECH
 HST Office gồm Writer (văn bản), Sheets (bảng tính), Slides (trình chiếu),
 Draw, Math và Base, giao diện tiếng Việt.
 Đọc và ghi ODF, DOCX, XLSX, PPTX, PDF.
 .
 Gói duy nhất này chứa toàn bộ ứng dụng, từ điển, biểu tượng, lối tắt trong
 menu ứng dụng và liên kết loại tệp. Cài trong /opt/hst-office1.0 và có thể
 cài cùng bản LibreOffice của bản phân phối.
 .
 Xây dựng từ LibreOffice của The Document Foundation. © 2026 HASON TECH."""

COPYRIGHT = """\
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: HST Office
Upstream-Contact: HASON TECH <lienhe@hasontech.vn>
Source: https://github.com/haduyson/hst-office

Files: *
Copyright: 2000-2026 The Document Foundation and LibreOffice contributors
License: MPL-2.0
 This Source Code Form is subject to the terms of the Mozilla Public License,
 v. 2.0. The full text and the licences of bundled third-party components are in
 /opt/hst-office1.0/LICENSE and /opt/hst-office1.0/LICENSE.html. On Debian systems
 the MPL-2.0 text is also in /usr/share/common-licenses/MPL-2.0.

Files: opt/hst-office1.0/share/extensions/hst-*
Copyright: 2026 HASON TECH
License: AGPL-3.0-only
 On Debian systems the full text is in /usr/share/common-licenses/AGPL-3
 (or at https://www.gnu.org/licenses/agpl-3.0.html).
"""

# Intentional departures from Debian policy, same as upstream LibreOffice packaging:
# the suite lives under /opt (no distro file collision, coexists with the distro
# LibreOffice) and ships its own libraries and executable-bit shared objects.
LINTIAN_OVERRIDES = """\
hst-office: dir-or-file-in-opt
hst-office: embedded-library
hst-office: shared-library-is-executable
"""

# Appended to the desktop-integration postrm. The install root belongs to this package
# alone; what dpkg cannot know about (runtime caches, a configuration file kept by a
# replaced split package in "config-files" state) would otherwise survive a removal.
POSTRM_CLEANUP = """\
# HST Office: remove the install root's leftovers (see make-single-deb.py).
if [ "$1" = purge ] || { [ "$1" = remove ] && [ -z "${2:-}" ]; }; then
  rm -rf __ROOT__
fi
exit 0
"""

METAINFO = """\
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>vn.hasontech.hstoffice</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MPL-2.0 AND AGPL-3.0-only</project_license>
  <name>HST Office</name>
  <developer id="vn.hasontech"><name>HASON TECH</name></developer>
  <summary>Bộ ứng dụng văn phòng: văn bản, bảng tính, trình chiếu</summary>
  <description>
    <p>HST Office là bộ ứng dụng văn phòng miễn phí của HASON TECH với giao diện tiếng Việt: Writer (văn bản), Sheets (bảng tính), Slides (trình chiếu), Draw, Math và Base.</p>
    <p>Đọc và ghi ODF, DOCX, XLSX, PPTX và PDF.</p>
  </description>
  <launchable type="desktop-id">vn.hasontech.hstoffice-startcenter.desktop</launchable>
  <icon type="stock">vn.hasontech.hstoffice-startcenter</icon>
  <url type="homepage">https://office.hasontech.vn</url>
  <content_rating type="oars-1.1"/>
  <categories><category>Office</category></categories>
  <provides><binary>hst-office</binary></provides>
  <releases><release version="{version}" date="{date}"{kind}/></releases>
</component>
"""
