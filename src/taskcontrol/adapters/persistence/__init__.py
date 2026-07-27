"""Relational persistence: storage models, explicit mappers, and repositories.

Storage models are not domain objects and never leave this package. Repositories take and
return domain objects, so nothing above this layer knows how data is shaped on disk.
"""

from __future__ import annotations

from taskcontrol.adapters.persistence.models import Base, TaskRecord, TaskRevisionRecord
from taskcontrol.adapters.persistence.repositories import (
    SqlAlchemyTaskRepository,
    SqlAlchemyTaskRevisionRepository,
)
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork

__all__ = [
    "Base",
    "SqlAlchemyTaskRepository",
    "SqlAlchemyTaskRevisionRepository",
    "TaskRecord",
    "TaskRevisionRecord",
    "UnitOfWork",
]
