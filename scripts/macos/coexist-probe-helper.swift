// SPDX-License-Identifier: AGPL-3.0-only
// LaunchServices and window facts for scripts/macos/coexist-probe.sh.
//   coexist-probe-helper defaults <ext>... [-- <url-scheme>...]   one "<ext|scheme> <bundle id> <app path>" line each
//   coexist-probe-helper windows <pid>                           number of on-screen normal windows of the process
import AppKit
import UniformTypeIdentifiers

func describe(_ url: URL?) -> String {
    guard let url = url else { return "none -" }
    return "\(Bundle(url: url)?.bundleIdentifier ?? "?") \(url.path)"
}

let args = Array(CommandLine.arguments.dropFirst())
switch args.first {
case "defaults":
    var schemes = false
    for item in args.dropFirst() {
        if item == "--" { schemes = true; continue }
        if schemes {
            let url = URL(string: "\(item):probe")!
            print("scheme:\(item) \(describe(NSWorkspace.shared.urlForApplication(toOpen: url)))")
        } else if let type = UTType(filenameExtension: item) {
            print("ext:\(item) \(describe(NSWorkspace.shared.urlForApplication(toOpen: type))) uti=\(type.identifier)")
        } else {
            print("ext:\(item) none - uti=?")
        }
    }
case "windows":
    guard args.count == 2, let pid = Int(args[1]) else { exit(64) }
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    print(list.filter { ($0[kCGWindowOwnerPID as String] as? Int) == pid && ($0[kCGWindowLayer as String] as? Int) == 0 }.count)
default:
    FileHandle.standardError.write("usage: coexist-probe-helper defaults <ext>... [-- <scheme>...] | windows <pid>\n".data(using: .utf8)!)
    exit(64)
}
