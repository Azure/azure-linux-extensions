from error_codes          import *
from errors               import is_error, get_input, print_errors
from .check_clconf        import check_customlog_conf

def check_custom_logs(interactive, prev_success=NO_ERROR):
    if (interactive):
        using_cl = get_input("Are you currently using custom logs? (y/n)",\
                            (lambda x : x.lower() in ['y','yes','n','no']),\
                            "Please type either 'y'/'yes' or 'n'/'no' to proceed.")
        # not using custom logs
        if (using_cl in ['n','no']):
            print("Continuing on with the rest of the troubleshooter...")
            print("================================================================================")
            return prev_success
        # using custom logs
        else:
            print("Continuing on with troubleshooter...")
            print("--------------------------------------------------------------------------------")

    print("CHECKING FOR CUSTOM LOG ISSUES...")

    success = prev_success


    # check td-agent.conf
    print("Checking for custom log configuration files...")
    checked_clconf = check_customlog_conf(interactive)
    if (is_error(checked_clconf)):
        return print_errors(checked_clconf)
    else:
        success = print_errors(checked_clconf)

    return success