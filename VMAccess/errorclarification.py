import enum

class ErrorCode(enum.Enum):
    SYSTEM_ERROR = 0
    USER_PASSWORD_ERROR = 1
    REPAIR_DISK_ERROR = 2
    CHECK_DISK_ERROR = 3
    CHECK_REPAIR_DISK_ERROR = 4