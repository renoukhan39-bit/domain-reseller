# Security and responsible disclosure

Treat all domain registration and payment workflows as financially sensitive. Do not post live credentials, registry API responses containing registrant personal information, or webhook payloads with private data in public issues.

Before a live launch: obtain an independent review, verify HTTPS/CSRF/tenant isolation, configure distributed throttling, test full database restoration, and reconcile all external payment and registrar side effects. A passed source compile is not a security audit. Disable sales and fulfillment via environment flags in an incident.

Security reports: contact the repository owner privately through an approved channel; do not publish exploit details or customer information.
