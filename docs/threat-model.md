# Threat model

| Threat | Control |
|---|---|
| Path traversal or malicious filename | Filename sanitization, generated storage names, no caller-controlled filesystem path |
| Oversized or unsupported input | Allowlisted extensions/MIME types and configurable 10 MB limit |
| Prompt or document injection | Extracted values are untrusted data, schema-checked, evidence-linked, and deterministically validated |
| Unauthorized decision | Server-side demo-user role enforcement |
| Approval replay | Token hash bound to case version and exact change set |
| Duplicate posting | Unique idempotency key and transactional write |
| Partial write | Database rollback and explicit rolled-back transaction record |
| Sensitive logging | Structured metadata only; no document bodies or secrets |
| SQL injection | SQLAlchemy parameterized statements |

Demo headers are not production identity. Production use requires SSO, durable secret storage, malware scanning, object storage, PostgreSQL, rate limiting, and separately secured enterprise adapters.
