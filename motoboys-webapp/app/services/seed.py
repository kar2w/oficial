def seed_weekly_couriers(db, payload: dict):
    return {"ok": True, "count": len(payload.get("items", []))}
