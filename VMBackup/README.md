# VMBackup Extension

Linux guest extension used by the **Azure Backup** service to take
application-consistent backups of Linux VMs running in Azure.

> **Note:** This extension is intended to be installed and managed by Azure
> Backup. Installing it manually outside that context is not supported.

## Deployment

The extension is deployed automatically as part of the first scheduled backup
after a VM is configured for backup. To configure a VM for backup, see:

- [Azure Portal](https://docs.microsoft.com/azure/backup/quick-backup-vm-portal)
- [Azure PowerShell](https://docs.microsoft.com/azure/backup/quick-backup-vm-powershell)
- [Azure CLI](https://docs.microsoft.com/azure/backup/quick-backup-vm-cli)

## Repository layout

```
VMBackup/
├── main/          Production source. Runs inside the target Linux VM.
├── test/          Unit tests and test helpers (not shipped in the zip).
├── references/    Vendored dependencies.
└── README.md      This file.
```

## Running unit tests

Tests live under `VMBackup/test/` and are written as `unittest.TestCase`
subclasses. The test runner requires **Python 3.6 or newer**. The
extension's own runtime Python compatibility is unchanged and continues to
be validated by manual VM deployment.

Run all commands from the `VMBackup/` directory.

### Option A — `unittest` (no install required)

```sh
python -m unittest discover -s test -p "test_*.py" -v
```

### Option B — `pytest` (nicer output, optional)

```sh
pip install -r test/requirements.txt
pytest test/ -v
```

Both runners discover the same test files; pick whichever you prefer.

## Adding tests

Place a test for `main/<Pkg>/<Module>.py` at
`test/unit/<pkg>/test_<module>.py` (lowercase package directory and file name).

```
main/Utils/WAAgentUtil.py   →   test/unit/utils/test_waagent_util.py
```

If a test needs filesystem staging, mocks, or other module-specific
scaffolding, add a fixtures module under `test/helpers/` (e.g.
`test/helpers/waagent_fixtures.py`) rather than putting that logic into
`test/helpers/tools.py`. Keep `tools.py` for genuinely shared utilities.
