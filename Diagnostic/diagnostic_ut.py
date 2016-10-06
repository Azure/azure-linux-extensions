import unittest
import diagnostic
import sys
import subprocess
import os

class FStabUnitTests(unittest.TestCase):
    _watcher = None
    _datapath = os.path.join(os.getcwd(), 'utdata')

    def setUp(self):
        self._watcher = diagnostic.Watcher(sys.stderr, sys.stdout)

        try:
            os.mkdir(self._datapath)
        except OSError as e:
            pass

        # mount an overlay so that we can make changes to /etc/fstab
        subprocess.call(['sudo', 
            'mount', '-t', 'overlayfs',
            '-olowerdir=/etc,upperdir=' + self._datapath,
            'overlayfs', '/etc'])
        pass

    def tearDown(self):
        subprocess.call(['sudo', 'umount', '/etc'])
        try:
            os.rmdir(self._datapath)
        except OSError as e:
            pass

    def test_fstab_basic(self):
        self.assertEqual(self._watcher.handle_fstab(), 0)
       
    def test_fstab_touch(self):
        subprocess.call(['sudo', 'touch', '/etc/fstab'])
        self.assertEqual(self._watcher.handle_fstab(), 0)

    def addFstabEntry(self, fstabentry):
        subprocess.call(['sudo',
            'echo', fstabentry, '>>', '/etc/fstab'])

    @unittest.skip('Skipping because mount -f fails to detect error')
    def test_fstab_baduuid(self):
        self.addFstabEntry('UUID=1111111-1111-1111-1111-111111111111 /test ext4 defaults 0 0')
        self.assertNotEqual(self._watcher.handle_fstab(), 0)

    @unittest.skip('Skipping because mount -f fails to detect error')
    def test_fstab_baddevicename(self):
        self.addFstabEntry('/dev/foobar /test ext4 defaults 0 0')
        self.assertNotEqual(self._watcher.handle_fstab(), 0)

    @unittest.skip('Skipping because mount -f fails to detect error')
    def test_fstab_malformedentry(self):
        self.addFstabEntry('/test /dev/foobar ext4 defaults 0 0')
        self.assertNotEqual(self._watcher.handle_fstab(), 0)

    def test_fstab_goodentry(self):
        self.addFstabEntry('/dev/sdb1 /test ext4 defaults 0 0')
        self.assertEqual(self._watcher.handle_fstab(), 0)



if __name__ == '__main__':
    unittest.main()

