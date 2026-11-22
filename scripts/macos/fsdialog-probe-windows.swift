// SPDX-License-Identifier: AGPL-3.0-only
// Lists every window of one process (on screen or not) as JSON lines, for the modal-dialog probe.
//   modal-probe-windows <pid>
import AppKit
import CoreGraphics

guard CommandLine.arguments.count >= 2, let pid = Int32(CommandLine.arguments[1]) else { exit(64) }
let info = (CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]]) ?? []
for w in info {
    guard (w[kCGWindowOwnerPID as String] as? Int32) == pid else { continue }
    let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
    let row: [String: Any] = [
        "id": w[kCGWindowNumber as String] as? Int ?? 0,
        "name": w[kCGWindowName as String] as? String ?? "",
        "layer": w[kCGWindowLayer as String] as? Int ?? 0,
        "onscreen": (w[kCGWindowIsOnscreen as String] as? Bool) ?? false,
        "alpha": w[kCGWindowAlpha as String] as? Double ?? 0,
        "x": Int(b["X"] ?? 0), "y": Int(b["Y"] ?? 0), "w": Int(b["Width"] ?? 0), "h": Int(b["Height"] ?? 0),
    ]
    if let data = try? JSONSerialization.data(withJSONObject: row), let s = String(data: data, encoding: .utf8) {
        print(s)
    }
}
