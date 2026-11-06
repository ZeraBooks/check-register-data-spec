import contextlib
import csv
import glob
import io
import json
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import check_register as cr  # noqa: E402
from amount_words import WordsError, amount_to_words, words_to_amount  # noqa: E402


class Words(unittest.TestCase):
    def test_common_styles(self):
        cases = {
            "One thousand two hundred fifty and 00/100": "1250.00",
            "**Forty-five & 07/100**": "45.07",
            "Three hundred twelve dollars and 50 cents": "312.50",
            "Two thousand and xx/100": "2000.00",
            "Fifteen and no/100 dollars": "15.00",
            "Eighty dollars only": "80.00",
            "Nine hundred ninety-nine thousand nine hundred ninety-nine and 99/100": "999999.99",
            "One million and 00/100": "1000000.00",
        }
        for text, want in cases.items():
            self.assertEqual(words_to_amount(text), Decimal(want), text)

    def test_round_trip(self):
        for cents in list(range(0, 2000, 7)) + [100000, 4800000, 99999999]:
            amt = Decimal(cents) / 100
            self.assertEqual(words_to_amount(amount_to_words(amt)), amt)

    def test_bad_words_raise(self):
        with self.assertRaises(WordsError):
            words_to_amount("Two hundred fiftey and 00/100")


class Routing(unittest.TestCase):
    def test_checksum(self):
        self.assertTrue(cr.aba_ok("011000015"))   # published Federal Reserve Bank of Boston example
        self.assertFalse(cr.aba_ok("011000016"))
        self.assertFalse(cr.aba_ok("12345"))


class Samples(unittest.TestCase):
    def test_registers_have_no_errors_and_tie_to_every_statement(self):
        stmts = sorted(glob.glob(os.path.join(ROOT, "samples", "statements", "*.json")))
        self.assertEqual(len(stmts), 36)
        for s in stmts:
            st = json.load(open(s, encoding="utf-8"))
            issues, summary = cr.check(os.path.join(ROOT, st["register_file"]), st)
            self.assertEqual([i for i in issues if i.severity == "error"], [], s)
            self.assertEqual(summary["cleared_total"], st["checks_paid_total"])

    def test_json_matches_csv(self):
        for f in glob.glob(os.path.join(ROOT, "samples", "registers", "*.csv")):
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
            j = json.load(open(f.replace("registers", "json").replace(".csv", ".json"), encoding="utf-8"))
            self.assertEqual(rows, j["checks"])

    def test_invalid_samples_fail_their_rule(self):
        cases = json.load(open(os.path.join(ROOT, "samples", "invalid", "expected.json"), encoding="utf-8"))
        self.assertEqual(len(cases), 15)
        for c in cases:
            st = json.load(open(os.path.join(ROOT, c["statement"]), encoding="utf-8")) if c["statement"] else None
            issues, _ = cr.check(os.path.join(ROOT, c["file"]), st)
            self.assertIn(c["must_fail"], {i.rule for i in issues}, c["file"])

    def test_rules_file_covers_validator(self):
        ids = {r["rule_id"] for r in csv.DictReader(open(os.path.join(ROOT, "rules", "check-rules.csv"), encoding="utf-8"))}
        src = open(os.path.join(ROOT, "cli", "check_register.py"), encoding="utf-8").read()
        used = {f"CHK-{n:03d}" for n in range(1, 40) if f'"CHK-{n:03d}"' in src}
        self.assertEqual(used - ids, set())

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cr.main([os.path.join(ROOT, "samples", "registers", "vega-cpa-2026-q3.csv")]), 0)
            self.assertEqual(cr.main([os.path.join(ROOT, "samples", "invalid", "figures-and-words-disagree.csv")]), 1)


if __name__ == "__main__":
    unittest.main()
