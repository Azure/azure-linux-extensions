# Sample Extension

In this page, we offer a sample extension using [Utils](./utils.md).

After this section, you can get the following directory:

```
SampleExtension/
├── disable.py
├── enable.py
├── HandlerManifest.json
├── install.py
├── references
├── uninstall.py
└── update.py
```

## HandlerManifest.json

```
[{
  "name": "SampleExtension",
  "version": 1.0,
  "handlerManifest": {
    "installCommand": "./install.py",
    "uninstallCommand": "./uninstall.py",
    "updateCommand": "./update.py",
    "enableCommand": "./enable.py",
    "disableCommand": "./disable.py",
    "rebootAfterInstall": false,
    "reportHeartbeat": false
  }
}]
```

## enable.py

1. Get the paramter `name` in the public settings.
2. Log the `name` into `extension.log`.

## references

This file is used to package the extension using [create_zip.sh](https://github.com/Azure/azure-linux-extensions/blob/master/script/create_zip.sh).

You can put `Utils` in `references`. Then `create_zip.sh` will put the direcotry `SampleExtension` and `Utils` into `SampleExtension-1.0.zip`.
