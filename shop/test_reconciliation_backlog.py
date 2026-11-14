"""M5-09 operator-monitoring tests use local ORM fixtures only."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import AuditEntry, DomainOrder, PaymentEvent


@override_settings(SALES_ENABLED=False, FULFILLMENT_ENABLED=False)
class ReconciliationBacklogMonitorTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            "monitor-customer", "private-contact@example.test"
        )

    def create_order(self, status, name, age_minutes=0):
        order = DomainOrder.objects.create(
            owner=self.customer,
            domain=name,
            operation=DomainOrder.REGISTER,
            amount_paise=129900,
            idempotency_key=name,
            status=status,
            razorpay_order_id="order_" + name.replace(".", "_"),
        )
        if age_minutes:
            DomainOrder.objects.filter(pk=order.pk).update(
                updated_at=timezone.now() - timedelta(minutes=age_minutes)
            )
            order.refresh_from_db()
        return order

    def create_event(self, event_id, outcome, *, age_minutes=0,
                     event_type="payment.captured", processed=True):
        event = PaymentEvent.objects.create(
            event_id=event_id,
            event_type=event_type,
            payload_sha256="a" * 64,
            outcome=outcome,
            processed_at=timezone.now() if processed else None,
        )
        if age_minutes:
            PaymentEvent.objects.filter(pk=event.pk).update(
                received_at=timezone.now() - timedelta(minutes=age_minutes)
            )
            event.refresh_from_db()
        return event

    def report(self, **kwargs):
        output = StringIO()
        call_command("check_reconciliation_backlog", stdout=output, **kwargs)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        return json.loads(output.getvalue())

    def test_clean_database_is_healthy_and_sends_no_external_requests(self):
        with patch("requests.sessions.Session.request") as network:
            report = self.report()
        network.assert_not_called()
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["minimum_age_minutes"], 30)
        self.assertEqual(report["alert_categories"], [])
        self.assertTrue(all(v == 0 for v in report["counts"].values()))

    def test_recent_in_flight_work_does_not_trigger_false_alerts(self):
        self.create_order(DomainOrder.PAID, "recentpaid.com", age_minutes=10)
        self.create_order(DomainOrder.PROCESSING, "recentprocessing.com", age_minutes=10)
        self.create_order(DomainOrder.REFUND_PENDING, "recentrefund.com", age_minutes=10)
        self.create_event("evt_recent", "waiting_order", age_minutes=10)
        self.assertEqual(self.report()["status"], "ok")

    def test_stale_and_review_states_are_separately_classified(self):
        orders = [
            self.create_order(DomainOrder.REVIEW, "manualreview.com"),
            self.create_order(DomainOrder.PAID, "unfulfilled.com", age_minutes=45),
            self.create_order(DomainOrder.PROCESSING, "staleprocessing.com", age_minutes=45),
            self.create_order(DomainOrder.REFUND_REVIEW, "refundreview.com"),
            self.create_order(DomainOrder.REFUND_PENDING, "stalerefund.com", age_minutes=45),
        ]
        self.create_event("evt_waiting", "waiting_order", age_minutes=45)
        self.create_event("evt_badamount", "unmatched_payment_review")
        self.create_event("evt_conflict", "payment_conflict_review")

        original_order_states = [
            (o.pk, o.status, o.updated_at) for o in orders
        ]
        events_before = PaymentEvent.objects.count()
        audits_before = AuditEntry.objects.count()
        with patch("requests.sessions.Session.request") as network:
            report = self.report(warn_only=True)

        network.assert_not_called()
        self.assertEqual(report["status"], "alert")
        self.assertEqual(report["counts"]["manual_review_orders"], 1)
        self.assertEqual(report["counts"]["stale_paid_orders"], 1)
        self.assertEqual(report["counts"]["stale_processing_orders"], 1)
        self.assertEqual(report["counts"]["refund_review_orders"], 1)
        self.assertEqual(report["counts"]["stale_refund_pending_orders"], 1)
        self.assertEqual(report["counts"]["stale_waiting_payment_events"], 1)
        self.assertEqual(report["counts"]["payment_event_conflicts"], 2)
        self.assertEqual(report["counts"]["stale_unprocessed_payment_events"], 0)
        self.assertEqual(AuditEntry.objects.count(), audits_before)
        self.assertEqual(PaymentEvent.objects.count(), events_before)
        self.assertEqual(
            [(pk, DomainOrder.objects.get(pk=pk).status,
              DomainOrder.objects.get(pk=pk).updated_at)
             for pk, _, _ in original_order_states],
            original_order_states,
        )

    def test_alert_defaults_to_nonzero_exit_with_json_on_stdout(self):
        self.create_order(DomainOrder.REVIEW, "reviewexample.com")
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "requires operator review"):
            call_command("check_reconciliation_backlog", stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "alert")
        self.assertEqual(report["counts"]["manual_review_orders"], 1)

    def test_never_prints_customer_domain_email_or_gateway_identifiers(self):
        self.create_order(DomainOrder.REVIEW, "privatebusiness.com")
        output = StringIO()
        call_command("check_reconciliation_backlog", stdout=output, warn_only=True)
        report = output.getvalue()
        for sensitive in ("privatebusiness.com", "private-contact@example.test",
                          "monitor-customer", "order_privatebusiness_com"):
            self.assertNotIn(sensitive, report)

    def test_legacy_ignored_and_unprocessed_events_are_visible(self):
        self.create_event("evt_legacy", "ignored")
        self.create_event("evt_unprocessed", "", processed=False,
                          age_minutes=45, event_type="payment.authorized")
        report = self.report(warn_only=True)
        self.assertEqual(report["counts"]["legacy_ignored_captures"], 1)
        self.assertEqual(report["counts"]["stale_unprocessed_payment_events"], 1)

    def test_age_limit_validation(self):
        for minutes in (-1, 0, 4, 10081):
            with self.subTest(minutes=minutes):
                with self.assertRaisesMessage(CommandError, "between 5 and 10080"):
                    call_command("check_reconciliation_backlog",
                                 minutes=minutes, stdout=StringIO())

    def test_custom_minimum_age_threshold_changes_only_staleness(self):
        self.create_order(DomainOrder.PROCESSING, "threshold.com", age_minutes=40)
        self.assertEqual(self.report(minutes=60)["status"], "ok")
        report = self.report(minutes=30, warn_only=True)
        self.assertEqual(report["counts"]["stale_processing_orders"], 1)
