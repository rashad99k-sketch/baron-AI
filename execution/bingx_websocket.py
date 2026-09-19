"""BingX USDT-M account WebSocket monitor.

The stream is informational/reconciliation-aware. REST remains the authority
for final state, while WebSocket provides low-latency event awareness.
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
import uuid

from .bingx_rest import BingXSignedREST


class BingXAccountStream:
    def __init__(self, on_event=None, logger=None):
        self.on_event = on_event or (lambda _e: None)
        self.logger = logger or (lambda *a, **k: None)
        self.rest = BingXSignedREST()
        self.enabled = os.getenv("BINGX_WS_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
        self.endpoint = os.getenv("BINGX_WS_ACCOUNT_URL", "wss://open-api-swap.bingx.com/swap-market")
        self._stop = threading.Event()
        self._thread = None
        self._listen_key = None
        self._ws = None
        self._state = {"status": "DISABLED" if not self.enabled else "STOPPED", "last_message": 0.0, "last_error": ""}

    def status(self):
        return dict(self._state)

    def start(self):
        if not self.enabled:
            self._state["status"] = "DISABLED"
            return None
        if self._thread and self._thread.is_alive():
            return self._thread
        if not self.rest.configured:
            self._state.update({"status": "DATA_UNAVAILABLE", "last_error": "BINGX credentials not configured"})
            return None
        self._thread = threading.Thread(target=self._run, name="baron-bingx-account-ws", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        if self._listen_key:
            self.rest.delete_listen_key(self._listen_key)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._state["status"] = "STOPPED"

    @staticmethod
    def _decode(message):
        if isinstance(message, bytes):
            try:
                return gzip.decompress(message).decode("utf-8")
            except Exception:
                return message.decode("utf-8", errors="replace")
        return str(message)

    def _on_message(self, ws, message):
        text = self._decode(message)
        self._state["last_message"] = time.time()
        if text == "Ping" or "ping" in text.lower():
            try:
                ws.send("Pong")
            except Exception:
                pass
            return
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw": text}
        self.on_event(payload)

    def _run(self):
        try:
            import websocket
        except Exception as exc:
            self._state.update({"status": "DATA_UNAVAILABLE", "last_error": f"websocket-client unavailable: {exc}"})
            return
        backoff = 2.0
        while not self._stop.is_set():
            try:
                self._listen_key = self.rest.create_listen_key()
                url = f"{self.endpoint}?listenKey={self._listen_key}"
                self._state.update({"status": "CONNECTING", "listen_key_active": True, "last_error": ""})
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=lambda _ws: self._state.update({"status": "CONNECTED"}),
                    on_message=self._on_message,
                    on_error=lambda _ws, err: self._state.update({"status": "DEGRADED", "last_error": str(err)}),
                    on_close=lambda *_args: self._state.update({"status": "DISCONNECTED"}),
                )
                # The periodic REST endpoint extends the key every 30 minutes.
                extender = threading.Thread(target=self._extend_loop, daemon=True)
                extender.start()
                self._ws.run_forever(ping_interval=0, ping_timeout=None)
            except Exception as exc:
                self._state.update({"status": "DEGRADED", "last_error": str(exc)})
                self.logger(f"[BINGX_WS] stream error: {exc}", "WARN")
            finally:
                self._ws = None
                if self._listen_key:
                    self.rest.delete_listen_key(self._listen_key)
                self._listen_key = None
            if self._stop.wait(backoff):
                break
            backoff = min(60.0, backoff * 2.0)

    def _extend_loop(self):
        while not self._stop.wait(1800):
            try:
                if self._listen_key:
                    self.rest.extend_listen_key(self._listen_key)
            except Exception as exc:
                self._state.update({"status": "DEGRADED", "last_error": f"listenKey renew: {exc}"})
