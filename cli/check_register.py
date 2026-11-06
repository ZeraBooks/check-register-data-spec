#!/usr/bin/env python3
"""Validate a check register CSV.

    python3 cli/check_register.py register.csv
    python3 cli/check_register.py register.csv --statement statement.json
    python3 cli/check_register.py register.csv --json

Checks every row against rules/check-rules.csv: the written amount against
the figures, the MICR line against the printed fields, the routing checksum,
duplicates and gaps in the check sequence, and (with --statement) that the
cleared checks add up to the checks-paid total on the bank statement.
Exit code 0 = no errors, 1 = errors, 2 = file could not be read.

Part of https://github.com/ZeraBooks/check-register-data-spec
(ZeraBooks, https://www.zerabooks.com/check-converter).
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amount_words import WordsError, words_to_amount  # noqa: E402

REQUIRED = ["check_number", "date", "payee", "amount", "amount_written", "routing_number", "account_last4", "micr_line", "status"]
MUST_FILL = ["check_number", "date", "routing_number", "account_last4", "micr_line", "status"]
AMOUNT_RE = re.compile(r"^[0-9]+\.[0-9]{2}$")
MICR_RE = re.compile(r"⑈\s*0*(?P<serial>\d+)\s*⑈\s*⑆\s*(?P<routing>\d{9})\s*⑆\s*(?P<account>[\d\s-]+?)\s*⑈")
ASSIGNED = set(range(0, 13)) | set(range(21, 33)) | set(range(61, 73)) | {80}


class Issue:
    def __init__(self, rule, severity, line, message):
        self.rule, self.severity, self.line, self.message = rule, severity, line, message

    def __repr__(self):
        where = f"line {self.line}" if self.line else "file"
        return f"{self.severity.upper():7} {self.rule} {where}: {self.message}"


def aba_ok(r):
    if not re.fullmatch(r"\d{9}", r):
        return False
    d = [int(c) for c in r]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])) % 10 == 0


def parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def check(path, statement=None):
    issues = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            return [Issue("CHK-001", "error", 1, f"missing columns: {', '.join(missing)}")], {}
        rows = list(reader)

    seen = {}
    numbers = {}
    cleared_total, cleared_count = Decimal("0"), 0
    written_total = Decimal("0")
    for n, r in enumerate(rows, start=2):
        r = {k: (v or "").strip() for k, v in r.items()}
        empty = [c for c in MUST_FILL if not r.get(c)]
        if empty:
            issues.append(Issue("CHK-001", "error", n, f"blank: {', '.join(empty)}"))
            continue
        num, status = r["check_number"], r["status"]
        void = status == "void"

        if void:
            if r["amount"] or r["amount_written"].upper() != "VOID":
                issues.append(Issue("CHK-013", "error", n, "a void check has no amount and VOID as the written amount"))
        else:
            if not AMOUNT_RE.match(r["amount"]) or Decimal(r["amount"]) <= 0:
                issues.append(Issue("CHK-002", "error", n, f"amount '{r['amount']}' must be positive, digits, two decimals"))
            else:
                try:
                    words = words_to_amount(r["amount_written"])
                except WordsError as exc:
                    issues.append(Issue("CHK-003", "error", n, f"can't read '{r['amount_written']}': {exc}"))
                else:
                    if words != Decimal(r["amount"]):
                        issues.append(Issue("CHK-004", "error", n, f"check {num}: figures say {r['amount']}, words say {words:.2f} ('{r['amount_written']}')"))
                    written_total += Decimal(r["amount"])
            if not r["payee"]:
                issues.append(Issue("CHK-015", "warning", n, f"check {num} has no payee"))

        if not aba_ok(r["routing_number"]):
            issues.append(Issue("CHK-005", "error", n, f"routing {r['routing_number']} fails the ABA checksum"))
        elif int(r["routing_number"][:2]) not in ASSIGNED:
            issues.append(Issue("CHK-006", "warning", n, f"routing prefix {r['routing_number'][:2]} is not an assigned Federal Reserve range"))

        m = MICR_RE.search(r["micr_line"])
        if not m:
            issues.append(Issue("CHK-007", "error", n, f"can't read MICR line '{r['micr_line']}'"))
        else:
            if int(m.group("serial")) != int(num):
                issues.append(Issue("CHK-007", "error", n, f"MICR check number {int(m.group('serial'))} vs printed {num}"))
            if m.group("routing") != r["routing_number"]:
                issues.append(Issue("CHK-008", "error", n, f"MICR routing {m.group('routing')} vs field {r['routing_number']}"))
            acct = re.sub(r"\D", "", m.group("account"))
            if not acct.endswith(r["account_last4"]):
                issues.append(Issue("CHK-009", "error", n, f"MICR account ends {acct[-4:]}, register says {r['account_last4']}"))

        key = (r["account_last4"], int(num))
        if key in seen:
            issues.append(Issue("CHK-010", "error", n, f"check {num} already on line {seen[key]}"))
        else:
            seen[key] = n
            numbers.setdefault(r["account_last4"], []).append(int(num))

        d = parse_date(r["date"])
        if d is None:
            issues.append(Issue("CHK-012", "error", n, f"date '{r['date']}' is not a real YYYY-MM-DD date"))
        cd = r.get("cleared_date", "")
        if cd:
            c = parse_date(cd)
            if c is None:
                issues.append(Issue("CHK-012", "error", n, f"cleared_date '{cd}' is not a real date"))
            elif d and c < d:
                issues.append(Issue("CHK-012", "error", n, f"check {num} cleared {cd}, before its date {r['date']}"))
        if status == "cleared" and not cd:
            issues.append(Issue("CHK-016", "warning", n, f"check {num} is cleared but has no cleared_date"))
        if status == "cleared" and cd and statement and AMOUNT_RE.match(r["amount"]):
            c = parse_date(cd)
            if c and dt.date.fromisoformat(statement["period_start"]) <= c <= dt.date.fromisoformat(statement["period_end"]):
                cleared_total += Decimal(r["amount"])
                cleared_count += 1

    gaps = {}
    for acct, nums in numbers.items():
        nums = sorted(nums)
        missing = [x for a, b in zip(nums, nums[1:]) for x in range(a + 1, b)]
        if missing:
            gaps[acct] = missing
            shown = ", ".join(str(x) for x in missing[:10]) + (" ..." if len(missing) > 10 else "")
            issues.append(Issue("CHK-011", "warning", 0, f"account {acct}: check numbers missing from the register: {shown}"))

    summary = {"checks": len(rows), "total_written": f"{written_total:.2f}", "gaps": gaps}
    if statement:
        want_total = Decimal(statement["checks_paid_total"])
        want_count = int(statement["checks_paid_count"])
        summary.update({"cleared_in_period": cleared_count, "cleared_total": f"{cleared_total:.2f}"})
        if cleared_total != want_total or cleared_count != want_count:
            issues.append(Issue("CHK-014", "error", 0,
                                f"register cleared {cleared_count} checks for {cleared_total:.2f}; statement says {want_count} for {want_total:.2f} (difference {want_total - cleared_total:.2f})"))
    return issues, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a check register CSV.")
    ap.add_argument("register")
    ap.add_argument("--statement", help="JSON with the statement's checks-paid count and total")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        st = json.load(open(a.statement, encoding="utf-8")) if a.statement else None
        issues, summary = check(a.register, st)
    except (OSError, UnicodeDecodeError, csv.Error, KeyError, ValueError) as exc:
        print(f"could not read: {exc}", file=sys.stderr)
        return 2
    errors = [i for i in issues if i.severity == "error"]
    if a.json:
        print(json.dumps({"file": a.register, "ok": not errors, "summary": summary, "issues": [vars(i) for i in issues]}, indent=2))
    else:
        for i in issues:
            print(i)
        print(f"{a.register}: {summary.get('checks', 0)} checks. " + ("OK" if not errors else f"{len(errors)} error(s)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
