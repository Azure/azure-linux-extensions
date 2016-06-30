## vNext (yyyy-mm-dd)
- Error message misleading [#150]
- Fix for internal DNS check [#98]

## 1.5.2.0 (2016-04-11)
- Fix state machine for status transitions. [#119]

## 1.5.1.0 (2016-04-05)
- Atomically write the status file. [#117]

## 1.5.0.0 (2016-03-23)
- Refactor CustomScript and add LogUtil & ScriptUtil
- Refine MDS enents to log which file the extension fails to download
- Do not log `commandToExecute` to `extension.log` if it's passed by protectedSettings

## 1.4.1.0 (2015-12-21)
- Move downloading scripts and internal DNS check into the daemon process
- Provide an option to disable internal DNS check
- Add a timeout to urllib2.urlopen()

## 1.4.0.0 (2015-11-19)
- Protect sensitive data in `commandToExecute`
