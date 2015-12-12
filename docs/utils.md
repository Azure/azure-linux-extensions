# Utils

You can write an extension from scrach using your favourate language following [Design Details](./design-details.md).

The utils we offer are optional. They are writen in Python, and they can accelerate your development. Without them, you need to handle the protocal between WALA and extensions by yourself.

## HandlerUtils

[HandlerUtils.py](https://github.com/Azure/azure-linux-extensions/blob/master/Utils/HandlerUtil.py) handles the protocal between WALA and extensions, status and heartbeat reporting, and the logging.

* Get your settings
  * `get_public_settings()` method returns the public settings
  * `get_protected_settings()` method returns the protected settings which have been decrypted.
* Status reporting
  * `do_status_report` method reports the status, but not exists.
  * `do_exit` method reports the status and exists.
* Logging
  * HandlerUtils.py will put the logs into the log file `extension.log` which is located in `logFolder` of `handlerEnvironment.json`.
  * The method `log` and `error` can be used.

## WAAgentUtil

WAAgentUtil.py helps to load the source of [WALA](https://github.com/Azure/WALinuxAgent). You can use the function in WALA, for e.g. GetFileContents.
