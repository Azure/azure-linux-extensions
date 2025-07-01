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
    try:
        if interactive:
            print("================================================================================")
            print("Metrics Troubleshooter does not support interactive mode yet.")
            print("The troubleshooter produces `MdmDataCollectionOutput_.*tar.gz`, which is required for investigating the issue.")

        status = subprocess.run(
            ["/bin/sh", TROUBLESHOOTER_FILE],
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # Timeout after 5 minutes
        )
        print(status.stdout.strip())
        status.check_returncode()  # Raises CalledProcessError if the command returned a non-zero exit code
    except subprocess.CalledProcessError as e:
        print("Error running Metrics Troubleshooter script: {}".format(TROUBLESHOOTER_FILE))
        print("Error ({}): {}".format(e.returncode, e.stderr.strip()))
        return ERR_FOUND
    except Exception as ex:
        print("An unexpected error occurred: {}".format(ex))
        print("An unexpected error occurred")
        print("Error ({}): {}".format(e.returncode, e.stderr.strip()))
        return ERR_FOUND

    return NO_ERROR
