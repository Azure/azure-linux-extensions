import os
import sys

from helpers        import get_input
from logcollector   import run_logcollector
from error_codes    import *
from errors         import get_input, is_error, err_summary
from install.install import check_installation
from connect.connect import check_connection
from general_health.general_health  import check_general_health
from high_cpu_mem.high_cpu_mem      import check_high_cpu_memory
from syslog_tst.syslog                  import check_syslog
from custom_logs.custom_logs        import check_custom_logs
from metrics_troubleshooter.metrics_troubleshooter import run_metrics_troubleshooter

# check to make sure the user is running as root
def check_sudo():
    if (os.geteuid() != 0):
        print("The troubleshooter is not currently being run as root. In order to have accurate results, we ask that you run this troubleshooter as root.")
        print("NOTE: it will not add, modify, or delete any files without express permission.")
        print("Please try running the troubleshooter again with 'sudo'. Thank you!")
        return False
    else:
        return True

def check_all(interactive):
    """
    Run all troubleshooter checks, continuing even if errors occur.
    Collects all results and reports the most severe issue at the end.
    """
    checks = [
        ("Installation", check_installation),
        ("Connection", check_connection),
        ("General Health", check_general_health),
        ("High CPU/Memory Usage", check_high_cpu_memory),
        ("Syslog", check_syslog),
        ("Custom logs", check_custom_logs),
        ("Metrics", run_metrics_troubleshooter),
    ]
    
    results = []
    overall_status = NO_ERROR
    
    for i, (check_name, check_func) in enumerate(checks, 1):
        print("================================================================================")
        print("Running check {0}/7: {1}...".format(i, check_name))
        
        try:
            result = check_func(interactive)
            results.append((check_name, result))
            
            # Track the most severe error (higher error codes are more severe)
            if is_error(result) and result > overall_status:
                overall_status = result
            elif not is_error(result) and result > overall_status and overall_status == NO_ERROR:
                overall_status = result
                
            # Print immediate result for this check
            if is_error(result):
                print("[ERROR] {0}: ERROR (code {1})".format(check_name, result))
            elif result != NO_ERROR:
                print("[WARN]  {0}: WARNING (code {1})".format(check_name, result))
            else:
                print("[OK]    {0}: OK".format(check_name))
                
        except Exception as e:
            print("[EXCEPTION] {0}: EXCEPTION - {1}".format(check_name, str(e)))
            results.append((check_name, "EXCEPTION: {0}".format(str(e))))
            overall_status = ERR_FOUND  # Set a generic error code
    
    # Summary of all results
    print("\n================================================================================")
    print("SUMMARY OF ALL CHECKS:")
    print("================================================================================")
    for check_name, result in results:
        if isinstance(result, str) and result.startswith("EXCEPTION"):
            print("[EXCEPTION] {0}: {1}".format(check_name, result))
        elif is_error(result):
            print("[ERROR] {0}: ERROR (code {1})".format(check_name, result))
        elif result != NO_ERROR:
            print("[WARN]  {0}: WARNING (code {1})".format(check_name, result))
        else:
            print("[OK]    {0}: OK".format(check_name))
    
    return overall_status

def collect_logs():
    # get output directory for logs
    print("Please input an existing, absolute filepath to a directory where the output for the zip file will be placed upon completion.")
    output_location = get_input("Output Directory", (lambda x : os.path.isdir(x)), \
                                "Please input an existing, absolute filepath.")    
    
    print("Collecting AMA logs...")
    print("================================================================================")
    run_logcollector(output_location)

def print_results(success):
    print("================================================================================")
    print("================================================================================")
    # print out all errors/warnings
    if (len(err_summary) > 0):
        print("ALL ERRORS/WARNINGS ENCOUNTERED:")
        for err in err_summary:
            print("  {0}".format(err))
            print("--------------------------------------------------------------------------------")
        
    # no errors found
    if (success == NO_ERROR):
        print("No errors were found.")
    # user requested to exit
    elif (success == USER_EXIT):
        return
    # error found
    else:
        print("Please review the errors found above.")

''' 
give information to user about next steps
'''
def print_next_steps():
    print("================================================================================")
    print("If you still have an issue, please run the troubleshooter again and collect the logs for AMA.\n"\
        "In addition, please include the following information:\n"\
        "  - Azure Subscription ID where the Log Analytics Workspace is located\n"\
        "  - Workspace ID the agent has been onboarded to\n"\
        "  - Workspace Name\n"\
        "  - Region Workspace is located\n"\
        "  - Pricing Tier assigned to the Workspace\n"\
        "  - Linux Distribution on the VM\n"\
        "  - Azure Monitor Agent Version")

    print("================================================================================")
    print("Restarting AMA can solve some of the problems. If you need to restart Azure Monitor Agent on this machine, "\
          "please execute the following commands as the root user:")
    print("  $ cd /var/lib/waagent/Microsoft.Azure.Monitor.AzureMonitorLinuxAgent-<agent version number>/")
    print("  $ ./shim.sh -disable")
    print("  $ ./shim.sh -enable")
    
### MAIN FUNCTION BODY BELOW ###



def run_troubleshooter():
    # check if running as sudo
    if (not check_sudo()):
        return
    
    # run all checks from command line
    if len(sys.argv) > 1 and sys.argv[1] == '-A':
        success = check_all(False)
        print_results(success)
        print_next_steps()
        return
    
    # run log collector from command line
    if len(sys.argv) > 1 and sys.argv[1] == '-L':
        collect_logs()
        return
            
    # check if want to run again
    run_again = True

    print("Welcome to the Azure Monitor Linux Agent Troubleshooter! What is your issue?\n")
    while (run_again):
        print("================================================================================\n"\
            # TODO: come up with scenarios
              "1: Installation failures. \n"\
              "2: Agent doesn't start or cannot connect to Log Analytics service.\n"\
              "3: Agent in unhealthy state. \n"\
              "4: Agent consuming high CPU/memory. \n"\
              "5: Syslog not flowing. \n"\
              "6: Custom logs not flowing. \n"\
              "7: Metrics not flowing.\n"\
              "================================================================================\n"\
              "A: Run through all scenarios.\n"\
              "L: Collect the logs for AMA.\n"\
              "Q: Press 'Q' to quit.\n"\
              "================================================================================")
        switcher = {
            '1': check_installation,
            '2': check_connection,
            '3': check_general_health,
            '4': check_high_cpu_memory,
            '5': check_syslog,
            '6': check_custom_logs,
            '7': run_metrics_troubleshooter,
            'A': check_all
        }
    
        issue = get_input("Please select an option",\
                        (lambda x : x.lower() in ['1','2','3','4','5','6','7','q','quit','l','a']),\
                        "Please enter an integer corresponding with your issue (1-6) to\n"\
                        "continue, 'A' to run through all scenarios, 'L' to run the log collector, or 'Q' to quit.")
        # quit troubleshooter
        if (issue.lower() in ['q','quit']):
            print("Exiting the troubleshooter...")
            return

        # collect logs
        if (issue.lower() == 'l'):
            collect_logs()
            return

        # silent vs interactive mode
        print("--------------------------------------------------------------------------------")
        print("The troubleshooter can be run in two different modes.\n"\
            "  - Silent Mode runs through with no input required\n"\
            "  - Interactive Mode includes extra checks that require input")
        mode = get_input("Do you want to run the troubleshooter in silent (s) or interactive (i) mode?",\
                        (lambda x : x.lower() in ['s','silent','i','interactive','q','quit']),\
                        "Please enter 's'/'silent' to run silent mode, 'i'/'interactive' to run \n"\
                            "interactive mode, or 'q'/'quit' to quit.")
        if (mode.lower() in ['q','quit']):
            print("Exiting the troubleshooter...")
            return
        elif (mode.lower() in ['s','silent']):
            print("Running troubleshooter in silent mode...")
            interactive_mode = False
        elif (mode.lower() in ['i','interactive']):
            print("Running troubleshooter in interactive mode...")
            interactive_mode = True

        # run troubleshooter
        section = switcher.get(issue.upper(), lambda: "Invalid input")
        print("================================================================================")
        success = section(interactive=interactive_mode)
    
        print_results(success)

        # if user ran single scenario, ask if they want to run again
        if (issue in ['1', '2', '3', '4', '5', '6', '7']):
            run_again = get_input("Do you want to run another scenario? (y/n)",\
                                  (lambda x : x.lower() in ['y','yes','n','no']),\
                                  "Please type either 'y'/'yes' or 'n'/'no' to proceed.")
            
            if (run_again.lower() in ['y', 'yes']):
                print("Please select another scenario below:")
            elif (run_again.lower() in ['n', 'no']):
                run_again = False
        else:
            run_again = False
            
        print_next_steps()
    return
    

if __name__ == '__main__':
    run_troubleshooter()
