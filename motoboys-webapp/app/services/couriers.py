from types import SimpleNamespace


def list_couriers(db, active=None, categoria=None, q=None):
    return []


def create_courier(db, nome_resumido, nome_completo, categoria, active=True):
    return SimpleNamespace(id="1", nome_resumido=nome_resumido, nome_completo=nome_completo, categoria=categoria, active=active)


def patch_courier(db, courier_id, nome_resumido=None, nome_completo=None, categoria=None, active=None):
    return SimpleNamespace(
        id=courier_id,
        nome_resumido=nome_resumido or "",
        nome_completo=nome_completo,
        categoria=categoria or "SEMANAL",
        active=True if active is None else active,
    )


def add_alias(db, courier_id, alias_raw):
    return SimpleNamespace(id="1", courier_id=courier_id, alias_raw=alias_raw, alias_norm=alias_raw.upper())


def delete_alias(db, courier_id, alias_id):
    return None


def upsert_payment(db, courier_id, key_type, key_value_raw, bank=None):
    return SimpleNamespace(courier_id=courier_id, key_type=key_type, key_value_raw=key_value_raw, bank=bank)


def get_courier_or_404(db, courier_id):
    return SimpleNamespace(id=courier_id)
