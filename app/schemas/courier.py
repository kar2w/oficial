from pydantic import BaseModel


class CourierBase(BaseModel):
    name: str


class CourierRead(CourierBase):
    id: int
