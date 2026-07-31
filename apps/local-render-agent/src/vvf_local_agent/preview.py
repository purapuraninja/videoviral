"""Read-only preview HTTP server for the local render PC.

Serves rendered video files (and only files under the configured tasks root) to
the VPS over Tailscale. It supports HTTP Range requests so the VPS can stream
without loading the whole file or storing it.

IMPORTANT: bind this to the Tailscale interface only (see VVF_PREVIEW_HOST),
never to 0.0.0.0 or a public interface.
"""

from __future__ import annotations

import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from vvf_shared.logging import get_logger


class _RangeHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with Range support + path confinement."""

    # directory is resolved per-instance in __init__ via functools.partial.

    def __init__(self, *args, root: str, **kwargs):
        self._root = os.path.abspath(root)
        super().__init__(*args, directory=self._root, **kwargs)

    # --- confine to root -----------------------------------------------
    def translate_path(self, path: str) -> str:  # noqa: D401
        # Base class maps URL path under self.directory; ensure result is inside root.
        translated = super().translate_path(path)
        full = os.path.abspath(translated)
        if not full.startswith(self._root + os.sep) and full != self._root:
            # Out-of-root access -> force a non-existent path (404).
            return os.path.join(self._root, "__forbidden__")
        return full

    # --- Range support --------------------------------------------------
    def send_head(self):  # noqa: D401
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.exists(path):
            return super().send_head()
        return self._send_range(path, rng)

    def _send_range(self, path: str, rng: str):
        size = os.path.getsize(path)
        start, end = self._parse_range(rng, size)
        if start is None:
            self.send_error(416, "Requested Range Not Satisfiable")
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        length = end - start + 1
        ctype = self.guess_type(path)
        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        f = open(path, "rb")
        f.seek(start)
        # copyfile streams the requested window; wrap in a limited reader.
        class _Limited:
            def __init__(self, fh, remaining):
                self._fh = fh
                self._n = remaining

            def read(self, n=-1):
                if self._n <= 0:
                    return b""
                if n < 0 or n > self._n:
                    n = self._n
                data = self._fh.read(n)
                self._n -= len(data)
                return data

        return _Limited(f, length)

    @staticmethod
    def _parse_range(rng: str, size: int):
        # Only support a single "bytes=start-end" / "bytes=start-" / "bytes=-suffix".
        try:
            unit, _, span = rng.partition("=")
            if unit.strip() != "bytes":
                return None, None
            s, _, e = span.partition("-")
            if s == "":
                length = int(e)
                return max(0, size - length), size - 1
            start = int(s)
            end = int(e) if e else size - 1
            if start > end or start >= size:
                return None, None
            return start, min(end, size - 1)
        except (ValueError, AttributeError):
            return None, None

    def log_message(self, fmt, *args):  # noqa: D401
        get_logger().info("preview: " + (fmt % args))


def start_preview_server(host: str, port: int, root: str) -> ThreadingHTTPServer:
    """Start the read-only preview server on ``host:port`` (daemon thread).

    ``host`` must be the Tailscale interface address. Raises if the bind fails.
    """
    resolved = str(Path(root).resolve())
    handler = lambda *a, **kw: _RangeHandler(*a, root=resolved, **kw)  # noqa: E731
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
    thread.start()
    get_logger().info(f"preview server listening on {host}:{port} serving {resolved}")
    return server
