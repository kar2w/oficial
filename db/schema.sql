-- =========================
-- Extensions
-- =========================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- =========================
-- Enums
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'week_status') THEN
    CREATE TYPE week_status AS ENUM ('OPEN','CLOSED','PAID');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'courier_category') THEN
    CREATE TYPE courier_category AS ENUM ('SEMANAL','DIARISTA');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'import_source') THEN
    CREATE TYPE import_source AS ENUM ('SAIPOS','YOOGA');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ride_status') THEN
    CREATE TYPE ride_status AS ENUM (
      'OK',
      'PENDENTE_ATRIBUICAO',
      'PENDENTE_REVISAO',
      'PENDENTE_MATCH',
      'DESCARTADO'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ledger_type') THEN
    CREATE TYPE ledger_type AS ENUM ('EXTRA','VALE');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_key_type') THEN
    CREATE TYPE payment_key_type AS ENUM ('CPF','CNPJ','TELEFONE','EMAIL','ALEATORIA','OUTRO');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'loan_status') THEN
    CREATE TYPE loan_status AS ENUM ('ACTIVE','PAUSED','DONE','CANCELLED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'installment_status') THEN
    CREATE TYPE installment_status AS ENUM ('DUE','PAUSED','PARTIAL','ROLLED','PAID','CANCELLED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rounding_mode') THEN
    CREATE TYPE rounding_mode AS ENUM ('REAL','CENT');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') THEN
    CREATE TYPE review_status AS ENUM ('PENDING','RESOLVED');
  END IF;
END$$;

-- =========================
-- Sequences
-- =========================
CREATE SEQUENCE IF NOT EXISTS week_closing_seq_seq;

-- =========================
-- Weeks (Qui->Qua editável, sem sobreposição)
-- =========================
CREATE TABLE IF NOT EXISTS weeks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  closing_seq  bigint NOT NULL DEFAULT nextval('week_closing_seq_seq'),
  start_date   date NOT NULL,
  end_date     date NOT NULL,
  status       week_status NOT NULL DEFAULT 'OPEN',
  note         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (start_date <= end_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS weeks_closing_seq_ux ON weeks(closing_seq);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'weeks_no_overlap'
  ) THEN
    ALTER TABLE weeks ADD CONSTRAINT weeks_no_overlap
      EXCLUDE USING gist (daterange(start_date, end_date, '[]') WITH &&);
  END IF;
END$$;

-- =========================
-- Couriers
-- =========================
CREATE TABLE IF NOT EXISTS couriers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome_resumido    text NOT NULL,
  nome_completo    text,
  categoria        courier_category NOT NULL DEFAULT 'DIARISTA',
  active           boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courier_payment (
  courier_id       uuid PRIMARY KEY REFERENCES couriers(id) ON DELETE CASCADE,
  key_type         payment_key_type,
  key_value_raw    text,
  bank             text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courier_aliases (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  courier_id  uuid NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  alias_raw   text NOT NULL,
  alias_norm  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (courier_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS courier_aliases_norm_ix ON courier_aliases(alias_norm);

-- =========================
-- Imports
-- =========================
CREATE TABLE IF NOT EXISTS imports (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source      import_source NOT NULL,
  filename    text NOT NULL,
  file_hash   text NOT NULL,
  imported_at timestamptz NOT NULL DEFAULT now(),
  status      text NOT NULL DEFAULT 'DONE',
  meta        jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS imports_source_hash_ux ON imports(source, file_hash);

-- =========================
-- Rides
-- =========================
CREATE TABLE IF NOT EXISTS rides (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source             import_source NOT NULL,
  import_id          uuid NOT NULL REFERENCES imports(id) ON DELETE CASCADE,

  external_id         text,
  source_row_number   int,
  signature_key       text,

  order_dt            timestamp NOT NULL,
  delivery_dt         timestamp,
  order_date          date NOT NULL,

  week_id             uuid NOT NULL REFERENCES weeks(id) ON DELETE RESTRICT,
  courier_id          uuid REFERENCES couriers(id) ON DELETE SET NULL,

  courier_name_raw    text,
  courier_name_norm   text,

  value_raw           numeric(12,2) NOT NULL,
  fee_type            smallint NOT NULL CHECK (fee_type IN (6,10)),

  is_cancelled        boolean,
  status              ride_status NOT NULL DEFAULT 'OK',
  pending_reason      text,

  paid_in_week_id     uuid REFERENCES weeks(id) ON DELETE SET NULL,

  meta                jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),

  CHECK (order_date = (order_dt::date))
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

-- =========================
-- Yooga review groups
-- =========================
CREATE TABLE IF NOT EXISTS yooga_review_groups (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  week_id        uuid NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  signature_key  text NOT NULL,
  status         review_status NOT NULL DEFAULT 'PENDING',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (week_id, signature_key)
);

CREATE TABLE IF NOT EXISTS yooga_review_items (
  group_id   uuid NOT NULL REFERENCES yooga_review_groups(id) ON DELETE CASCADE,
  ride_id    uuid NOT NULL REFERENCES rides(id) ON DELETE CASCADE,
  PRIMARY KEY (group_id, ride_id)
);

-- =========================
-- Ledger (extras/vales)
-- =========================
CREATE TABLE IF NOT EXISTS ledger_entries (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  courier_id       uuid NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  week_id          uuid NOT NULL REFERENCES weeks(id) ON DELETE RESTRICT,
  effective_date   date NOT NULL,
  type             ledger_type NOT NULL,
  amount           numeric(12,2) NOT NULL CHECK (amount > 0),
  related_ride_id  uuid REFERENCES rides(id) ON DELETE SET NULL,
  note             text,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ledger_week_courier_ix ON ledger_entries(week_id, courier_id);
CREATE INDEX IF NOT EXISTS ledger_effective_courier_ix ON ledger_entries(effective_date, courier_id);

-- =========================
-- Loans (future MVP+)
-- =========================
CREATE TABLE IF NOT EXISTS loan_plans (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  courier_id        uuid NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  total_amount      numeric(12,2) NOT NULL CHECK (total_amount > 0),
  n_installments    int NOT NULL CHECK (n_installments >= 1),
  rounding          rounding_mode NOT NULL DEFAULT 'REAL',
  status            loan_status NOT NULL DEFAULT 'ACTIVE',
  start_closing_seq bigint NOT NULL,
  note              text,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS loan_installments (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id          uuid NOT NULL REFERENCES loan_plans(id) ON DELETE CASCADE,
  installment_no   int NOT NULL,
  due_closing_seq  bigint NOT NULL,
  amount           numeric(12,2) NOT NULL CHECK (amount > 0),
  paid_amount      numeric(12,2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
  status           installment_status NOT NULL DEFAULT 'DUE',
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (plan_id, installment_no)
);

CREATE INDEX IF NOT EXISTS loan_installments_due_ix
  ON loan_installments(due_closing_seq)
  WHERE status IN ('DUE','ROLLED','PARTIAL');

CREATE TABLE IF NOT EXISTS loan_installment_applications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  installment_id  uuid NOT NULL REFERENCES loan_installments(id) ON DELETE CASCADE,
  week_id         uuid NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  applied_amount  numeric(12,2) NOT NULL CHECK (applied_amount > 0),
  applied_at      timestamptz NOT NULL DEFAULT now(),
  note            text
);
CREATE INDEX IF NOT EXISTS loan_apps_week_ix ON loan_installment_applications(week_id);

-- =========================
-- Snapshot (future MVP+)
-- =========================
CREATE TABLE IF NOT EXISTS week_payouts (
  week_id             uuid NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
  courier_id          uuid NOT NULL REFERENCES couriers(id) ON DELETE CASCADE,
  rides_amount         numeric(12,2) NOT NULL,
  extras_amount        numeric(12,2) NOT NULL,
  vales_amount         numeric(12,2) NOT NULL,
  installments_amount  numeric(12,2) NOT NULL,
  net_amount           numeric(12,2) NOT NULL,
  pending_count        int NOT NULL,
  is_flag_red          boolean NOT NULL DEFAULT false,
  computed_at          timestamptz NOT NULL DEFAULT now(),
  paid_at              timestamptz,
  PRIMARY KEY (week_id, courier_id)
);
