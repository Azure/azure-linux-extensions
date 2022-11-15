import os

from helpers        import get_input
from logcollector   import run_logcollector
from error_codes    import *
from errors         import get_input, print_errors, err_summary
from install.install import check_installation
from connect.connect import check_connection

# check to make sure the user is running as root
def check_sudo():
    if (os.geteuid() != 0):
        print("The troubleshooter is not currently being run as root. In order to have accurate results, we ask that you run this troubleshooter as root.")
        print("NOTE: it will not add, modify, or delete any files without express permission.")
        print("Please try running the troubleshooter again with 'sudo'. Thank you!")
        return False
    else:
        return True

def collect_logs():
    # get output directory for logs
    print("Please input an existing, absolute filepath to a directory where the output for the zip file will be placed upon completion.")
    output_location = get_input("Output Directory", (lambda x : os.path.isdir(x)), \
                                "Please input an existing, absolute filepath.")    
    
    print("Collecting AMA logs...")
    print("================================================================================")
    run_logcollector(output_location)



### MAIN FUNCTION BODY BELOW ###



def run_troubleshooter():
    # check if running as sudo
    if (not check_sudo()):
        return
    
    # check if want to run again
    run_again = True

    print("Welcome to the Azure Monitor Linux Agent Troubleshooter! What is your issue?\n")
    while (run_again):
        print("================================================================================\n"\
            # TODO: come up with scenarios
              "1: Installation failures. \n"\
              "2: Agent doesn't start or cannot connect to Log Analytics service.\n"\
              "================================================================================\n"\
              "L: Collect the logs for AMA.\n"\
              "Q: Press 'Q' to quit.\n"\
              "================================================================================")
        switcher = {
            '1': check_installation,
            '2': check_connection
        }
        issue = get_input("Please select an option",\
                        (lambda x : x.lower() in ['1','2','q','quit','l']),\
                        "Please enter an integer corresponding with your issue (1-2) to\n"\
                        "continue, 'L' to run the log collector, or 'Q' to quit.")
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

        # if user ran single scenario, ask if they want to run again
        if (issue in ['1', '2']):
            run_again = get_input("Do you want to run another scenario? (y/n)",\
                                  (lambda x : x.lower() in ['y','yes','n','no']),\
                                  "Please type either 'y'/'yes' or 'n'/'no' to proceed.")
            
            if (run_again.lower() in ['y', 'yes']):
                print("Please select another scenario below:")
            elif (run_again.lower() in ['n', 'no']):
                run_again = False
        else:
            run_again = False
            
    # give information to user about next steps
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
    return
    

if __name__ == '__main__':
    run_troubleshooter()
