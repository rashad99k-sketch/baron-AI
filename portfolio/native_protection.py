"""Exchange-native conditional protection adapter.

The adapter is fail-closed: it only reports PROTECTED after the exchange
returns an order id.  Because conditional-order parameters differ by venue,
activation is explicit via ENABLE_NATIVE_PROTECTION=1 and the order type/extra
params are configurable. Synthetic management remains the fallback.
"""
from __future__ import annotations
import hashlib, json, os, time

class NativeProtectionManager:
    def __init__(self, exchange=None, logger=None):
        self.exchange=exchange
        self.logger=logger or (lambda *a,**k:None)
        _raw = os.getenv("ENABLE_NATIVE_PROTECTION","0").strip().strip('"').strip("'")
        self.enabled=_raw.lower() in {"1","true","yes","on"}
        self.order_type=os.getenv("NATIVE_PROTECTION_ORDER_TYPE","STOP_MARKET").strip().strip('"').strip("'")
        self._orders={}
    @staticmethod
    def _key(symbol, position_side=None):
        sym = str(symbol or "")
        leg = str(position_side or "").upper()
        return (sym, leg) if leg in {"LONG", "SHORT"} else (sym, "")

    def status(self,symbol,position_side=None):
        key = self._key(symbol, position_side)
        o = self._orders.get(key)
        if o and o.get("sl_order_id"): return "PROTECTED"
        if position_side is None:
            for (sym, _leg), item in self._orders.items():
                if sym == str(symbol or "") and item.get("sl_order_id"):
                    return "PROTECTED"
        return "UNPROTECTED"
    def summary(self):
        """Sanitized manager diagnostic (no credentials, no order ids)."""
        return {
            "enabled": bool(self.enabled),
            "order_type": str(self.order_type),
            "verify": os.getenv("NATIVE_PROTECTION_VERIFY","1").strip().lower() in {"1","true","yes","on"},
            "exchange_present": self.exchange is not None,
            "protected_symbols": [f"{sym}:{leg}" if leg else sym for (sym, leg) in sorted(self._orders.keys())],
        }
    def _params(self, side, position_side, trigger, client_order_id=None, position_mode=None):
        mode = str(position_mode or "HEDGE").upper()
        params={"positionSide": "BOTH" if mode in {"ONE_WAY", "ONEWAY"} else position_side, "stopPrice":float(trigger),
                "workingType":os.getenv("NATIVE_PROTECTION_WORKING_TYPE", "MARK_PRICE")}
        # Current BingX perpetual-swap docs support clientOrderId for MARKET
        # and LIMIT orders only. Native protection is conditional (normally
        # STOP_MARKET/TAKE_PROFIT_MARKET), so correlate it locally with the
        # venue order id instead of sending an unsupported clientOrderId.
        order_type = str(self.order_type or "").upper()
        if client_order_id and order_type in {"MARKET", "LIMIT"}:
            params["clientOrderId"] = str(client_order_id)[:40]
        if mode in {"ONE_WAY", "ONEWAY"}:
            params["reduceOnly"] = True
        raw=os.getenv("NATIVE_PROTECTION_PARAMS_JSON","").strip()
        if raw:
            try: params.update(json.loads(raw))
            except Exception: pass
        return params
    def place(self,symbol,side,qty,sl,position_side,position_mode=None):
        if not self.enabled:return {"status":"DISABLED"}
        if self.exchange is None or not sl or qty<=0:return {"status":"UNPROTECTED","reason":"MISSING_EXCHANGE_OR_LEVEL"}
        close_side="sell" if str(side).upper()=="BUY" else "buy"
        try:
            cid = "brnsl" + hashlib.sha1(f"{symbol}|{position_side}|{sl}|{qty}".encode()).hexdigest()[:24]
            order=self.exchange.create_order(symbol,self.order_type,close_side,float(qty),None,self._params(side,position_side,sl,cid,position_mode=position_mode))
            oid=(order or {}).get("id")
            if not oid: return {"status":"UNPROTECTED","reason":"NO_ORDER_ID"}
            # A create-order ACK is not sufficient for live protection: some
            # venues/adapters can acknowledge a conditional request before its
            # final order state is visible.  When fetch_order is available,
            # re-read the exact order and fail closed on rejected/cancelled
            # states.
            verify = os.getenv("NATIVE_PROTECTION_VERIFY", "1").strip().lower() in {"1","true","yes","on"}
            if verify:
                fetch_order = getattr(self.exchange, "fetch_order", None)
                if not callable(fetch_order):
                    return {"status":"UNPROTECTED","reason":"NO_ORDER_VERIFIER"}
                try:
                    confirmed = fetch_order(oid, symbol)
                    if not isinstance(confirmed, dict):
                        return {"status":"UNPROTECTED","reason":"INVALID_ORDER_VERIFICATION"}
                    confirmed_id = confirmed.get("id") or (confirmed.get("info") or {}).get("orderId")
                    status = str(confirmed.get("status") or "").lower()
                    if confirmed_id and str(confirmed_id) != str(oid):
                        return {"status":"UNPROTECTED","reason":"ORDER_ID_MISMATCH"}
                    if status in {"canceled","cancelled","rejected","expired","failed"}:
                        return {"status":"UNPROTECTED","reason":f"ORDER_STATUS_{status.upper()}"}
                except Exception as verify_exc:
                    self.logger(f"[NATIVE_PROTECTION] {symbol} verification failed: {verify_exc}","ERROR")
                    return {"status":"UNPROTECTED","reason":"ORDER_VERIFICATION_FAILED"}
            self._orders[self._key(symbol, position_side)]={"sl_order_id":oid,"sl":float(sl),"qty":float(qty),
                                 "updated_at":time.time(), "status":"VERIFIED",
                                 "position_side":str(position_side or "").upper()}
            self.logger(f"[NATIVE_PROTECTION] {symbol} SL ACK id={oid} level={sl}","SUCCESS")
            return {"status":"PROTECTED","sl_order_id":oid,"sl":float(sl)}
        except Exception as exc:
            self.logger(f"[NATIVE_PROTECTION] {symbol} placement failed: {exc}","ERROR")
            return {"status":"UNPROTECTED","reason":str(exc)}
    def update(self,symbol,side,qty,sl,position_side,position_mode=None):
        if not self.enabled:return {"status":"DISABLED"}
        key = self._key(symbol, position_side)
        old=(self._orders.get(key) or {}).get("sl_order_id")
        result=self.place(symbol,side,qty,sl,position_side,position_mode=position_mode)
        new=result.get("sl_order_id")
        # Place-first, cancel-second prevents a protection gap if the new order
        # is rejected. The old stop remains active in that case.
        if result.get("status")=="PROTECTED" and old and old != new:
            try:self.exchange.cancel_order(old,symbol)
            except Exception as exc:self.logger(f"[NATIVE_PROTECTION] old SL cancel failed: {exc}","WARN")
        return result

    def cancel(self,symbol,position_side=None):
        if position_side is None:
            keys = [k for k in self._orders if k[0] == str(symbol or "")]
        else:
            keys = [self._key(symbol, position_side)]
        items = [(k, self._orders.pop(k, None)) for k in keys]
        items = [(k, item) for k, item in items if item]
        if not items or not self.enabled:return True
        ok = True
        for _key, item in items:
            oid=item.get("sl_order_id")
            if not oid:
                continue
            try:
                self.exchange.cancel_order(oid,symbol)
                self.logger(f"[NATIVE_PROTECTION] {symbol} SL cancelled id={oid}","INFO")
            except Exception as exc:
                ok = False
                self.logger(f"[NATIVE_PROTECTION] {symbol} cancel failed: {exc}","WARN")
        return ok

    def info(self,symbol,position_side=None):
        """Read-only snapshot of the tracked protective order.

        In Hedge mode the key includes LONG/SHORT so one symbol can safely
        carry independent protection orders for both legs.
        """
        if position_side is not None:
            item=self._orders.get(self._key(symbol, position_side))
            return dict(item) if item else None
        matches=[item for (sym,_leg), item in self._orders.items() if sym == str(symbol or "")]
        return dict(matches[0]) if len(matches) == 1 else None
