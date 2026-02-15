from types import SimpleNamespace

from app.services import pendings


class _FakeFilter:
    def __init__(self, obj):
        self.obj = obj

    def first(self):
        return self.obj


class _FakeQuery:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *args, **kwargs):
        return _FakeFilter(self.obj)


class _FakeDB:
    def __init__(self, group):
        self.group = group
        self.committed = False

    def query(self, _model):
        return _FakeQuery(self.group)

    def commit(self):
        self.committed = True


def test_resolve_yooga_approve_all_moves_unmatched_to_assignment(monkeypatch):
    grp = SimpleNamespace(status="PENDING")
    ride_ok = SimpleNamespace(status="PENDENTE_REVISAO", courier_id="c1", pending_reason="YOOGA_ASSINATURA_COLISAO")
    ride_unmatched = SimpleNamespace(status="PENDENTE_REVISAO", courier_id=None, pending_reason="YOOGA_ASSINATURA_COLISAO")
    db = _FakeDB(grp)

    monkeypatch.setattr(pendings, "yooga_group_items", lambda *_: [ride_ok, ride_unmatched])

    out = pendings.resolve_yooga(db, "group-1", "APPROVE_ALL", keep_ride_id=None)

    assert out["resolved"] == "APPROVE_ALL"
    assert ride_ok.status == "OK"
    assert ride_ok.pending_reason is None
    assert ride_unmatched.status == "PENDENTE_ATRIBUICAO"
    assert ride_unmatched.pending_reason == "NOME_NAO_CADASTRADO"
    assert grp.status == "RESOLVED"
    assert db.committed is True


def test_resolve_yooga_keep_one_discards_others(monkeypatch):
    grp = SimpleNamespace(status="PENDING")
    keep = SimpleNamespace(id="keep-me", status="PENDENTE_REVISAO", courier_id="c1", pending_reason="x")
    discard = SimpleNamespace(id="drop-me", status="PENDENTE_REVISAO", courier_id="c2", pending_reason="x")
    db = _FakeDB(grp)

    monkeypatch.setattr(pendings, "yooga_group_items", lambda *_: [keep, discard])

    out = pendings.resolve_yooga(db, "group-1", "KEEP_ONE", keep_ride_id="keep-me")

    assert out["resolved"] == "KEEP_ONE"
    assert keep.status == "OK"
    assert keep.pending_reason is None
    assert discard.status == "DESCARTADO"
    assert discard.pending_reason is None
    assert grp.status == "RESOLVED"
