#!/usr/bin/env python3
"""
Unit Tests for ApexEngine Benchmark Suite.
Verifies calculations, JSON export schemas, and execution boundaries.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.benchmark_memory import simulate_standard_conversation
from benchmarks.benchmark_head_to_head import simulate_head_to_head


class TestBenchmarks(unittest.TestCase):
    def test_simulate_standard_conversation(self):
        # 10 turns with 1000 bytes per turn: sum(1..10) * 1000 = 55,000 bytes = 13,750 tokens
        tokens = simulate_standard_conversation(10, avg_turn_bytes=1000)
        self.assertEqual(tokens, 13750)

    def test_head_to_head_simulation_schema(self):
        # Run a quick 3-turn simulation
        report = simulate_head_to_head(total_turns=3)

        self.assertIn("total_turns", report)
        self.assertEqual(report["total_turns"], 3)
        self.assertIn("naive_tokens", report)
        self.assertIn("apex_tokens", report)
        self.assertIn("token_savings_percent", report)
        self.assertIn("cost_comparison", report)
        self.assertIn("code_quality", report)

        # Savings should be strictly positive
        self.assertGreater(report["token_savings_percent"], 50.0)

        # Placeholders in ApexEngine should be 0
        self.assertEqual(report["code_quality"]["placeholders_allowed"]["apex_engine"], 0)


if __name__ == "__main__":
    unittest.main()
