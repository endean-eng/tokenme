# ADR-003: Hierarchical Mipmap Sharding Architecture and Hard Token Ceilings

* **Status:** Accepted
* **Date:** 2026-11-09
* **Component:** `TOKENME.txt` v2.0 Enterprise Epistemic Specification

## 1. Context and Problem Statement
In small repositories (<2,500 LOC), a single monolithic `TOKENME.txt` file compresses the codebase at >100:1 while consuming <1,500 tokens. However, in mid-to-large production repositories or polyglot monorepos, a monolithic symbol catalog grows beyond 5,000–15,000 tokens. Injecting a 10,000-token index on turn 1 recreates the exact context-window saturation and "lost-in-the-middle" attention degradation that `TOKENME.txt` was designed to eliminate.

## 2. Decision
We model repository context after computer graphics **Mipmap Pyramids** (`L0` $\rightarrow$ `L1` $\rightarrow$ `L2` $\rightarrow$ `L3`), enforcing strict token ceilings and deterministic sharding triggers:

1. **Resolution Tiers:**
   * **L0 (System Identity & Global Invariants):** Root `TOKENME.txt` header and subsystem routing table ($\le 1,000$ tokens when sharded).
   * **L1 (File Inventory & Role Invariants):** File-level responsibility and mutation constraints.
   * **L2 (Symbol Coordinate Digest):** Granular class/function `[Lstart-Lend]` spans within subsystem shards ($\le 2,000$ tokens per shard).
   * **L3 (Raw Source Code):** Surgical line-range reads executed on demand by the agent.
2. **Deterministic Sharding Triggers:** A monolithic `TOKENME.txt` MUST transition to Sharded Mipmap Mode when it breaches any of four thresholds:
   * Estimated index size $> 3,000$ tokens
   * Index length $> 250$ lines
   * Extracted symbol count $> 75\text{--}100$ symbols
   * Polyglot boundary $\ge 2$ distinct execution runtimes

## 3. Consequences
* **Positive:** Guarantees bounded $O(1)$ initial context entry cost ($\le 1,000$ tokens) regardless of whether the underlying monorepo contains 5,000 or 500,000 lines of code.
* **Negative:** Requires automated shard-budget calculation and routing-table generation during scaffolding and synchronization (`tokenme-sync.py`).