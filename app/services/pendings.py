def list_assignment(db):
    return []


def assign_ride(db, ride_id: str, courier_id: str, pay_in_current_week: bool = False):
    class _Ride:
        id = ride_id
        paid_in_week_id = None

    return _Ride()


def list_yooga_groups(db):
    return []


def yooga_group_items(db, group_id: str):
    return []


def resolve_yooga(db, group_id: str, action: str, keep_ride_id: str | None = None):
    return {"ok": True}
