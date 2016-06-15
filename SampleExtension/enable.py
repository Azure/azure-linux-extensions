#!/usr/bin/env python

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

ExtensionShortName = "SampleExtension"

def main():
    #Global Variables definition
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))

    operation = "enable"
    status = "success"
    msg = "Enabled successfully."

    hutil = parse_context(operation)
    hutil.log("Start to enable.")
    public_settings = hutil.get_public_settings()
    name = public_settings.get("name")
    if name:
        hutil.log("Hello {0}".format(name))
    else:
        hutil.error("The name in public settings is not provided.")
    hutil.log(msg)
    hutil.do_exit(0, operation, status, '0', msg)


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context(operation)
    return hutil


if __name__ == '__main__' :
    main()
