import enum

class ErrorCode(enum.Enum):
    CHECK_REPAIR_DISK_ERROR = -3
    REPAIR_DISK_ERROR = -2
    CHECK_DISK_ERROR = -1

    SYSTEM_ERROR = 0
    
    USER_PASSWORD_ERROR = 1
