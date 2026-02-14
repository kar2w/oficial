from pydantic import BaseModel


class WeekBase(BaseModel):
    label: str


class WeekRead(WeekBase):
    id: int
