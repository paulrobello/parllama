###############################################################################
# Common make values.
lib    := parllama
run    := pipenv run
python := $(run) python
lint   := $(run) pylint
mypy   := $(run) mypy
twine  := $(run) twine
build  := $(python) -m build
black  := $(run) black
isort  := $(run) isort

export PIPENV_VERBOSITY=-1
##############################################################################
# Run the app.
.PHONY: run
run:	        # Run the app
	$(python) -m $(lib)

.PHONY: app_help
app_help:	        # Show app help
	$(python) -m $(lib) --help

.PHONY: restore_defaults
restore_defaults:	        # Restore application default settings
	$(python) -m $(lib) --restore-defaults

.PHONY: clear_cache
clear_cache:	        # Clear application cache
	$(python) -m $(lib) --clear-cache

.PHONY: dev
dev:	        # Run in dev mode
	$(run) textual run --dev $(lib).app:ParLlamaApp


.PHONY: debug
debug:	        # Run in debug mode
	TEXTUAL=devtools make

.PHONY: console
console:	        # Run textual dev console
	$(run) textual console

##############################################################################
.PHONY: pip-lock
pip-lock:
	pipenv lock

.PHONY: first-setup
first-setup: pip-lock setup typecheck setupstubs	        # use this for first time run

# Setup/update packages the system requires.
.PHONY: setup
setup:				# Install all dependencies and type stubs
	pipenv sync --dev

.PHONY: resetup
resetup: remove-venv setup			# Recreate the virtual environment from scratch

.PHONY: remove-venv
remove-venv:			# Remove the virtual environment
	rm -rf $(shell pipenv --venv)

.PHONY: depsoutdated
depsoutdated:			# Show a list of outdated dependencies
	pipenv update --outdated

.PHONY: depsupdate
depsupdate:			# Update all dependencies
	pipenv update --dev

.PHONY: depsshow
depsshow:			# Show the dependency graph
	pipenv graph

.PHONY: setupsubs  # Install mypy type stubs
setupstubs:
	$(run) mypy --install-types --non-interactive

##############################################################################
# Checking/testing/linting/etc.
.PHONY: lint
lint:				# Run Pylint over the library
	$(lint) $(lib)

.PHONY: typecheck
typecheck:			# Perform static type checks with mypy
	$(mypy) --scripts-are-modules $(lib)

.PHONY: stricttypecheck
stricttypecheck:	        # Perform a strict static type checks with mypy
	$(mypy) --scripts-are-modules --strict $(lib)

.PHONY: checkall
checkall: lint typecheck	        # Check all the things

.PHONY: dobeforecommit
dobeforecommit: ugly checkall	        # Format then check

##############################################################################
# Package/publish.
.PHONY: package
package:			# Package the library
	$(build) -w

.PHONY: spackage
spackage:			# Create a source package for the library
	$(build) -s

.PHONY: packagecheck
packagecheck: clean package spackage		# Check the packaging.
	$(twine) check dist/*

.PHONY: testdist
testdist: packagecheck		# Perform a test distribution
	$(twine) upload --repository testpypi dist/*
	#$(twine) upload --skip-existing --repository testpypi dist/*

.PHONY: dist
dist: packagecheck		# Upload to pypi
	$(twine) upload --skip-existing dist/*

##############################################################################
# Utility.
.PHONY: ugly
ugly:				# Reformat the code with black.
	$(isort) $(lib)
	$(black) $(lib)

.PHONY: repl
repl:				# Start a Python REPL
	$(python)

.PHONY: clean
clean:				# Clean the build directories
	rm -rf build dist $(lib).egg-info

.PHONY: help
help:				# Display this help
	@grep -Eh "^[a-z]+:.+# " $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.+# "}; {printf "%-20s %s\n", $$1, $$2}'

##############################################################################
# Housekeeping tasks.
.PHONY: housekeeping
housekeeping:			# Perform some git housekeeping
	git fsck
	git gc --aggressive
	git remote update --prune

### Makefile ends here
