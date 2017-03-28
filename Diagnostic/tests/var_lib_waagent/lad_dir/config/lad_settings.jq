{
  "runtimeSettings": [
    {
      "handlerSettings": {
        "publicSettings": {
          "StorageAccount": "ladunittestdiag487",
          "ladCfg": {
            "syslogEvents" : {
              "syslogEventConfiguration": {
                "LOG_USER": "LOG_ERR",
                "LOG_LOCAL0": "LOG_CRIT"
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
        "protectedSettings": "MIICegYJKoZIhvcNAQcDoIICazCCAmcCAQAxggFpMIIBZQIBADBNMDkxNzA1BgoJkiaJk/IsZAEZFidXaW5kb3dzIEF6dXJlIENSUCBDZXJ0aWZpY2F0ZSBHZW5lcmF0b3ICECWFsb6OvJW0TYHmRYlfr/AwDQYJKoZIhvcNAQEBBQAEggEAe83LxfpDCKI50YABlHbMixdxtOuu5/Vbf48nnmnIfTir1hkIqD/9NDtXZbGSN8qwITejQawJVCczZiSMcQZ6FIHR3iHG4XmexEsQ7TyLWEK9Km7bETrHamfZqEUrZ5BSPSVac/Eaz+ZQc3uLy6Hgfs4hghw5LQqbyKcJlTYlEd09ORdrHLToi217fKV7Xt9/13KbtOwpPSub2t+qxeVgHd41RbI0ZaKp0gCRTEnUYNgLCcysfLPD14zn5D3hb2IVgXZD38XRMLQhlgmLl0MXOCSdLGbRunL9M4+sSZug6J109sVAeexiohHHfCW/SBm51J2it1wbBDDHD4F8gW2kiDCB9AYJKoZIhvcNAQcBMBQGCCqGSIb3DQMHBAgVu1ai8A1ki4CB0C1028B2+hTG0fp6uGi9UHdFipspl6RZoJLCABKuaTr+OAbAqfYxy7fV8pWAqlw83OdoTHW97m1VR8skyR2OZwymxrSw64o73szc5lBBSH8N9g0pC7gMjTgeB1ghHCtnYAoBO0MnC5Eg6h/lMFAQ/Ceez/LMzg7FStStM76fcBDOMhwaHMriVXSpDoYf90IYKFaVW2RfMUo8cUeZKmR5o+UXWgY/sLiKLgFw5dJYyWx0TEGwrw9VAHigCDGGh/jN247OcLCOUKvnR5FFiYtc8PA="
      }
    }
  ]
}
