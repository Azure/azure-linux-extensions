include ../Makefile.in.version

VERSION=${VERSION_NUM}
PACKAGE=lad-mdsd
LABEL?=dev

DATAROOT=./data-root
FAKEROOT=$(DATAROOT)/$(PACKAGE)-$(VERSION)
DOCDIR=$(FAKEROOT)/usr/share/doc/$(PACKAGE)
SHAREDIR=$(FAKEROOT)/usr/share/$(PACKAGE)
MDSD_BIN_DIR=$(FAKEROOT)/usr/local/lad/bin

MDSD_BUILT_BIN=../../builddir/release/bin/mdsd

RPM=RPMS/x86_64/$(PACKAGE)-$(VERSION)-$(LABEL).x86_64.rpm

TARBALL=$(PACKAGE)-$(VERSION).tgz

RPM: $(TARBALL)
	rpmbuild -v -bb --clean --define "_topdir $(realpath .)" SPECS/lad-mdsd.spec

$(TARBALL): rpm_prepare install-deps $(DOCDIR)/ChangeLog
	find $(FAKEROOT) -type d | xargs chmod 0755
	find $(FAKEROOT) -type d | xargs chmod ug-s
	cd $(DATAROOT) && tar -czf ../SOURCES/$@ *

$(DOCDIR):
	mkdir -p $@

$(DOCDIR)/ChangeLog: ../changelog $(DOCDIR)
	cp $< $@

rpm_prepare: clean
	mkdir -p SOURCES SPECS BUILD BUILDROOT RPMS SRPMS
	cp lad-mdsd.spec SPECS
	sed -i '/^Name:/c Name: $(PACKAGE)' SPECS/lad-mdsd.spec
	sed -i '/^Version:/c Version: $(VERSION)' SPECS/lad-mdsd.spec
	sed -i '/^Release:/c Release: $(LABEL)' SPECS/lad-mdsd.spec

.PHONY: clean install-clean install-deps

clean: install-clean
	-rm -rf SOURCES SPECS BUILD BUILDROOT RPMS SRPMS

install-clean:
	-rm -rf $(DATAROOT)

install-deps: install-clean
	mkdir -p $(MDSD_BIN_DIR)
	install -m 755 $(MDSD_BUILT_BIN) $(MDSD_BIN_DIR)/mdsd
