// SPDX-License-Identifier: AGPL-3.0-only
// HST Writer, HST Sheets, HST Slides, HST Draw and HST PDF: tiny launcher apps that open HST Office in one module.
// They are built into "HST Office.app/Contents/Helpers/" (scripts/macos/make-app-launchers.py); the Dock tiles of
// "Thêm vào Dock" name those nested copies, and HST Office copies them into /Applications or ~/Applications for
// Launchpad, Spotlight and Finder (extensions/.../hst_office/mac_app_launchers.py).
//
// Info.plist of the launcher: HSTOfficeModule = writer | calc | impress | draw | pdf; HSTOfficeHostIdentifier = the
// bundle id of HST Office. The host is, in this order: the bundle three levels up (a nested copy), the running HST
// Office, "HST Office.app" in the launcher's own folder, then the copy Launch Services knows by bundle id (never one
// in the Trash).
//   - A module, HST Office not running: Launch Services opens the host with "--<module>" (it starts in that module
//     and is its own responsible process for privacy prompts).
//   - A module, HST Office running: the host's soffice runs once with "--<module>"; it hands the request to the
//     running office over its single-instance pipe and exits. The running office is then brought to the front.
//   - pdf: an open panel limited to PDF files; the chosen files are opened by HST Office (HST PDF shows them).
//   - No host (HST Office was removed): an alert; a copy outside the bundle offers to move itself to the Trash.
// No shell, no AppleScript; the launcher exits as soon as the request is handed over.
#import <AppKit/AppKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#include <spawn.h>
#include <sys/wait.h>

extern char **environ;

static const NSTimeInterval kOpenTimeout = 60.0;      // Launch Services answers long before the office is ready
static const NSTimeInterval kForwardTimeout = 30.0;   // a second soffice exits right after the hand-over

static int fail(NSString *message) {
    NSLog(@"HST launcher: %@", message);
    return 1;
}

static BOOL validModule(NSString *module) {
    return [@[ @"writer", @"calc", @"impress", @"draw", @"pdf" ] containsObject:module];
}

// Activation is cooperative from macOS 14: this launcher (just activated by the Dock or Finder) yields first.
static void bringToFront(NSRunningApplication *app) {
    if (@available(macOS 14.0, *)) {
        [NSApp yieldActivationToApplication:app];
        [app activateWithOptions:0];
    } else {
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
        [app activateWithOptions:NSApplicationActivateIgnoringOtherApps];
#pragma clang diagnostic pop
    }
}

static void comeForward(void) {  // a background launcher must come forward to show a panel or an alert
    [NSApp finishLaunching];  // windows of an app that never finished launching may not take the keyboard
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    [NSApp activateIgnoringOtherApps:YES];
#pragma clang diagnostic pop
}

static int forwardToRunningOffice(NSBundle *host, NSString *flag, NSRunningApplication *running) {
    NSString *soffice = host.executablePath;
    if (soffice.length == 0 || ![NSFileManager.defaultManager isExecutableFileAtPath:soffice])
        return fail([NSString stringWithFormat:@"no executable in %@", host.bundlePath]);
    if (@available(macOS 14.0, *))
        [NSApp yieldActivationToApplication:running];  // lets the office raise the new window itself
    char *argv[] = { (char *)soffice.fileSystemRepresentation, (char *)flag.UTF8String, NULL };
    pid_t pid = 0;
    int rc = posix_spawn(&pid, argv[0], NULL, NULL, argv, environ);
    if (rc != 0)
        return fail([NSString stringWithFormat:@"cannot start %@: %s", soffice, strerror(rc)]);
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:kForwardTimeout];
    int status = 0;
    pid_t done = 0;
    while ((done = waitpid(pid, &status, WNOHANG)) == 0 && deadline.timeIntervalSinceNow > 0)
        [NSThread sleepForTimeInterval:0.1];
    if (done == 0)  // the running office quit meanwhile and this one became the office: leave it running
        NSLog(@"HST launcher: soffice %d still running after %.0f s", pid, kForwardTimeout);
    else if (done < 0 || !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        NSLog(@"HST launcher: hand-over ended with status %d", status);
    bringToFront(running);
    return 0;
}

// Waits for a Launch Services request; `start` is given the completion handler to pass on.
static int awaitLaunchServices(NSURL *hostURL, void (^start)(void (^)(NSRunningApplication *, NSError *))) {
    __block NSError *failure = nil;
    __block BOOL finished = NO;
    start(^(NSRunningApplication *app, NSError *error) {
        (void)app;
        failure = error;
        finished = YES;
    });
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:kOpenTimeout];
    while (!finished && deadline.timeIntervalSinceNow > 0)
        [NSRunLoop.currentRunLoop runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
    if (!finished)
        return fail(@"Launch Services did not answer");
    if (failure)
        return fail([NSString stringWithFormat:@"cannot open %@: %@", hostURL.path, failure.localizedDescription]);
    return 0;
}

static int openHost(NSURL *hostURL, NSString *flag) {
    NSWorkspaceOpenConfiguration *config = [NSWorkspaceOpenConfiguration configuration];
    config.arguments = @[ flag ];
    config.activates = YES;
    return awaitLaunchServices(hostURL, ^(void (^done)(NSRunningApplication *, NSError *)) {
        [NSWorkspace.sharedWorkspace openApplicationAtURL:hostURL configuration:config completionHandler:done];
    });
}

// HST PDF: the files the user picks open in HST Office, which shows a PDF in HST PDF (as a double click does).
static int choosePdf(NSURL *hostURL) {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = NO;
    panel.allowsMultipleSelection = YES;
    panel.allowedContentTypes = @[ UTTypePDF ];
    panel.title = @"HST PDF";
    panel.message = @"Chọn tệp PDF để mở";
    panel.prompt = @"Mở";
    comeForward();
    if ([panel runModal] != NSModalResponseOK || panel.URLs.count == 0)
        return 0;  // cancelled: nothing to open
    NSArray<NSURL *> *files = panel.URLs;
    NSWorkspaceOpenConfiguration *config = [NSWorkspaceOpenConfiguration configuration];
    config.activates = YES;
    return awaitLaunchServices(hostURL, ^(void (^done)(NSRunningApplication *, NSError *)) {
        [NSWorkspace.sharedWorkspace openURLs:files withApplicationAtURL:hostURL configuration:config
                            completionHandler:done];
    });
}

static NSBundle *hostAt(NSURL *url, NSString *hostId) {
    if (url == nil || [url.path containsString:@"/.Trash/"])  // an uninstalled HST Office still known to Launch Services
        return nil;
    NSBundle *bundle = [NSBundle bundleWithURL:url.URLByStandardizingPath];
    return [bundle.bundleIdentifier isEqualToString:hostId] ? bundle : nil;
}

static NSBundle *findHost(NSBundle *me, NSString *hostId, NSRunningApplication *running) {
    NSURL *folder = me.bundleURL.URLByDeletingLastPathComponent;
    NSBundle *host = hostAt(folder.URLByDeletingLastPathComponent.URLByDeletingLastPathComponent, hostId);
    if (host == nil)
        host = hostAt(running.bundleURL, hostId);
    if (host == nil)
        host = hostAt([folder URLByAppendingPathComponent:@"HST Office.app"], hostId);
    if (host == nil) {
        if (@available(macOS 12.0, *)) {
            for (NSURL *url in [NSWorkspace.sharedWorkspace URLsForApplicationsWithBundleIdentifier:hostId])
                if ((host = hostAt(url, hostId)) != nil)
                    break;
        }
    }
    if (host == nil)
        host = hostAt([NSWorkspace.sharedWorkspace URLForApplicationWithBundleIdentifier:hostId], hostId);
    return host;
}

// HST Office is gone. A copy in /Applications or ~/Applications offers to move itself to the Trash; a nested copy
// (inside a damaged bundle) only says so.
static void hostMissing(NSBundle *me, BOOL nested) {
    NSString *name = [me objectForInfoDictionaryKey:@"CFBundleDisplayName"] ?: @"HST Office";
    NSAlert *alert = [[NSAlert alloc] init];
    alert.alertStyle = NSAlertStyleWarning;
    alert.messageText = @"HST Office chưa được cài đặt.";
    if (nested) {
        alert.informativeText = @"Hãy cài lại HST Office rồi thử lại.";
        comeForward();
        [alert runModal];
        return;
    }
    alert.informativeText = [NSString stringWithFormat:@"%@ cần HST Office để mở. Hãy cài lại HST Office, hoặc chuyển "
                                                         @"biểu tượng %@ vào Thùng rác.", name, name];
    [alert addButtonWithTitle:@"Chuyển vào Thùng rác"];
    [alert addButtonWithTitle:@"Để sau"];
    comeForward();
    if ([alert runModal] != NSAlertFirstButtonReturn)
        return;
    NSError *error = nil;
    if (![NSFileManager.defaultManager trashItemAtURL:me.bundleURL resultingItemURL:nil error:&error]) {
        NSAlert *failed = [[NSAlert alloc] init];
        failed.alertStyle = NSAlertStyleWarning;
        failed.messageText = [NSString stringWithFormat:@"Không chuyển được %@ vào Thùng rác.", name];
        failed.informativeText = error.localizedDescription ?: @"";
        [failed runModal];
    }
}

int main(void) {
    @autoreleasepool {
        [NSApplication sharedApplication];
        NSBundle *me = NSBundle.mainBundle;
        NSString *module = [me objectForInfoDictionaryKey:@"HSTOfficeModule"];
        NSString *hostId = [me objectForInfoDictionaryKey:@"HSTOfficeHostIdentifier"];
        if (![module isKindOfClass:NSString.class] || !validModule(module) || ![hostId isKindOfClass:NSString.class])
            return fail(@"HSTOfficeModule or HSTOfficeHostIdentifier missing from Info.plist");
        // The office runs one instance per user: any running copy of HST Office takes the request.
        NSRunningApplication *running = nil;
        for (NSRunningApplication *app in [NSRunningApplication runningApplicationsWithBundleIdentifier:hostId]) {
            if (!app.terminated) { running = app; break; }
        }
        NSBundle *host = findHost(me, hostId, running);
        if (host == nil) {
            hostMissing(me, [me.bundlePath containsString:@".app/Contents/"]);
            return fail([NSString stringWithFormat:@"no %@ for %@", hostId, me.bundlePath]);
        }
        if ([module isEqualToString:@"pdf"])
            return choosePdf(running ? running.bundleURL : host.bundleURL);
        NSString *flag = [@"--" stringByAppendingString:module];
        return running ? forwardToRunningOffice(host, flag, running) : openHost(host.bundleURL, flag);
    }
}
