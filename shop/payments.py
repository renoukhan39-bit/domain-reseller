"""Razorpay HTTP integration. Never accept payment evidence from browser alone."""
import hashlib
import hmac
import re
import requests
from django.conf import settings


class PaymentError(Exception):
    pass


def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    if (not isinstance(body, bytes) or not isinstance(secret, str) or not secret
            or not isinstance(signature, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", signature)):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def valid_gateway_id(value, prefix):
    """Gateway IDs are path segments, never caller-supplied URL paths."""
    return (isinstance(value, str) and len(value) <= 80
            and re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_]+", value) is not None)


def _identifier(value, prefix):
    if not valid_gateway_id(value, prefix):
        raise PaymentError("Invalid payment gateway identifier")
    return value


class Razorpay:
    ROOT = "https://api.razorpay.com/v1"

    def __init__(self, session=None):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise PaymentError("Razorpay API credentials missing")
        self.session = session or requests.Session()
        self.auth = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)

    def _request(self, method, path, payload=None):
        try:
            response = self.session.request(method, self.ROOT + path,
                                            auth=self.auth, json=payload, timeout=20,
                                            allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise PaymentError("Payment gateway returned an unsuccessful response")
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise PaymentError("Unexpected payment gateway response")
            return result
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise PaymentError("Payment gateway operation failed") from exc

    def create_order(self, order):
        # receipt is deterministic; if request times out, reconcile before trying again.
        return self._request("POST", "/orders", {
            "amount": order.amount_paise, "currency": "INR",
            "receipt": str(order.id)[:40], "notes": {"domain": order.domain, "operation": order.operation},
        })

    def fetch_payment(self, payment_id):
        _identifier(payment_id, "pay_")
        return self._request("GET", f"/payments/{payment_id}")

    def fetch_order(self, order_id):
        _identifier(order_id, "order_")
        return self._request("GET", f"/orders/{order_id}")

    def fetch_order_payments(self, order_id):
        _identifier(order_id, "order_")
        return self._request("GET", f"/orders/{order_id}/payments")

    def fetch_refund(self, refund_id):
        _identifier(refund_id, "rfnd_")
        return self._request("GET", f"/refunds/{refund_id}")

    def refund_payment(self, payment_id, amount_paise):
        _identifier(payment_id, "pay_")
        if type(amount_paise) is not int or amount_paise <= 0:
            raise PaymentError("Invalid refund amount")
        return self._request("POST", f"/payments/{payment_id}/refund", {"amount": amount_paise})
