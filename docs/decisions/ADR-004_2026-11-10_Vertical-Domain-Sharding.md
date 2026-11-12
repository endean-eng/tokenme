# ADR-004: Vertical Domain Sharding with Root L2 Eviction Over Horizontal Function Sharding

* **Status:** Implemented (Partially Superseded by ADR-010)
* **Date:** 2026-11-10
* **Context:** TOKENME v2.0 Specification & `init_tokenme.py` Bootstrapper

## Context and Problem Statement
L2 symbol coordinates (functions, classes, methods, and their `[Lstart-Lend]` spans) account for 75–85% of the token volume in a `TOKENME` catalog. As a repository grows past small-project bounds, function listings rapidly saturate the root `TOKENME.txt` budget. We must decide whether the primary sharding mechanism should:
1. **Horizontal Layer Sharding:** Offload all L2 function coordinates into a dedicated `TOKENME.functions.txt` sub-shard while keeping L1 file summaries in `TOKENME.txt`.
2. **Vertical Domain Sharding with Root L2 Eviction:** Strip all L2 function coordinates from the root `TOKENME.txt` (turning it into a pure L0/L1 router) and co-locate L2 functions with their parent L1 file invariants inside domain shards (`TOKENME.<subsystem>.txt`), using a dedicated `TOKENME.symbols.txt` shard strictly as a fallback for flat, single-directory repositories.

## Decision Drivers
* **Minimizing Agent Tool-Call Hops:** Every intermediate shard read adds 3–8 seconds of latency and compounds prompt-cache token overhead.
* **Epistemic Locality (Invariant Coupling):** Agents must read file-level invariants (e.g., concurrency locks, batching rules, mutation authority) in the same visual block as the `[Lstart-Lend]` function coordinates they plan to read or mutate.
* **Git Merge Isolation:** Concurrent branches modifying different subsystems should not collide on a single global function registry.

## Decision Outcome
**Chosen Option: Option 2 — Vertical Domain Sharding with Root L2 Eviction (and Flat-Directory Fallback).**

1. **Aggressive Root Eviction (`SHARD_TRIGGER_SYMBOLS = 75`):** When sharding triggers, the root `TOKENME.txt` is stripped of all L2 function coordinates (even for root-level files if total symbols exceed bounds). It retains only L0 global invariants, the L1 Subsystem Shard Routing Table, and a compact L1 file list.
2. **Co-Located Domain Shards (`TOKENME.<subsystem>.txt`):** Within each shard, L1 file role/invariant headers remain directly above their L2 function coordinates.
3. **Flat-Repository Fallback (`TOKENME.symbols.txt`):** If a repository exceeds sharding thresholds (`>75` symbols or `>250` lines) but lacks multiple subsystem directories (e.g., >80% of symbols reside in a single flat folder like `root/` or `src/`), the bootstrapper strips L2 functions from `TOKENME.txt` (leaving L0 invariants + L1 file summaries in root) and offloads the L2 symbol digest into `TOKENME.symbols.txt` (chunked if exceeding 2,000 tokens).

## Consequences
* **Positive:** Preserves 1-hop domain routing for modular repos, keeps file invariants physically bound to function spans, prevents global merge conflicts, and solves the single-directory flat-repo failure mode.
* **Negative:** Requires slightly more sophisticated sharding logic in `init_tokenme.py` to distinguish multi-directory repositories from flat repositories.