"""Minimal signed BingX REST helper for authenticated user-data streams.

This module is intentionally read/stream-lifecycle only; trading orders remain
inside the existing CCXT execution kernel.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import requests


class BingXSignedREST:
    def __init__(self, api_key=None, secret_key=None, base_url=None, timeout=None):
        self.api_key = api_key or os.getenv("BINGX_API_KEY", "")
        self.secret_key = secret_key or os.getenv("BINGX_SECRET_KEY", "")
        self.base_url = (base_url or os.getenv("BINGX_API_BASE_URL", "https://open-api.bingx.com")).rstrip("/")
        self.timeout = float(timeout or os.getenv("BINGX_REST_TIMEOUT_SEC", "10"))
        self.source_key = os.getenv("BINGX_SOURCE_KEY", "BX-AI-SKILL")
        self.session = requests.Session()

    @property
    def configured(self):
        return bool(self.api_key and self.secret_key)

    def _signed_params(self, params: dict[str, Any] | None = None):
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        recv = os.getenv("BINGX_RECV_WINDOW", "5000")
        if recv and "recvWindow" not in payload:
            payload["recvWindow"] = int(recv)
        signing = "&".join(f"{k}={payload[k]}" for k in sorted(payload))
        signature = hmac.new(self.secret_key.encode(), signing.encode(), hashlib.sha256).hexdigest()
        payload["signature"] = signature
        return payload

    def request(self, method: str, path: str, params: dict[str, Any] | None = None):
        if not self.configured:
            raise RuntimeError("BINGX_API_KEY/BINGX_SECRET_KEY not configured")
        signed = self._signed_params(params)
        url = f"{self.base_url}{path}"
        headers = {"X-BX-APIKEY": self.api_key}
        if self.source_key:
            headers["X-SOURCE-KEY"] = self.source_key
        if method.upper() == "GET":
            resp = self.session.request("GET", url, params=signed, headers=headers, timeout=self.timeout)
        else:
            resp = self.session.request(
                method.upper(), url,
                data=urlencode(signed),
                headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or int(payload.get("code", -1)) != 0:
            code = payload.get("code") if isinstance(payload, dict) else "UNKNOWN"
            msg = payload.get("msg") if isinstance(payload, dict) else "invalid response"
            raise RuntimeError(f"BingX REST error {code}: {msg}")
        return payload.get("data")

    def create_listen_key(self) -> str:
        data = self.request("POST", "/openApi/user/auth/userDataStream") or {}
        key = data.get("listenKey") if isinstance(data, dict) else None
        if not key:
            raise RuntimeError("BingX did not return listenKey")
        return str(key)

    def extend_listen_key(self, listen_key: str):
        self.request("PUT", "/openApi/user/auth/userDataStream", {"listenKey": listen_key})

    def delete_listen_key(self, listen_key: str):
        try:
            self.request("DELETE", "/openApi/user/auth/userDataStream", {"listenKey": listen_key})
        except Exception:
            pass
