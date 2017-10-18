#!/bin/bash

# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

# This will build mdsd and its libraries
# Usage: see Usage()
#

TotalErrors=0

BuildType=
CCompiler=gcc
CXXCompiler=g++
BuildName=dev
BUILDDIR=builddir
MakeFileOnly=0
Parallelism="-j4"

# If CodeCoverage=1, build with code coverage options.
# NOTE: only gcc is supported and it must be debug build.
CodeCoverage=OFF

Usage()
{
    echo "Usage: $0 <-a> | <-d|-o> <-c|-g> [-b buildname] [-mC] [-p parallelism] [-s] [-t]"
    echo "    -b: use buildname. Default: timestamp."
    echo "    -C: capture code coverage."
    echo "    -d: build debug build."
    echo "    -m: create makefiles only. After done, run 'make help' for options."
    echo "    -o: build optimized(release) build."
    echo "    -p: specify number of parallel compile operations (default 4)."
}

if [ "$#" == "0" ]; then
    Usage
    exit 1
fi

args=`getopt b:Cdhmop: $*`
if [ $? != 0 ]; then
    Usage
    exit 1
fi
set -- $args

for i; do
    case "$i" in
        -b)
            BuildName=$2
            shift ; shift ;;
        -C)
            CodeCoverage=ON
            shift ;;
        -d)
            if [ -z "${BuildType}" ]; then
                BuildType=d
            else
                echo "Error: build type is already set to be ${BuildType}."
                exit 1
            fi
            shift ;;
        -h)
            Usage
            exit 0
            shift ;;
        -m)
            MakeFileOnly=1
            shift ;;
        -o)
            if [ -z "${BuildType}" ]; then
                BuildType=o
            else
                echo "Error: build type is already set to be ${BuildType}."
                exit 1
            fi
            shift ;;
        -p)
            declare -i numJobs  # This variable is an integer, guaranteed by the shell
            numJobs=$2
            if [ $numJobs -gt 1 ]; then
                Parallelism="-j$numJobs"
                echo "Setting parallelism to $Parallelism"
            else
                Parallelism=""
                echo "Disabling parallel compilation"
            fi
            shift; shift ;;
        --) shift; break ;;
    esac
done

if [ -z "${BuildType}" ]; then
    echo "Error: missing build type. -d or -o is required."
    exit 1
fi

if [ "${CodeCoverage}" == "ON" ]; then
    if [ "${BuildType}" != "d" ]; then
        echo "Error: only debug build is supported for code coverage."
        exit 1
    fi
fi

BuildWithCMake()
{
    echo
    echo Start to build source code. BuildType=${BuildType} ...
    BinDropDir=${BUILDDIR}.${BuildType}.${CCompiler}
    rm -rf ${BUILDDIR} ${BinDropDir}
    mkdir ${BinDropDir}
    ln -s ${BinDropDir} ${BUILDDIR}

    pushd ${BinDropDir}

    DefBuildNumber=
    if [ ! -z "${BuildName}" ]; then
        DefBuildNumber=-DBUILD_NUMBER=${BuildName}
    fi
    echo "BuildName: '${DefBuildNumber}'"

    CMakeBuildType="Release"
    if [ ${BuildType} == "d" ]; then
        CMakeBuildType="Debug"
    fi

    cmake -DCMAKE_C_COMPILER=${CCompiler} -DCMAKE_CXX_COMPILER=${CXXCompiler} \
          -DCMAKE_BUILD_TYPE=${CMakeBuildType} ${DefBuildNumber} \
          -DBUILD_COV=${CodeCoverage} ../

    CheckCmdError "cmake"

    if [ ${MakeFileOnly} != 0 ]; then
        echo
        echo Makfiles are created. To make, cd ${BUILDDIR}, run make \<target\>.
        echo
        make help
        exit ${TotalErrors}
    fi

    make ${Parallelism}
    CheckCmdError "make ${Parallelism}"

    make install
    CheckCmdError "make install"

    if [ ${CCompiler} == "gcc" ]; then
        # Make deb/rpm packages for LAD mdsd
        make -C ../lad-mdsd/deb LABEL=${BuildName}
        CheckCmdError  "lad-mdsd/deb"
        make -C ../lad-mdsd/rpm LABEL=${BuildName}
        CheckCmdError  "lad-mdsd/rpm"
    fi
    tar czf release.tar.gz release
    popd
}

# Check whether previous command has error or not.
# Usage: CheckCmdError "description"
CheckCmdError()
{
    if [ $? != 0 ]; then
        let TotalErrors+=1
        echo Error: build $1 failed
        exit ${TotalErrors}
    else
        echo Finished building $1 successfully
    fi
}

# Usage: ParseGlibcVer <dirname> <filename>(optional)
ParseGlibcVer()
{
    # Maximum GLIBC version supported by oldest supported distro
    glibcver=2.15
    ParserScript=./parseglibc.py
    dirname=$1
    filename=$2  # optional, can be NULL
    echo
    if [ -n "${filename}" ]; then
        echo python ${ParserScript} -f ${dirname}/${filename} -v ${glibcver}
        python ${ParserScript} -f ${dirname}/${filename} -v ${glibcver}
    else
        echo python ${ParserScript} -d ${dirname} -v ${glibcver}
        python ${ParserScript} -d ${dirname} -v ${glibcver}
    fi

    if [ $? != 0 ]; then
        let TotalErrors+=1
        echo Error: ParseGlibcVer failed: maximum supported GLIBC version is ${glibcver}.
        exit ${TotalErrors}
    fi
}

# Download/build/install the appropriate version of openssl.
#    This is needed because the lib{ssl,crypto}.a that's available through the Ubuntu repo
#    is causing some link errors at the last stage. We need to use /usr/local/ssl as the
#    top-level OpenSSL directory for the libraries, to make them work on all distros
#    (especially SUSE 11, which is already done that way).
BuildOpenSsl()
{
    opensslDir=openssl-1.0.2* # Grab the only (which must be latest) OpenSSL 1.0.2 release
    tgzFile=$opensslDir.tar.gz
    wget ftp://ftp.openssl.org/source/$tgzFile || exit 1
    InstallOpenSSL=1
    if [ -e /usr/local/lib/libcrypto.a -a -e /usr/local/lib/libssl.a ]; then
        OpenSSLVersion=$(strings /usr/local/lib/libssl.a | egrep "^OpenSSL " | awk '{ print $2 }')
        DownloadedTGZName=$(ls $tgzFile)
        if [ "$DownloadedTGZName" == "openssl-$OpenSSLVersion.tar.gz" ]; then # Already latest
            InstallOpenSSL=0
        fi
    fi
    if [ "$InstallOpenSSL" == "1" ]; then
        tar xfz $tgzFile
        cd $opensslDir
         # Need to make the lib*.a linkable to .so as well (for AI SDK lib*.so) by adding -fPIC.
        export CC="gcc -fPIC"
        ./config --prefix=/usr/local --openssldir=/usr/lib/ssl zlib
        make
        CheckCmdError "openssl make"
        sudo make install_sw
        CheckCmdError "openssl make install_sw"
        cd ..
    fi
}


echo Start build at `date`. BuildType=${BuildType} CC=${CCompiler} ...

BuildOpenSsl

BuildWithCMake

# Remaining steps should be run only on a non-static build except ParseGlibcVer on bin build.

ParseGlibcVer ./${BUILDDIR}/release/bin
ParseGlibcVer ./${BUILDDIR}/release/lib

echo
echo Finished all builds at `date`. error = ${TotalErrors}
exit ${TotalErrors}
