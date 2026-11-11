# ADR-002: Plain-Text `.txt` Extension, `[Lstart-Lend]` Coordinate Grammar, and Self-Referential Bootstrap

* **Status:** Accepted
* **Date:** 2026-11-08 (Updated 2026-11-11)
* **Component:** Core Specification (`TOKENME.txt` v1.1 / v2.0)

## 1. Context and Problem Statement
To help coding agents navigate source code without reading entire files, we must define both the internal serialization grammar and the file extension for the repository state index. Two key design questions arise:
1. **Serialization Format:** Should repository topology be stored in binary/structured databases (SQLite, vector embeddings, JSON AST dumps) or line-oriented text?
2. **File Extension (`.txt` vs. `.md`):** Given that `README.md` and `AGENTS.md` use the `.md` extension and our internal coordinate tables use lightweight Markdown syntax, why mandate `TOKENME.txt` (`.txt`) instead of `TOKENME.md`?

## 2. Decision Drivers
* **Zero-Tooling Agent Readability:** Every LLM agent possesses a native file-reading tool capable of slicing 1-based line ranges from plain text.
* **Build-Pipeline & SSG Isolation:** Documentation generators (Eleventy, MkDocs, Docusaurus, Astro) and prose linters (`vale`, `markdownlint`, `cspell`) routinely glob `**/*.md`.
* **Formatter & Editor Stability:** Auto-formatters (e.g., Prettier on save) frequently reflow `.md` tables and list indentation, risking parser drift during automated coordinate synchronization (`tokenme-sync.py`).
* **Epistemic Modality Signaling:** Developers and tools should immediately distinguish human/governance prose (`.md`) from machine-targeted token catalogs (`.txt`).

## 3. Decision
We standardize on **UTF-8 plain text with the explicit `.txt` file extension (`TOKENME.txt`)**, structured internally with lightweight Markdown headers/tables, `[Lstart-Lend]` 1-based line coordinates, and a mandatory **Self-Referential YAML Bootstrap Footer**.

### A. Intentional Selection of `.txt` Over `.md`
1. **SSG & CI Glob Immunity:** Using `.txt` prevents static site generators, documentation bundlers, and Markdown spell/link checkers (`**/*.md`) from accidentally ingesting, publishing, or failing CI builds on internal symbol coordinates and `[TODO: AGENT_FILL]` directives.
2. **Prettier / Auto-Formatter Bypass:** Standard IDE setups often run Prettier or Markdown table reflowers on `.md` files upon save. Keeping `TOKENME*.txt` as `.txt` preserves deterministic single-line record formatting required by `tokenme-sync.py`.
3. **Convention Continuity (`robots.txt` / `llms.txt` / `requirements.txt`):** In software engineering, `.txt` denotes a canonical, machine-ingested control or manifest artifact served as raw `text/plain; charset=utf-8`, visually separating the live data index (`TOKENME.txt`) from narrative/governance documents (`README.md`, `AGENTS.md`).

### B. Surgical Coordinate Grammar & Self-Referential Footer
1. **Coordinate Spans:** Every indexed file and symbol specifies its exact 1-based line span (`[L12-L88]`), mapping directly to the `start_line`/`end_line` parameters of standard agent file-reading tools.
2. **Self-Referential Bootstrap Block:** Every `TOKENME.txt` ends with a compact `agent_execution_protocol` YAML block instructing any cold agent reading the file on how to route via Mipmap coordinates, issue surgical L3 reads, and synchronize coordinates via `tokenme-sync.py`.

## 4. Consequences
* **Positive:** 100% immune to `.md` static-site build collisions and Prettier table-reflow corruption; instant visual distinction inside the Repository Context Triad (`README.md`, `AGENTS.md`, `TOKENME.txt`); compatible with every LLM and Git diff viewer.
* **Negative:** Code editors do not enable Markdown syntax highlighting on `TOKENME.txt` by default unless the user maps `TOKENME*.txt` to Markdown in their local IDE settings (a minor cosmetic trade-off for machine safety).