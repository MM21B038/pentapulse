from enum import Enum

class Status(str, Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    PENDING = "pending"
    STARTED = "started"
    WORKING = "working"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    INPUT_REQUIRED = "input_required"