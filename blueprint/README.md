# Quant Platform Blueprint

Reference architecture for a multi-tenant SaaS platform enabling hedge funds to productionalize quantitative models on Google Cloud Platform. Emphasises full local reproducibility of production, silo tenancy, and portable open-source components over cloud-proprietary services.

## Building the PDF

### One-time setup

```bash
# pandoc (markdown → PDF orchestration)
brew install pandoc

# mermaid-cli (render .mmd diagrams to PDF)
npm install -g @mermaid-js/mermaid-cli

# tectonic (modern, lightweight LaTeX engine; auto-fetches packages)
brew install tectonic
```

Alternative PDF engines: `basictex`, `mactex`, or `weasyprint` (see `Makefile`).

### Build

```bash
make pdf        # render diagrams + build blueprint.pdf
make clean      # remove build artefacts
make diagrams   # render diagrams only
```

Output: `output/blueprint.pdf`

## Structure

```
blueprint/
├── src/           # markdown sections (numbered)
├── diagrams/      # mermaid sources (.mmd) + rendered (.pdf)
├── templates/     # pandoc / latex templates
├── metadata.yaml  # pandoc document metadata
└── Makefile       # build orchestration
```

## Authoring

- One file per section in `src/`, numbered for ordering
- Diagrams live in `diagrams/*.mmd`, referenced from markdown as `![caption](diagrams/rendered/<name>.pdf){width=90%}`
- Mermaid diagrams are pre-rendered to vector PDF; re-run `make diagrams` after edits
