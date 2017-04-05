{
  "runtimeSettings": [
    {
      "handlerSettings": {
        "publicSettings": {
          "StorageAccount": "ladunittestdiag487",
          "ladCfg": {
            "diagnosticMonitorConfiguration": {
              "syslogEvents": {
                "syslogEventConfiguration": {
                  "LOG_USER": "LOG_ERR",
                  "LOG_LOCAL0": "LOG_CRIT"
                }
              }
            }
          },
          "fileLogs" : [
            {
              "file": "/var/log/mydaemonlog1",
              "table": "MyDaemon1Events"
            },
            {
              "file": "/var/log/mydaemonlog2",
              "table": "MyDaemon2Events"
            }
          ]
        },
        "protectedSettingsCertThumbprint": "B175B535DFE9F93659E5AFD893BF99BBF9DF28A5",
        "protectedSettings": {
          "storageAccountName":"ladunittestfakeaccount",
          "storageAccountKey":"NOT_A_REAL_KEY",
          "storageAccountEndPoint":"https://core.windows.net/"
        }
      }
    }
  ]
}
