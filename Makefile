NAME    = openshokz
VERSION = $(shell grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
TARBALL = $(NAME)-$(VERSION).tar.gz

.PHONY: srpm rpm tarball clean

tarball: $(TARBALL)

$(TARBALL):
	git archive --prefix=$(NAME)-$(VERSION)/ HEAD | gzip > $(TARBALL)

srpm: $(TARBALL)
	rpmbuild -bs $(NAME).spec \
	    --define "_sourcedir $(CURDIR)" \
	    --define "_srcrpmdir $(CURDIR)"

rpm: $(TARBALL)
	rpmbuild -bb $(NAME).spec \
	    --define "_sourcedir $(CURDIR)" \
	    --define "_rpmdir $(CURDIR)"

clean:
	rm -f $(TARBALL) *.src.rpm
	rm -rf build/ dist/ src/*.egg-info/
