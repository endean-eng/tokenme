#!/usr/bin/env python3
"""
test_v2.1.1_tokenme-sync.py
Comprehensive, zero-dependency standard-library unit & integration test suite
for tokenme-sync.py (v2.1.1) covering all architectural invariants across
ADR-001 through ADR-016.

Usage:
  python test_v2.1.1_tokenme-sync.py
  python -m unittest test_v2.1.1_tokenme-sync.py -v

Coverage Matrix:
  - ADR-001 & ADR-002: Context Triad separation, TOKENME.txt nomenclature, [L1-Ln] coordinate spans.
  - ADR-003 & ADR-004: Hierarchical mipmap sharding triggers (>75 symbols, >=8 opaque, hop budget).
  - ADR-005: Qualified Class.method scoping, @bound ADR tags, arity extraction, barrel/init detection.
  - ADR-006: Fail-closed quarantine (binary null byte, oversize >1MiB, invalid UTF-8, Python SyntaxError).
  - ADR-007 & ADR-010 HC-03: 3-tuple ADR naming, docs/adr/ primary vs. docs/decisions/ fallback, collision gates.
  - ADR-008: Multi-tier Merkle STATE_ROOT, CRLF-to-LF invariance, child shard STATE_ROOT rollup.
  - ADR-009 & ADR-010 ERR-01/02: Opaque PNG/GIF/JPEG/SVG/PDF inspection, L4 demotion, unscrambled .l3.txt stubs.
  - ADR-011: Self-consuming [BOOTSTRAP_REQUIRED] prompts, polymorphic [#sig:xxxxxx] locks, 3-stage AST pruning.
  - ADR-012: Clamped hop-distance threshold curve S_trigger(d), ATOMIC_MONOLITH guard, R_max=1 overflow warn.
  - ADR-013: UTF-8 byte token estimator (k_safe=2.8), 1.25x guardbands, 35% merge floor, 65% parent headroom, --compact.
  - ADR-014: Profile A default AGENTS.md scaffolding, Single-State Isolation check (rejects <!-- comments).
  - ADR-015: --triage work queue (UNFILLED_BOOTSTRAP, STALE_HASH MINOR/MAJOR, UNTRACKED_ARTIFACT, ORPHANED_ENTRY) & --ack.
  - ADR-016: Unified 5-column # === [FILES] === schema, Dual-Hash Auto-Ack (content:struct), --strict-bytes override.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List, Tuple


def _load_tokenme_sync_module() -> Any:
    """Dynamically loads tokenme-sync.py (or fallback filenames) from the working directory."""
    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / "tokenme-sync.py",
        base_dir / "tokenme-sync-v2.1.1.py",
        base_dir / "tokenme-sync-v2.1.1.txt",
        Path.cwd() / "tokenme-sync.py",
        Path.cwd() / "tokenme-sync-v2.1.1.txt",
    ]
    for cand in candidates:
        if cand.is_file():
            spec = importlib.util.spec_from_file_location("tokenme_sync", str(cand))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["tokenme_sync"] = mod
                spec.loader.exec_module(mod)
                return mod
    raise FileNotFoundError(
        "Could not locate `tokenme-sync.py` (or `tokenme-sync-v2.1.1.txt`) in the current directory."
    )


ts = _load_tokenme_sync_module()


def _make_valid_png_bytes(width: int = 256, height: int = 256, text_chunk: Tuple[str, str] = ("Author", "TOKENME")) -> bytes:
    """Constructs a valid binary PNG header with an IHDR chunk and optional tEXt metadata."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + b"\x00\x00\x00\x00"
    k, v = text_chunk
    text_payload = k.encode("ascii") + b"\x00" + v.encode("ascii")
    text_part = struct.pack(">I", len(text_payload)) + b"tEXt" + text_payload + b"\x00\x00\x00\x00"
    # Pad to >= 512 bytes so MIN_RASTER_BYTES gate passes
    padding = b"\x00" * 600
    return sig + ihdr_chunk + text_part + padding


class TokenmeSyncV211TestSuite(unittest.TestCase):
    """Exhaustive test suite verifying ADR-001 through ADR-016 invariants in tokenme-sync.py v2.1.1."""

    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="tokenme_test_v211_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_cli(self, args: List[str]) -> Tuple[int, str, str]:
        """Runs ts.main() in-process with captured stdout and stderr."""
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = ["tokenme-sync.py"] + args
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                try:
                    rc = ts.main()
                except SystemExit as exc:
                    rc = int(exc.code) if exc.code is not None else 0
        finally:
            sys.argv = old_argv
        return rc, out_buf.getvalue(), err_buf.getvalue()

    def _hydrate_all_shards(self, root: Path, role_text: str = "Core deterministic module enforcing domain invariants.") -> None:
        """Simulates an agent hydrating [PURPOSE], [TOPOLOGY], and [FILES] placeholders across all shards."""
        first_py_file = None
        for p in sorted(root.rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            if not rel.startswith("."):
                first_py_file = rel
                break
        target_endpoint = f"{first_py_file}::*" if first_py_file else "TOKENME.txt::[FILES]"

        for shard in ts.find_existing_tokenme_shards(root):
            txt = shard.read_text(encoding="utf-8")
            lines = txt.splitlines()
            new_lines: List[str] = []
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.strip().startswith("# [BOOTSTRAP_REQUIRED: POPULATE_PURPOSE"):
                    new_lines.append("SYSTEM: Deterministic epistemic state compiler and repository router.")
                    new_lines.append("BOUNDARY: Source AST and opaque assets -> Cryptographically locked TOKENME shards.")
                    new_lines.append("RUNTIME: Python >= 3.9 Standard Library Only")
                    # Skip the 3 placeholder lines (SYSTEM:, BOUNDARY:, RUNTIME:)
                    i += 4
                    continue
                if line.strip().startswith("# [BOOTSTRAP_REQUIRED: POPULATE_TOPOLOGY"):
                    new_lines.append(
                        f"{target_endpoint} -> TOKENME.txt::[FILES] : Synchronizes AST coordinates and dual hashes"
                    )
                    i += 1
                    continue
                if "| [BOOTSTRAP_REQUIRED] |" in line:
                    line = line.replace("| [BOOTSTRAP_REQUIRED] |", f"| {role_text} |")
                new_lines.append(line)
                i += 1
            shard.write_text("\n".join(new_lines) + "\n", encoding="utf-8", newline="\n")

    # -------------------------------------------------------------------------
    # 1. ADR-013 & ADR-016 HC-03 / HC-04 / HC-05: Math, Budgets & Hop Curve
    # -------------------------------------------------------------------------

    def test_01_utf8_byte_token_estimation_and_hop_curve(self) -> None:
        """Verifies ADR-013 k_safe=2.8 token estimator and ADR-012/016 clamped hop relaxation curve."""
        self.assertEqual(ts.VERSION, "2.1.1")
        self.assertEqual(ts.SPEC_VERSION, "2.1")
        self.assertEqual(ts.utf8_byte_len("abc"), 3)
        self.assertEqual(ts.estimate_tokens(""), 0)
        # 28 UTF-8 bytes / 2.8 = 10 tokens
        self.assertEqual(ts.estimate_tokens("a" * 28), 10)
        self.assertEqual(ts.estimate_tokens("a" * 29), 11)

        # Clamped Hop-Distance Curve: d=0 (1500), d=1 (2250), d=2 (3000), d=3 (3750), d>=4 (4000 cap)
        expected_curve = [1500, 2250, 3000, 3750, 4000, 4000]
        actual_curve = [ts.hop_split_token_ceiling(d, is_monolith=False) for d in range(6)]
        self.assertEqual(actual_curve, expected_curve)

        # Unsharded Monolith d=0 ceiling = 3000 tokens
        self.assertEqual(ts.hop_split_token_ceiling(0, is_monolith=True), 3000)

        # Reverse merge floor = floor(0.35 * T_split(d))
        self.assertEqual(ts.hop_merge_token_floor(1), int(0.35 * 2250))  # 787
        self.assertEqual(ts.hop_merge_token_floor(2), int(0.35 * 3000))  # 1050

    def test_02_archetype_classification_and_byte_guardbands(self) -> None:
        """Verifies ADR-011 & ADR-016 HC-05 8-archetype taxonomy and 1.25x byte guardbands."""
        self.assertEqual(ts.classify_archetype("src/__init__.py"), "BARREL_INIT")
        self.assertEqual(ts.classify_archetype("tests/test_engine.py"), "TEST_SUITE")
        self.assertEqual(ts.classify_archetype("pyproject.toml"), "BUILD_CONFIG")
        self.assertEqual(ts.classify_archetype("config/schema.json"), "DATA_SCHEMA")
        self.assertEqual(ts.classify_archetype("docs/architecture.md"), "SPEC_DOC")
        self.assertEqual(ts.classify_archetype("cli.py", source_text="import argparse\n"), "ORCHESTRATOR")
        self.assertEqual(ts.classify_archetype("src/engine.py", source_text="class Engine: pass\n"), "DOMAIN_CODE")
        self.assertEqual(ts.classify_archetype("diagram.png", is_opaque=True), "OPAQUE_ASSET")

        # At 50 LOC, ratio = 1.0 -> log2(1.0) = 0 -> t_target = base_tok (25 for DOMAIN_CODE)
        t_tok, b_target, b_hard = ts.compute_file_budget_bytes("DOMAIN_CODE", effective_loc=50)
        self.assertEqual(t_tok, 25)
        self.assertEqual(b_target, 70)   # ceil(2.8 * 25) = 70 B
        self.assertEqual(b_hard, 88)     # ceil(1.25 * 70) = 88 B

    # -------------------------------------------------------------------------
    # 2. ADR-005 & ADR-011: Polymorphic AST, State Effects & 3-Stage Pruning
    # -------------------------------------------------------------------------

    def test_03_python_ast_scoping_bound_tags_and_structural_sig_invariance(self) -> None:
        """Verifies qualified Class.method scoping, @bound tags, comment invariance, and state effect sensitivity."""
        code_v1 = (
            "# Header comment\n"
            "class FlightController:\n"
            "    \"\"\"Docstring v1.\"\"\"\n"
            "    # @bound ADR-005\n"
            "    def compute_thrust(self, mass: float, accel: float) -> float:\n"
            "        # Internal comment v1\n"
            "        k = 9.81\n"
            "        return max(0.0, mass * accel * k)\n"
        )
        code_v2_comment_and_literal_change = (
            "# Completely different comment!\n"
            "class FlightController:\n"
            "    \"\"\"Updated docstring v2 with extra details.\"\"\"\n"
            "    # @bound ADR-005\n"
            "    def compute_thrust(self, mass: float, accel: float) -> float:\n"
            "        # Changed literal constant from 9.81 to 9.80665\n"
            "        k = 9.80665\n"
            "        return max(0.0, mass * accel * k)\n"
        )
        code_v3_effect_and_arg_change = (
            "class FlightController:\n"
            "    def compute_thrust(self, mass: float, accel: float, limit: float) -> float:\n"
            "        if mass <= 0:\n"
            "            raise ValueError('bad mass')\n"
            "        return max(0.0, mass * accel)\n"
        )

        p1 = self.tmp_dir / "controller.py"
        p1.write_text(code_v1, encoding="utf-8")
        recs1, _, _, sig_map1 = ts.scan_repository(self.tmp_dir, max_size_bytes=1024 * 1024, leaf_len=6, dry_run=True)
        self.assertEqual(len(recs1), 1)
        r1 = recs1[0]
        sym_names = [s.name for s in r1.symbols]
        self.assertIn("FlightController", sym_names)
        self.assertIn("FlightController.compute_thrust", sym_names)
        method_sym = [s for s in r1.symbols if s.name == "FlightController.compute_thrust"][0]
        self.assertEqual(method_sym.arity, 2)  # 'self' excluded
        self.assertEqual(method_sym.bound_adr, "ADR-005")

        # Mutate comments, docstrings, and numeric literals -> content_hash MUST change, struct_sig MUST remain identical
        p1.write_text(code_v2_comment_and_literal_change, encoding="utf-8")
        recs2, _, _, sig_map2 = ts.scan_repository(self.tmp_dir, max_size_bytes=1024 * 1024, leaf_len=6, dry_run=True)
        r2 = recs2[0]
        self.assertNotEqual(r1.content_hash, r2.content_hash)
        self.assertEqual(r1.struct_sig, r2.struct_sig)
        self.assertEqual(
            sig_map1["controller.py"]["FlightController.compute_thrust"],
            sig_map2["controller.py"]["FlightController.compute_thrust"],
        )

        # Mutate argument signature and add 'raise' effect -> struct_sig MUST change
        p1.write_text(code_v3_effect_and_arg_change, encoding="utf-8")
        recs3, _, _, _ = ts.scan_repository(self.tmp_dir, max_size_bytes=1024 * 1024, leaf_len=6, dry_run=True)
        r3 = recs3[0]
        self.assertNotEqual(r2.struct_sig, r3.struct_sig)

    def test_04_three_stage_progressive_ast_pruning(self) -> None:
        """Verifies Stage 0 (full), Stage 1 (strip _private), and Stage 2 (fold >4 methods to Class[Nm])."""
        syms = [
            ts.SymbolSpan(kind="class", name=" CoreEngine", start_line=1, end_line=200, arity=1),
            ts.SymbolSpan(kind="def", name="CoreEngine.__init__", start_line=5, end_line=15, arity=2),
            ts.SymbolSpan(kind="def", name="CoreEngine._private_helper", start_line=16, end_line=30, arity=1),
            ts.SymbolSpan(kind="def", name="CoreEngine.step_a", start_line=31, end_line=50, arity=1),
            ts.SymbolSpan(kind="def", name="CoreEngine.step_b", start_line=51, end_line=70, arity=2),
            ts.SymbolSpan(kind="def", name="CoreEngine.step_c", start_line=71, end_line=90, arity=0),
            ts.SymbolSpan(kind="def", name="CoreEngine.step_d", start_line=91, end_line=110, arity=3),
        ]
        syms[0].name = "CoreEngine"

        # Stage 0: effective_loc < 150 and generous b_target includes _private_helper
        col_s0 = ts.format_pruned_ast_column(syms, b_target=500, effective_loc=80)
        self.assertIn("_private_helper", col_s0)

        # Stage 1: effective_loc >= 150 strips _private_helper but keeps __init__ and public methods
        col_s1 = ts.format_pruned_ast_column(syms, b_target=500, effective_loc=200)
        self.assertNotIn("_private_helper", col_s1)
        self.assertIn("__init__", col_s1)

        # Stage 2: tight b_target folds >4 methods into CoreEngine[5m]
        col_s2 = ts.format_pruned_ast_column(syms, b_target=45, effective_loc=250)
        self.assertIn("CoreEngine[5m]", col_s2)

    def test_05_non_python_polymorphic_structural_anchors(self) -> None:
        """Verifies Markdown [Heading], JSON key, and CSV header/@row_id structural signature extraction."""
        md_sigs, md_col = ts.scan_non_python_structural_sigs(
            "docs/spec.md",
            "# Overview\nText\n```python\n# fake heading in fence\n```\n## Architecture & Flow\n| A | B |\n",
        )
        self.assertIn("[Overview]", md_sigs)
        self.assertIn("[Architecture & Flow]", md_sigs)
        self.assertIn("[architecture-flow]", md_sigs)
        self.assertIn("secs=Overview, Architecture & Flow", md_col)

        json_sigs, json_col = ts.scan_non_python_structural_sigs("config.json", '{"port": 8080, "host": "localhost"}')
        self.assertIn("port", json_sigs)
        self.assertIn("host", json_sigs)
        self.assertIn("json_keys=[port, host]", json_col)

        csv_sigs, csv_col = ts.scan_non_python_structural_sigs("pinout.csv", "Pin,Signal,Voltage\nP1,VCC,3.3V\nP2,GND,0V\n")
        self.assertIn("Pin", csv_sigs)
        self.assertIn("@P1", csv_sigs)
        self.assertIn("2 rows", csv_col)

    # -------------------------------------------------------------------------
    # 3. ADR-006: Fail-Closed Quarantine Pipeline
    # -------------------------------------------------------------------------

    def test_06_fail_closed_quarantine_isolation(self) -> None:
        """Verifies binary null-bytes, invalid UTF-8, oversize text, and Python SyntaxError route to [QUARANTINE]."""
        (self.tmp_dir / "good.py").write_text("def ok() -> int:\n    return 1\n", encoding="utf-8")
        (self.tmp_dir / "broken_syntax.py").write_text("def broken(\n", encoding="utf-8")
        (self.tmp_dir / "null_binary.dat").write_bytes(b"some text\x00with null byte")
        (self.tmp_dir / "bad_utf8.txt").write_bytes(b"\xff\xfe\xfd invalid utf-8 sequence")
        (self.tmp_dir / "oversize.txt").write_text("A" * (60 * 1024), encoding="utf-8")  # 60 KiB > 32 KiB limit

        recs, q_log, _, _ = ts.scan_repository(self.tmp_dir, max_size_bytes=32 * 1024, leaf_len=6, dry_run=True)
        self.assertEqual([r.rel_path for r in recs], ["good.py"])

        q_map = {q.rel_path: q.reason for q in q_log}
        self.assertIn("broken_syntax.py", q_map)
        self.assertIn("SyntaxError", q_map["broken_syntax.py"])
        self.assertIn("null_binary.dat", q_map)
        self.assertIn("BinaryNullByte", q_map["null_binary.dat"])
        self.assertIn("bad_utf8.txt", q_map)
        self.assertIn("UnicodeDecodeError", q_map["bad_utf8.txt"])
        self.assertIn("oversize.txt", q_map)
        self.assertIn("OversizeText", q_map["oversize.txt"])

    # -------------------------------------------------------------------------
    # 4. ADR-009 & ADR-010 ERR-01 / ERR-02: Opaque Assets & L4 Sidecar Stubs
    # -------------------------------------------------------------------------

    def test_07_opaque_png_err01_svg_and_pdf_l4_demotion_err02(self) -> None:
        """Verifies PNG IHDR slice (ERR-01), micro-icon filtering, SVG scraping, and unscrambled L4 .l3.txt (ERR-02)."""
        # 1. Valid 256x256 PNG with tEXt metadata
        png_path = self.tmp_dir / "schematic.png"
        png_path.write_bytes(_make_valid_png_bytes(320, 240, ("Board", "RevC")))

        # 2. Tiny 32x32 PNG icon -> must be ignored (< 128px)
        tiny_png = self.tmp_dir / "icon.png"
        tiny_png.write_bytes(_make_valid_png_bytes(32, 32))

        # 3. Vector SVG with <title> and <text>
        svg_path = self.tmp_dir / "topology.svg"
        svg_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><title>Power Bus</title><text id="t1">24V Rail</text></svg>',
            encoding="utf-8",
        )

        # 4. Flat scanned PDF with 6 pages (> FLAT_PDF_PAGE_LIMIT=5) -> triggers L4 demotion & .l3.txt sidecar
        pdf_path = self.tmp_dir / "manual.pdf"
        pdf_Pages = b"%PDF-1.4\n" + (b"/Type /Page\n" * 6) + b"%%EOF\n"
        pdf_path.write_bytes(pdf_Pages)

        recs, _, _, _ = ts.scan_repository(self.tmp_dir, max_size_bytes=1024 * 1024, leaf_len=6, dry_run=False)
        rec_by_path = {r.rel_path: r for r in recs}

        self.assertNotIn("icon.png", rec_by_path)
        self.assertIn("schematic.png", rec_by_path)
        png_rec = rec_by_path["schematic.png"]
        self.assertIsNotNone(png_rec.opaque_info)
        self.assertEqual(png_rec.opaque_info.dimensions, "320x240px")
        self.assertIn("Board=RevC", png_rec.opaque_info.pre_scraped_meta)
        self.assertFalse(png_rec.opaque_info.is_l4_demoted)

        self.assertIn("topology.svg", rec_by_path)
        self.assertIn("Power Bus", rec_by_path["topology.svg"].opaque_info.pre_scraped_meta)

        self.assertIn("manual.pdf", rec_by_path)
        pdf_rec = rec_by_path["manual.pdf"]
        self.assertTrue(pdf_rec.opaque_info.is_l4_demoted)
        sidecar_file = self.tmp_dir / "manual.pdf.l3.txt"
        self.assertTrue(sidecar_file.is_file())
        sidecar_txt = sidecar_file.read_text(encoding="utf-8")
        # Verify ERR-02 fix: natural English placeholder strings
        self.assertIn("Map page ranges to section headers so L4 binary can be queried by page slice", sidecar_txt)
        self.assertIn("Critical extracted tables, pinouts, part numbers, or torque specs", sidecar_txt)

    # -------------------------------------------------------------------------
    # 5. ADR-007, ADR-008 & ADR-010 HC-03: ADR Discovery & Merkle STATE_ROOT
    # -------------------------------------------------------------------------

    def test_08_adr_discovery_primary_fallback_and_collision_gates(self) -> None:
        """Verifies docs/adr/ priority over docs/decisions/, YAML frontmatter status parsing, and ID collision rejection."""
        adr_dir = self.tmp_dir / "docs" / "adr"
        dec_dir = self.tmp_dir / "docs" / "decisions"
        adr_dir.mkdir(parents=True)
        dec_dir.mkdir(parents=True)

        # Put ADR-001 in docs/adr/ and a conflicting ADR-001 in docs/decisions/
        # Per ADR-010 HC-03, docs/adr/ is primary and docs/decisions/ is ignored when docs/adr/ exists
        (adr_dir / "ADR-001_2026-11-08_Context-Triad.md").write_text(
            "# ADR-001\n* **Status:** Implemented\n", encoding="utf-8"
        )
        (adr_dir / "ADR-012_2026-11-13_Hop-Distance.md").write_text(
            "---\nrecord_id: ADR-012\nstatus: Accepted (Amended by ADR-016)\n---\n# ADR-012\n",
            encoding="utf-8",
        )
        (dec_dir / "ADR-001_2026-11-08_Legacy-Copy.md").write_text(
            "# Legacy duplicate that must not be scanned when docs/adr/ exists\n", encoding="utf-8"
        )

        adrs = ts.discover_adr_records(self.tmp_dir, leaf_len=6)
        self.assertEqual(len(adrs), 2)
        self.assertEqual(adrs[0].record_id, "ADR-001")
        self.assertEqual(adrs[0].status, "Implemented")
        self.assertEqual(adrs[1].record_id, "ADR-012")
        self.assertEqual(adrs[1].status, "Accepted (Amended by ADR-016)")

        # Duplicate Record ID inside the same active directory MUST fail closed
        (adr_dir / "ADR-001_2026-11-09_Duplicate-ID.md").write_text("# Conflict\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            ts.discover_adr_records(self.tmp_dir, leaf_len=6)

    def test_09_merkle_state_root_crlf_invariance_and_agents_coupling(self) -> None:
        """Verifies ADR-008 CRLF/LF normalization and AGENTS.md coupling into STATE_ROOT."""
        agents_p = self.tmp_dir / "AGENTS.md"
        agents_p.write_bytes(b"# Governance\r\nRule 1\r\n")
        tokenme_lf = "# TOKENME_VERSION: 2.1\n# STATE_ROOT: PENDING\n# ADR_COUNT: 0\n\n# === [PURPOSE] ===\n"
        tokenme_crlf = tokenme_lf.replace("\n", "\r\n")

        stamped_lf, root_lf = ts.stamp_state_root_in_text(tokenme_lf, agents_p, root_len=8)
        stamped_crlf, root_crlf = ts.stamp_state_root_in_text(tokenme_crlf, agents_p, root_len=8)
        self.assertEqual(root_lf, root_crlf)
        self.assertIn(f"# STATE_ROOT: {root_lf}", stamped_lf)

        # Mutating AGENTS.md MUST change the computed Merkle STATE_ROOT
        agents_p.write_bytes(b"# Governance\nRule 1 modified\n")
        _, root_mutated = ts.stamp_state_root_in_text(tokenme_lf, agents_p, root_len=8)
        self.assertNotEqual(root_lf, root_mutated)

    # -------------------------------------------------------------------------
    # 6. ADR-011, ADR-014 & ADR-016: Bootstrap Lifecycle, [#sig] & AGENTS.md
    # -------------------------------------------------------------------------

    def test_10_cold_init_bootstrap_self_consumption_and_adr014_agents_isolation(self) -> None:
        """Tests cold --init, Profile A AGENTS.md creation, self-consuming prompts, [#sig] locking, and --check."""
        (self.tmp_dir / "app.py").write_text(
            "import argparse\ndef run_app(port: int) -> bool:\n    return True\n", encoding="utf-8"
        )

        # 1. Cold --init scaffolds TOKENME.txt and Profile A AGENTS.md
        rc, out, err = self._run_cli([str(self.tmp_dir), "--init"])
        self.assertEqual(rc, 0, msg=err)
        self.assertTrue((self.tmp_dir / "TOKENME.txt").is_file())
        self.assertTrue((self.tmp_dir / "AGENTS.md").is_file())

        # 2. Unhydrated state MUST fail --check with exit code 2
        rc_chk1, _, err_chk1 = self._run_cli([str(self.tmp_dir), "--check"])
        self.assertEqual(rc_chk1, 2)
        self.assertIn("BOOTSTRAP_REQUIRED", err_chk1)

        # 3. Hydrate shards and run --sync to self-consume prompts and stamp [#sig:xxxxxx]
        self._hydrate_all_shards(self.tmp_dir)
        rc_sync, _, err_sync = self._run_cli([str(self.tmp_dir), "--sync"])
        self.assertEqual(rc_sync, 0, msg=err_sync)

        tokenme_txt = (self.tmp_dir / "TOKENME.txt").read_text(encoding="utf-8")
        self.assertNotIn("[BOOTSTRAP_REQUIRED", tokenme_txt)
        self.assertRegex(tokenme_txt, r"RUNTIME:.*\[#sig:[0-9a-f]{6}\]")
        self.assertRegex(tokenme_txt, r"app\.py::\* -> TOKENME\.txt::\[FILES\].*\[#sig:[0-9a-f]{6}\]")

        # 4. --check MUST now pass with exit code 0
        rc_chk2, out_chk2, err_chk2 = self._run_cli([str(self.tmp_dir), "--check"])
        self.assertEqual(rc_chk2, 0, msg=err_chk2)
        self.assertIn("CLEAN", out_chk2)

        # 5. ADR-014 Single-State Isolation: injecting <!-- comment into AGENTS.md MUST fail --check
        agents_file = self.tmp_dir / "AGENTS.md"
        agents_file.write_text(agents_file.read_text(encoding="utf-8") + "\n<!-- Dormant Profile B -->\n", encoding="utf-8")
        rc_chk3, _, err_chk3 = self._run_cli([str(self.tmp_dir), "--check"])
        self.assertEqual(rc_chk3, 2)
        self.assertIn("ADR-014 Single-State Isolation violation", err_chk3)

    # -------------------------------------------------------------------------
    # 7. ADR-012 & ADR-013: Subdirectory Sharding, Hysteresis & --compact
    # -------------------------------------------------------------------------

    def test_11_subdir_sharding_hysteresis_retention_and_compact_coalescing(self) -> None:
        """Tests forward sharding on >75 symbols, hysteresis retention below 35%, and --compact coalescing with edge promotion."""
        (self.tmp_dir / "main.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
        sub_dir = self.tmp_dir / "engine"
        sub_dir.mkdir()

        # Create 2 files in engine/ with > 75 total symbols so Pass 1 sharding triggers
        funcs_a = "\n".join(f"def fn_a_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(45))
        funcs_b = "\n".join(f"def fn_b_{i}(y: int) -> int:\n    return y * {i}\n" for i in range(45))
        (sub_dir / "part_a.py").write_text(funcs_a, encoding="utf-8")
        (sub_dir / "part_b.py").write_text(funcs_b, encoding="utf-8")

        rc, _, _ = self._run_cli([str(self.tmp_dir), "--init"])
        self.assertEqual(rc, 0)
        child_shard = sub_dir / "TOKENME.engine.txt"
        self.assertTrue(child_shard.is_file(), "Expected engine/TOKENME.engine.txt to be spawned.")

        # Hydrate root and child shard, including an inter-module and intra-module topology edge in child
        self._hydrate_all_shards(self.tmp_dir)
        child_txt = child_shard.read_text(encoding="utf-8")
        child_txt = child_txt.replace(
            "engine/part_a.py::* -> TOKENME.txt::[FILES] : Synchronizes AST coordinates and dual hashes",
            "engine/part_a.py::fn_a_0 -> main.py::main : Cross-module dispatch\n"
            "engine/part_a.py::fn_a_0 -> engine/part_b.py::fn_b_0 : Intra-module pipeline",
        )
        child_shard.write_text(child_txt, encoding="utf-8")
        self._run_cli([str(self.tmp_dir), "--sync"])

        # Contract engine/ so it has only 2 tiny functions (well below the 35% merge floor of 787 tokens)
        (sub_dir / "part_a.py").write_text("def fn_a_0(x: int) -> int:\n    return x\n", encoding="utf-8")
        (sub_dir / "part_b.py").write_text("def fn_b_0(y: int) -> int:\n    return y\n", encoding="utf-8")

        # Standard --sync (without --compact) MUST preserve child shard on disk and emit [WARN: COMPACT_ELIGIBLE]
        rc_ret, _, err_ret = self._run_cli([str(self.tmp_dir), "--sync"])
        self.assertEqual(rc_ret, 0)
        self.assertTrue(child_shard.is_file(), "Hysteresis must retain child shard when --compact is not passed.")
        self.assertIn("[WARN: COMPACT_ELIGIBLE]", err_ret)

        # Running with --compact MUST coalesce child shard into root TOKENME.txt, delete child shard,
        # promote cross-module edge (engine/part_a.py -> main.py), and inline intra-module coupling note
        rc_cmp, _, err_cmp = self._run_cli([str(self.tmp_dir), "--sync", "--compact"])
        self.assertEqual(rc_cmp, 0, msg=err_cmp)
        self.assertFalse(child_shard.exists(), "Child shard should be deleted after --compact coalescing.")

        root_txt = (self.tmp_dir / "TOKENME.txt").read_text(encoding="utf-8")
        self.assertIn("engine/part_a.py::fn_a_0 -> main.py::main", root_txt)
        self.assertIn("[Coupling: -> engine/part_b.py::fn_b_0]", root_txt)

    def test_12_atomic_monolith_exemption_directive(self) -> None:
        """Verifies ADR-012 <!-- TOKENME:ATOMIC_MONOLITH=true --> prevents subdir sharding."""
        sub_dir = self.tmp_dir / "monolith_pkg"
        sub_dir.mkdir()
        funcs_a = "# <!-- TOKENME:ATOMIC_MONOLITH=true -->\n" + "\n".join(
            f"def mono_a_{i}() -> int:\n    return {i}\n" for i in range(50)
        )
        funcs_b = "\n".join(f"def mono_b_{i}() -> int:\n    return {i}\n" for i in range(50))
        (sub_dir / "a.py").write_text(funcs_a, encoding="utf-8")
        (sub_dir / "b.py").write_text(funcs_b, encoding="utf-8")

        self._run_cli([str(self.tmp_dir), "--init"])
        self.assertFalse(
            (sub_dir / "TOKENME.monolith-pkg.txt").exists(),
            "Subdirectory flagged with TOKENME:ATOMIC_MONOLITH=true must not be split into a child shard.",
        )

    # -------------------------------------------------------------------------
    # 8. ADR-015 & ADR-016: --triage Queue, Dual-Hash Auto-Ack & --ack
    # -------------------------------------------------------------------------

    def test_13_triage_lifecycle_dual_hash_auto_ack_and_atomic_ack(self) -> None:
        """Verifies --triage states, Dual-Hash Auto-Ack on comment edits, --strict-bytes, and --ack safety gates."""
        mod_path = self.tmp_dir / "service.py"
        mod_path.write_text(
            "def process_order(order_id: int, amount: float) -> bool:\n"
            "    return amount > 0.0\n",
            encoding="utf-8",
        )
        self._run_cli([str(self.tmp_dir), "--init"])

        # 1. --triage on unhydrated repo reports UNFILLED_BOOTSTRAP
        rc_t1, out_t1, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertEqual(rc_t1, 0)
        self.assertIn("STATE: DIRTY", out_t1)
        self.assertIn("UNFILLED_BOOTSTRAP", out_t1)

        # 2. Attempting --ack on an unfilled [BOOTSTRAP_REQUIRED] entry MUST fail with Exit 2
        rc_bad_ack, _, err_bad_ack = self._run_cli([str(self.tmp_dir), "--ack", "service.py"])
        self.assertEqual(rc_bad_ack, 2)
        self.assertIn("[ACK REJECTED]", err_bad_ack)

        # 3. Hydrate and sync -> --triage MUST report CLEAN (0 items)
        self._hydrate_all_shards(self.tmp_dir)
        self._run_cli([str(self.tmp_dir), "--sync"])
        rc_t2, out_t2, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertEqual(rc_t2, 0)
        self.assertIn("STATE: CLEAN | ITEMS: 0", out_t2)

        # 4. ADR-016 HC-02 Dual-Hash Auto-Ack: Edit only comments/literals -> content_hash changes, struct_sig matches
        mod_path.write_text(
            "# Added explanatory comment without changing AST structure or calls\n"
            "def process_order(order_id: int, amount: float) -> bool:\n"
            "    return amount > 0.01\n",
            encoding="utf-8",
        )
        _, out_t3, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("STATE: CLEAN | ITEMS: 0", out_t3, "Comment/literal-only edit must auto-ack when struct_sig matches.")

        # 5. Passing --strict-bytes MUST surface the comment-only byte change in --triage
        _, out_t4, _ = self._run_cli([str(self.tmp_dir), "--triage", "--strict-bytes"])
        self.assertIn("STALE_HASH", out_t4)

        # 6. Structural change (add outgoing call + new parameter) -> triggers STALE_HASH in default --triage
        mod_path.write_text(
            "def validate_id(oid: int) -> bool:\n"
            "    return oid > 0\n\n"
            "def process_order(order_id: int, amount: float, currency: str = 'USD') -> bool:\n"
            "    return validate_id(order_id) and amount > 0.0\n",
            encoding="utf-8",
        )
        _, out_t5, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("STALE_HASH", out_t5)
        self.assertIn("service.py", out_t5)

        # 7. Run --ack service.py -> updates hash & cascades STATE_ROOT without rewriting prose
        rc_ack, out_ack, err_ack = self._run_cli([str(self.tmp_dir), "--ack", "service.py"])
        self.assertEqual(rc_ack, 0, msg=err_ack)
        self.assertIn("Acknowledged 1 file(s)", out_ack)

        _, out_t6, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("STATE: CLEAN | ITEMS: 0", out_t6)

        # 8. Add untracked file and delete tracked file -> verify UNTRACKED_ARTIFACT (with DISK_HASH) & ORPHANED_ENTRY
        (self.tmp_dir / "new_helper.py").write_text("def help_me() -> int:\n    return 42\n", encoding="utf-8")
        mod_path.unlink()
        _, out_t7, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("UNTRACKED_ARTIFACT", out_t7)
        self.assertIn("DISK_HASH:", out_t7)
        self.assertIn("ORPHANED_ENTRY", out_t7)

    def test_14_git_diff_minor_vs_major_delta_routing(self) -> None:
        """Verifies ADR-015 git diff efficiency gate (rho_diff <= 0.60 -> MINOR_DELTA vs > 0.60 -> MAJOR_DELTA)."""
        if shutil.which("git") is None:
            self.skipTest("git executable not available in environment.")

        subprocess.run(["git", "init"], cwd=str(self.tmp_dir), capture_output=True, check=False)
        subprocess.run(["git", "config", "user.email", "test@tokenme.local"], cwd=str(self.tmp_dir), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tokenme Test"], cwd=str(self.tmp_dir), capture_output=True)

        lines_20 = [f"def fn_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(10)]
        target_py = self.tmp_dir / "math_ops.py"
        target_py.write_text("".join(lines_20), encoding="utf-8")

        self._run_cli([str(self.tmp_dir), "--init"])
        self._hydrate_all_shards(self.tmp_dir)
        self._run_cli([str(self.tmp_dir), "--sync"])

        subprocess.run(["git", "add", "."], cwd=str(self.tmp_dir), capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=str(self.tmp_dir), capture_output=True)

        # Mutate 1 function signature out of 10 (2 lines changed out of 20 -> ratio ~ 0.10 <= 0.60 -> MINOR_DELTA)
        lines_minor = list(lines_20)
        lines_minor[0] = "def fn_0(x: int, y: int) -> int:\n    return abs(x + y)\n"
        target_py.write_text("".join(lines_minor), encoding="utf-8")

        _, out_minor, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("STALE_HASH (MINOR_DELTA)", out_minor)
        self.assertIn("GIT_DIFF_CMD:       git diff HEAD -- math_ops.py", out_minor)

        # Mutate all 10 functions (> 60% lines changed -> MAJOR_DELTA)
        lines_major = [f"def fn_new_{i}(a: int, b: int) -> int:\n    return max(a, b) * {i}\n" for i in range(10)]
        target_py.write_text("".join(lines_major), encoding="utf-8")

        _, out_major, _ = self._run_cli([str(self.tmp_dir), "--triage"])
        self.assertIn("STALE_HASH (MAJOR_DELTA)", out_major)
        self.assertIn("READ_FILE_DIRECTLY", out_major)

    def test_15_topology_stale_edge_blocks_atomic_ack(self) -> None:
        """Verifies ADR-011 & ADR-015: deleting a symbol referenced in [TOPOLOGY] flags [STALE_EDGE] and blocks --ack."""
        mod = self.tmp_dir / "api.py"
        mod.write_text("def start_server() -> None:\n    pass\n\ndef stop_server() -> None:\n    pass\n", encoding="utf-8")
        self._run_cli([str(self.tmp_dir), "--init"])
        self._hydrate_all_shards(self.tmp_dir)

        # Point [TOPOLOGY] edge specifically at api.py::start_server
        t_path = self.tmp_dir / "TOKENME.txt"
        txt = t_path.read_text(encoding="utf-8").replace(
            "api.py::* -> TOKENME.txt::[FILES]",
            "api.py::start_server -> api.py::stop_server",
        )
        t_path.write_text(txt, encoding="utf-8")
        self._run_cli([str(self.tmp_dir), "--sync"])
        self.assertEqual(self._run_cli([str(self.tmp_dir), "--check"])[0], 0)

        # Rename start_server -> launch_server so api.py::start_server no longer exists
        mod.write_text("def launch_server() -> None:\n    pass\n\ndef stop_server() -> None:\n    pass\n", encoding="utf-8")

        # --ack api.py MUST reject with Exit 2 because api.py::start_server is now a broken [STALE_EDGE]
        rc_ack, _, err_ack = self._run_cli([str(self.tmp_dir), "--ack", "api.py"])
        self.assertEqual(rc_ack, 2)
        self.assertIn("[STALE_EDGE]", err_ack)


if __name__ == "__main__":
    unittest.main(verbosity=2)