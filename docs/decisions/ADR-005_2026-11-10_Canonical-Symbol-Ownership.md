# ADR-005: Canonical Symbol Ownership, Qualified Class Scoping, and Cross-Shard Pointer Linking

* **Status:** Accepted
* **Date:** 2026-11-10
* **Context:** TOKENME v2.0 Specification & `init_tokenme.py` (v0.0.2)

## Context and Problem Statement
When a repository spans multiple files and subsystem shards, identical or related symbol identifiers frequently appear in multiple locations across three distinct patterns:
1. **Intra-File Class/Impl Collisions:** Multiple classes or `impl` blocks in the same file define methods with identical names (e.g., `__init__`, `validate`, `run`, `new`). Keying synchronization state solely by `(file_path, symbol_name)` causes silent description overwrites during `--sync`.
2. **Header / Interface Prototype Splits:** Languages such as C, C++, and TypeScript (`*.h`, `*.hpp`, `*.d.ts`) declare 1-line prototypes in interface directories (`include/`) while placing executable bodies in implementation directories (`src/`).
3. **Barrel / Facade Re-Exports:** Module entrypoints (`__init__.py`, `index.ts`, `mod.rs`, `lib.rs`) re-export symbols defined in deeper shards without defining local executable bodies.

We must establish a deterministic governance rule that prevents duplicate semantic `[TODO: AGENT_FILL]` maintenance across shards, eliminates intra-file `--sync` collisions, and preserves 1-hop navigation when an agent lands on a header or facade file.

## Decision Drivers
* **Zero Duplicate Semantic Maintenance:** Agents and humans must never be asked to maintain prose descriptions for the same logical function in two different places.
* **Zero Silent Data Loss on `--sync`:** Overloaded functions or identically named methods in separate classes within the same file must never collide during coordinate resynchronization.
* **Eliminating Dead-End Shard Hops:** Reading an interface header (`TOKENME.include.txt`) or barrel file must immediately reveal the exact target file, `[Lstart-Lend]` span, and shard where the executable body resides.

## Decision Outcome
**Chosen Architecture: Single Canonical Coordinate Ownership + Deterministic Pointer Linking + Qualified Scoping.**

1. **Qualified Enclosing Scope (`ClassName.method_name`):** Both indentation-scoped and brace-scoped lexical scanners track enclosing `class`, `struct`, `interface`, `trait`, and `impl` boundaries. Methods are emitted and keyed with their enclosing type qualifier (`def ClassName.method_name`) plus an overload occurrence index `(rel_path, kind, qualified_name, overload_idx)` to guarantee 0% collision during `--sync`.
2. **Canonical Ownership at Executable Body:** Prose descriptions (`[TODO: AGENT_FILL]`) are allocated exclusively to the symbol's executable implementation (`end_line > start_line` or concrete body).
3. **Deterministic Cross-Shard `-> impl:` Pointers:** A post-scan $O(N)$ linker pass resolves `decl` prototypes in headers (`.h`, `.hpp`, `.d.ts`) against concrete definitions across the repository. Instead of emitting a `[TODO: AGENT_FILL]` slot on a prototype, the script automatically populates:
   `-> impl: <target_file> [Lstart-Lend] (Shard: <target_shard>)`
4. **Barrel / Facade Routing Line:** Barrel files (`__init__.py`, `index.ts/js`, `mod.rs`, `lib.rs`) are scanned for re-export statements and summarized via a single routing metadata line (`- **Re-Exports / Facade Routes:** ...`) pointing directly to target paths and shards.

## Consequences
* **Positive:** Reduces `--sync` description overwrite risk on multi-class files from 100% to 0%; eliminates redundant `[TODO: AGENT_FILL]` slots in C/C++/TS headers; turns interface and barrel files into zero-cost routing tables.
* **Negative:** Slightly increases scanner state-machine complexity (tracking enclosing class scope and running a secondary symbol-resolution pass).