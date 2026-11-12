"""Path validation for root-owned pre/post scripts and configuration files."""

import os
import stat


def is_trusted_root_owned_file(filename, logger, allowed_public_permissions=0):
    """Reject replaceable paths, symlinks, and files accessible beyond policy."""
    if os.pardir in filename.split(os.sep):
        logger.log('Parent-directory references are not allowed: ' + filename,
                   True, 'Error')
        return False

    path = os.path.abspath(filename)
    directory = os.path.dirname(path)
    directories = []
    while True:
        directories.append(directory)
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent

    try:
        for directory in reversed(directories):
            entry = os.lstat(directory)
            if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != 0 or
                    entry.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
                logger.log('Untrusted parent directory: ' + directory,
                           True, 'Error')
                return False

        entry = os.lstat(path)
        public_permissions = entry.st_mode & 0o077
        if (not stat.S_ISREG(entry.st_mode) or entry.st_uid != 0 or
                public_permissions & ~allowed_public_permissions):
            logger.log('Untrusted file or permissions: ' + path, True, 'Error')
            return False
    except OSError as err:
        logger.log('Error validating trusted path ' + path + ': ' + str(err),
                   True, 'Error')
        return False

    return True
