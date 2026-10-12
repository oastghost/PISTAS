from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

Role = Literal["despachante", "ana", "controlador", "handler"]
UUIDStr = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F-]{36}$")]


class CamelModel(BaseModel):
    """JSON in camelCase, the same shapes as src/types.ts in the frontend."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LoginIn(CamelModel):
    username: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class UserOut(CamelModel):
    id: str
    name: str
    role: Role
    company: str | None


class LoginOut(CamelModel):
    token: str
    user: UserOut


class StandOut(CamelModel):
    id: str
    name: str
    apron: str
    critical: str
    category: str
    max_wingspan_m: float


class AircraftTypeOut(CamelModel):
    code: str
    label: str
    category: str
    wingspan_m: float


class StandRequestIn(CamelModel):
    request_id: UUIDStr
    stand_id: Annotated[str, StringConstraints(min_length=1, max_length=8)]
    flight_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    aircraft_type: Annotated[str, StringConstraints(min_length=1, max_length=8)]
    start: datetime
    end: datetime
    handler: Annotated[str, StringConstraints(max_length=40)] | None = None

    @field_validator("start", "end")
    @classmethod
    def to_utc(cls, v: datetime) -> datetime:
        return _utc(v)


class ReservationOut(CamelModel):
    id: str
    request_id: str
    stand_id: str
    flight_number: str
    company: str
    aircraft_type: str
    start: datetime
    end: datetime
    status: Literal["approved", "removed"]
    handler: str | None


class NoticeOut(CamelModel):
    id: str
    reservation_id: str
    company: str
    message: str
    created_at: datetime


class ReportIn(CamelModel):
    reservation_id: UUIDStr
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ReportOut(CamelModel):
    id: str
    reservation_id: str
    text: str
    author: str
    created_at: datetime = Field(...)
