# Documentation build plan

## Deliverables

1. `docs/manual/` — task-oriented System Knowledge Designer user and administrator manual.
2. `docs/er-language/` — normative, versioned `.erd` syntax and compatibility reference.

Markdown is authoritative. HTML and PDF are generated release artefacts.

## Planned source structure

```text
docs/
├── manual/
│   ├── index.md
│   ├── installation-and-security.md
│   ├── projects-and-catalogue.md
│   ├── er-workbench.md
│   ├── revisions-and-repository.md
│   ├── sample-data-and-sandbox.md
│   ├── sql-workbench.md
│   ├── knowledge-and-search.md
│   ├── assistant-and-actions.md
│   ├── cross-project-systems.md
│   ├── control-api.md
│   ├── administration-and-jobs.md
│   ├── backup-restore-and-deployment.md
│   ├── troubleshooting.md
│   └── procurement-demonstration.md
└── er-language/
    ├── index.md
    ├── lexical-rules.md
    ├── model-and-layout.md
    ├── objects-and-fields.md
    ├── keys-constraints-and-indexes.md
    ├── relationships.md
    ├── cross-project-references.md
    ├── includes-and-layout-hints.md
    ├── grammar.md
    ├── diagnostics.md
    ├── examples.md
    ├── mermaid-import.md
    └── versioning-and-deprecation.md
```

## Source-of-truth rules

- Application behavior is demonstrated by automated workflow tests.
- ER syntax is defined by the Lark grammar and typed intermediate model.
- Every syntax example is stored as a parser fixture or extracted into a generated fixture during documentation validation.
- Screenshots must be reproducible, version-labelled and free of sensitive data.
- Commands use safe development defaults and call out production differences.
- Unsupported or planned behavior is labelled clearly and never written as currently available.

## Automated documentation checks

- Markdown link and heading validation.
- Example extraction and parser validation for valid `.erd` blocks.
- Expected-error assertions for invalid syntax examples.
- Smoke tests for installation, launch, health and demonstrated workflows.
- Checks that documented routes and settings exist.
- Optional HTML/PDF render and visual inspection before release.

## Phase acceptance

Each phase handover lists manual and syntax pages added or changed. A phase cannot close when its delivered UI, configuration, API or grammar is undocumented. The first usable release requires complete manual coverage, a complete reference for all implemented grammar, passing documentation checks, and versioned generated outputs.
