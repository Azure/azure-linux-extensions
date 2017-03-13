all: package
<<<<<<< HEAD
.PHONY: all
.PHONY: clean
.PHONY: package

LADSOURCES = \
=======

SOURCES = \
>>>>>>> b5fe884410782544f86dbef55d790fee6f7a12b1
	dsc.py \
	test \
	HandlerManifest.json \
	manifest.xml \
	azure \
	packages \

clean:
	rm -rf output

<<<<<<< HEAD
package: $(LADSOURCES) 
	mkdir -p output
	cp -t output -r $(LADSOURCES)
	zip -r DSC.zip output/* > /dev/null
=======
package: $(SOURCES) 
	mkdir -p output
	cp -t output -r $(SOURCES)

	cd output && zip -r ../DSC.zip * > /dev/null

.PHONY: all clean package

>>>>>>> b5fe884410782544f86dbef55d790fee6f7a12b1
