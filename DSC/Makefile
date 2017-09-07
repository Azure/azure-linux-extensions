all: package

SOURCES = \
	httpclientfactory.py \
        subprocessfactory.py \
	curlhttpclient.py \
        serializerfactory.py \
        httpclient.py \
        urllib2httpclient.py \
        dsc.py \
	test \
	HandlerManifest.json \
	manifest.xml \
	azure \
	packages \
	../Utils \

clean:
	rm -rf output

package: $(SOURCES) 
	mkdir -p output
	cp -t output -r $(SOURCES)

	cd output && zip -r ../DSC.zip * > /dev/null

.PHONY: all clean package

