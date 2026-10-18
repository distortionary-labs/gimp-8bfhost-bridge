PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
PLUGIN := gimp-8bfhost-bridge
VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' $(PLUGIN)/gimp_8bfhost_bridge/__init__.py)
SOURCES := $(PLUGIN) tests

.PHONY: test lint format package install gimp-smoke clean

test:
	$(PYTEST) -q

lint:
	ruff check $(SOURCES)
	ruff format --check $(SOURCES)

format:
	ruff format $(SOURCES)

# A zip holding the plug-in folder, to extract into GIMP's plug-ins folder.
package:
	rm -rf dist && mkdir -p dist
	zip -qr dist/$(PLUGIN)-$(VERSION).zip $(PLUGIN) LICENSE -x '*/__pycache__/*' '*.pyc'
	@echo dist/$(PLUGIN)-$(VERSION).zip

install:
	scripts/install.sh

# Runs the plug-in inside a real, headless GIMP 3 with a throwaway profile.
gimp-smoke:
	tests/gimp_smoke/run.sh

clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
