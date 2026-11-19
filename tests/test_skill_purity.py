"""Automated Skill Quality and Purity Auditing Test Suite.

Verifies SKILL.md for:
1. File existence and UTF-8 readability.
2. YAML frontmatter extraction, schema, length bounds (<1024 chars), "Use when..." grammar, and CSO leak-free description.
3. Core Architectural Section presence (4 gates, Virtual 2M Memory Engine + condense.py commands,
   Rationalization Defense Matrix >= 10 rows, Red Flags & Circuit Breakers, Adaptive Swarm Protocol,
   and Walkthrough Example with executable code).
4. Tool purity (no non-standard or hallucinated tools; strictly standard tools).
"""

import ast
import os
import re
import textwrap
import unittest

try:
    import yaml
except ImportError:
    yaml = None


class TestSkillPurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tests_dir = os.path.dirname(os.path.abspath(__file__))
        cls.skill_dir = os.path.dirname(cls.tests_dir)
        cls.skill_path = os.path.join(cls.skill_dir, "SKILL.md")

        if os.path.exists(cls.skill_path):
            with open(cls.skill_path, "r", encoding="utf-8") as f:
                cls.content = f.read()
        else:
            cls.content = ""

    def test_skill_file_exists_and_utf8_readable(self):
        """Requirement 1: SKILL.md must exist and be readable as valid UTF-8."""
        self.assertTrue(
            os.path.exists(self.skill_path),
            f"SKILL.md must exist at {self.skill_path}"
        )
        self.assertTrue(os.path.isfile(self.skill_path))

        # Test UTF-8 decoding explicitly
        with open(self.skill_path, "rb") as f:
            raw_bytes = f.read()

        try:
            decoded = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            self.fail(f"SKILL.md failed UTF-8 decoding: {e}")

        self.assertGreater(len(decoded), 1000, "SKILL.md content is unexpectedly small")

    def _extract_frontmatter(self):
        """Helper to extract raw frontmatter string and parsed dict."""
        self.assertTrue(
            self.content.startswith("---"),
            "SKILL.md must begin with frontmatter delimiter '---'"
        )
        parts = self.content.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, "Frontmatter must be enclosed in '---'")
        raw_fm = parts[1]

        data = {}
        if yaml is not None:
            data = yaml.safe_load(raw_fm) or {}
        else:
            # Fallback parser for standard simple YAML frontmatter
            for line in raw_fm.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    data[key.strip()] = val.strip()

        return raw_fm, data

    def test_yaml_frontmatter_presence_and_length(self):
        """Requirement 2a: Frontmatter exists and length is strictly under 1024 characters."""
        raw_fm, data = self._extract_frontmatter()
        fm_with_delimiters = f"---{raw_fm}---"
        self.assertLess(
            len(fm_with_delimiters),
            1024,
            f"Frontmatter length ({len(fm_with_delimiters)}) exceeds 1024 characters"
        )
        self.assertLess(
            len(raw_fm),
            1024,
            f"Raw frontmatter body length ({len(raw_fm)}) exceeds 1024 characters"
        )

    def test_yaml_frontmatter_required_fields(self):
        """Requirement 2b: Frontmatter contains required name and description fields."""
        _, data = self._extract_frontmatter()
        self.assertIn("name", data, "Frontmatter must contain 'name'")
        self.assertEqual(data["name"], "apex-engine", "Skill name must be 'apex-engine'")

        self.assertIn("description", data, "Frontmatter must contain 'description'")
        desc = data["description"]
        self.assertIsInstance(desc, str, "Description must be a string")
        self.assertTrue(len(desc.strip()) > 0, "Description must not be empty")

    def test_frontmatter_description_grammar_and_voice(self):
        """Requirement 2c: Description starts with 'Use when...' and is in third-person voice."""
        _, data = self._extract_frontmatter()
        desc = data.get("description", "").strip()

        self.assertTrue(
            desc.startswith("Use when"),
            f"Description must start with 'Use when...', got: '{desc[:30]}'"
        )

        # Third-person check: should not start with first-person or second-person pronouns
        first_person_starts = ["i ", "we ", "you ", "my ", "our "]
        lower_desc = desc.lower()
        for prefix in first_person_starts:
            self.assertFalse(
                lower_desc.startswith(prefix),
                f"Description should be in third-person voice; starts with '{prefix}'"
            )

    def test_frontmatter_cso_no_workflow_leaks(self):
        """Requirement 2d: CSO check - Description contains NO internal workflow leaks."""
        _, data = self._extract_frontmatter()
        desc = data.get("description", "").lower()

        leak_indicators = [
            "4 gates",
            "4-gate",
            "gate 1",
            "gate 2",
            "gate 3",
            "gate 4",
            "condense.py",
            "step 1",
            "step 2",
            "step 3",
            "step 4",
            "circuit breaker",
            "red flags",
            "active_state.md",
            "history.log"
        ]

        for leak in leak_indicators:
            self.assertNotIn(
                leak,
                desc,
                f"Description contains internal workflow leak '{leak}' which violates CSO principles"
            )

    def test_core_architectural_four_gates(self):
        """Requirement 3a: Contains all 4 gates with iron rules and mandatory actions."""
        expected_gates = [
            "Gate 1: Context Invariant Lock",
            "Gate 2: Contract-First TDD",
            "Gate 3: Defensive Production Rigor",
            "Gate 4: Empirical Terminal Verification"
        ]

        for gate in expected_gates:
            self.assertIn(
                gate,
                self.content,
                f"SKILL.md is missing required gate: '{gate}'"
            )

        # Verify key gate invariants
        self.assertIn("Iron Rule", self.content, "Gates must define Iron Rules")
        self.assertIn("Inspect Before Edit", self.content, "Gate 1 must mandate inspect before edit")
        self.assertIn("Red Before Green", self.content, "Gate 2 must mandate red before green")
        self.assertIn("Defensive Implementation", self.content, "Gate 3 must mandate defensive implementation")
        self.assertIn("Evidence Before Assertion", self.content, "Gate 4 must mandate evidence before assertion")

    def test_virtual_2m_memory_engine_and_condense_specs(self):
        """Requirement 3b: Contains Virtual 2M Memory Engine and condense.py specifications."""
        self.assertIn(
            "Virtual 2M Infinite Context Memory Engine",
            self.content,
            "SKILL.md must contain Virtual 2M Infinite Context Memory Engine section"
        )
        self.assertIn("active_state.md", self.content)
        self.assertIn("history.log", self.content)

        # condense.py command specifications
        expected_commands = [
            ("init", "condense.py init"),
            ("update", "condense.py update"),
            ("checkpoint", "condense.py checkpoint"),
            ("status", "condense.py status")
        ]

        for cmd_name, cmd_syntax in expected_commands:
            self.assertTrue(
                cmd_syntax in self.content or f"`{cmd_name}`" in self.content,
                f"SKILL.md missing specification for condense.py command '{cmd_name}'"
            )

    def test_rationalization_defense_matrix(self):
        """Requirement 3c: Contains Rationalization Defense Matrix with at least 10 rows."""
        self.assertIn(
            "Rationalization Defense Matrix",
            self.content,
            "SKILL.md must contain Rationalization Defense Matrix section"
        )

        # Locate table rows in section 4
        # Rows format: | 1 | ... | ... |
        matrix_rows = re.findall(r'\|\s*(\d+)\s*\|([^|]+)\|([^|]+)\|', self.content)
        self.assertGreaterEqual(
            len(matrix_rows),
            10,
            f"Rationalization Defense Matrix must contain at least 10 rows, found {len(matrix_rows)}"
        )

        # Validate that row numbers are sequential from 1 up to count
        row_numbers = [int(r[0]) for r in matrix_rows]
        self.assertEqual(row_numbers[0], 1, "Matrix must start at row 1")
        for i in range(len(row_numbers) - 1):
            self.assertEqual(
                row_numbers[i + 1],
                row_numbers[i] + 1,
                "Matrix rows must be strictly sequential"
            )

    def test_red_flags_and_circuit_breakers(self):
        """Requirement 3d: Contains Red Flags & Circuit Breakers with triggers and procedure."""
        self.assertIn(
            "Red Flags & Circuit Breakers",
            self.content,
            "SKILL.md must contain Red Flags & Circuit Breakers section"
        )
        self.assertIn("Red Flag Triggers", self.content)
        self.assertIn("Circuit Breaker Procedure", self.content)

        # Check critical triggers
        self.assertIn("Unread File Mutation", self.content)
        self.assertIn("Blind Implementation", self.content)
        self.assertIn("Placeholder Generation", self.content)
        self.assertIn("Unsubstantiated Completion", self.content)
        self.assertIn("Command Thrashing", self.content)

    def test_adaptive_swarm_protocol(self):
        """Requirement 3e: Contains Adaptive Swarm Protocol for Antigravity and single-agent fallback."""
        self.assertIn(
            "Adaptive Teamwork & Subagent Swarm Protocol",
            self.content,
            "SKILL.md must contain Adaptive Teamwork & Subagent Swarm Protocol section"
        )
        # Antigravity Swarm Mode
        self.assertIn("Antigravity Orchestration", self.content)
        self.assertIn("ARCHITECT", self.content)
        self.assertIn("TEST-WRITER", self.content)
        self.assertIn("IMPLEMENTER", self.content)
        self.assertIn("VERIFIER", self.content)
        self.assertIn("Handoff Envelope Standard", self.content)

        # Single-Agent Fallback
        self.assertIn("Single-Agent Fallback", self.content)
        self.assertIn("[GATE 1: LOCK CONTEXT]", self.content)
        self.assertIn("[GATE 4: EMPIRICAL VERIFICATION]", self.content)

    def test_walkthrough_example_executable(self):
        """Requirement 3f: Contains Walkthrough Example with syntactically valid and executable code."""
        self.assertIn(
            "Concrete End-to-End Walkthrough Example",
            self.content,
            "SKILL.md must contain Walkthrough Example section"
        )

        walkthrough_pos = self.content.find("Concrete End-to-End Walkthrough Example")
        self.assertNotEqual(walkthrough_pos, -1)
        walkthrough_text = self.content[walkthrough_pos:]

        # Extract python code blocks from the walkthrough section
        # Using a regex that handles indentation and multiline code fences
        code_blocks = re.findall(
            r'^[ \t]*```python[ \t]*\r?\n(.*?)\r?\n[ \t]*```',
            walkthrough_text,
            re.MULTILINE | re.DOTALL
        )

        self.assertGreaterEqual(
            len(code_blocks),
            2,
            f"Walkthrough must contain at least 2 python code blocks (test and implementation), found {len(code_blocks)}"
        )

        # Check AST syntax validity for all extracted code blocks
        parsed_ast = []
        for i, code in enumerate(code_blocks):
            dedented_code = textwrap.dedent(code).strip()
            try:
                tree = ast.parse(dedented_code)
                parsed_ast.append((dedented_code, tree))
            except SyntaxError as e:
                self.fail(f"Walkthrough python code block #{i+1} has syntax error: {e}")

        # The walkthrough contains:
        # Block 0: test_limiter.py (tests for SlidingWindowRateLimiter)
        # Block 1: limiter.py (implementation of SlidingWindowRateLimiter)
        # Let's verify that the implementation defines SlidingWindowRateLimiter
        # and when executed with the test logic, all tests pass!
        impl_code = None
        for code, _ in parsed_ast:
            if "class SlidingWindowRateLimiter" in code:
                impl_code = code
                break

        self.assertIsNotNone(
            impl_code,
            "Walkthrough must contain the SlidingWindowRateLimiter implementation class"
        )

        # Execute implementation in an isolated scope
        exec_scope = {}
        try:
            exec(impl_code, exec_scope)
        except Exception as e:
            self.fail(f"Failed to execute SlidingWindowRateLimiter implementation: {e}")

        RateLimiterClass = exec_scope.get("SlidingWindowRateLimiter")
        self.assertIsNotNone(RateLimiterClass)

        # Execute the behavioral assertions described in the test block
        # 1. Under limit allowed
        limiter = RateLimiterClass(limit=2, window_seconds=10.0)
        self.assertTrue(limiter.is_allowed("user-1"))
        self.assertTrue(limiter.is_allowed("user-1"))

        # 2. Over limit blocked
        limiter2 = RateLimiterClass(limit=2, window_seconds=10.0)
        self.assertTrue(limiter2.is_allowed("user-2"))
        self.assertTrue(limiter2.is_allowed("user-2"))
        self.assertFalse(limiter2.is_allowed("user-2"))

        # 3. Window expiry allows new requests
        curr_time = 1000.0
        limiter3 = RateLimiterClass(
            limit=1,
            window_seconds=5.0,
            time_func=lambda: curr_time
        )
        self.assertTrue(limiter3.is_allowed("user-3"))
        self.assertFalse(limiter3.is_allowed("user-3"))
        curr_time += 6.0
        self.assertTrue(limiter3.is_allowed("user-3"))

    def test_tool_purity(self):
        """Requirement 4: Tool purity check - strictly standard tools, no hallucinated tools."""
        allowed_standard_tools = {
            "read_file",
            "write_file",
            "edit_file",
            "run_command",
            "invoke_subagent",
            "send_message"
        }

        # List of known hallucinated or non-standard tools across various harnesses
        hallucinated_tools = [
            "execute_bash",
            "str_replace_editor",
            "view_file",
            "modify_file",
            "create_file",
            "replace_file_content",
            "modify_file_exact",
            "terminal_cmd",
            "bash_command",
            "view_code_item",
            "execute_command",
            "file_editor",
            "str_replace",
            "write_to_file",
            "read_from_file"
        ]

        # Ensure no hallucinated tool names appear in the document as tool mentions
        for tool in hallucinated_tools:
            self.assertNotIn(
                f"`{tool}`",
                self.content,
                f"SKILL.md references non-standard/hallucinated tool `{tool}`"
            )
            self.assertNotIn(
                f"tool `{tool}`",
                self.content.lower(),
                f"SKILL.md references non-standard/hallucinated tool `{tool}`"
            )

        # Inspect any tool invocations mentioned with backticks like `tool_name`
        # and verify they don't purport to be tools outside the standard whitelist
        tool_call_patterns = re.findall(
            r'(?:using|call|invoke|execute)\s+`([a-z_]+)`',
            self.content,
            re.IGNORECASE
        )

        for invoked in tool_call_patterns:
            # If it's a tool-like snake_case name (contains underscore), verify it's standard
            if "_" in invoked:
                self.assertIn(
                    invoked,
                    allowed_standard_tools,
                    f"Referenced tool `{invoked}` is not in standard tools whitelist {allowed_standard_tools}"
                )


if __name__ == "__main__":
    unittest.main()
