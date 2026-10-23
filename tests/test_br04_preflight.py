"""Exercise the workflow's actual inline identity gate without running the builder."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'fa3ac869c21bb9e71ff1fe22aa9b5aa060f11849dabe241fdadbc84cfdb53ec3'
WORKFLOW = (ROOT / '.github/workflows/build-br04-s1.yml').read_text()
START = "          python -I -S - <<'PY_PREFLIGHT'\n"
END = '          PY_PREFLIGHT\n'
CODE = textwrap.dedent(WORKFLOW.split(START, 1)[1].split(END, 1)[0])
FIXTURE = b'from pathlib import Path\nPath("BUILDER_EXECUTED").touch()\n'

class BR04PreflightTests(unittest.TestCase):
    def run_gate(self, payload=None, kind='file', fixture_pin=False, optimized=False):
        code = CODE
        if fixture_pin:
            # Test the success branch with inert bytes; production pin stays unchanged.
            code = code.replace(EXPECTED, hashlib.sha256(FIXTURE).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            builder = root / 'src/build_br04_candidate.py'
            if kind == 'directory':
                builder.mkdir()
            elif kind == 'symlink':
                (root / 'fixture.py').write_bytes(FIXTURE)
                builder.symlink_to(root / 'fixture.py')
            elif payload is not None:
                builder.write_bytes(payload)
            result = subprocess.run([sys.executable, '-I', '-S'] + (['-O'] if optimized else []) + ['-'], input=code, text=True, cwd=root, capture_output=True, timeout=10)
            self.assertFalse((root / 'BUILDER_EXECUTED').exists(), 'identity check executed builder')
            return result

    def test_production_pin(self):
        self.assertEqual(CODE.count(EXPECTED), 1)

    def test_success_without_execution(self):
        self.assertEqual(self.run_gate(FIXTURE, fixture_pin=True).returncode, 0)

    def test_success_with_optimized_python(self):
        self.assertEqual(self.run_gate(FIXTURE, fixture_pin=True, optimized=True).returncode, 0)

    def test_changed_bytes_rejected(self):
        self.assertNotEqual(self.run_gate(FIXTURE + b'\n', fixture_pin=True).returncode, 0)

    def test_wrong_identity_rejected(self):
        self.assertNotEqual(self.run_gate(FIXTURE).returncode, 0)

    def test_wrong_identity_optimized_rejected(self):
        self.assertNotEqual(self.run_gate(FIXTURE, optimized=True).returncode, 0)

    def test_missing_rejected(self):
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_directory_rejected(self):
        self.assertNotEqual(self.run_gate(kind='directory').returncode, 0)

    def test_symlink_rejected_even_if_target_matches(self):
        self.assertNotEqual(self.run_gate(kind='symlink', fixture_pin=True).returncode, 0)

    def test_guard_runs_before_dependencies_and_builder(self):
        index = WORKFLOW.index('- name: Verify accepted BR-04 builder identity')
        self.assertLess(index, WORKFLOW.index('- name: Install dependencies'))
        self.assertLess(index, WORKFLOW.index('- name: Build BR-04 S1 candidate'))
        block = WORKFLOW[index:WORKFLOW.index('- name: Install dependencies')]
        self.assertNotIn('continue-on-error:', block)
        self.assertNotIn('        if:', block)

if __name__ == '__main__':
    unittest.main()
