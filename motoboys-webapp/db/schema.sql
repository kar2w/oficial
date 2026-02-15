-- Este arquivo não é o schema oficial.
--
-- Fonte única de verdade:
--   ../db/schema.sql (na raiz do repositório)
--
-- Para aplicar manualmente a partir da raiz:
--   docker exec -i motoboys-db psql -U postgres -d motoboys < ./db/schema.sql
--
-- Este arquivo existe apenas para evitar ambiguidade para quem procurar schema dentro de
-- motoboys-webapp. Não adicione DDL aqui.

-- =========================
-- Audit Log (P4)
-- =========================
CREATE TABLE IF NOT EXISTS audit_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at   timestamptz NOT NULL DEFAULT now(),
  actor        text NOT NULL,
  role         text,
  ip           inet,
  action       text NOT NULL,
  entity_type  text,
  entity_id    uuid,
  meta         jsonb
);

CREATE INDEX IF NOT EXISTS audit_log_created_at_ix ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_ix ON audit_log(action);
CREATE INDEX IF NOT EXISTS audit_log_entity_ix ON audit_log(entity_type, entity_id);
