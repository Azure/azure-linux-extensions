import sys 
import os 
import subprocess 
import threading 
from time import sleep   

def threadForOracle(args): 
    process = subprocess.Popen(args) 
    #stdout=subprocess.PIPE 

def threadForPreDaemon(args): 
    global daemonProcess 
    daemonProcess = subprocess.Popen(args) 
    while daemonProcess.poll()==None: 
        print("Daemon: Waiting") 
        sleep(30) 

def timeoutDaemon(): 
    global preDaemonThread 
    #####Start Oracle##### 
    preDaemonOracle = "sqlplus -s / as sysdba @/hdd/python/sqlScripts/preDaemon.sql " + str(maxTime) 
    argsDaemon = ["su", "-", oracleUser, "-c", preDaemonOracle] 
    preDaemonThread = threading.Thread(target=threadForPreDaemon, args=[argsDaemon]) 
    preDaemonThread.start() 
    #####End Oracle##### 
    print("PreDaemon: Started")   

def preMaster(): 
    print("WorkloadPatch: Entering pre mode for master") 
    #####Start Oracle##### 
    preOracle="sqlplus -s / as sysdba @/hdd/python/sqlScripts/pre.sql" 
    args = ["su", "-", oracleUser, "-c", preOracle] 
    process = subprocess.Popen(args) 
    while process.poll()==None: 
        print("Pre: Waiting") 
        sleep(1) 
    timeoutDaemon() 
    #####End Oracle##### 
    print("Pre: DONE!!") 

def postMaster(): 
    print("WorkloadPatch: Entering post mode for master") 
    #----Start of Backup Insights----# 
    if preDaemonThread.isAlive(): 
        print("Post: Backup successful") 
        print("Post: Initiating Post Script") 
        daemonProcess.terminate() 
    else: 
        print("Post: Backup unsuccessful") 
        return 
    #----End of Backup Insights----# 
    #####Start Oracle#### 
    postOracle="sqlplus -s / as sysdba @/hdd/python/sqlScripts/post.sql" 
    args = ["su", "-", oracleUser, "-c", postOracle] 
    process = subprocess.Popen(args) 
    while process.poll()==None: 
        print("Post: Waiting") 
        sleep(1) 
    ####End Oracle##### 
    print("Post: DONE!!") 

#----Start Snapshot----# 
def snapshot(): 
    print("Snapshot: Taking a snapshot") 
    snapshotLocation = "/hdd/python/snapshot.sh" 
    args = [snapshotLocation] 
    snapshotProcess = subprocess.Popen(args) 
    while snapshotProcess.poll()==None: 
        print("Snapshot: Waiting ...") 
        sleep(60) 
    print("Snapshot: Complete") 
#----End Snapshot----# 

#----Main Program----#  

#----Start Config File----# 
oracleUser="AzureBackup" 
maxTime=60 
#----End Config File----# 

preMaster() 
snapshot() 
postMaster() 

print("WorkloadPatch: Backup Complete") 