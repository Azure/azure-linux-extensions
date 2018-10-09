from omsData import *
from VMRunScript import *

import os
import os.path
import subprocess
import re
import sys
import time

outFile = 'az-cli-run.out'
openFile = open(outFile, 'a+')

'''
Common logic to run any command and check/get its output for further use
'''
def execCommand(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True)
        return out
    except subprocess.CalledProcessError as e:
        print(e.returncode)
        return (e.returncode)

'''
Common logic to save command outputs
'''
def writeLogOutput(out):
    if(type(out) != str): out=str(out)
    openFile.write(out + '\n')
    openFile.write('-' * 80)
    openFile.write('\n')
    return

'''
Common logic to save command itself
'''
def writeLogCommand(cmd):
    print(cmd)
    openFile.write(cmd + '\n')
    openFile.write('=' * 40)
    openFile.write('\n')
    return

def appendFile(filename):
    f = open(filename, 'r')
    openFile.write(f.read())
    f.close()

def create_vm_and_install_extensions():
    cmd='python -u VMRunScript.py -vmandext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Creating VM and Adding OMS Extension')
    appendFile('omsresults.out')

def remove_and_reinstall_extension():
    cmd='python -u VMRunScript.py -removeext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Removing OMS Extension')
    appendFile('omsresults.out')
    cmd='python -u VMRunScript.py -addext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Reinstall OMS Extension')
    appendFile('omsresults.out')

create_vm_and_install_extensions()
time.sleep(60)
#kusto verification code here
remove_and_reinstall_extension()




