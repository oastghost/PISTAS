from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

Role = Literal["despachante", "ana", "ana_supervisor", "controlador", "handler"]
UUIDStr = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F-]{36}$")]

# Aircraft registration as painted on the tail: CS-TNP, D-AIUA, N123AB. Hyphen optional.
Registration = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z0-9]{1,2}-?[A-Z0-9]{2,5}$"),
]
# ICAO airport code of the origin: four letters (LEMD, EGLL).
IcaoCode = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z]{4}$"),
]


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
    must_change_password: bool = False
    # What a dispatcher's flight numbers must start with. Empty for everyone else.
    flight_prefixes: list[str] = []


class ChangePasswordIn(CamelModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    new_password: Annotated[str, StringConstraints(min_length=12, max_length=200)]


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
    registration: Registration
    # The ARRIVAL flight. The aircraft leaves under another number, so it is only information.
    flight_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    origin: IcaoCode
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
    registration: str
    flight_number: str
    origin: str
    company: str
    aircraft_type: str
    start: datetime
    end: datetime
    status: Literal["approved", "removed"]
    handler: str | None
    requested_by: str | None = None  # the dispatcher who made the request


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
    registration: str
    flight_number: str
    aircraft_type: str
    stand_id: str
    created_at: datetime = Field(...)


# --- account administration (ana_supervisor) ---

Username = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9._-]{3,40}$")
]
Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
NewPassword = Annotated[str, StringConstraints(min_length=12, max_length=200)]


Prefix = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z0-9]{2,3}$"),
]


class AirlineOut(CamelModel):
    name: str
    prefixes: list[str]
    dispatchers: int
    active_dispatchers: int


class AirlineIn(CamelModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=40)]
    prefixes: Annotated[list[Prefix], Field(min_length=1, max_length=6)]


class PrefixIn(CamelModel):
    prefix: Prefix


class AccountOut(CamelModel):
    id: str
    username: str
    name: str
    email: str | None
    role: Role
    company: str | None
    active: bool


class AccountIn(CamelModel):
    username: Username
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    email: Email
    role: Literal["despachante", "ana"]
    company: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    password: NewPassword


class AccountPatch(CamelModel):
    active: bool | None = None
    password: NewPassword | None = None


class AuditOut(CamelModel):
    id: int
    at: datetime
    username: str | None
    action: str
    detail: str | None
