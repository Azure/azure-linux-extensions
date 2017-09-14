include ../Makefile.in.version

VERSION=${VERSION_NUM}
PACKAGE=lad-mdsd
LABEL?=~dev

ARCH?=amd64
VER=$(VERSION)-$(LABEL)

FAKEROOT=./data-root
DOCDIR=$(FAKEROOT)/usr/share/doc/$(PACKAGE)
SHAREDIR=$(FAKEROOT)/usr/share/$(PACKAGE)
MDSD_BIN_DIR=$(FAKEROOT)/usr/local/lad/bin

MDSD_BUILT_BIN=../../builddir/release/bin/mdsd

DEB=$(PACKAGE)-$(VER).$(ARCH).deb

package: $(DEB)

signed-package: _gpgorigin $(DEB)
	ar r $(DEB) $<

_gpgorigin: $(DEB)
	-rm -f $@
	ar p $(DEB) debian-binary control.tar.gz data.tar.gz | gpg -abs -o _gpgorigin

$(DEB): tarballs debian-binary
	-rm -f $@
	ar rc $@ debian-binary control.tar.gz data.tar.gz

$(DOCDIR):
	mkdir -p $@

$(DOCDIR)/changelog.Debian.gz: ../changelog $(DOCDIR)
	cat $< | gzip -9 > $@

$(DOCDIR)/copyright: ../copyright $(DOCDIR)
	cp $< $@

debian-binary:
	echo 2.0 > debian-binary

tarballs: data.tar.gz control.tar.gz

control.tar.gz: md5sums control
	-rm -rf control-root
	-mkdir -p control-root
	cp control md5sums control-root
	chmod 644 control-root/*
	sed -i '/^Version:/c Version: $(VER)' control-root/control
	sed -i '/^Package:/c Package: $(PACKAGE)' control-root/control
	sed -i '/^Architecture:/c Architecture: $(ARCH)' control-root/control
	cd control-root && tar -czf ../$@ --owner=root --group=root .

md5sums: install-deps
	(cd $(FAKEROOT) && md5sum `find -type f`) > $@
	chmod 0644 $@

data.tar.gz: install-deps \
		$(DOCDIR)/changelog.Debian.gz \
		$(DOCDIR)/copyright \
		$(LINTIANOVERRIDES)
	find $(FAKEROOT) -type d | xargs chmod 0755
	find $(FAKEROOT) -type d | xargs chmod ug-s
	find $(FAKEROOT)/usr/share/doc -type f | xargs chmod 0644
	cd $(FAKEROOT) && tar -czf ../$@ --owner=root --group=root --mode=go-w *

.PHONY: clean install-clean install-deps

clean: install-clean
	-rm -rf control-root
	-rm -f debian-binary *.tar.gz _gpgorigin md5sums
	-rm -f $(PACKAGE)*.deb

install-clean:
	-rm -rf $(FAKEROOT)

install-deps: install-clean
	mkdir -p $(MDSD_BIN_DIR)
	install -m 755 $(MDSD_BUILT_BIN) $(MDSD_BIN_DIR)/mdsd
