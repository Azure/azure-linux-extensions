all: package
.PHONY: all
.PHONY: clean
.PHONY: package

LADSOURCES = \
	dsc.py \
	test \
	HandlerManifest.json \
	manifest.xml \
	azure \
	packages \

clean:
	rm -rf output

package: $(LADSOURCES) 
	mkdir -p output
	cp -t output -r $(LADSOURCES)
	zip -r DSC.zip output/* > /dev/null
