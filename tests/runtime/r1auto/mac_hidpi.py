# SPDX-License-Identifier: AGPL-3.0-only
"""A real 2x (Retina) desktop on a runner VM whose only display offers 1x modes.

WindowServer's CGVirtualDisplay (the API DeskPad and BetterDisplay use) adds a display with a HiDPI mode; making it
the main display lets HST Office render at backing scale 2, so screenshots are genuine 2x pixels, never upscaled.
The display exists only while this process holds the returned object."""
import time

_ALIVE = []


def create(width=1440, height=900):
    import objc
    import Quartz as q
    from dispatch import dispatch_queue_create
    descriptor = objc.lookUpClass("CGVirtualDisplayDescriptor").alloc().init()
    descriptor.setName_("R1 Retina")
    descriptor.setMaxPixelsWide_(width * 2)
    descriptor.setMaxPixelsHigh_(height * 2)
    descriptor.setSizeInMillimeters_((330.0, 206.0))  # a 15" panel: about 220 ppi at 2880x1800
    descriptor.setVendorID_(0x4853)
    descriptor.setProductID_(0x5231)
    descriptor.setSerialNum_(1)
    descriptor.setQueue_(dispatch_queue_create(b"r1.hidpi", None))
    display = objc.lookUpClass("CGVirtualDisplay").alloc().initWithDescriptor_(descriptor)
    if display is None:
        raise RuntimeError("WindowServer từ chối màn hình ảo")
    settings = objc.lookUpClass("CGVirtualDisplaySettings").alloc().init()
    settings.setHiDPI_(1)
    mode = objc.lookUpClass("CGVirtualDisplayMode").alloc().initWithWidth_height_refreshRate_(width, height, 60.0)
    settings.setModes_([mode])
    if not display.applySettings_(settings):
        raise RuntimeError("Màn hình ảo không nhận chế độ HiDPI")
    _ALIVE.append(display)
    ident = display.displayID()
    time.sleep(2)
    # The main display is the one at the global origin: move the virtual display there.
    error, config = q.CGBeginDisplayConfiguration(None)
    if error:
        raise RuntimeError("Không cấu hình được màn hình")
    q.CGConfigureDisplayOrigin(config, ident, 0, 0)
    old = q.CGMainDisplayID()
    if old != ident:
        q.CGConfigureDisplayOrigin(config, old, width, 0)
    if q.CGCompleteDisplayConfiguration(config, q.kCGConfigureForSession):
        raise RuntimeError("Không đặt được màn hình ảo làm màn hình chính")
    time.sleep(2)
    return ident
