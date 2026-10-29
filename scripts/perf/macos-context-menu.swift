// SPDX-License-Identifier: AGPL-3.0-only
// Measures right-click -> context-menu window latency for one running soffice process on macOS.
// Build:  swiftc -swift-version 5 scripts/perf/macos-context-menu.swift -framework AppKit -framework ApplicationServices -o build/tools/macos-context-menu
// Synthetic mode posts CGEvents (needs Accessibility); --manual listens to your physical right-clicks
// (needs Input Monitoring). The menu is detected via CGWindowListCopyWindowInfo owner/layer/bounds only.
// NOT compiled or run on the authoring machine (Linux): UNVERIFIED until the first Mac run.
import AppKit
import ApplicationServices
import Foundation

struct Options {
    var pid: pid_t = 0, trials = 20, timeoutMs = 5000.0, xFrac = 0.5, yFrac = 0.45
    var waitWindowS = 90.0, settleS = 5.0, intervalMs = 700.0, out = "", manual = false
}

struct WinInfo { let number: Int; let layer: Int; let bounds: CGRect }

func logErr(_ msg: String) { FileHandle.standardError.write((msg + "\n").data(using: .utf8)!) }
func fail(_ msg: String, code: Int32 = 2) -> Never { logErr(msg); exit(code) }

func parseOptions() -> Options {
    var o = Options()
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let a = it.next() {
        if a == "--manual" { o.manual = true; continue }
        guard let v = it.next() else { fail("missing value for \(a)") }
        switch a {
        case "--pid": o.pid = pid_t(v) ?? 0
        case "--trials": o.trials = Int(v) ?? 20
        case "--timeout-ms": o.timeoutMs = Double(v) ?? 5000
        case "--x-frac": o.xFrac = Double(v) ?? 0.5
        case "--y-frac": o.yFrac = Double(v) ?? 0.45
        case "--wait-window-s": o.waitWindowS = Double(v) ?? 90
        case "--settle-s": o.settleS = Double(v) ?? 5
        case "--interval-ms": o.intervalMs = Double(v) ?? 700
        case "--out": o.out = v
        default: fail("unknown argument \(a)")
        }
    }
    if o.pid <= 0 { fail("--pid is required") }
    return o
}

var timebase = mach_timebase_info_data_t()
func nowMs() -> Double {
    if timebase.denom == 0 { mach_timebase_info(&timebase) }
    return Double(mach_absolute_time()) * Double(timebase.numer) / Double(timebase.denom) / 1_000_000.0
}

func windows(_ pid: pid_t) -> [WinInfo] {
    guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] else { return [] }
    var out: [WinInfo] = []
    for w in list {
        guard let owner = w[kCGWindowOwnerPID as String] as? Int, owner == Int(pid),
              let num = w[kCGWindowNumber as String] as? Int,
              let layer = w[kCGWindowLayer as String] as? Int,
              let bd = w[kCGWindowBounds as String] as? [String: Any],
              let rect = CGRect(dictionaryRepresentation: bd as CFDictionary) else { continue }
        out.append(WinInfo(number: num, layer: layer, bounds: rect))
    }
    return out
}

// kCGPopUpMenuWindowLevel is 101; NSPopUpButtonCell / NSMenu popups live at that level.
func newMenuWindow(_ pid: pid_t, _ baseline: Set<Int>) -> WinInfo? {
    return windows(pid).first { !baseline.contains($0.number) && $0.layer >= 101 && $0.bounds.width >= 20 && $0.bounds.height >= 20 }
}

func rectJSON(_ r: CGRect) -> [Double] { return [Double(r.minX), Double(r.minY), Double(r.width), Double(r.height)] }

func waitMainWindow(_ o: Options) -> WinInfo {
    let end = Date().addingTimeInterval(o.waitWindowS)
    while Date() < end {
        let big = windows(o.pid).filter { $0.layer == 0 && $0.bounds.width >= 300 && $0.bounds.height >= 300 }
        if let m = big.max(by: { $0.bounds.width * $0.bounds.height < $1.bounds.width * $1.bounds.height }) { return m }
        Thread.sleep(forTimeInterval: 0.25)
    }
    fail("no document window for pid \(o.pid) within \(o.waitWindowS)s", code: 4)
}

func postMouse(_ type: CGEventType, _ p: CGPoint) {
    CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: p, mouseButton: .right)?.post(tap: .cghidEventTap)
}

func postEscape() {
    for down in [true, false] { CGEvent(keyboardEventSource: nil, virtualKey: 53, keyDown: down)?.post(tap: .cghidEventTap) }
}

func syntheticTrial(_ i: Int, _ p: CGPoint, _ o: Options) -> [String: Any] {
    let baseline = Set(windows(o.pid).map { $0.number })
    postMouse(.mouseMoved, p)
    Thread.sleep(forTimeInterval: 0.15)
    let t0 = nowMs()
    postMouse(.rightMouseDown, p)
    var hit: WinInfo? = nil
    while nowMs() - t0 < o.timeoutMs {
        if let m = newMenuWindow(o.pid, baseline) { hit = m; break }
        Thread.sleep(forTimeInterval: 0.001)
    }
    let ms = nowMs() - t0
    var trial: [String: Any] = ["i": i, "timeout": hit == nil]
    if let h = hit {
        trial["ms"] = (ms * 100).rounded() / 100
        trial["layer"] = h.layer
        trial["bounds"] = rectJSON(h.bounds)
        postEscape()
        let gone = Date().addingTimeInterval(3)  // wait for the menu window to close before the next trial
        while Date() < gone && windows(o.pid).contains(where: { $0.number == h.number }) { Thread.sleep(forTimeInterval: 0.02) }
    } else {
        trial["ms"] = NSNull()
        trial["new_windows"] = windows(o.pid).filter { !baseline.contains($0.number) }.map { ["layer": $0.layer, "bounds": rectJSON($0.bounds)] }
        postEscape()
    }
    postMouse(.rightMouseUp, p)
    Thread.sleep(forTimeInterval: o.intervalMs / 1000.0)
    return trial
}

// manual mode: passive listen-only event tap; t0 = tap callback receipt
var armedAt: Double? = nil, armedBaseline = Set<Int>(), manualTrials: [[String: Any]] = [], manualOpts = Options()

func tapCallback(proxy: CGEventTapProxy, type: CGEventType, event: CGEvent, refcon: UnsafeMutableRawPointer?) -> Unmanaged<CGEvent>? {
    let isRight = type == .rightMouseDown
    let isCtrlLeft = type == .leftMouseDown && event.flags.contains(.maskControl)
    if (isRight || isCtrlLeft) && armedAt == nil {
        let t0 = nowMs()
        let now = windows(manualOpts.pid)
        if !now.contains(where: { $0.layer >= 101 }) {  // ignore clicks while a popup is already open
            armedBaseline = Set(now.map { $0.number })
            armedAt = t0
        }
    }
    return Unmanaged.passUnretained(event)
}

func writeResult(_ doc: [String: Any], _ path: String) {
    guard let data = try? JSONSerialization.data(withJSONObject: doc, options: [.prettyPrinted, .sortedKeys]) else { fail("cannot encode JSON", code: 5) }
    if path.isEmpty { print(String(data: data, encoding: .utf8) ?? ""); return }
    do { try data.write(to: URL(fileURLWithPath: path)) } catch { fail("cannot write \(path): \(error)", code: 5) }
}

func runManual(_ o: Options, _ base: [String: Any]) {
    manualOpts = o
    let mask = CGEventMask((1 << CGEventType.rightMouseDown.rawValue) | (1 << CGEventType.leftMouseDown.rawValue))
    guard let tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .listenOnly,
                                      eventsOfInterest: mask, callback: tapCallback, userInfo: nil) else {
        fail("cannot create event tap: grant Input Monitoring to Terminal (System Settings > Privacy & Security)", code: 3)
    }
    let src = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), src, .commonModes)
    CGEvent.tapEnable(tap: tap, enable: true)
    logErr("Manual mode: right-click (or Control-click) in the LibreOffice window \(o.trials) times; Esc closes each menu.")
    Timer.scheduledTimer(withTimeInterval: 0.002, repeats: true) { _ in
        guard let t0 = armedAt else { return }
        let el = nowMs() - t0
        var trial: [String: Any]? = nil
        if let m = newMenuWindow(o.pid, armedBaseline) {
            trial = ["i": manualTrials.count + 1, "ms": (el * 100).rounded() / 100, "timeout": false, "layer": m.layer, "bounds": rectJSON(m.bounds)]
        } else if el > o.timeoutMs {
            trial = ["i": manualTrials.count + 1, "ms": NSNull(), "timeout": true]
        }
        if let t = trial {
            manualTrials.append(t)
            armedAt = nil
            logErr("trial \(manualTrials.count)/\(o.trials): \(t["ms"] ?? "timeout") ms")
            if manualTrials.count >= o.trials {
                var doc = base
                doc["trials"] = manualTrials
                writeResult(doc, o.out)
                exit(0)
            }
        }
    }
    RunLoop.main.run()
}

let opts = parseOptions()
let trusted = AXIsProcessTrusted()
if !opts.manual && !trusted {
    _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary)
    fail("Accessibility permission missing for this terminal: enable it in System Settings > Privacy & Security > Accessibility, restart Terminal, rerun (or use --manual).", code: 3)
}
_ = waitMainWindow(opts)
Thread.sleep(forTimeInterval: opts.settleS)
NSRunningApplication(processIdentifier: opts.pid)?.activate(options: [.activateIgnoringOtherApps])
Thread.sleep(forTimeInterval: 0.5)
let mainWin = waitMainWindow(opts)  // re-pick after settle: a splash window may have gone away
let point = CGPoint(x: mainWin.bounds.minX + mainWin.bounds.width * opts.xFrac, y: mainWin.bounds.minY + mainWin.bounds.height * opts.yFrac)
var header: [String: Any] = ["tool": "macos-context-menu", "mode": opts.manual ? "manual" : "synthetic", "pid": Int(opts.pid),
                             "accessibility_trusted": trusted, "window": rectJSON(mainWin.bounds), "point": [Double(point.x), Double(point.y)],
                             "clock": "mach_absolute_time converted to ms; manual mode t0 = tap callback receipt"]
if opts.manual {
    runManual(opts, header)
} else {
    var trials: [[String: Any]] = []
    for i in 1...max(1, opts.trials) { trials.append(syntheticTrial(i, point, opts)) }
    header["trials"] = trials
    writeResult(header, opts.out)
}
