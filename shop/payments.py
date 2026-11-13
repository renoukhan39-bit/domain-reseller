"""Razorpay HTTP integration. Never accept payment evidence from browser alone."""
import hashlib
import hmac
import requests
from django.conf import settings


class PaymentError(Exception):
    pass


def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


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
                                            auth=self.auth, json=payload, timeout=20)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaymentError("Payment gateway operation failed") from exc

    def create_order(self, order):
        # receipt is deterministic; if request times out, reconcile before trying again.
        return self._request("POST", "/orders", {
            "amount": order.amount_paise, "currency": "INR",
            "receipt": str(order.id)[:40], "notes": {"domain": order.domain, "operation": order.operation},
        })

    def fetch_payment(self, payment_id):
        if not payment_id.startswith("pay_") or len(payment_id) > 80:
            raise PaymentError("Invalid payment identifier")
        return self._request("GET", f"/payments/{payment_id}")

    def refund_payment(self, payment_id, amount_paise):
        if not payment_id.startswith("pay_"):
            raise PaymentError("Invalid payment identifier")
        return self._request("POST", f"/payments/{payment_id}/refund", {"amount": amount_paise})
