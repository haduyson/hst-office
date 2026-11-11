# SPDX-License-Identifier: AGPL-3.0-only
"""Start-up tracer for the office's embedded Python, used only by scripts/perf/startup-timing.py.

The timing harness puts this directory on PYTHONPATH and names a trace file in HST_STARTUP_TRACE; the office's
Py_Initialize() then imports this module (site.py imports sitecustomize). Nothing here runs in a normal start: the
installation never contains this file. One JSON object per line, "t" in seconds since the epoch:
  {"ev": "python-init"}                                       the interpreter is up (sitecustomize imported)
HST_STARTUP_PYCACHE=<dir> also turns on a bytecode cache in <dir> (sys.pycache_prefix), as a per-user cache would.
  {"ev": "import", "mod", "dt", "src"}                        one module executed: own time plus its imports,
                                                              src "pyc" (bytecode read) or "py" (compiled now)
  {"ev": "compile", "path", "dt"}                             one source file compiled to bytecode (no usable .pyc)
  {"ev": "call", "what", "dt", "thread"}                      an HST job/handler method or a start-up callback
  {"ev": "net", "what", "host", "thread"}                     a DNS lookup or socket connect, with its thread
"""
import json
import os
import sys
import threading
import time

_PATH = os.environ.get("HST_STARTUP_TRACE")
_LOCK = threading.Lock()


def emit(event, **fields):
    if not _PATH:
        return
    fields.update(ev=event, t=time.time(), pid=os.getpid())
    line = json.dumps(fields, default=str)
    with _LOCK:
        try:
            with open(_PATH, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


class _TimedLoader:
    """Wraps a module's loader: times exec_module and tells whether bytecode was read or source compiled."""

    def __init__(self, loader, name):
        self._loader, self._name = loader, name

    def __getattr__(self, attr):
        return getattr(self._loader, attr)

    def create_module(self, spec):
        return self._loader.create_module(spec)

    def exec_module(self, module):
        began = time.perf_counter()
        compiled = []
        get_code = getattr(self._loader, "source_to_code", None)
        if get_code is not None:
            def source_to_code(*args, **kwargs):
                compiled.append(True)
                return get_code(*args, **kwargs)
            try:
                self._loader.source_to_code = source_to_code
            except AttributeError:
                pass
        try:
            self._loader.exec_module(module)
        finally:
            if get_code is not None:
                try:
                    del self._loader.source_to_code
                except AttributeError:
                    pass
            origin = getattr(module, "__file__", "") or ""
            emit("import", mod=self._name, dt=round(time.perf_counter() - began, 6),
                 src="py" if compiled else ("pyc" if origin.endswith((".py", ".pyc")) else "ext"))


class _Finder:
    """Meta-path finder that hands every found spec a timing loader (the real finders still find it)."""

    def find_spec(self, name, path=None, target=None):
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                if spec.loader is not None and hasattr(spec.loader, "exec_module"):
                    spec.loader = _TimedLoader(spec.loader, name)
                return spec
        return None


def _timed(what, function):
    def wrapper(*args, **kwargs):
        began = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            emit("call", what=what, dt=round(time.perf_counter() - began, 6), thread=threading.current_thread().name)
    wrapper.__wrapped__ = function
    return wrapper


def _wrap_hst(module):
    """Time the job, handler and start-up callback entry points of an HST module (classes with execute/dispatch)."""
    for name, value in list(vars(module).items()):
        if isinstance(value, type) and value.__module__ == module.__name__:
            for method in ("execute", "dispatch", "trigger", "queryDispatch", "queryDispatches", "addStatusListener"):
                if method in vars(value):
                    setattr(value, method, _timed("%s.%s.%s" % (module.__name__, name, method), vars(value)[method]))
    if module.__name__ == "hst_office.welcome_job" and hasattr(module, "run_later"):
        original = module.run_later

        def run_later(ctx, callback, *args, **kwargs):
            return original(ctx, _timed("run_later:%s" % getattr(callback, "__qualname__", "callback"), callback),
                            *args, **kwargs)
        module.run_later = run_later


class _HstHook(_TimedLoader):
    def exec_module(self, module):
        super().exec_module(module)
        if module.__name__.startswith("hst_office"):
            _wrap_hst(module)
        elif module.__name__ == "socket":  # wrapped once someone imports it: the tracer itself never does
            try:
                _wrap_network(module)
            except Exception as error:  # noqa: BLE001
                emit("tracer-error", error=repr(error))


class _HstFinder(_Finder):
    def find_spec(self, name, path=None, target=None):
        spec = super().find_spec(name, path, target)
        if spec is not None and isinstance(spec.loader, _TimedLoader):
            spec.loader = _HstHook(spec.loader._loader, name)
        return spec


def _wrap_compile():
    """Every source compile of the import system, timed (it runs only when no usable .pyc exists)."""
    from importlib import _bootstrap_external
    original = _bootstrap_external.SourceLoader.source_to_code

    def source_to_code(self, data, path, *args, **kwargs):
        began = time.perf_counter()
        try:
            return original(self, data, path, *args, **kwargs)
        finally:
            emit("compile", path=os.path.basename(str(path)), dt=round(time.perf_counter() - began, 6))
    _bootstrap_external.SourceLoader.source_to_code = source_to_code


def _wrap_network(socket):
    getaddrinfo, connect = socket.getaddrinfo, socket.socket.connect

    def traced_getaddrinfo(host, *args, **kwargs):
        emit("net", what="getaddrinfo", host=host, thread=threading.current_thread().name)
        return getaddrinfo(host, *args, **kwargs)

    def traced_connect(self, address):
        emit("net", what="connect", host=address, thread=threading.current_thread().name)
        return connect(self, address)
    socket.getaddrinfo = traced_getaddrinfo
    socket.socket.connect = traced_connect


_CACHE = os.environ.get("HST_STARTUP_PYCACHE")
if _CACHE:  # what a per-user bytecode cache would do: write and reuse .pyc there, never next to the sources
    sys.pycache_prefix, sys.dont_write_bytecode = _CACHE, False

if _PATH:
    emit("python-init", pycache_prefix=sys.pycache_prefix, executable=sys.executable, version=sys.version.split()[0],
         dont_write_bytecode=sys.dont_write_bytecode)
    sys.meta_path.insert(0, _HstFinder())
    try:
        _wrap_compile()
        if "socket" in sys.modules:  # imported before this tracer was installed
            _wrap_network(sys.modules["socket"])
    except Exception as error:  # noqa: BLE001 - tracing must never stop the office's Python
        emit("tracer-error", error=repr(error))
