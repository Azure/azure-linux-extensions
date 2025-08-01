# Azure VM Encryption Extension - Test Suite

Unit tests for the Azure Linux VM Encryption Extension. Tests ensure cross-platform compatibility (Python 2.7/3.x) across multiple Linux distributions.

## Quick Start

```bash
# Navigate to main directory
cd "c:/path/to/VMEncryption/main"

# Run all tests
py -m unittest discover test/ -v

# Run specific test
py -m unittest test.test_azurelinuxPatching -v
```

## Setup

Create and activate a virtual environment, then install dependencies:
```bash
# Create virtual environment
python -m venv vmencryption-test-env

# Activate (Windows)
vmencryption-test-env\Scripts\activate

# Activate (Linux/macOS)
source vmencryption-test-env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Test Structure

| Test File | Purpose |
|-----------|---------|
| `test_azurelinuxPatching.py` | Azure Linux package management |
| `test_UbuntuPatching.py` | Ubuntu-specific operations |
| `test_redhatPatching.py` | RedHat/CentOS operations |
| `test_disk_util.py` | Disk operations and SCSI handling |
| `test_command_executor.py` | Command execution with timeouts |
| `test_bek_util.py` | BitLocker key utilities |
| `test_encryption_config.py` | Configuration parsing |

## Running Tests

Set the Python path to include the main directory, then run tests:

```bash
# From VMEncryption/main directory
$env:PYTHONPATH = "C:\Source\Repos\azure-linux-extensions\VMEncryption\main"

# All tests (from VMEncryption directory) - Most tests now work!
cd .. && py -m unittest discover main/test/ -v

# Specific module (recommended for individual development)
py -m unittest test.test_azurelinuxPatching -v

# Individual test case
py -m unittest test.test_azurelinuxPatching.Test_azurelinuxPatching.test_install_cryptsetup_already_installed -v
```

**Test Status**: 51 of 58 tests now pass successfully. Remaining issues are primarily platform-specific compatibility problems, not the original import failures.

## Writing New Tests

### Basic Test Template
```python
import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock  # Python 2.7 compatibility

from YourModule import YourClass
from console_logger import ConsoleLogger

class Test_YourClass(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.instance = YourClass(self.logger)
    
    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_method_success(self, mock_execute):
        mock_execute.return_value = 0
        result = self.instance.your_method()
        self.assertEqual(result, 0)
        mock_execute.assert_called_with("expected_command")
```

### Using GitHub Copilot

This codebase includes Copilot instructions at `../.copilot-instructions.md`. To generate tests for new code:

1. Open the file you want to test
2. Type a comment like: `# @copilot generate unit tests for this class`
3. Copilot will generate tests following the project's patterns and Python 2.7/3.x compatibility

The instructions ensure generated tests include proper mocking, cross-platform compatibility, and follow established patterns.
