#!/usr/bin/env python3
"""
Unit Tests for ApexEngine STE Precision Engine (scripts/ste_engine.py)
Verifies 80% Simplified Technical English (ASD-STE100) validation,
AI slop/conversational padding elimination, and technical vocabulary preservation.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.ste_engine import lint_ste, format_ste_step, STEViolation


class TestSTEEngine(unittest.TestCase):
    def test_detects_ai_conversational_slop(self):
        slop_text = "Certainly! I would be very happy to assist you in designing this database connection pool."
        violations = lint_ste(slop_text)
        self.assertTrue(any("SLOP" in v.rule_code for v in violations), f"Expected SLOP violation in {violations}")

    def test_detects_passive_voice_constructs(self):
        passive_text = "The authentication token should be verified by the middleware handler before processing."
        violations = lint_ste(passive_text)
        self.assertTrue(any("PASSIVE" in v.rule_code for v in violations), f"Expected PASSIVE violation in {violations}")

    def test_detects_excessive_sentence_length(self):
        long_sentence = (
            "When the user attempts to initiate a new concurrent payment transaction across the distributed network "
            "while the primary replica database is undergoing an automatic failover sequence, the system must immediately "
            "queue the inbound payload into a persistent buffer and notify the monitoring telemetry channel."
        )
        violations = lint_ste(long_sentence)
        self.assertTrue(any("LENGTH" in v.rule_code for v in violations), f"Expected LENGTH violation in {violations}")

    def test_preserves_deep_technical_vocabulary(self):
        # Must NOT choke on technical programming terms
        technical_clean_text = (
            "Initialize the transactional mutex.\n"
            "Verify the idempotency token.\n"
            "Handle polymorphic deserialization errors."
        )
        violations = lint_ste(technical_clean_text)
        self.assertEqual(len(violations), 0, f"Expected clean technical text to pass without violations, got {violations}")

    def test_formats_atomic_imperative_step(self):
        messy_step = "You need to make sure that the port is set to 8000."
        formatted = format_ste_step(messy_step)
        self.assertTrue(formatted.startswith("Set port to 8000") or "8000" in formatted)
        self.assertFalse("You need to make sure" in formatted)


if __name__ == "__main__":
    unittest.main()
