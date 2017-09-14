This directory contains files to create the Debian package and the RPM package for
the mdsd static binary executable that'll be bundled in LAD 3.0. LAD 3.0 depends on
omsagent, scx, omi packages (that are installed through
the omsagent shell bundle), and we shouldn't let these packages be removed when
the OMS Agent for Linux extension is uninstalled (the OMS Agent extension also uses
the omsagent shell bundle). The Debian/RPM packages include just the mdsd binary
at /usr/local/lad/bin, and specify the dependencies.

To run the Makefile on Ubuntu, the rpm package must be installed first:

    $ sudo apt-get install rpm

Then simply run 'make' at this directory, and collect the **/lad-mdsd-*.deb and the
**/lad-mdsd-*.rpm files.

NOTE: Version number conventions are different on dpkg and rpm, so that's why now
VERSION_NUM is separately defined in Makefile.in.version, and actual
version strings are composed for different deb/rpm packaging directories.
