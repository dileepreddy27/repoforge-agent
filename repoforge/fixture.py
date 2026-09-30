from pathlib import Path

from git import Repo

SOURCE = '''def mean(values):
    if not values:
        return 0
    return sum(values) // len(values)
'''
TESTS = '''import unittest
from stats import mean

class MeanTests(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(mean([1, 2]), 1.5)
    def test_negative(self):
        self.assertEqual(mean([-1, -2]), -1.5)
    def test_empty(self):
        with self.assertRaises(ValueError):
            mean([])
    def test_integer(self):
        self.assertEqual(mean([2, 4]), 3)
'''
ISSUE = "Fix mean: preserve fractional results, support negatives, and raise ValueError for empty samples."


def create_fixture(root: Path):
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/stats.py").write_text(SOURCE, encoding="utf-8")
    (root / "tests/test_stats.py").write_text(TESTS, encoding="utf-8")
    repo = Repo.init(root)
    repo.index.add(["src/stats.py", "tests/test_stats.py"])
    with repo.config_writer() as config:
        config.set_value("user", "name", "RepoForge Demo")
        config.set_value("user", "email", "demo@example.invalid")
    repo.index.commit("Add synthetic failing statistics fixture")
