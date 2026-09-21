# ITS-Convert Makefile
# Cross-platform build system for creating executables and AppImages
#
# Targets:
#   make help           - Show this help
#   make install        - Install ITS-Convert in development mode
#   make test           - Run all tests
#   make translate      - Translate example scripts to all languages
#   make build-exe      - Build Windows .exe using PyInstaller
#   make build-nuitka   - Build with Nuitka (cross-platform)
#   make build-appimage - Build Linux AppImage
#   make build-all      - Build for all platforms
#   make clean          - Clean build artifacts
#   make review         - AI code review using codepolisher-cli
#   make pipeline       - Full pipeline: translate -> review -> build

.PHONY: help install test translate build-exe build-nuitka build-appimage build-all clean review pipeline

# Configuration
PYTHON ?= python3
PIP ?= pip
NPM ?= npm
ITSCONVERT ?= itsconvert
CODEPOLISHER ?= codepolisher

# Directories
SRC_DIR ?= .
EXAMPLES_DIR ?= examples
BUILD_DIR ?= build
DIST_DIR ?= dist

# Example script to use for builds
EXAMPLE_SCRIPT ?= $(EXAMPLES_DIR)/demo.py
TRANSLATED_DIR ?= $(BUILD_DIR)/translated
BUILD_SCRIPT ?= $(TRANSLATED_DIR)/demo.py

# Platform detection
UNAME := $(shell uname -s)
ifeq ($(UNAME),Linux)
    PLATFORM = linux
else ifeq ($(UNAME),Darwin)
    PLATFORM = macos
else ifeq ($(UNAME),MINGW*)
    PLATFORM = windows
else
    PLATFORM = unknown
endif

help: ## Show this help message
    @echo "ITS-Convert Build System"
    @echo "======================="
    @echo ""
    @echo "Available targets:"
    @echo ""
    @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
    @echo ""

install: ## Install ITS-Convert in development mode
    $(PIP) install -e ".[dev]"
    @echo "Done: ITS-Convert installed in development mode"

test: ## Run all tests
    pytest tests/ -v
    @echo "Done: All tests passed"

translate: ## Translate example scripts to all supported languages
    @mkdir -p $(TRANSLATED_DIR)
    $(ITSCONVERT) batch $(EXAMPLE_SCRIPT) \
        --to py --to sh --to ps1 --to cmd \
        --to js --to ts --to rb --to pl \
        --to lua --to php --to go --to rs \
        --to java --to c --to cpp --to cs \
        --to swift --to kt --to dart --to r \
        --to scala --to nim --to zig --to v \
        --to jl --to ex \
        --output-dir $(TRANSLATED_DIR)
    @echo "Done: Translated to all supported languages"

build-exe: ## Build Windows .exe using PyInstaller
    @mkdir -p $(DIST_DIR)
    $(ITSCONVERT) build $(BUILD_SCRIPT) --builder pyinstaller --output-dir $(DIST_DIR)
    @echo "Done: Built Windows .exe with PyInstaller"

build-nuitka: ## Build with Nuitka (creates standalone executable)
    @mkdir -p $(DIST_DIR)
    $(ITSCONVERT) build $(BUILD_SCRIPT) --builder nuitka --output-dir $(DIST_DIR)
    @echo "Done: Built with Nuitka"

build-appimage: ## Build Linux AppImage
    @mkdir -p $(DIST_DIR)
    $(ITSCONVERT) build $(BUILD_SCRIPT) --builder appimage --output-dir $(DIST_DIR)
    @echo "Done: Built Linux AppImage"

build-all: clean translate build-platform ## Build for all supported platforms
    @echo "Done: Full build completed"

clean: ## Clean all build artifacts
    rm -rf $(BUILD_DIR) $(DIST_DIR)
    @echo "Done: Cleaned build directories"
