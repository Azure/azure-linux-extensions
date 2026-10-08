import os
import subprocess

from error_codes import *

# Resolve absolute path to the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TROUBLESHOOTER_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "metrics_troubleshooter.sh"))

def run_metrics_troubleshooter(interactive):
    """
    Executes the metrics troubleshooter script.
    """
    if not os.path.exists(TROUBLESHOOTER_FILE):
        print("Metrics Troubleshooter script not found at: {}".format(TROUBLESHOOTER_FILE))
        return ERR_FOUND

    status = None
    if interactive:
        print("================================================================================")
        print("Metrics Troubleshooter does not support interactive mode yet.")
        print("The troubleshooter produces `MdmDataCollectionOutput_.*tar.gz`, which is required for investigating the issue.")

    try:
        proc = subprocess.Popen(
            ["/bin/sh", TROUBLESHOOTER_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate()
        status = proc.returncode

        if status != 0:
            print("Error ({}): {}".format(status, stderr.strip()))
            # raise Exception or return False here if needed
        else:
            print("Troubleshooter output: {}".format(stdout.strip()))

    except Exception as e:
        print("Unexpected error: {}".format(str(e)))

    return NO_ERROR
