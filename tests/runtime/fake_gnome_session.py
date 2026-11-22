# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""A minimal org.gnome.SessionManager for the session-end checks: the office's gtk3 frames register with it, then a
log out is played as GNOME does it (QueryEndSession, then EndSession). Run as a separate process with the host's
python3 and Gio on a private session bus (check-session-end-gnome.py starts it):
  python3 fake_gnome_session.py <control dir>; touch <dir>/query, then <dir>/end
It logs every call to <dir>/sm.log and writes the number of inhibitors (unsaved documents) to <dir>/inhibitors.
"""
import os
import sys
import time

from gi.repository import Gio, GLib

XML = """<node>
 <interface name="org.gnome.SessionManager">
  <method name="RegisterClient"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="o" direction="out"/></method>
  <method name="Inhibit"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="u" direction="out"/></method>
  <method name="Uninhibit"><arg type="u" direction="in"/></method>
  <method name="IsInhibited"><arg type="u" direction="in"/><arg type="b" direction="out"/></method>
 </interface>
</node>"""
CLIENT_XML = """<node>
 <interface name="org.gnome.SessionManager.ClientPrivate">
  <method name="EndSessionResponse"><arg type="b" direction="in"/><arg type="s" direction="in"/></method>
  <signal name="QueryEndSession"><arg type="u"/></signal>
  <signal name="EndSession"><arg type="u"/></signal>
  <signal name="CancelEndSession"/>
  <signal name="Stop"/>
 </interface>
</node>"""
CTL = sys.argv[1]
LOG = open(os.path.join(CTL, "sm.log"), "a", buffering=1)
STATE = {"conn": None, "clients": [], "inhibit": {}, "next": 1, "done": set()}


def log(text):
    LOG.write("%.3f %s\n" % (time.time(), text))


def on_call(conn, sender, path, iface, method, params, inv):
    args = params.unpack()
    log("call %s %s %r from %s" % (path, method, args, sender))
    if method == "RegisterClient":
        cpath = "/org/gnome/SessionManager/Client%d" % (len(STATE["clients"]) + 1)
        conn.register_object(cpath, Gio.DBusNodeInfo.new_for_xml(CLIENT_XML).interfaces[0], on_call, None, None)
        STATE["clients"].append(cpath)
        inv.return_value(GLib.Variant("(o)", (cpath,)))
    elif method == "Inhibit":
        cookie = STATE["next"]
        STATE["next"] += 1
        STATE["inhibit"][cookie] = args
        inv.return_value(GLib.Variant("(u)", (cookie,)))
    elif method == "Uninhibit":
        STATE["inhibit"].pop(args[0], None)
        inv.return_value(None)
    elif method == "IsInhibited":
        inv.return_value(GLib.Variant("(b)", (bool(STATE["inhibit"]),)))
    else:
        inv.return_value(None)


def emit(name, params):
    for cpath in STATE["clients"]:
        STATE["conn"].emit_signal(None, cpath, "org.gnome.SessionManager.ClientPrivate", name, params)
    log("emit %s to %d clients; inhibitors now %r" % (name, len(STATE["clients"]), list(STATE["inhibit"].values())))


def poll():
    for name, signal, params in (("query", "QueryEndSession", GLib.Variant("(u)", (1,))),
                                 ("end", "EndSession", GLib.Variant("(u)", (1,)))):
        if name not in STATE["done"] and os.path.exists(os.path.join(CTL, name)):
            STATE["done"].add(name)
            emit(signal, params)
    with open(os.path.join(CTL, "inhibitors"), "w") as handle:
        handle.write("%d\n" % len(STATE["inhibit"]))
    return True


def on_bus(conn, name):
    STATE["conn"] = conn
    conn.register_object("/org/gnome/SessionManager", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], on_call, None,
                         None)


Gio.bus_own_name(Gio.BusType.SESSION, "org.gnome.SessionManager", Gio.BusNameOwnerFlags.NONE, on_bus,
                 lambda *a: log("name acquired"), lambda *a: log("name lost"))
GLib.timeout_add(200, poll)
GLib.MainLoop().run()
