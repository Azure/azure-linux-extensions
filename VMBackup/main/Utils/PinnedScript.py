"""Keep script validation and execution bound to the same open file."""

import errno
import os
import stat


class PinnedScript(object):
    def __init__(self, path, logger):
        self.path = path
        self.logger = logger
        self.fd = None
        fd = None
        try:
            # Nonblocking open prevents a substituted FIFO from hanging validation.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError(errno.EACCES, 'Script is not a regular file')
            if metadata.st_uid != 0 or metadata.st_mode & 0o077:
                raise OSError(errno.EACCES,
                              'Script must be root-owned with no group/other access')
            self.device = metadata.st_dev
            self.inode = metadata.st_ino
            self.fd = fd
            logger.log('Pinned script {0}: device={1}, inode={2}'.format(
                path, self.device, self.inode), True, 'Info')
        except (OSError, AttributeError) as err:
            if fd is not None:
                os.close(fd)
            logger.log('Cannot pin script {0}: {1}'.format(path, err),
                       True, 'Error')
            raise

    def execution_path(self):
        if self.fd is None:
            raise OSError(errno.EBADF, 'Validated script descriptor is closed')
        # A parent-owned procfs reference works on Python 2.7 without inheriting
        # unrelated descriptors or using preexec_fn in the threaded plugin host.
        path = '/proc/{0}/fd/{1}'.format(os.getpid(), self.fd)
        metadata = os.stat(path)
        if (metadata.st_dev, metadata.st_ino) != (self.device, self.inode):
            raise OSError(errno.EACCES, 'Pinned script procfs identity mismatch')
        return path

    def duplicate(self):
        if self.fd is None:
            raise OSError(errno.EBADF, 'Validated script descriptor is closed')
        duplicate = PinnedScript.__new__(PinnedScript)
        duplicate.path = self.path
        duplicate.logger = self.logger
        duplicate.device = self.device
        duplicate.inode = self.inode
        duplicate.fd = os.dup(self.fd)
        return duplicate

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)
