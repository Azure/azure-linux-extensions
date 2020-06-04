default: clean init build

EXTENSIONS = \
	CustomScript \
	DSC \
	OSPatching \
	VMBackup

clean:
	rm -rf build

init:
	@mkdir -p build

build: init $(EXTENSIONS) buildVMAccess


define make-extension-zip
$(eval NAME    = $(shell grep -Pom1 "(?<=<Type>)[^<]+" $@/manifest.xml))
$(eval VERSION = $(shell grep -Pom1 "(?<=<Version>)[^<]+" $@/manifest.xml))

@echo "Building '$(NAME)-$(VERSION).zip' ..."
@cd $@ && find . -type f | grep -v "/test/" | grep -v "./references" | zip -9 -@ ../build/$(NAME)-$(VERSION).zip > /dev/null
@find ./Utils    -type f | grep -v "/test/"                          | zip -9 -@ build/$(NAME)-$(VERSION).zip > /dev/null
endef


$(EXTENSIONS):
	$(make-extension-zip)
	@cd Common/ && echo ./waagentloader.py           | zip -9 -@ ../build/$(NAME)-$(VERSION).zip > /dev/null
	@cd Common/WALinuxAgent-2.0.16 && echo ./waagent | zip -9 -@ ../../build/$(NAME)-$(VERSION).zip > /dev/null



buildVMAccess:
	$(eval NAME  = $(shell grep -Pom1 "(?<=<Type>)[^<]+" VMAccess/manifest.xml))
	$(eval VERSION = $(shell grep -Pom1 "(?<=<Version>)[^<]+" VMAccess/manifest.xml))
	@echo "Building '$(NAME)-$(VERSION).zip' ..."
	@cd VMAccess && find . -type f | grep -v "/test/" | grep -v "./references" | zip -9 -@ ../build/$(NAME)-$(VERSION).zip > /dev/null
	@zip -9 build/$(NAME)-$(VERSION).zip ./Utils/__init__.py ./Utils/constants.py ./Utils/distroutils.py\
		./Utils/extensionutils.py ./Utils/handlerutil2.py ./Utils/logger.py ./Utils/ovfutils.py > /dev/null


.PHONY: clean build $(EXTENSIONS) buildVMAccess
