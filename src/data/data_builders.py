"""
Dynamic Test Data Builder.

Design pattern: Builder — chain `.with_x()` calls to construct a complex
test entity step by step, then `.build()` to materialize it. Prevents
constructor calls with 15 positional args and lets a base "sane default"
entity be tweaked minimally per test (only override what that test cares
about), which is the #1 reason hand-written fixture data drifts out of
sync with the real domain model over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from faker import Faker

_fake = Faker()


@dataclass
class UserData:
    first_name: str
    last_name: str
    email: str
    username: str
    password: str
    phone_number: str
    address: str
    zip_code: str
    extra: dict = field(default_factory=dict)


class UserDataBuilder:
    def __init__(self) -> None:
        self._first_name = _fake.first_name()
        self._last_name = _fake.last_name()
        self._email = _fake.unique.email()
        self._username = _fake.unique.user_name()
        self._password = _fake.password(length=12, special_chars=True, digits=True)
        self._phone_number = _fake.phone_number()
        self._address = _fake.street_address()
        self._zip_code = _fake.postcode()
        self._extra: dict = {}

    def with_first_name(self, value: str) -> "UserDataBuilder":
        self._first_name = value
        return self

    def with_last_name(self, value: str) -> "UserDataBuilder":
        self._last_name = value
        return self

    def with_email(self, value: str) -> "UserDataBuilder":
        self._email = value
        return self

    def with_username(self, value: str) -> "UserDataBuilder":
        self._username = value
        return self

    def with_password(self, value: str) -> "UserDataBuilder":
        self._password = value
        return self

    def with_zip_code(self, value: str) -> "UserDataBuilder":
        self._zip_code = value
        return self

    def with_extra(self, key: str, value) -> "UserDataBuilder":
        self._extra[key] = value
        return self

    def build(self) -> UserData:
        return UserData(
            first_name=self._first_name,
            last_name=self._last_name,
            email=self._email,
            username=self._username,
            password=self._password,
            phone_number=self._phone_number,
            address=self._address,
            zip_code=self._zip_code,
            extra=dict(self._extra),
        )


def random_credit_card() -> dict[str, str]:
    """Faker's built-in test-safe (non-real) card generator — for payment-flow tests."""
    return {
        "number": _fake.credit_card_number(),
        "expiry": _fake.credit_card_expire(),
        "cvv": _fake.credit_card_security_code(),
        "holder_name": _fake.name(),
    }
