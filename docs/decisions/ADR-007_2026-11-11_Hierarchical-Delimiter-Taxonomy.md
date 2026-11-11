# ADR-007: Hierarchical Delimiter Decision Record Taxonomy
* **Filename:** `ADR-007_2026-11-11_Hierarchical-Delimiter-Taxonomy.md`
* **Date:** 2026-11-11
* **Status:** Accepted
* **Subsystem:** Repository Taxonomy / Context Triad (`AGENTS.md`, `TOKENME.txt`, `tokenme-sync.py`)

### 1. Context & Problem Statement
Architecture Decision Records (ADRs) and Internal Decision Records (IDRs) encode three distinct metadata attributes inside their filenames:
1. A monotonically increasing sequence identifier (`ADR-007`).
2. An ISO-8601 creation date (`2026-11-11`).
3. A human-readable semantic title slug (`Hierarchical-Delimiter-Decision-Record-Taxonomy`).

Conventional single-delimiter naming schemas (`kebab-case` such as `adr-007-2026-11-11-hierarchical-delimiter-taxonomy.md` or `snake_case`) overload a single ASCII character to represent both **inter-field boundaries** and **intra-field token separators**. This delimiter overloading introduces two structural defects:
* **Non-Trivial Lexical Parsing:** Extracting `[ID, Date, Slug]` from a flat hyphenated string requires brittle index slicing (`parts[0:2]`, `parts[2:5]`, `parts[5:]`) or regular expression capture groups because the title slug has variable token length.
* **High Visual Scan Latency:** In narrow IDE file trees and terminal directory listings, flat delimiter strings destroy visual chunking boundaries between fixed-width metadata fields and variable-width semantic titles.

### 2. Decision & Governing Mechanics
All repository decision records in `docs/adr/` (and gitignored internal records in `.roo/decisions-internal/`) MUST obey a two-level hierarchical ASCII delimiter grammar, whereas the public `TOKENME.txt` specification recommends this grammar as a non-mandatory reference pattern for deterministic tooling.

#### Formal EBNF Grammar
```ebnf
Filename   := RecordID "_" ISODate "_" TitleSlug ".md" ;
RecordID   := ("ADR" | "IDR") "-" Digit Digit Digit ;
ISODate    := Digit Digit Digit Digit "-" Digit Digit "-" Digit Digit ;
TitleSlug  := Word ("-" Word)* ;
Word       := UpperAlpha (LowerAlpha | UpperAlpha | Digit)* ;
```

#### Structural Invariants
1. **Level 1 Major Field Delimiter (`_`):** The underscore character (`0x5F`) is strictly reserved for separating the three top-level tuple elements (`[RecordID, ISODate, TitleSlug]`). Underscores are forbidden inside any individual field.
2. **Level 2 Intra-Field Delimiter (`-`):** The hyphen-minus character (`0x2D`) is used exclusively for internal token separation within `RecordID`, `ISODate`, and `TitleSlug`.
3. **Deterministic $O(1)$ Tuple Extraction:** Any compliant filename stem is guaranteed to decompose into an exact 3-tuple via a single string split without regular expressions:
   ```python
   def parse_decision_filename(filename: str) -> tuple[str, str, str]:
       stem = filename.removesuffix(".md")
       parts = stem.split("_")
       if len(parts) != 3:
           raise ValueError(f"Malformed decision filename: {filename}")
       return parts[0], parts[1], parts[2]  # (RecordID, ISODate, TitleSlug)
   ```
4. **Lexicographical & Chronological Alignment:** Placing `RecordID` (`ADR-NNN`) in the first tuple position ensures that standard ASCII sorting preserves strict chronological creation order while keeping short sequence identifiers left-aligned in narrow file explorers.
5. **Triad Separation of Concerns:**
   * **`AGENTS.md` (Imperative Governance):** Enforces this filename grammar as a hard constraint on all agents (`architect`, `code`, `docs-maintainer`) mutating `docs/adr/`.
   * **`TOKENME.txt` (Declarative State):** Indexes the resulting file paths under its architectural decision pointers without embedding imperative naming rules.
   * **Public Spec Scope:** External repositories adopting `TOKENME.txt` are not required to rename legacy ADRs (e.g., `0001-slug.md`), preserving zero-friction adoption while establishing the 3-tuple schema as the canonical reference convention.

### 3. Rejected Alternatives & Technical Postmortems (DO NOT RE-IMPLEMENT)
* **Rejected Option 1 (Flat Kebab-Case: `adr-007-2026-11-11-title-slug.md`):** Overloads `-` across four distinct semantic roles (prefix joiner, field separator, ISO-8601 date separator, and word separator). Splitting on `-` yields an array of length $5 + k$ (where $k$ is the number of words in the title), requiring hardcoded slice offsets to reconstruct fields and degrading human visual parsing.
* **Rejected Option 2 (Date-First Prefix: `2026-11-11_ADR-007_Title-Slug.md`):** Consumes the first 11 characters of every filename in the IDE sidebar with high-redundancy year/month prefixes (`2026-11-...`), pushing the unique reference handle (`ADR-007`) and semantic slug out of view in narrow directory trees while providing no sorting advantage over a monotonically increasing `ADR-NNN` prefix.
* **Rejected Option 3 (Enforcing the 3-Tuple Schema as a Mandatory `TOKENME.txt` Spec Rule):** Requiring external adopters to migrate existing `adr-tools` (`NNNN-title.md`) directories to pass `TOKENME.txt` validation introduces an unnecessary adoption barrier unrelated to context-window indexing.

### 4. Consequences & Engineering Trade-Offs
* **Markdown / LaTeX Inline Escaping Requirement:** Because the middle field (`_YYYY-MM-DD_`) is flanked by a pair of underscores, pasting a raw filename into Markdown prose or LaTeX without code fences will trigger inline italicization (`ADR-007` *2026-11-11* `Title-Slug.md`). All documentation and agent outputs MUST wrap raw filenames in backticks (`` `...` ``) or standard Markdown link targets.
* **Fixed Sequence Ceiling (`ADR-999`):** Zero-padding `RecordID` to 3 digits preserves lexicographical sorting up to 999 records per repository, which exceeds expected single-repository architectural decision volume by an order of magnitude without wasting horizontal character budget.