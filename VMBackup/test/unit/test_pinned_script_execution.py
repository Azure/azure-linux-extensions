"""Descriptor policy, worker lifecycle, and harmless Linux identity regressions."""

import errno
import io
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

from Utils import PinnedScript as pinned_module
from common import CommonVariables


def _import_modules():
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


ScriptRunner, PluginHost = _import_modules()


class _Logger(object):
    def __init__(self):
        self.messages = []

    def log(self, *args):
        self.messages.append(args)


class _FileSystem(object):
    O_RDONLY = os.O_RDONLY
    O_NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0x20000)
    O_NONBLOCK = getattr(os, 'O_NONBLOCK', 0x40000)
    getpid = staticmethod(os.getpid)

    def __init__(self):
        self.fds = set()
        self.flags = []
        self.mode = stat.S_IFREG | 0o700
        self.uid = 0
        self.open_error = None
        self.proc_error = None
        self.identity_mismatch = False

    def open(self, path, flags):
        self.flags.append(flags)
        if self.open_error is not None:
            raise self.open_error
        if os.name == 'nt':
            # Allow the same open-file rename semantics as Linux in this fixture.
            import ctypes
            from ctypes import wintypes
            import msvcrt
            if not os.path.exists(path):
                raise OSError(errno.ENOENT, 'Script fixture missing')
            create_file = ctypes.windll.kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            create_file.restype = wintypes.HANDLE
            text = path if sys.version_info[0] == 3 else path.decode('utf-8')
            handle = create_file(text, 0x80000000, 7, None, 3, 0x80, None)
            if handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError()
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        else:
            fd = os.open(path, os.O_RDONLY)
        self.fds.add(fd)
        return fd

    def fstat(self, fd):
        metadata = list(os.fstat(fd))
        metadata[stat.ST_MODE] = self.mode
        metadata[stat.ST_UID] = self.uid
        return os.stat_result(metadata)

    def stat(self, path):
        if self.proc_error is not None:
            raise self.proc_error
        metadata = list(self.fstat(int(path.rsplit('/', 1)[1])))
        if self.identity_mismatch:
            metadata[stat.ST_INO] += 1
        return os.stat_result(metadata)

    def dup(self, fd):
        duplicate = os.dup(fd)
        self.fds.add(duplicate)
        return duplicate

    def close(self, fd):
        os.close(fd)
        self.fds.remove(fd)


class _Process(object):
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.killed = False
        self.waited = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self):
        self.waited = True
        return self.returncode


class PinnedScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.pre = os.path.join(self.directory, 'pre.sh')
        self.post = os.path.join(self.directory, 'post.sh')
        for path in [self.pre, self.post]:
            with open(path, 'wb') as script:
                script.write(b'original\n')
        self.config = os.path.join(self.directory, 'plugin.json')
        with open(self.config, 'w') as config:
            json.dump({'preScriptLocation': self.pre,
                       'postScriptLocation': self.post,
                       'continueBackupOnFailure': False}, config)
        self.fs = _FileSystem()
        self.saved_os = pinned_module.os
        pinned_module.os = self.fs
        self.logger = _Logger()
        self.runner = ScriptRunner.ScriptRunner(
            self.logger, 'test', self.config, 60)
        self.saved_popen = ScriptRunner.subprocess.Popen
        self.calls = []
        self.process = _Process()
        self.launch_error = None
        self.close_host_during_launch = False
        ScriptRunner.subprocess.Popen = self._popen

    def tearDown(self):
        self.runner.close()
        ScriptRunner.subprocess.Popen = self.saved_popen
        pinned_module.os = self.saved_os
        remaining = list(self.fs.fds)
        for fd in remaining:
            self.fs.close(fd)
        shutil.rmtree(self.directory)
        self.assertEqual([], remaining, 'Descriptor leaked by test execution')

    def _popen(self, arguments, **kwargs):
        self.calls.append((arguments, kwargs))
        if self.launch_error is not None:
            raise self.launch_error
        if self.close_host_during_launch:
            self.runner.close()
        fd = int(arguments[1].rsplit('/', 1)[1])
        os.lseek(fd, 0, os.SEEK_SET)
        self.executed_content = os.read(fd, 4096)
        return self.process

    def _validate(self):
        self.assertEqual(0, self.runner.validate_scripts()[0])

    def _run(self, stage):
        completed, results = [False], [None]
        getattr(self.runner, stage + '_script')(0, completed, results)
        self.assertTrue(completed[0])
        return results[0]

    def test_pre_replacement_executes_validated_file(self):
        self._validate()
        os.rename(self.pre, self.pre + '.original')
        with open(self.pre, 'w') as replacement:
            replacement.write('replacement\n')
        self.assertEqual(0, self._run('pre').errorCode)
        self.assertEqual(b'original\n', self.executed_content)
        self.assertTrue(self.runner.PreScriptCompletedSuccessfully)

    def test_post_replacement_across_snapshot_executes_validated_file(self):
        self._validate()
        self._run('pre')
        os.rename(self.post, self.post + '.original')
        with open(self.post, 'w') as replacement:
            replacement.write('replacement\n')
        self.assertEqual(0, self._run('post').errorCode)
        self.assertEqual(b'original\n', self.executed_content)

    def test_arguments_and_fd_isolation_are_preserved(self):
        self._validate()
        self.runner.preScriptParams = ['one argument', 'secret-test-argument']
        self._run('pre')
        arguments, kwargs = self.calls[0]
        self.assertEqual('/bin/sh', arguments[0])
        self.assertTrue(arguments[1].startswith('/proc/'))
        self.assertNotEqual(self.pre, arguments[1])
        self.assertEqual(self.runner.preScriptParams, arguments[2:])
        self.assertTrue(kwargs['close_fds'])
        self.assertNotIn('secret-test-argument', str(self.logger.messages))

    def test_non_root_file_is_rejected_and_handle_closed(self):
        self.fs.uid = 1001
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)
        self.assertFalse(self.calls)

    def test_group_access_is_rejected(self):
        self.fs.mode = stat.S_IFREG | 0o740
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)

    def test_non_regular_file_is_rejected_with_nonblocking_open(self):
        self.fs.mode = stat.S_IFIFO | 0o700
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertTrue(self.fs.flags[0] & self.fs.O_NONBLOCK)
        self.assertTrue(self.fs.flags[0] & self.fs.O_NOFOLLOW)
        self.assertFalse(self.fs.fds)

    def test_symlink_open_failure_is_not_retried_by_path(self):
        self.fs.open_error = OSError(errno.ELOOP, 'symlink')
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.calls)
        self.assertEqual(1, len(self.fs.flags))

    def test_missing_pre_script_retains_not_found_error(self):
        os.remove(self.pre)
        self.assertEqual(CommonVariables.FailedPrepostPreScriptNotFound,
                         self.runner.validate_scripts()[0])

    def test_missing_post_script_releases_pre_descriptor(self):
        os.remove(self.post)
        self.assertEqual(CommonVariables.FailedPrepostPostScriptNotFound,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)

    def test_invalid_post_permissions_release_both_descriptors(self):
        original_fstat = self.fs.fstat
        def metadata(fd):
            entry = list(original_fstat(fd))
            if len(self.fs.flags) == 2:
                entry[stat.ST_MODE] = stat.S_IFREG | 0o777
            return os.stat_result(entry)
        self.fs.fstat = metadata
        self.assertEqual(CommonVariables.FailedPrepostPostScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)

    def test_missing_procfs_fails_closed_before_execution(self):
        self.fs.proc_error = OSError(errno.ENOENT, 'procfs unavailable')
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)
        self.assertFalse(self.calls)

    def test_procfs_identity_mismatch_fails_closed(self):
        self.fs.identity_mismatch = True
        self.assertEqual(CommonVariables.FailedPrepostPreScriptPermissionError,
                         self.runner.validate_scripts()[0])
        self.assertFalse(self.fs.fds)

    def test_unvalidated_worker_returns_failure_without_launch(self):
        self.runner.continueBackupOnFailure = False
        result = self._run('pre')
        self.assertEqual(CommonVariables.FailedPrepostPreScriptFailed,
                         result.errorCode)
        self.assertFalse(result.continueBackup)
        self.assertFalse(self.calls)

    def test_launch_failure_publishes_completion_and_closes_worker_handle(self):
        self._validate()
        self.launch_error = OSError(errno.EACCES, 'shell denied')
        result = self._run('post')
        self.assertEqual(CommonVariables.FailedPrepostPostScriptFailed,
                         result.errorCode)
        self.assertFalse(result.continueBackup)
        self.assertEqual(2, len(self.fs.fds))

    def test_timeout_kills_and_reaps_shell_before_closing_worker_handle(self):
        self._validate()
        self.process.returncode = None
        self.runner.pollTotalCount = 0
        result = self._run('post')
        self.assertEqual(CommonVariables.FailedPrepostPostScriptTimeout,
                         result.errorCode)
        self.assertFalse(result.continueBackup)
        self.assertTrue(self.process.killed)
        self.assertTrue(self.process.waited)
        self.assertTrue(self.process.stdout.closed)
        self.assertEqual(2, len(self.fs.fds))

    def test_failed_kill_retains_worker_handle_until_shell_exit(self):
        self._validate()
        self.process.returncode = None
        self.runner.pollTotalCount = 0
        waited_with_handle = []
        def kill():
            raise OSError(errno.EPERM, 'fixture kill denied')
        def wait():
            waited_with_handle.append(len(self.fs.fds) == 3)
            self.process.returncode = 1
        self.process.kill = kill
        self.process.wait = wait
        result = self._run('pre')
        self.assertEqual(CommonVariables.FailedPrepostPreScriptFailed,
                         result.errorCode)
        self.assertEqual([True], waited_with_handle)
        self.assertIn('retaining its descriptor until exit', str(self.logger.messages))
        self.assertEqual(2, len(self.fs.fds))

    def test_nonzero_exit_preserves_failure_policy(self):
        self._validate()
        self.process.returncode = 17
        result = self._run('pre')
        self.assertEqual(CommonVariables.FailedPrepostPreScriptFailed,
                         result.errorCode)
        self.assertFalse(result.continueBackup)
        self.assertTrue(self.process.waited)

    def test_host_cleanup_does_not_close_inflight_worker_duplicate(self):
        self._validate()
        self.close_host_during_launch = True
        self.assertEqual(0, self._run('pre').errorCode)
        self.assertEqual(b'original\n', self.executed_content)
        self.assertFalse(self.fs.fds)

    def test_context_cleanup_releases_skipped_post_script_on_exception(self):
        self._validate()
        host = PluginHost.PluginHost(self.logger)
        host.plugins = [self.runner]
        with self.assertRaises(RuntimeError):
            with host:
                self._run('pre')
                raise RuntimeError('snapshot fixture failed')
        self.assertFalse(self.fs.fds)

    def test_normal_context_cleanup_releases_unused_scripts(self):
        self._validate()
        host = PluginHost.PluginHost(self.logger)
        host.plugins = [self.runner]
        with host:
            pass
        self.assertFalse(self.fs.fds)

    def test_valid_plugin_cannot_mask_an_earlier_rejected_script(self):
        host = PluginHost.PluginHost(self.logger)
        config = os.path.join(self.directory, 'host.conf')
        with open(config, 'w') as stream:
            stream.write('[pre_post]\nnumberOfPlugins=2\n')
            for index in range(2):
                stream.write(
                    'pluginName{0}=ScriptRunner\npluginPath{0}={1}\n'
                    'pluginConfigPath{0}={2}\n'.format(
                        index, _MAIN_DIR, self.config))
        host.configLocation = config
        host.get_permissions = lambda path: '600'
        host.find_owner = lambda path: 'root'
        self.fs.open_error = OSError(errno.ELOOP, 'symlink')
        saved_path = list(sys.path)
        try:
            with host:
                self.assertEqual(
                    CommonVariables.FailedPrepostPreScriptPermissionError,
                    host.load_modules()[0])
                self.assertFalse(host.modulesLoaded)
                self.assertEqual(1, len(self.fs.flags))
        finally:
            sys.path[:] = saved_path
        self.assertFalse(self.fs.fds)

    def test_revalidation_and_repeated_cleanup_do_not_leak_descriptors(self):
        self._validate()
        self._validate()
        self.assertEqual(2, len(self.fs.fds))
        self.runner.close()
        self.runner.close()
        self.assertFalse(self.fs.fds)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux procfs and /bin/sh')
class NativeLinuxExecutionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.logger = _Logger()
        self.saved_fstat = os.fstat
        # CI is unprivileged: simulate only the root ownership policy, not opens,
        # procfs resolution, shell execution, symlinks, or descriptor lifetime.
        def root_metadata(fd):
            metadata = list(self.saved_fstat(fd))
            metadata[stat.ST_UID] = 0
            return os.stat_result(metadata)
        os.fstat = root_metadata

    def tearDown(self):
        os.fstat = self.saved_fstat
        shutil.rmtree(self.directory)

    def test_renamed_and_replaced_script_executes_original_bytes(self):
        import subprocess
        path = os.path.join(self.directory, 'script.sh')
        output = os.path.join(self.directory, 'result.txt')
        with open(path, 'w') as script:
            script.write('printf "%s" "$1" > "$2"\n')
        os.chmod(path, 0o700)
        script = pinned_module.PinnedScript(path, self.logger)
        try:
            os.rename(path, path + '.old')
            with open(path, 'w') as replacement:
                replacement.write('printf replacement > "$2"\n')
            process = subprocess.Popen(
                ['/bin/sh', script.execution_path(), 'original argument', output],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            stdout, stderr = process.communicate()
            self.assertEqual(0, process.returncode, stderr)
            with open(output) as result:
                self.assertEqual('original argument', result.read())
        finally:
            script.close()

    def test_symlink_is_rejected_by_real_nofollow_open(self):
        target = os.path.join(self.directory, 'target.sh')
        link = os.path.join(self.directory, 'link.sh')
        with open(target, 'w') as script:
            script.write('exit 0\n')
        os.chmod(target, 0o700)
        os.symlink(target, link)
        with self.assertRaises(OSError):
            pinned_module.PinnedScript(link, self.logger)

    def test_full_runner_pins_pre_and_post_across_replacement(self):
        pre = os.path.join(self.directory, 'pre.sh')
        post = os.path.join(self.directory, 'post.sh')
        output = os.path.join(self.directory, 'result.txt')
        for path in [pre, post]:
            with open(path, 'w') as script:
                script.write('printf "%s" "$1" >> "$2"\n')
            os.chmod(path, 0o700)
        config = os.path.join(self.directory, 'config.json')
        with open(config, 'w') as stream:
            json.dump({'preScriptLocation': pre, 'postScriptLocation': post,
                       'preScriptParams': ['pre-original ', output],
                       'postScriptParams': ['post-original', output]}, stream)
        runner = ScriptRunner.ScriptRunner(self.logger, 'native', config, 60)
        try:
            self.assertEqual(0, runner.validate_scripts()[0])
            runner.pollSleepTime = 0.01
            runner.pollTotalCount = 100
            for stage, path in [('pre', pre), ('post', post)]:
                os.rename(path, path + '.old')
                with open(path, 'w') as replacement:
                    replacement.write('printf replacement >> "$2"\n')
                completed, results = [False], [None]
                getattr(runner, stage + '_script')(0, completed, results)
                self.assertTrue(completed[0])
                self.assertEqual(0, results[0].errorCode)
            with open(output) as result:
                self.assertEqual('pre-original post-original', result.read())
        finally:
            runner.close()


if __name__ == '__main__':
    unittest.main()
