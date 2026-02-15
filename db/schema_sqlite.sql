PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS weeks (
  id           TEXT PRIMARY KEY,
  closing_seq  INTEGER NOT NULL UNIQUE,
  start_date   TEXT NOT NULL,
  end_date     TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','PAID')),
  note         TEXT,
  created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (date(start_date) <= date(end_date))
);

CREATE TABLE IF NOT EXISTS couriers (
  id               TEXT PRIMARY KEY,
  nome_resumido    TEXT NOT NULL,
  nome_completo    TEXT,
  categoria        TEXT NOT NULL DEFAULT 'DIARISTA' CHECK (categoria IN ('SEMANAL','DIARISTA')),
  active           INTEGER NOT NULL DEFAULT 1,
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courier_payment (
  courier_id       TEXT PRIMARY KEY REFERENCES couriers(id) ON DELETE CASCADE,
  key_type         TEXT CHECK (key_type IN ('CPF','CNPJ','TELEFONE','EMAIL','ALEATORIA','OUTRO')),
  key_value_raw    TEXT,
  bank             TEXT,
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courier_aliases (
  id          TEXT PRIMARY KEY,
  courier_id  TEXT NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  alias_raw   TEXT NOT NULL,
  alias_norm  TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (courier_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS courier_aliases_norm_ix ON courier_aliases(alias_norm);

CREATE TABLE IF NOT EXISTS imports (
  id          TEXT PRIMARY KEY,
  source      TEXT NOT NULL CHECK (source IN ('SAIPOS','YOOGA')),
  filename    TEXT NOT NULL,
  file_hash   TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status      TEXT NOT NULL DEFAULT 'DONE',
  meta        TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS imports_source_hash_ux ON imports(source, file_hash);

CREATE TABLE IF NOT EXISTS rides (
  id                 TEXT PRIMARY KEY,
  source             TEXT NOT NULL CHECK (source IN ('SAIPOS','YOOGA')),
  import_id          TEXT NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  external_id        TEXT,
  source_row_number  INTEGER,
  signature_key      TEXT,
  order_dt           TEXT NOT NULL,
  delivery_dt        TEXT,
  order_date         TEXT NOT NULL,
  week_id            TEXT NOT NULL REFERENCES weeks(id) ON DELETE RESTRICT,
  courier_id         TEXT REFERENCES couriers(id) ON DELETE SET NULL,
  courier_name_raw   TEXT,
  courier_name_norm  TEXT,
  value_raw          NUMERIC NOT NULL,
  fee_type           INTEGER NOT NULL CHECK (fee_type IN (6,10)),
  is_cancelled       INTEGER,
  status             TEXT NOT NULL DEFAULT 'OK' CHECK (status IN ('OK','PENDENTE_ATRIBUICAO','PENDENTE_REVISAO','PENDENTE_MATCH','DESCARTADO')),
  pending_reason     TEXT,
  paid_in_week_id    TEXT REFERENCES weeks(id) ON DELETE SET NULL,
  meta               TEXT NOT NULL DEFAULT '{}',
  created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (date(order_date) = date(order_dt))
);

CREATE UNIQUE INDEX IF NOT EXISTS rides_saipos_external_ux
  ON rides(source, external_id)
  WHERE source = 'SAIPOS' AND external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS rides_yooga_import_row_ux
  ON rides(import_id, source_row_number)
  WHERE source = 'YOOGA' AND source_row_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS rides_week_courier_ix ON rides(week_id, courier_id);
CREATE INDEX IF NOT EXISTS rides_status_ix ON rides(status);
CREATE INDEX IF NOT EXISTS rides_signature_ix ON rides(signature_key) WHERE signature_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS rides_order_date_ix ON rides(order_date);

CREATE TABLE IF NOT EXISTS yooga_review_groups (
  id             TEXT PRIMARY KEY,
  week_id        TEXT NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  signature_key  TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RESOLVED')),
  created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (week_id, signature_key)
);

CREATE TABLE IF NOT EXISTS yooga_review_items (
  group_id   TEXT NOT NULL REFERENCES yooga_review_groups(id) ON DELETE CASCADE,
  ride_id    TEXT NOT NULL REFERENCES rides(id) ON DELETE CASCADE,
  PRIMARY KEY (group_id, ride_id)
);

CREATE TABLE IF NOT EXISTS ledger_entries (
  id               TEXT PRIMARY KEY,
  courier_id       TEXT NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  week_id          TEXT NOT NULL REFERENCES weeks(id) ON DELETE RESTRICT,
  effective_date   TEXT NOT NULL,
  type             TEXT NOT NULL CHECK (type IN ('EXTRA','VALE')),
  amount           NUMERIC NOT NULL CHECK (amount > 0),
  related_ride_id  TEXT REFERENCES rides(id) ON DELETE SET NULL,
  note             TEXT,
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ledger_week_courier_ix ON ledger_entries(week_id, courier_id);
CREATE INDEX IF NOT EXISTS ledger_effective_courier_ix ON ledger_entries(effective_date, courier_id);

CREATE TABLE IF NOT EXISTS loan_plans (
  id                TEXT PRIMARY KEY,
  courier_id        TEXT NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  total_amount      NUMERIC NOT NULL CHECK (total_amount > 0),
  n_installments    INTEGER NOT NULL CHECK (n_installments >= 1),
  rounding          TEXT NOT NULL DEFAULT 'REAL' CHECK (rounding IN ('REAL','CENT')),
  status            TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','PAUSED','DONE','CANCELLED')),
  start_closing_seq INTEGER NOT NULL,
  note              TEXT,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS loan_installments (
  id               TEXT PRIMARY KEY,
  plan_id          TEXT NOT NULL REFERENCES loan_plans(id) ON DELETE CASCADE,
  installment_no   INTEGER NOT NULL,
  due_closing_seq  INTEGER NOT NULL,
  amount           NUMERIC NOT NULL CHECK (amount > 0),
  paid_amount      NUMERIC NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
  status           TEXT NOT NULL DEFAULT 'DUE' CHECK (status IN ('DUE','PAUSED','PARTIAL','ROLLED','PAID','CANCELLED')),
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (plan_id, installment_no)
);
CREATE INDEX IF NOT EXISTS loan_installments_due_ix
  ON loan_installments(due_closing_seq)
  WHERE status IN ('DUE','ROLLED','PARTIAL');

CREATE TABLE IF NOT EXISTS loan_installment_applications (
  id              TEXT PRIMARY KEY,
  installment_id  TEXT NOT NULL REFERENCES loan_installments(id) ON DELETE CASCADE,
  week_id         TEXT NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  applied_amount  NUMERIC NOT NULL CHECK (applied_amount > 0),
  applied_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note            TEXT
);
CREATE INDEX IF NOT EXISTS loan_apps_week_ix ON loan_installment_applications(week_id);

CREATE TABLE IF NOT EXISTS week_payouts (
  week_id              TEXT NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  courier_id           TEXT NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  rides_amount         NUMERIC NOT NULL,
  extras_amount        NUMERIC NOT NULL,
  vales_amount         NUMERIC NOT NULL,
  installments_amount  NUMERIC NOT NULL,
  net_amount           NUMERIC NOT NULL,
  pending_count        INTEGER NOT NULL,
  is_flag_red          INTEGER NOT NULL DEFAULT 0,
  computed_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  paid_at              TEXT,
  PRIMARY KEY (week_id, courier_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id           TEXT PRIMARY KEY,
  created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actor        TEXT NOT NULL,
  role         TEXT,
  ip           TEXT,
  action       TEXT NOT NULL,
  entity_type  TEXT,
  entity_id    TEXT,
  meta         TEXT
);

CREATE INDEX IF NOT EXISTS audit_log_created_at_ix ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_ix ON audit_log(action);
CREATE INDEX IF NOT EXISTS audit_log_entity_ix ON audit_log(entity_type, entity_id);
