# Architecture

ReleaseFlow uses one orchestrator and bounded typed services. FastAPI accepts evidence and commands, Pydantic validates boundaries, SQLAlchemy persists operational state, NetworkX evaluates BOM graphs, and React presents control gates. The posting adapter writes only to synthetic ERP/PLM tables in the same transaction. A later enterprise adapter must preserve the approval digest, idempotency key, snapshots, and audit contract.

The workflow state registry is authoritative. Each accepted or rejected transition emits an audit event. Candidate extraction cannot mutate master records; proposed changes remain isolated until a current role-approved token is presented.
