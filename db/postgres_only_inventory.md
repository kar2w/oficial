# Inventário de objetos Postgres-only (`db/schema.sql`)

## Extensions
- `pgcrypto` (usada por `gen_random_uuid()`).
- `btree_gist` (suporte ao `EXCLUDE USING gist`).

## Enums nativos
- `week_status`
- `courier_category`
- `import_source`
- `ride_status`
- `ledger_type`
- `payment_key_type`
- `loan_status`
- `installment_status`
- `rounding_mode`
- `review_status`

## Tipos e expressões específicas
- `jsonb` (`imports.meta`, `rides.meta`, `audit_log.meta`).
- Casts `::jsonb`.
- `inet` (`audit_log.ip`).
- `uuid` com default `gen_random_uuid()`.
- sequence + `nextval('week_closing_seq_seq')`.
- `timestamptz` e `now()`.

## Constraints/índices específicos
- `EXCLUDE USING gist (daterange(start_date, end_date, '[]') WITH &&)` para não sobrepor semanas.
- Índices parciais (também suportados em SQLite moderno, mas originalmente usados no desenho Postgres):
  - `rides_saipos_external_ux`
  - `rides_yooga_import_row_ux`
  - `rides_signature_ix`
  - `loan_installments_due_ix`
