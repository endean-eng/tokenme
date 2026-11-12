# ADR-001: Separation of the Repository Context Triad and `TOKENME.txt` Nomenclature

* **Status:** Implemented
* **Date:** 2026-11-08
* **Component:** Core Specification (`TOKENME.txt` v1.1 / v2.0)

## 1. Context and Problem Statement
Autonomous and IDE-based coding agents suffer severe token bloat (wasting 60%+ of context budgets on blind `grep` and full-file reads) when entering a cold repository. Early iterations used `llms-dev.txt` or overloaded `AGENTS.md` / `README.md` to store repository topology. However, two structural problems emerged:
1. **Conflation of Concerns:** Mixing human marketing/onboarding prose (`README.md`), imperative behavioral constraints (`AGENTS.md` / `.clinerules`), and live spatial symbol coordinates inside a single file causes instruction dilution and chronic staleness when code line numbers shift.
2. **Nomenclature Collision with `llms.txt`:** The emerging `llms.txt` convention targets external web documentation scraping for public websites rather than internal repository state and line-number indexing.

## 2. Decision
We establish the **Repository Context Triad**, strictly orthogonalizing repository documentation by epistemic modality, and standardize on the filename **`TOKENME.txt`** (pairing symmetrically with `README.md`):

1. **`README.md` (Human Narrative Layer):** Explains *why* the project exists, how to install it, and high-level human onboarding.
2. **`AGENTS.md` (Imperative Governance Layer):** Defines *how* agents must behave—coding style, testing mandates, mutation boundaries, and forbidden anti-patterns.
3. **`TOKENME.txt` (Declarative Epistemic State Layer):** Maps *what* exists and *where* it lives—system invariants, subsystem routing, and exact `[Lstart-Lend]` symbol coordinates.

## 3. Consequences
* **Positive:** High-frequency coordinate updates in `TOKENME.txt` never pollute or overwrite immutable behavioral rules in `AGENTS.md` or human prose in `README.md`. The uppercase `TOKENME.txt` nomenclature provides immediate visual parity with `README.md` while maintaining a backward-compatible mental bridge from `llms-dev.txt`.
* **Negative:** Introduces a third top-level documentation artifact that must be explained to adopters via visual triad diagrams.