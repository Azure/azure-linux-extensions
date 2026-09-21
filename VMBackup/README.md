# VMBackup Extension

VMBackup is a Linux VM extension used by Azure Backup to create application-consistent recovery points.

> [!NOTE]
> Azure Backup installs and manages this extension. Installing it directly outside the Azure Backup service workflow is not supported.

## Deployment

Azure Backup deploys the extension as part of backup operations after backup is enabled for a virtual machine. For configuration instructions, see:

- [Back up a VM with the Azure portal](https://learn.microsoft.com/azure/backup/quick-backup-vm-portal)
- [Back up a VM with Azure PowerShell](https://learn.microsoft.com/azure/backup/quick-backup-vm-powershell)
- [Back up a VM with Azure CLI](https://learn.microsoft.com/azure/backup/quick-backup-vm-cli)

## Repository layout

```text
VMBackup/
|-- main/          Extension source and bundled runtime files
|-- test/          Unit tests, excluded from the extension package
|-- references     Shared repository dependencies used during packaging
|-- setup.py       Extension packaging script
`-- README.md
```

## Run unit tests

The unit tests use Python's standard `unittest` framework, require no additional packages, and are compatible with Python 2.7 through Python 3.14. This does not change the extension's runtime compatibility requirements.

From the `VMBackup` directory, run:

```sh
python -m unittest discover -s test -p "test_*.py" -v
```

Unit-test modules should be placed under `test/unit/` and named `test_<module>.py`. Keep reusable helpers under `test/helpers/`.

Pull-request validation runs the unit tests on Python 2.7.18 in a digest-pinned container and on Python 3.8 through Python 3.14 using the GitHub-hosted Python tool cache.

## Measure code coverage

Coverage is measured across all Python production modules under `main/`, including modules that are not executed by the current tests. Test modules, helpers, and temporary fixture copies are not counted as separate source files. The initial branch-coverage gate is the measured baseline of 0.41%.

Coverage measurement uses Python 3.12 and `coverage.py` 7.16.0 as development-only dependencies. It does not change the Python versions supported by the unit tests or extension runtime.

From the `VMBackup` directory on Linux, run:

```sh
python -m pip install coverage==7.16.0
export VMBACKUP_COVERAGE_TEMP="$(mktemp -d)"
export TMPDIR="$VMBACKUP_COVERAGE_TEMP"
export COVERAGE_FILE="$VMBACKUP_COVERAGE_TEMP/.coverage"
python -m coverage erase
python -m coverage run -m unittest discover -s test -p "test_*.py" -v
python -m coverage combine
python -m coverage report
rm -rf "$VMBACKUP_COVERAGE_TEMP"
```
