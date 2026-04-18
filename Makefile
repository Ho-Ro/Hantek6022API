PACKAGE_NAME = hantek6022api

all: firmware pyht6022

firmware: fw_version fw_DSO6021 fw_DSO6022BE fw_DSO6022BL fw_DDS120

FIRMWARE_DIR=Firmware
FWDSO6021=$(FIRMWARE_DIR)/DSO6021
FWDSO6022BE=$(FIRMWARE_DIR)/DSO6022BE
FWDSO6022BL=$(FIRMWARE_DIR)/DSO6022BL
FWDDS120=$(FIRMWARE_DIR)/DDS120
PYFWHEX=../../PyHT6022/Firmware/HEX
PYTHON=$(shell which python || which python3)


FX2LIB_DIR = fx2lib
DEB_DIST_DIR = deb_dist
BUILD_DIR = build
DIST_DIR = dist
PYHT6022_DIR = PyHT6022
EGG_INFO_DIR = *.egg-info


.PHONY: fw_DSO6021
fw_DSO6021: fw_version
	cd $(FWDSO6021) && make && cp dso6021-firmware.hex $(PYFWHEX)


.PHONY: fw_DSO6022BE
fw_DSO6022BE: fw_version
	cd $(FWDSO6022BE) && make && cp dso6022be-firmware.hex $(PYFWHEX)


.PHONY: fw_DSO6022BL
fw_DSO6022BL: fw_version
	cd $(FWDSO6022BL) && make && cp dso6022bl-firmware.hex $(PYFWHEX)


.PHONY: fw_DDS120
fw_DDS120: fw_version
	cd $(FWDDS120) && make && cp dds120-firmware.hex $(PYFWHEX)


.PHONY: fx2upload
fx2upload:
	cd fx2upload && make


# update the changelog from git
.PHONY:	changelog
changelog:
	git log --pretty="%cs: %s [%h]" > changelog


# firmware version synchronisation to OpenHantek
.PHONY:	fw_version
fw_version:
	@echo
	@./MK_FW_VERSION.sh | tee $(FIRMWARE_DIR)/dso602x_fw_version.h


# build the python package
.PHONY: pyht6022
pyht6022: firmware
	$(PYTHON) -m build


# create a debian binary package
.PHONY:	deb
deb:	firmware changelog
	@echo "Building Debian package..."
	debuild -us -uc -b
	@mkdir -p $(DEB_DIST_DIR)
	@rm -f $(DEB_DIST_DIR)/*
	@mv ../hantek6022api_* $(DEB_DIST_DIR)
	@ls -l $(DEB_DIST_DIR)/hantek6022api_*.deb


# Install the latest version of *.deb package
# If there is no *.deb file then "make deb"
.PHONY: debinstall
debinstall:
	@ls -l $(DEB_DIST_DIR)/hantek6022api_*.deb || make deb
	@sudo dpkg --install `ls $(DEB_DIST_DIR)/hantek6022api_*.deb | tail -1` || sudo apt -f install


# Uninstall Debian package
.PHONY: debuninstall
debuninstall:
	@echo "Uninstalling Debian package..."
	sudo dpkg --purge hantek6022api


# remove all compiler and package build artefacts
.PHONY: clean
clean:
	-rm -rf *~ .*~ deb_dist dist *.tar.gz *.egg* build tmp
	@$(MAKE) -C $(FWDSO6021) clean 2>/dev/null || true
	@$(MAKE) -C $(FWDSO6022BE) clean 2>/dev/null || true
	@$(MAKE) -C $(FWDSO6022BL) clean 2>/dev/null || true
	@$(MAKE) -C $(FWDDS120) clean 2>/dev/null || true
	@$(MAKE) -C fx2upload clean 2>/dev/null || true
# Clean Python build artifacts
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	rm -rf $(EGG_INFO_DIR)
	rm -rf $(PYTHON_CACHE)
# Clean Debian build artifacts
	rm -rf $(DEB_DIST_DIR)


# remove all package builds
.PHONY:	distclean
distclean: clean
	-rm -f *.deb


.PHONY: init
init:
	git submodule update --init --recursive
	sudo apt build-dep .

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
