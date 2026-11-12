"""Pre/post validation tests; filesystem ownership and process launch are mocked."""

import errno
import json
import os
import shutil
import stat
import sys
import tempfile
import types
import unittest


_MAIN_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, 'main'))
if _MAIN_DIR not in sys.path:
    sys.path.insert(0, _MAIN_DIR)

from Utils import TrustedPath
from common import CommonVariables


def _import_script_modules():
    # Windows lacks pwd and the Linux guest-agent dependencies; mock only imports.
    saved = {}
    if os.name == 'nt':
        import Utils
        saved_handler = getattr(Utils, 'HandlerUtil', None)
        pwd = types.ModuleType('pwd')
        pwd.getpwuid = lambda uid: type('Owner', (object,), {'pw_name': 'root'})()
        handler = types.ModuleType('Utils.HandlerUtil')
        for name, module in [('pwd', pwd), ('Utils.HandlerUtil', handler)]:
            saved[name] = sys.modules.get(name)
            sys.modules[name] = module
        Utils.HandlerUtil = handler
    try:
        import ScriptRunner
        import PluginHost
        return ScriptRunner, PluginHost
    finally:
        if os.name == 'nt':
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
            if saved_handler is None:
                del Utils.HandlerUtil
            else:
                Utils.HandlerUtil = saved_handler


ScriptRunner, PluginHost = _import_script_modules()


class _Logger(object):
    def __init__(self):
        self.messages = []

    def log(self, *args):
        self.messages.append(args)


class _FileSystem(object):
    path = os.path
    sep = os.sep
    pardir = os.pardir

    def __init__(self):
        self.overrides = {}

    def lstat(self, path):
        path = os.path.abspath(path)
        override = self.overrides.get(path)
        if isinstance(override, OSError):
            raise override
        entry = list(os.lstat(path))
        # Model a root-managed installation without requiring root or chmod.
        entry[stat.ST_UID] = 0
        entry[stat.ST_MODE] = (
            stat.S_IFDIR | 0o755 if os.path.isdir(path) else stat.S_IFREG | 0o700)
        if override is not None:
            entry[stat.ST_UID], entry[stat.ST_MODE] = override
        return os.stat_result(entry)

    def stat(self, path):
        return self.lstat(path)


class TrustedScriptPathTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.scripts = os.path.join(self.directory, 'scripts')
        os.mkdir(self.scripts)
        self.pre = os.path.join(self.scripts, 'pre.sh')
        self.post = os.path.join(self.scripts, 'post.sh')
        for path in [self.pre, self.post]:
            with open(path, 'w') as script:
                script.write('exit 0\n')
        self.config = os.path.join(self.directory, 'plugin.json')
        with open(self.config, 'w') as config:
            json.dump({'preScriptLocation': self.pre,
                       'postScriptLocation': self.post,
                       'continueBackupOnFailure': False}, config)
        self.host_config = os.path.join(self.directory, 'host.conf')
        self._write_host_config([self.config])
        self.logger = _Logger()
        self.fs = _FileSystem()
        self.saved_sys_path = list(sys.path)
        self.fs.overrides[self.config] = (0, stat.S_IFREG | 0o600)
        self.fs.overrides[self.host_config] = (0, stat.S_IFREG | 0o644)
        self.saved_os = [module.os for module in
                         [TrustedPath, ScriptRunner, PluginHost]]
        for module in [TrustedPath, ScriptRunner, PluginHost]:
            module.os = self.fs
        self.runner = ScriptRunner.ScriptRunner(
            self.logger, 'test', self.config, 60)
        self.runner.find_owner = lambda path: 'root'
        self.host = PluginHost.PluginHost(self.logger)
        self.host.configLocation = self.host_config
        self.host.find_owner = lambda path: 'root'

    def tearDown(self):
        for module, saved in zip(
                [TrustedPath, ScriptRunner, PluginHost], self.saved_os):
            module.os = saved
        sys.path[:] = self.saved_sys_path
        shutil.rmtree(self.directory)

    def _write_host_config(self, paths):
        with open(self.host_config, 'w') as config:
            config.write('[pre_post]\nnumberOfPlugins={0}\n'.format(len(paths)))
            for index, path in enumerate(paths):
                config.write('pluginName{0}=ScriptRunner\npluginPath{0}={1}\n'
                             'pluginConfigPath{0}={2}\n'.format(
                                 index, _MAIN_DIR, path))

    def test_root_owned_script_in_user_owned_parent_is_rejected(self):
        self.fs.overrides[self.scripts] = (1001, stat.S_IFDIR | 0o755)
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])

    def test_post_script_with_writable_parent_is_rejected(self):
        post_directory = os.path.join(self.directory, 'post')
        os.mkdir(post_directory)
        post = os.path.join(post_directory, 'post.sh')
        with open(post, 'w') as script:
            script.write('exit 0\n')
        with open(self.config, 'w') as config:
            json.dump({'preScriptLocation': self.pre,
                       'postScriptLocation': post}, config)
        self.fs.overrides[post_directory] = (0, stat.S_IFDIR | 0o775)
        self.assertEqual(CommonVariables.FailedPrepostPostScriptPermissionError,
                         self.runner.validate_scripts()[0])

    def test_writable_higher_ancestor_is_rejected(self):
        self.fs.overrides[self.directory] = (0, stat.S_IFDIR | 0o777)
        self.assertFalse(self.runner.validate_permissions(self.pre))
        self.assertTrue(self.logger.messages)

    def test_symlink_parent_is_rejected(self):
        self.fs.overrides[self.scripts] = (0, stat.S_IFLNK | 0o777)
        self.assertFalse(self.runner.validate_permissions(self.pre))

    def test_symlink_script_is_rejected(self):
        self.fs.overrides[self.pre] = (0, stat.S_IFLNK | 0o700)
        self.assertFalse(self.runner.validate_permissions(self.pre))

    def test_non_regular_script_is_rejected(self):
        self.fs.overrides[self.pre] = (0, stat.S_IFIFO | 0o700)
        self.assertFalse(self.runner.validate_permissions(self.pre))

    def test_non_root_script_is_rejected(self):
        self.fs.overrides[self.pre] = (1001, stat.S_IFREG | 0o700)
        self.assertFalse(self.runner.validate_permissions(self.pre))

    def test_group_readable_script_is_rejected(self):
        self.fs.overrides[self.pre] = (0, stat.S_IFREG | 0o740)
        self.assertFalse(self.runner.validate_permissions(self.pre))

    def test_missing_ancestor_fails_closed(self):
        self.fs.overrides[self.scripts] = OSError(errno.ENOENT, 'missing')
        self.assertFalse(self.runner.validate_permissions(self.pre))
        self.assertTrue(self.logger.messages)

    def test_parent_reference_is_rejected(self):
        path = os.path.join(self.scripts, os.pardir, 'scripts', 'pre.sh')
        self.assertFalse(self.runner.validate_permissions(path))

    def test_safe_paths_preserve_config_and_execution_arguments(self):
        self.assertEqual(CommonVariables.PrePost_PluginStatus_Success,
                         self.runner.validate_scripts()[0])
        self.assertTrue(self.runner.configLoaded)
        self.assertFalse(self.runner.continueBackupOnFailure)
        self.runner.preScriptParams = ['one argument', 'two']
        self.runner.postScriptParams = ['post argument']
        calls = []

        class _Process(object):
            returncode = 0

            def poll(self):
                return 0

        def popen(arguments, **kwargs):
            calls.append(arguments)
            return _Process()

        saved = ScriptRunner.subprocess.Popen
        ScriptRunner.subprocess.Popen = popen
        try:
            for invoke in [self.runner.pre_script, self.runner.post_script]:
                completed, results = [False], [None]
                invoke(0, completed, results)
                self.assertTrue(completed[0])
                self.assertEqual(0, results[0].errorCode)
            self.assertEqual([['sh', self.pre, 'one argument', 'two'],
                              ['sh', self.post, 'post argument']], calls)
        finally:
            ScriptRunner.subprocess.Popen = saved

    def test_plugin_config_under_user_owned_parent_is_not_read(self):
        self.fs.overrides[self.directory] = (1001, stat.S_IFDIR | 0o755)
        self.runner.get_config()
        self.assertFalse(self.runner.configLoaded)
        self.assertIsNone(self.runner.preScriptLocation)

    def test_repeated_config_load_does_not_retain_success_on_rejection(self):
        self.runner.get_config()
        self.assertTrue(self.runner.configLoaded)
        self.fs.overrides[self.directory] = (1001, stat.S_IFDIR | 0o755)
        self.runner.get_config()
        self.assertFalse(self.runner.configLoaded)

    def test_host_config_under_user_owned_parent_is_rejected(self):
        self.fs.overrides[self.directory] = (1001, stat.S_IFDIR | 0o755)
        result = self.host.load_modules()
        self.assertEqual(
            CommonVariables.FailedPrepostPluginhostConfigPermissionError,
            result[0])
        self.assertFalse(self.host.modulesLoaded)

    def test_host_config_can_be_world_readable_but_not_writable(self):
        self.fs.overrides[self.host_config] = (0, stat.S_IFREG | 0o644)
        self.assertTrue(TrustedPath.is_trusted_root_owned_file(
            self.host_config, self.logger, 0o044))
        self.fs.overrides[self.host_config] = (0, stat.S_IFREG | 0o664)
        self.assertFalse(TrustedPath.is_trusted_root_owned_file(
            self.host_config, self.logger, 0o044))

    def test_safe_host_config_loads_a_valid_plugin(self):
        self.assertEqual(CommonVariables.PrePost_PluginStatus_Success,
                         self.host.pre_check()[0])
        self.assertTrue(self.host.modulesLoaded)
        self.assertEqual(1, self.host.noOfPlugins)

    def test_later_valid_plugin_cannot_hide_unsafe_script(self):
        unsafe_directory = os.path.join(self.directory, 'unsafe')
        os.mkdir(unsafe_directory)
        unsafe_script = os.path.join(unsafe_directory, 'pre.sh')
        with open(unsafe_script, 'w') as script:
            script.write('exit 0\n')
        unsafe_config = os.path.join(self.directory, 'unsafe.json')
        with open(unsafe_config, 'w') as config:
            json.dump({'preScriptLocation': unsafe_script,
                       'postScriptLocation': self.post}, config)
        self.fs.overrides[unsafe_config] = (0, stat.S_IFREG | 0o600)
        self.fs.overrides[unsafe_directory] = (1001, stat.S_IFDIR | 0o755)
        self._write_host_config([unsafe_config, self.config])
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.host.load_modules()[0])
        self.assertFalse(self.host.modulesLoaded)
        self.assertEqual([], self.host.plugins)

    def test_later_valid_plugin_cannot_hide_unsafe_config(self):
        unsafe_directory = os.path.join(self.directory, 'unsafe')
        os.mkdir(unsafe_directory)
        unsafe_config = os.path.join(unsafe_directory, 'plugin.json')
        shutil.copyfile(self.config, unsafe_config)
        self.fs.overrides[unsafe_config] = (0, stat.S_IFREG | 0o600)
        self.fs.overrides[unsafe_directory] = (1001, stat.S_IFDIR | 0o755)
        self._write_host_config([unsafe_config, self.config])
        self.assertEqual(CommonVariables.FailedPrepostPluginConfigPermissionError,
                         self.host.load_modules()[0])
        self.assertFalse(self.host.modulesLoaded)
        self.assertEqual([], self.host.plugins)


if __name__ == '__main__':
    unittest.main()
