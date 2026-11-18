# AGENTS.md — Imperative Governance & Epistemic Routing Laws (`endean-eng/tokenme`)

> **Scope:** Authoritative behavioral constraints for all coding agents (`architect`, `code`, `auditor`, `docs-maintainer`) operating in this repository [Ref: `ADR-001`..`ADR-016`].

---

## 1. Context Triad & Turn-1 Mipmap Routing [Ref: `ADR-001`..`ADR-004`, `ADR-008`, `ADR-012`, `ADR-016`]

1. **Strict Separation of Epistemic Modality (`ADR-001`, `ADR-014`):**
   - `README.md` = Human narrative onboarding, white paper prose, and opt-in configuration documentation. NEVER dump live symbol tables here.
   - `AGENTS.md` = Single-state imperative behavioral rules (`DO` / `DO NOT`), strictly capped at 60–150 lines. NEVER stuff file trees, symbol maps, or dormant commented-out profiles here (`ADR-014` Single-State Instruction Isolation).
   - `TOKENME.txt` = Declarative epistemic state (`v2.1`), `STATE_ROOT` Merkle provenance, `# === [TOPOLOGY] ===` edges, and `# === [FILES] ===` `[L1-Ln]` coordinates.
2. **Turn-1 `STATE_ROOT` & Mipmap Read (`ADR-003`, `ADR-008`, `ADR-012`):**
   - Read `./TOKENME.txt` (and any mounted `<subdir>/TOKENME.<slug>.txt` child shards in `# === [SHARDS] ===` relevant to your active task scope) BEFORE executing broad directory searches (`grep`, `find`) or full-file reads.
   - Use `[L1-Ln]` spans and AST coordinate signatures from `# === [FILES] ===` to issue surgical L3 line-range reads.
   - Where `ADR-016` or `ADR-010` amends an earlier ADR, **`ADR-016` strictly governs**.

---

## 2. Epistemic State & Declarative Sync (`TOKENME` v2.1 — Profile A) [Ref: `ADR-011`, `ADR-014`..`ADR-016`]

1. **Deterministic Triage Queue (`--triage`):**
   - Run `python tokenme-sync.py --triage` to locate `[BOOTSTRAP_REQUIRED]`, `[STALE_EDGE]`, `[SIG_DRIFT]`, `[BUDGET_EXCEEDED]`, `STALE_HASH (MINOR_DELTA | MAJOR_DELTA)`, `UNTRACKED_ARTIFACT`, or `ORPHANED_ENTRY` items across shards without reading clean manifests.
   - For `STALE_HASH (MINOR_DELTA)`, run the emitted `GIT_DIFF_CMD` rather than reading the entire file.
2. **Zero-Edit Atomic Hash Acknowledgment (`--ack`):**
   - Comment, docstring, and literal-only edits where the 6-hex structural signature (`struct_sig`) is unchanged auto-acknowledge during `python tokenme-sync.py --sync`.
   - When a structural code edit is strictly internal and preserves the file's public contract and `# === [TOPOLOGY] ===` edges, run `python tokenme-sync.py --ack <path>` to re-seal its `content:struct` hash and cascade `STATE_ROOT` without rewriting prose.
3. **Self-Consuming Bootstrap & Cryptographic Signature Locks (`[#sig:xxxxxx]`):**
   - Never write freeform prose in `# === [PURPOSE] ===` or `# === [TOPOLOGY] ===`; strictly obey the 3-line `SYSTEM:` / `BOUNDARY:` / `RUNTIME:` grammar and the directed `<File::Anchor> -> <File::Anchor> : <Mechanism>` edge grammar.
   - Never manually write or edit `[#sig:xxxxxx]` tags. Write clean declarative lines (or strip an outdated `[#sig:xxxxxx]` tag after verifying a `# [SIG_DRIFT]` warning) and run `python tokenme-sync.py --sync` to auto-stamp cryptographic locks and self-consume `# [BOOTSTRAP_REQUIRED]` prompts.
   - Keep every file's `Declarative Role & Invariants` column strictly within the UTF-8 byte ceiling (`<=B_hard B`) displayed in its `Archetype & Budget` column (`ADR-013`, `ADR-016` HC-05).

---

## 3. Decision Record Taxonomy & Scaffolder Boundaries [Ref: `ADR-005`..`ADR-008`, `ADR-010`, `ADR-013`, `ADR-016`]

1. **Hierarchical 3-Tuple Filename Grammar (`ADR-007`, `ADR-010` HC-03/04):**
   - All Decision Records in `docs/adr/` (primary) or `docs/decisions/` (fallback) MUST obey `RecordID "_" ISODate "_" TitleSlug ".md"` (e.g., `ADR-016_2026-11-13_Spec-Harmony-Triage.md`). Always wrap ADR filenames in backticks in Markdown prose.
2. **Append-Only Ledger & Status Lifecycle (`ADR-010` AMB-03):**
   - Never retroactively rewrite historical ADR bodies when scope evolves. Create a superseding ADR, update the amended ADR's status metadata (`Accepted (Amended by ADR-NNN)` or `Implemented (Amended by ADR-NNN)`), and sync `TOKENME.txt`.
3. **Zero-Dependency Standard-Library Invariant (`ADR-006`, `ADR-013`):**
   - `tokenme-sync.py` MUST remain a zero-dependency Python >= 3.9 standard-library script using the conservative UTF-8 byte estimator ($k_{\text{safe}} = 2.8\text{ B/tok}$). Never add `tiktoken` or third-party `pip` dependencies.
   - After mutating source files, `AGENTS.md`, ADRs, or `.l3.txt` sidecars, run `python tokenme-sync.py --sync` (adding `--compact` only when explicitly coalescing contracted shards below the 35% hysteresis floor) and verify with `python tokenme-sync.py --check` (`Exit 0`).

---

## 4. Opaque Assets, `.l3.txt` Surrogate Sidecars, & `L4` Cold Storage [Ref: `ADR-009`, `ADR-010`, `ADR-016`]

1. **Hydration Queue & Modality Rules:**
   - **Standard `L3` Opaque Assets (`[OPAQUE_L3]`):** Inspect the rendered image/SVG alongside pre-scraped metadata (`meta=...` in column 4 of `# === [FILES] ===`) and populate the 5th column (`Declarative Role & Invariants`) within its byte budget. Never hallucinate OCR text from surface textures.
   - **Demoted `L4` Assets (`[L4_DEMOTED]`):** Populate the adjacent `<filename>.<ext>.l3.txt` sidecar (`Asset_Class`, `Visual_Or_Content_Summary`, `Page_Map_And_TOC`, `Key_Specs_And_OCR`), change `# STATUS:` to `HYDRATED`, and summarize the asset in `# === [FILES] ===`.
   - **Multi-Page Flat PDF Cap:** For scanned PDFs (`MODALITY: FLAT_PDF`) exceeding 5 pages, inspect only Front Matter (Pages 1–5) and Back Matter (last 2 index pages) to build `Page_Map_And_TOC`. Mark body pages as `[L4_UNINDEXED_RASTER: Pages X..Y]`.
2. **Immutable Sidecar Header & `L4` Access Prohibition:**
   - NEVER alter Lines 1–4 of any `.l3.txt` sidecar (`# L4_SOURCE_FILE`, `# L4_SOURCE_HASH`, `# L4_BYTES`).
   - NEVER ingest a raw `[L4_DEMOTED]` binary whole into context. Read `<filename>.<ext>.l3.txt` first $\rightarrow$ locate target pages in `Page_Map_And_TOC` $\rightarrow$ query $\le 5$ pages per slice.