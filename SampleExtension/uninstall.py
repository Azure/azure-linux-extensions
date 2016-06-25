#!/usr/bin/env python

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

ExtensionShortName = "SampleExtension"

def main():
    #Global Variables definition
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))

    operation = "uninstall"
    status = "success"
    msg = "Uninstalled successfully."

    hutil = parse_context(operation)
    hutil.log("Start to uninstall.")
    hutil.log(msg)
    hutil.do_exit(0, operation, status, '0', msg)


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context(operation)
    return hutil


if __name__ == '__main__' :
    main()
