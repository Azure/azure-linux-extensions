from error_codes          import *
from errors               import is_error, print_errors
from .check_logrot        import check_log_rotation
from .check_usage         import check_usage

def check_high_cpu_memory(interactive, prev_success=NO_ERROR):
    print("CHECKING FOR HIGH CPU / MEMORY USAGE...")

    success = prev_success

    # check log rotation
    print("Checking if log rotation is working correctly...")
    checked_logrot = check_log_rotation()
    if (is_error(checked_logrot)):
        return print_errors(checked_logrot)
    else:
        success = print_errors(checked_logrot)

    # check AMA CPU/memory usage
    checked_usage = check_usage(interactive)
    if (is_error(checked_usage)):
        return print_errors(checked_usage)
    else:
        success = print_errors(checked_usage)
    return success