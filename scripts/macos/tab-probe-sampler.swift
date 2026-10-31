// SPDX-License-Identifier: AGPL-3.0-only
// Samples window state of one process at ~50 Hz for macOS tab-switch diagnosis.
//   tab-probe-sampler <pid> <seconds> > samples.csv
// Columns: t_ms, frontmost_pid, n_onscreen, n_fullscreen, windows
//   windows = "id:x,y,wxh" of the pid's normal-layer windows that are on screen (kCGWindowIsOnscreen).
// n_fullscreen counts on-screen windows that cover a whole display (native full screen or maximized).
import AppKit
import CoreGraphics

let args = CommandLine.arguments
guard args.count >= 3, let pid = Int32(args[1]), let seconds = Double(args[2]) else {
    FileHandle.standardError.write("usage: tab-probe-sampler <pid> <seconds>\n".data(using: .utf8)!)
    exit(64)
}
let displays = NSScreen.screens.map { $0.frame }
let start = Date()
print("t_ms,frontmost_pid,n_onscreen,n_fullscreen,windows")
while Date().timeIntervalSince(start) < seconds {
    let t = Int(Date().timeIntervalSince(start) * 1000)
    let front = NSWorkspace.shared.frontmostApplication?.processIdentifier ?? -1
    let info = (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]]) ?? []
    var parts: [String] = []
    var full = 0
    for w in info {
        guard (w[kCGWindowOwnerPID as String] as? Int32) == pid,
              (w[kCGWindowLayer as String] as? Int) == 0,
              let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
        let rect = CGRect(x: b["X"] ?? 0, y: b["Y"] ?? 0, width: b["Width"] ?? 0, height: b["Height"] ?? 0)
        if rect.width < 200 || rect.height < 150 { continue }
        let id = w[kCGWindowNumber as String] as? Int ?? 0
        parts.append("\(id):\(Int(rect.minX)),\(Int(rect.minY)),\(Int(rect.width))x\(Int(rect.height))")
        if displays.contains(where: { abs($0.width - rect.width) < 2 && rect.height >= $0.height - 1 }) { full += 1 }
    }
    print("\(t),\(front),\(parts.count),\(full),\(parts.joined(separator: "|"))")
    fflush(stdout)
    usleep(20_000)
}
