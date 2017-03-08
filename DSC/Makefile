all: package

SOURCES = \
	dsc.py \
	test \
	HandlerManifest.json \
	manifest.xml \
	azure \
	packages \

clean:
	rm -rf output

package: $(SOURCES) 
	mkdir -p output
	cp -t output -r $(SOURCES)

	cd output && zip -r ../DSC.zip * > /dev/null

.PHONY: all clean package

