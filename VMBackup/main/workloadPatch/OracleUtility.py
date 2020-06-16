import sys
import Utils.HandlerUtil
import threading
import os
from time import sleep
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import subprocess

class OracleUtility:
    def __init__(self, logger):
        self.logger = logger
        self.name = "oracle"
        self.dbnames = []
        self.login_path = "oracle"

    def containerName(self):

            if 'oracle' in self.name.lower():
                containerNameArgs =  "su - " + self.login_path + " -c " + "'sqlplus -s / as sysdba<<-EOF\nSHOW CON_NAME;\nEOF'"
                oracleContainerName = subprocess.check_output(containerNameArgs, shell=True)
                self.logger.log("Shrid: containerName- " + str(oracleContainerName))
                print("Shrid: containerName- ", str(oracleContainerName))
                
                if "CDB$ROOT" in str(oracleContainerName):
                    self.logger.log("Shrid: containerName- In CDB$ROOT")
                    print("Shrid: containerName- In CDB$ROOT")
                    return True
                else:
                    self.logger.log("Shrid: Pre- Error. Not in CDB$ROOT")
                    print("Shrid: Pre- Error. Not in CDB$ROOT")
                    changeContainerArgs = "su - " + self.login_path + " -c " + "'sqlplus -s / as sysdba<<-EOF\nALTER SESSION SET CONTAINER=CDB$ROOT;\nEOF'"
                    oracleChangeContainer = subprocess.check_output(changeContainerArgs, shell=True)
                    self.logger.log("Shrid: containerName- " + str(oracleChangeContainer))
                    print("Shrid: containerName- ", str(oracleChangeContainer))
                    if "Session altered." in str(oracleChangeContainer):
                        return True
                    else:
                        return False
            
            return False
