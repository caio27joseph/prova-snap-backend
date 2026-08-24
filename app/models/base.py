"""Shared declarative base and model-wide conventions.

Conventions applied by every model in this package (why-comments live here,
once, instead of repeated per column):

- PKs are UUIDv7 generated app-side (AI log Decisão 5, docs/ESCALABILIDADE.md):
  time-ordered, so a future keyset cursor is just `id > :cursor ORDER BY id`,
  and globally unique without coordination, so rows survive a functional shard
  split without PK rewrites.
- Time columns are `DateTime(timezone=True)` with `server_default=func.now()`
  (Decisão 7): the database is the single time source — N app instances mean
  N clocks, and clock skew in an audit trail is unacceptable.
"""

import uuid

import uuid_utils
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def uuid7() -> uuid.UUID:
    # uuid_utils.uuid7() returns its own UUID type; SQLAlchemy's UUID column
    # expects stdlib uuid.UUID, so rewrap the 16 raw bytes.
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
