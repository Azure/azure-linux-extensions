import json
import os
import os.path
import subprocess
import re
import sys
import time

from collections import OrderedDict

from omsData import *
from VMRunScript import *
from json2html import *

outFile = 'az-cli-run.log'
outOpen = open(outFile, 'a+')
htmlFile = 'az-cli-testrun-result.html'
htmlOpen = open(htmlFile, 'w+')

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
    outOpen.write(out + '\n')
    outOpen.write('=' * 80)
    outOpen.write('\n')
    return

'''
Common logic to save command itself
'''
def writeLogCommand(cmd):
    print(cmd)
    outOpen.write(cmd + '\n')
    outOpen.write('-' * 40)
    outOpen.write('\n')
    return

def appendFile(filename, destFile):
    f = open(filename, 'r')
    destFile.write(f.read())
    f.close()

def create_vm_and_install_extensions():
    cmd='python -u VMRunScript.py -vmandext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Creating VM and Adding OMS Extension')
    appendFile('omsresults.out', outOpen)
    appendFile('omsresults.html', htmlOpen)

def verify_data():
    cmd='python -u VMRunScript.py -verifydata'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Verifying Data')
    with open('e2eresults.json', 'r') as infile:
        data = json.load(infile)
    appendFile('e2eresults.json', outOpen)
    distros = data.keys()
    results = [v[0] for v in  data.values()]
    # prepend distro column to each results row before generating the table
    data = [OrderedDict([('Distro', distros[i])] + results[i].items()) for i in range(len(distros))]
    out = json2html.convert(json=data)
    htmlOpen.write(out)

def remove_extension():
    cmd='python -u VMRunScript.py -removeext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Removing OMS Extension')
    appendFile('omsresults.out', outOpen)
    appendFile('omsresults.html', htmlOpen)

def install_extension():
    cmd='python -u VMRunScript.py -addext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    writeLogCommand('Status After Reinstall OMS Extension')
    appendFile('omsresults.out', outOpen)
    appendFile('omsresults.html', htmlOpen)

def delete_extension_and_vm():
    cmd='python -u VMRunScript.py -removeext'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)
    cmd='python -u VMRunScript.py -deletevm'
    out=execCommand(cmd)
    writeLogCommand(cmd)
    writeLogOutput(out)


htmlstart="""<!DOCTYPE html>
<html>
<head>
<style>
table {
    font-family: arial, sans-serif;
    border-collapse: collapse;
    width: 100%;
}

table:not(th) {
    font-weight: lighter;
}

td, th {
    border: 1px solid #dddddd;
    text-align: left;
    padding: 8px;
}

tr:nth-child(even) {
    background-color: #dddddd;
}
</style>
</head>
<body>
"""

htmlOpen.write(htmlstart)
htmlOpen.write('<h1> Create VM and Install Extension <h1>')
create_vm_and_install_extensions()
time.sleep(600)
htmlOpen.write('<h1> Verify Data from OMS Workspace <h1>')
verify_data()
htmlOpen.write('<h1> Remove Extension <h1>')
remove_extension()
time.sleep(60)
htmlOpen.write('<h1> Reinstall Extension <h1>')
install_extension()

htmlend="""
</body>
</html>
"""
htmlOpen.write(htmlend)
htmlOpen.close()
time.sleep(60)
delete_extension_and_vm()
