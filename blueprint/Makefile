SHELL := /bin/bash

SRC_DIR      := src
DIAGRAM_DIR  := diagrams
RENDER_DIR   := $(DIAGRAM_DIR)/rendered
OUTPUT_DIR   := output
METADATA     := metadata.yaml

MD_FILES     := $(sort $(wildcard $(SRC_DIR)/*.md))
MMD_FILES    := $(wildcard $(DIAGRAM_DIR)/*.mmd)
RENDERED     := $(patsubst $(DIAGRAM_DIR)/%.mmd,$(RENDER_DIR)/%.pdf,$(MMD_FILES))

PDF_ENGINE   ?= tectonic
PANDOC_OPTS  := \
	--from=markdown+yaml_metadata_block+raw_tex \
	--metadata-file=$(METADATA) \
	--toc --toc-depth=2 \
	--number-sections \
	--pdf-engine=$(PDF_ENGINE) \
	-V geometry:margin=1in \
	-V papersize=a4 \
	-V linkcolor=blue \
	-V mainfont="Helvetica Neue" \
	-V monofont="Menlo" \
	-V mathfont="STIX Two Math" \
	-V fontsize=10pt \
	-V colorlinks=true

OUTPUT_PDF   := $(OUTPUT_DIR)/blueprint.pdf

.PHONY: all pdf diagrams clean check

all: pdf

pdf: check $(OUTPUT_PDF)

$(OUTPUT_PDF): $(MD_FILES) $(RENDERED) $(METADATA) | $(OUTPUT_DIR)
	pandoc $(PANDOC_OPTS) $(MD_FILES) -o $@
	@echo "Built: $@"

diagrams: $(RENDERED)

$(RENDER_DIR)/%.pdf: $(DIAGRAM_DIR)/%.mmd | $(RENDER_DIR)
	mmdc -i $< -o $@ -b transparent -t default

$(OUTPUT_DIR) $(RENDER_DIR):
	mkdir -p $@

clean:
	rm -rf $(OUTPUT_DIR) $(RENDER_DIR)

check:
	@command -v pandoc >/dev/null || { echo "pandoc not installed (brew install pandoc)"; exit 1; }
	@command -v mmdc >/dev/null || { echo "mmdc not installed (npm i -g @mermaid-js/mermaid-cli)"; exit 1; }
	@command -v $(PDF_ENGINE) >/dev/null || { echo "$(PDF_ENGINE) not installed (brew install tectonic)"; exit 1; }
