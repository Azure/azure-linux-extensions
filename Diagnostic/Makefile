all: package
.PHONY: all
.PHONY: clean
.PHONY: package

LADSOURCES = \
	diagnostic.py \
	watcherutil.py \
	tests \
	HandlerManifest.json \
	license.txt \
	manifest.xml \
	mdsdConfig.xml.template \
	portal.xml.template \
	rsyslog5 \
	rsyslog7 \
	rsyslog8 \
	run_unittests.sh \
	services \
	Utils \
	
UTILSOURCES = \
	../Utils/HandlerUtil.py \
	../Utils/__init__.py \
	../Utils/WAAgentUtil.py \

clean:
	rm -rf output

package: $(LADSOURCES) $(UTILSOURCES)
	mkdir -p output
	cp -t output -r $(LADSOURCES)
	cp -t output/Utils -r $(UTILSOURCES)

	
