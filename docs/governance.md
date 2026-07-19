# Governance

Consequential changes require a role-matched approval. The approval is bound to the case version and exact change-set digest. Any case change makes it stale. Posting additionally requires an idempotency key and is transactional.

Hard stops include circular or self-referential BOMs, missing critical safety/regulatory data, ambiguous duplicates, missing approval, stale approval, and failed impact analysis. The system never autonomously merges items, selects a substitute, approves an ECO, scraps stock, cancels a PO, or posts unapproved data.
