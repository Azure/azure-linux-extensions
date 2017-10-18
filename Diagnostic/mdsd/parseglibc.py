# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

# This script is to parse glibc-based binary files and print out
# symbols whose GLIBC versions are higher than given version.
# Report error if any such symbol is found.

import argparse
import glob
import os
import sys
import time

totalErrors = 0


def LogError(msg):
    global totalErrors
    totalErrors = totalErrors + 1
    msg2 = "%s: Error: %s" % (sys.argv[0], msg)
    print msg2


def LogInfo(msg):
    print msg


def ParseCmdLine():
    parser = argparse.ArgumentParser(sys.argv[0])
    parser.add_argument("-d", "--dir", type=str, required=False,
                        help="directory where all its files are parsed.")
    parser.add_argument("-f", "--filepath", type=str, required=False, help="binary filepath.")

    parser.add_argument("-v", "--glibcver", type=str, required=True, help="max GLIBC ver. ex: 2.14")
    args = parser.parse_args()

    if not args.dir and not args.filepath:
        LogError("either '-d' or '-f' is required.")

    return args


def GetFilesToParse(filepath, dirname):
    files = []
    if filepath:
        if not os.path.isfile(filepath):
            LogError("%s is not a regular file." % (filepath))
        else:
            files.append(filepath)

    elif dirname:
        if not os.path.isdir(dirname):
            LogError("%s is not a directory." % (dirname))
        else:
            files = GetAllFiles(dirname)

    return files


# Get all files in a directory. This doesn't include subdirectories and symbolic links.
def GetAllFiles(dirname):
    if not dirname:
        return []

    filepattern = dirname + "/*"
    filedirs = glob.glob(filepattern)
    files = []
    for f in filedirs:
        if os.path.isfile(f) and (not os.path.islink(f)):
            files.append(f)
    return files


# Get symbol file by running 'nm'
def GetSymbols(filepath):
    outputfile = "testfile-" + str(time.time()) + ".txt"
    cmdline = "nm " + filepath + " 1>" + outputfile + " 2>&1"
    errCode = os.system(cmdline)
    if errCode != 0:
        LogError("cmd: '%s' failed with error %d" % (cmdline, errCode))
        return ""
    return outputfile


# Parse symbol file created by 'nm'
def ParseSymbols(symbolfile, glibcver):
    with open(symbolfile, "r") as fh:
        lines = fh.readlines()

    for line in lines:
        if "@GLIBC_" in line:
            line = line.strip()
            ParseLine(line, glibcver)

        # libstdc++ should be statically linked starting from version 1.4
        for unexpected_symbol in ["GLIBCXX", "CXXABI"]:
            if unexpected_symbol in line:
                LogError("Unexpected symbol {0}".format(unexpected_symbol))


# Parse one line to check for higher GLIBC version.
# Report error if found
def ParseLine(line, glibcver):
    global totalErrors
    items = line.split("GLIBC_")
    if len(items) != 2:
        LogError("unexpected symbol: %s" % (line))
    else:
        if CompareVer(items[1], glibcver):
            totalErrors = totalErrors + 1
            LogInfo(line)


# Return True if ver1 > ver2.
# Return False otherwise.
def CompareVer(ver1, ver2):
    v1list = ver1.split(".")
    v2list = ver2.split(".")
    n = min(len(v1list), len(v2list))
    for i in range(n):
        x = int(v1list[i])
        y = int(v2list[i])
        if x > y:
            return True
        elif x < y:
            return False

    if len(v1list) > len(v2list):
        return True

    return False


def RunTest(filepath, dirname, glibcver):
    LogInfo("Parse GLIBC versions ...")
    files = GetFilesToParse(filepath, dirname)

    if len(files) == 0:
        LogError("no file to parse. Abort.")
        return

    for binfile in files:
        LogInfo("\nStart to parse file '%s' ..." % (binfile))
        symbolfile = GetSymbols(binfile)
        if symbolfile:
            ParseSymbols(symbolfile, glibcver)
            os.remove(symbolfile)

    if totalErrors == 0:
        LogInfo("\nNo error is found. Test passed successfully.")
    else:
        LogInfo("\nTest failed. Total errors found: %d" % (totalErrors))


if __name__ == "__main__":
    args = ParseCmdLine()
    RunTest(args.filepath, args.dir, args.glibcver)
    sys.exit(totalErrors)
