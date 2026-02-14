def list_week_ledger(db, week_id: str, courier_id: str | None = None):
    return []


def create_ledger_entry(db, courier_id: str, week_id: str, effective_date, type: str, amount: float, related_ride_id=None, note=None):
    return {
        "id": "1",
        "courier_id": courier_id,
        "week_id": week_id,
        "effective_date": effective_date,
        "type": type,
        "amount": amount,
        "related_ride_id": related_ride_id,
        "note": note,
    }


def delete_ledger_entry(db, ledger_id: str):
    return {"ok": True, "id": ledger_id}
