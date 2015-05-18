#!/usr/bin/python
import json

idleTestScriptLocal = """
#!/usr/bin/python
# Locally.
def is_vm_idle():
    return True
"""

healthyTestScriptLocal = """
#!/usr/bin/python
# Locally.
def is_vm_healthy():
    return True
"""

idleTestScriptGithub = "https://raw.githubusercontent.com/bingosummer/scripts/master/idleTest.py"
healthyTestScriptGithub = "https://raw.githubusercontent.com/bingosummer/scripts/master/healthyTest.py"

idleTestScriptStorage = "https://binxia.blob.core.windows.net/ospatching-v2/idleTest.py"
healthyTestScriptStorage = "https://binxia.blob.core.windows.net/ospatching-v2/healthyTest.py"

settings = {
    "disabled" : "false",
    "stop" : "false",
    "rebootAfterPatch" : "rebootifneed",
    "category" : "important",
    "installDuration" : "00:30",
    "oneoff" : "false",
    "intervalOfWeeks" : "1",
    "dayOfWeek" : "everyday",
    "startTime" : "03:00",
    "vmStatusTest" : {
        "local" : "true",
        "idleTestScript" : idleTestScriptLocal, #idleTestScriptStorage,
        "healthyTestScript" : healthyTestScriptLocal, #healthyTestScriptStorage
    },
    "storageAccountName" : "<TOCHANGE>",
    "storageAccountKey" : "<TOCHANGE>"
}

settings_string = json.dumps(settings)
settings_file = "default.settings"
with open(settings_file, "w") as f:
    f.write(settings_string)
