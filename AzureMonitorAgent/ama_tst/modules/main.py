import os

from helpers import get_input
from logcollector import run_logcollector

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
              "(NOTE: troubleshooting scenarios are coming, currently only log collection is available)\n"\
              "================================================================================\n"\
              "L: Collect the logs for AMA.\n"\
              "Q: Press 'Q' to quit.\n"\
              "================================================================================")
        issue = get_input("Please select an option",\
                        (lambda x : x.lower() in ['q','quit','l']),\
                        "Please enter 'L' to run the log collector, or 'Q' to quit.")

        # quit troubleshooter
        if (issue.lower() in ['q','quit']):
            print("Exiting the troubleshooter...")
            return

        # collect logs
        if (issue.lower() == 'l'):
            collect_logs()
            return

    
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