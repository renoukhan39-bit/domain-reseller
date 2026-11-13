# Operator/provider setup checklist

**Never commit API credentials or customer personal data. Never initiate live purchases without explicit owner approval.**

## Openprovider
- [ ] Create authorized reseller and isolated sandbox accounts.
- [ ] Review official current API/version support; earlier `/v1beta` implementations must be audited for compatibility with `/v1`.
- [ ] Validate sandbox auth, availability and premium status, contact creation, registration, renewal, name server management, errors/timeouts and status reconciliation.
- [ ] Check supported TLDs, actual wholesale pricing, transfer/registry restrictions and account funding.

## Razorpay
- [ ] Use test mode API keys plus a separate webhook signing secret.
- [ ] Verify captured-payment signature against raw webhook body; test duplicated/reordered events and amount/currency mismatch.
- [ ] Review KYC, checkout restrictions, refunds, tax and payout settlement before live payments.

## Cloud
- [ ] Verify AWS/Azure credits and expiration, cloud budget alerts, eligible services and secret storage.
- [ ] Provision least-privilege IAM, TLS, private DB, secure email, monitoring and backups after owner approval.
- [ ] Test restore and rollback before launch.
