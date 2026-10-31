// SPDX-License-Identifier: AGPL-3.0-only
// Samples the on-screen windows of the HST Office process(es) at 20 Hz for start-up timing.
//   startup-probe-sampler <seconds> > samples.csv
// Columns: epoch_ms, windows ("WxH" of every on-screen normal-layer window owned by a soffice/HST Office
// process, larger than 150x100 points, sorted, joined by "|").
import CoreGraphics
import Foundation

guard CommandLine.arguments.count >= 2, let seconds = Double(CommandLine.arguments[1]) else {
    FileHandle.standardError.write("usage: startup-probe-sampler <seconds>\n".data(using: .utf8)!)
    exit(64)
}
setvbuf(stdout, nil, _IOLBF, 0)  // line-buffered: the probe script reads the file while it grows
let start = Date()
print("epoch_ms,windows")
while Date().timeIntervalSince(start) < seconds {
    let now = Int(Date().timeIntervalSince1970 * 1000)
    let info = (CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]]) ?? []
    var sizes: [String] = []
    for w in info {
        let owner = (w[kCGWindowOwnerName as String] as? String) ?? ""
        guard owner.contains("soffice") || owner.contains("HST Office"),
              (w[kCGWindowLayer as String] as? Int) == 0,
              let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
        let width = Int(b["Width"] ?? 0), height = Int(b["Height"] ?? 0)
        if width > 150 && height > 100 { sizes.append("\(width)x\(height)") }
    }
    print("\(now),\(sizes.sorted().joined(separator: "|"))")
    usleep(50_000)
}
