# JD Capital — Phase 1/2 implementation notes

## Compatibility decisions

- The existing v2 dashboard and HTTP paths remain available. Its `Ingresos`
  card preserves the previous cash-inflow presentation for compatibility, but
  the Financial Core metric `generated_income` excludes owner contributions.
- Existing v2 movements are not deleted. The original v1 floating-point tables,
  when encountered, are retained as `transactions_v1_archive` and
  `opportunities_v1_archive`. Normalized v2 movements are migrated once into the
  ledger and keep their original timestamp, note, kind and source id.
- Because the legacy model did not store a real account or provider, migrated
  cash is assigned to the explicit account `Legacy cash (unspecified)`. No bank,
  wallet, platform or exchange is inferred.

## Exact amounts in SQLite

SQLite has no fixed-precision decimal storage class. Financial Core therefore
stores signed integer `amount_minor` values and resolves their scale from each
asset's immutable `precision`. Domain inputs and outputs use `Decimal`/decimal
strings; Python `float` is rejected by the financial service.

## Transaction lifecycle

The service creates a transaction as `draft`, inserts all entries within one
`BEGIN IMMEDIATE` transaction and changes it to `posted` only after validation.
Database triggers reject unbalanced posting, cross-environment/account entries,
direct posting, invalid status transitions and destructive changes to posted
transactions or entries.

## Current scope boundary

- Financial Core v1 is implemented for the local SQLite runtime used by the
  Windows application. The existing PostgreSQL path remains available for the
  v2 tables, but the new ledger requires a future PostgreSQL-specific migration.
- Availability and transaction status are stored separately. This phase records
  the availability attached to every entry; a separate availability-event
  history is deferred until a workflow needs post-settlement state transitions.
- The v2 visual dashboard is intentionally retained. Full REAL/PRUEBA navigation
  and the redesigned accounts/ledger screens belong to the later UI phase.
