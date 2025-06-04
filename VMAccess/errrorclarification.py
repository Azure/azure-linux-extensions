import enum

class ErrorCode(enum.Enum):
    SYSTEM_ERROR = 0
    USER_ERROR = 1
    USER_PASSWORD_ERROR = 2
    REPAIR_DISK_ERROR = 3
    CHECK_DISK_ERROR = 4
    CHECK_REPAIR_DISK_ERROR = 5