default: clean init build

EXTENSIONS = \
	CustomScript \
	DSC \
	OSPatching \
	VMAccess \
	VMBackup

clean:
	rm -rf build

init:
	@mkdir -p build

build: init $(EXTENSIONS)

define make-extension-zip
$(eval NAME    = $(shell grep -Pom1 "(?<=<Type>)[^<]+" $@/manifest.xml))
$(eval VERSION = $(shell grep -Pom1 "(?<=<Version>)[^<]+" $@/manifest.xml))

@echo "Building '$(NAME)-$(VERSION).zip' ..."
@cd $@ && find . -type f | grep -v "/test/" | grep -v "./references" | zip -9 -@ ../build/$(NAME)-$(VERSION).zip > /dev/null
@find ./Utils    -type f | grep -v "/test/"                          | zip -9 -@ build/$(NAME)-$(VERSION).zip > /dev/null
endef

$(EXTENSIONS):
	$(make-extension-zip)

.PHONY: clean build $(EXTENSIONS)
