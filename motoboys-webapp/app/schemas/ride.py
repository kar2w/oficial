from pydantic import BaseModel


class RideBase(BaseModel):
    courier_id: int


class RideRead(RideBase):
    id: int
