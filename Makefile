all: fw_DSO6021 fw_DSO6022BE fw_DSO6022BL fw_DDS120 fx2upload fw_version

FIRMWARE=Firmware
FWDSO6021=$(FIRMWARE)/DSO6021
FWDSO6022BE=$(FIRMWARE)/DSO6022BE
FWDSO6022BL=$(FIRMWARE)/DSO6022BL
FWDDS120=$(FIRMWARE)/DDS120
PYFWHEX=../../PyHT6022/Firmware/HEX
PYTHON=$(shell which python || which python3)

.PHONY: fw_DSO6021
fw_DSO6021:
	cd $(FWDSO6021) && make && cp dso6021-firmware.hex $(PYFWHEX)


.PHONY: fw_DSO6022BE
fw_DSO6022BE:
	cd $(FWDSO6022BE) && make && cp dso6022be-firmware.hex $(PYFWHEX)


.PHONY: fw_DSO6022BL
fw_DSO6022BL:
	cd $(FWDSO6022BL) && make && cp dso6022bl-firmware.hex $(PYFWHEX)


.PHONY: fw_DDS120
fw_DDS120:
	cd $(FWDDS120) && make && cp dds120-firmware.hex $(PYFWHEX)


.PHONY: fx2upload
fx2upload:
	cd fx2upload && make


# update the changelog from git
.PHONY:	changelog
changelog:
	git log --pretty="%cs: %s [%h]" > CHANGELOG


# firmware version synchronisation to OpenHantek
.PHONY:	fw_version
fw_version:
	@echo
	@./MK_FW_VERSION.sh | tee $(FIRMWARE)/dso602x_fw_version.h


# create a debian binary package
.PHONY:	deb
deb:	clean all changelog
	DEB_BUILD_OPTIONS=nocheck $(PYTHON) setup.py --command-packages=stdeb.command bdist_deb
	-rm -f hantek6022api_*_all.deb hantek6022api-*.tar.gz
	ln `ls deb_dist/hantek6022api_*_all.deb | tail -1` .
	ls -l deb_dist/hantek6022api_*_all.deb


# create a debian source package
.PHONY:	dsc
dsc:	clean all changelog
	DEB_BUILD_OPTIONS=nocheck $(PYTHON) setup.py --command-packages=stdeb.command sdist_dsc


.PHONY: debinstall
debinstall: deb
	sudo dpkg -i hantek6022api_*_all.deb


# remove all compiler and package build artefacts
.PHONY: clean
clean:
	$(PYTHON) setup.py clean
	-rm -rf *~ .*~ deb_dist dist *.tar.gz *.egg* build tmp
	( cd $(FWDSO6021) && make clean )
	( cd $(FWDSO6022BE) && make clean )
	( cd $(FWDSO6022BL) && make clean )
	( cd $(FWDDS120) && make clean )
	( cd fx2upload && make clean )


# remove all package builds
.PHONY:	distclean
distclean: clean
	-rm -f *.deb


# transfer the needed hex files to OpenHantek
.PHONY: xfer
xfer: all
	cp $(FWDSO6021)/dso6021-firmware.hex \
	../OpenHantek6022/openhantek/res/firmware
	cp $(FWDSO6022BE)/dso6022be-firmware.hex \
	../OpenHantek6022/openhantek/res/firmware
	cp $(FWDSO6022BL)/dso6022bl-firmware.hex \
	../OpenHantek6022/openhantek/res/firmware
	cp $(FIRMWARE)/dso602x_fw_version.h \
	../OpenHantek6022/openhantek/res/firmware
