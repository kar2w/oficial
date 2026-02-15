from enum import Enum


class RideStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    canceled = "canceled"
