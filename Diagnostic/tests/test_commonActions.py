import unittest
import os
import errno
import platform
import time
import string
import random
import DistroSpecific
from Utils.WAAgentUtil import waagent


class TestCommonActions(unittest.TestCase):
    _pid = os.getpid()
    _sequence = 0
    _messages = []
    _distro = None

    def make_temp_filename(self):
        self._sequence += 1
        return '/tmp/TestCommonActions_{0}_{1}_{2}'.format(self._pid, time.time(), self._sequence)

    def log(self, message):
        self._messages.append(message)

    @staticmethod
    def random_string(size, charset=string.ascii_uppercase + string.digits):
        return ''.join(random.SystemRandom().choice(charset) for _ in range(size))

    def setUp(self):
        dist = platform.dist()
        self._messages = []
        self._distro = DistroSpecific.get_distro_actions(dist[0], dist[1], self.log)

    def tearDown(self):
        pass

    def test_log_run_get_output_silent_success(self):
        (error, results) = self._distro.log_run_get_output('/bin/true')
        self.assertEqual(error, 0)
        self.assertEqual(results, '')

    def test_log_run_get_output_success(self):
        expected = TestCommonActions.random_string(50) + '\n'
        filename = self.make_temp_filename()
        with open(filename, 'w') as f:
            f.write(expected)
        (error, results) = self._distro.log_run_get_output('cat {0}'.format(filename))
        os.remove(filename)
        self.assertEqual(results, expected)
        self.assertEqual(error, 0)

    def test_log_run_get_output_failure(self):
        bad_file= '/bin/ThIsDoEsNoTeXiSt'
        (error, results) = self._distro.log_run_get_output(bad_file)
        self.assertEqual(127, error)
        self.assertIn(bad_file, results)    # Should be an error message talking about the non-existent file

    def test_log_run_ignore_output(self):
        filename = self.make_temp_filename()
        try:
            os.remove(filename)
        except OSError as e:
            if e.errno != errno.ENOENT:
                self.fail("Pre-test os.delete({0}) returned {1}".format(filename, errno.errorcode[e.errno]))
        error = self._distro.log_run_ignore_output("touch {0}".format(filename))
        self.assertEqual(error, 0)
        try:
            os.remove(filename)
        except IOError as e:
            if e.errno == errno.ENOENT:
                self.fail("Test command did not properly execute")
            else:
                self.fail("Post-test os.delete({0}) returned {1}".format(filename, errno.errorcode[e.errno]))

    def test_log_run_with_timeout_force_timeout(self):
        (status, output) = self._distro.log_run_with_timeout("sleep 10; echo sleep done", timeout=5)
        self.assertEqual(output, 'Process timeout\n')
        self.assertEqual(status, 1)

    def test_log_run_with_timeout_without_timeout(self):
        (status, output) = self._distro.log_run_with_timeout("echo success; exit 2", timeout=5)
        self.assertEqual(output, 'success\n')
        self.assertEqual(status, 2)

    def test_log_run_multiple_cmds(self):
        expected = 'foo\nbar\n'
        cmds = ('echo foo', 'echo bar')
        error, output = self._distro.log_run_multiple_cmds(cmds, False)
        self.assertEqual(error, 0)
        self.assertEqual(output, expected)

    def test_log_run_multiple_cmds_no_timeout(self):
        expected = 'foo\nbar\n'
        cmds = ('echo foo', 'echo bar')
        error, output = self._distro.log_run_multiple_cmds(cmds, True)
        self.assertEqual(error, 0)
        self.assertEqual(output, expected)

    def test_log_run_multiple_cmds_partial_timeout(self):
        expected = 'Process timeout\nbar\n'
        cmds = ('sleep 30; echo foo', 'echo bar')
        error, output = self._distro.log_run_multiple_cmds(cmds, True, 5)
        self.assertEqual(error, 1)
        self.assertEqual(output, expected)


if __name__ == '__main__':
    waagent.LoggerInit('waagent.verbose.log', None, True)
    unittest.main()
