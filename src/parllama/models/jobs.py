"""Data classes for job queue"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class QueueJob(BaseModel):
    """Base job"""

    id: UUID = Field(default_factory=uuid4)
    modelName: str


class PushModelJob(QueueJob):
    """Push model job"""


class PullModelJob(QueueJob):
    """Pull model job"""


class DeleteModelJob(QueueJob):
    """Delete model job"""


class CopyModelJob(QueueJob):
    """Copy model job"""

    dstModelName: str


class CreateModelJob(QueueJob):
    """Create model job"""

    modelCode: str
    quantizationLevel: str | None
