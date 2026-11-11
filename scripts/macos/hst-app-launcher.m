// SPDX-License-Identifier: AGPL-3.0-only
// HST Writer.app, HST Sheets.app and HST Slides.app: tiny launchers inside
// "HST Office.app/Contents/Helpers/" that open HST Office in one module (scripts/macos/make-app-launchers.py builds
// and bundles them; the Dock pins them, see extensions/.../hst_office/app_shortcuts.py).
//
// Info.plist of the launcher: HSTOfficeModule = writer | calc | impress; HSTOfficeHostIdentifier = the bundle id of
// HST Office. The host is the bundle three levels up (Contents/Helpers/<launcher>.app), never looked up elsewhere.
//   - HST Office not running: Launch Services opens the host with "--<module>" (it starts in that module and is its
//     own responsible process for privacy prompts).
//   - running: the host's soffice runs once with "--<module>"; it hands the request to the running office over its
//     single-instance pipe and exits. The running office is then brought to the front.
// No shell, no AppleScript; the launcher exits as soon as the request is handed over.
#import <AppKit/AppKit.h>
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
    return [@[ @"writer", @"calc", @"impress" ] containsObject:module];
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

static int openHost(NSURL *hostURL, NSString *flag) {
    NSWorkspaceOpenConfiguration *config = [NSWorkspaceOpenConfiguration configuration];
    config.arguments = @[ flag ];
    config.activates = YES;
    __block NSError *failure = nil;
    __block BOOL finished = NO;
    [NSWorkspace.sharedWorkspace openApplicationAtURL:hostURL
                                        configuration:config
                                    completionHandler:^(NSRunningApplication *app, NSError *error) {
        (void)app;
        failure = error;
        finished = YES;
    }];
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:kOpenTimeout];
    while (!finished && deadline.timeIntervalSinceNow > 0)
        [NSRunLoop.currentRunLoop runMode:NSDefaultRunLoopMode beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
    if (!finished)
        return fail(@"Launch Services did not answer");
    if (failure)
        return fail([NSString stringWithFormat:@"cannot open %@: %@", hostURL.path, failure.localizedDescription]);
    return 0;
}

static void tellUser(NSString *text) {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = text;
    alert.alertStyle = NSAlertStyleWarning;
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
    [NSApp activateIgnoringOtherApps:YES];  // a background launcher must come forward to show the alert
#pragma clang diagnostic pop
    [alert runModal];
}

int main(void) {
    @autoreleasepool {
        [NSApplication sharedApplication];
        NSBundle *me = NSBundle.mainBundle;
        NSString *module = [me objectForInfoDictionaryKey:@"HSTOfficeModule"];
        NSString *hostId = [me objectForInfoDictionaryKey:@"HSTOfficeHostIdentifier"];
        if (![module isKindOfClass:NSString.class] || !validModule(module) || ![hostId isKindOfClass:NSString.class])
            return fail(@"HSTOfficeModule or HSTOfficeHostIdentifier missing from Info.plist");
        NSURL *hostURL = me.bundleURL.URLByDeletingLastPathComponent.URLByDeletingLastPathComponent
                             .URLByDeletingLastPathComponent.URLByStandardizingPath;
        NSBundle *host = [NSBundle bundleWithURL:hostURL];
        if (host == nil || ![host.bundleIdentifier isEqualToString:hostId]) {
            tellUser(@"Không tìm thấy HST Office. Hãy cài lại HST Office rồi thử lại.");
            return fail([NSString stringWithFormat:@"%@ is not %@", hostURL.path, hostId]);
        }
        NSString *flag = [@"--" stringByAppendingString:module];
        // The office runs one instance per user: any running copy of HST Office takes the request.
        NSRunningApplication *running = nil;
        for (NSRunningApplication *app in [NSRunningApplication runningApplicationsWithBundleIdentifier:hostId]) {
            if (!app.terminated) { running = app; break; }
        }
        return running ? forwardToRunningOffice(host, flag, running) : openHost(hostURL, flag);
    }
}
