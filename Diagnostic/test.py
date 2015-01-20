import os
import sys
import re
import diagnostic
diagnostic=reload(diagnostic)
class test_util:
    def log(self,msg):
        sys.stdout.flush()
        print("Log:"+str(msg))
    def error(self,msg):
        print("Error:"+str(msg))
    def set_inused_config_seq(self,seq):
        print("set sequnce")
    def get_seq_no(self):
        print("get_seq_no")
        return 1
    def is_current_config_seq_greater_inused(self):
        print("check seq")
        return True
    def do_status_report(self,*arg):
        print(arg)

    def try_parse_context(self):
        print("parse ")
    def get_public_settings(self):
        print("get_public_settings")
    def get_protected_settings(self):
        print("get_print_settings")
        return {'xmlCfg':'<xml>test</xmld>'}

def RunGetOutput(*arg):
    print("Run: ",arg)
    if  arg[0].count("ps aux") > 0:
        return 0,'1' 
    if  arg[0].count(" rsyslog |grep") >0:
        return 0,"5.10" 
    return 0,"looks good"
 
def main(command):
    diagnostic.hutil = test_util()
    diagnostic.RunGetOutput = RunGetOutput
    diagnostic.StartDaemonConfig=os.path.join(os.getcwd(), __file__)
    if re.match("^([-/]*)(daemon)", command):    
        diagnostic.main("-daemon")
    else:
        diagnostic.main("install")
        diagnostic.main("uninstall")
        diagnostic.main("enable")
        diagnostic.main("disable")    

if __name__ == '__main__' :
    if len(sys.argv) > 1:
        main(sys.argv[1])
