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

build: init $(EXTENSIONS)

$(EXTENSIONS):
	$(eval NAME    = $(shell grep -Pom1 "(?<=<Type>)[^<]+" $@/manifest.xml))
	$(eval VERSION = $(shell grep -Pom1 "(?<=<Version>)[^<]+" $@/manifest.xml))

	@echo "Building '$(NAME)-$(VERSION).zip' ..."
	@cd $@ && find . -type f | grep -v "/test/" | grep -v "./references" | zip -9 -@ ../build/$(NAME)-$(VERSION).zip > /dev/null
	@find ./Utils    -type f | grep -v "/test/"                          | zip -9 -@ build/$(NAME)-$(VERSION).zip > /dev/null

.PHONY: clean build $(EXTENSIONS)
