"""Generate the fictional check registers in samples/.

    python3 scripts/generate_samples.py

Every business, bank, routing number and account number is made up.
Routing numbers start with 5x, a prefix the Federal Reserve has not
assigned, so they pass the ABA checksum but can never match a real bank.
Seeded, so the output is the same on every run.

Writes, for 12 fictional businesses, July to September 2026:
  samples/registers/<slug>-2026-q3.csv    the check register
  samples/json/<slug>-2026-q3.json        the same rows as JSON (schema rows)
  samples/statements/<slug>-2026-MM.json  checks paid per monthly statement
and samples/invalid/ with one broken register per rule.
"""
import csv
import datetime as dt
import json
import os
import random
import shutil
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
from amount_words import amount_to_words  # noqa: E402

OUT = os.path.join(ROOT, "samples")
FIELDS = ["check_number", "date", "payee", "amount", "amount_written", "memo", "bank", "routing_number", "account_last4", "micr_line", "status", "cleared_date", "source_file"]

BUSINESSES = [
    ("juniper-lane-bakery", "Juniper Lane Bakery LLC", "Harbor Point Savings Bank", 1043),
    ("okafor-family-dental", "Okafor Family Dental PC", "Cedar Valley Credit Union", 5210),
    ("brightwater-landscaping", "Brightwater Landscaping Inc", "Northfield National Bank", 3301),
    ("redline-freight", "Redline Freight Co", "Prairie Trust Bank", 8817),
    ("vega-cpa", "Marisol Vega CPA", "Lakeshore Community Bank", 2004),
    ("st-brendan-parish", "St. Brendan Parish Food Pantry", "Harbor Point Savings Bank", 610),
    ("copperline-electric", "Copperline Electric LLC", "Granite Valley Bank", 4420),
    ("meadowbrook-hoa", "Meadowbrook Homeowners Association", "Prairie Trust Bank", 1188),
    ("tan-and-ruiz-law", "Tan & Ruiz Law Group", "Northfield National Bank", 7032),
    ("blue-heron-vet", "Blue Heron Veterinary Clinic", "Cedar Valley Credit Union", 2555),
    ("ironwood-property", "Ironwood Property Management", "Lakeshore Community Bank", 9140),
    ("little-acorns-daycare", "Little Acorns Daycare", "Granite Valley Bank", 1320),
]
PAYEES = [
    ("Sysco Foods", "Inv 448120"), ("Cintas Corporation", "Uniform rental"), ("Valley Propane Co", "Acct 22-1904"),
    ("City of Fairhaven Utilities", "Water/sewer"), ("Henry Schein", "Supplies"), ("Patterson Dental", "Order 77310"),
    ("Main Street Properties LLC", "Rent"), ("Ortiz Plumbing", "Job 1182"), ("Lopez Tree Service", "Subcontract"),
    ("IRS", "941 Q2"), ("State Comptroller", "Sales tax"), ("Ace Hardware", ""), ("Grainger", "PO 5512"),
    ("Dana Whitfield", "Contract labor"), ("Kofi Mensah", "Reimbursement"), ("Hartwell Insurance Agency", "Policy BOP-2231"),
    ("Pioneer Equipment Rental", "Lift rental"), ("Northside Fuel", ""), ("Greenleaf Janitorial", "Monthly cleaning"),
    ("County Treasurer", "Property tax"), ("Riverbend Printing", "Inv 9031"), ("A. Petrovic", "Refund deposit"),
    ("Second Harvest Regional", "Food order"), ("Fairhaven Glass", "Repair"), ("Summit Payroll Services", "Fees"),
]


def routing_for(bank):
    rng = random.Random(bank)
    d = [5, rng.randint(0, 9)] + [rng.randint(0, 9) for _ in range(6)]
    for last in range(10):
        full = d + [last]
        if (3 * (full[0] + full[3] + full[6]) + 7 * (full[1] + full[4] + full[7]) + (full[2] + full[5] + full[8])) % 10 == 0:
            return "".join(map(str, full))
    raise AssertionError


def written(rng, amount):
    base = amount_to_words(amount)
    style = rng.random()
    if style < 0.6:
        return base
    if style < 0.75:
        return "**" + base.replace(" and ", " & ") + "**"
    if style < 0.85 and amount == int(amount):
        return base.replace(" and 00/100", " and xx/100")
    if style < 0.95:
        return base + " dollars"
    dollars, cents = int(amount), int((amount - int(amount)) * 100)
    return amount_to_words(Decimal(dollars)).replace(" and 00/100", "") + f" dollars and {cents} cents"


def micr(serial, routing, account):
    return f"⑈{serial:06d}⑈ ⑆{routing}⑆ {account}⑈"


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def main():
    rng = random.Random(20261105)
    for sub in ("registers", "json", "statements", "invalid"):
        shutil.rmtree(os.path.join(OUT, sub), ignore_errors=True)
        os.makedirs(os.path.join(OUT, sub))
    index = []
    period_end = dt.date(2026, 9, 30)
    for slug, biz, bank, first in BUSINESSES:
        routing = routing_for(bank)
        account = f"{rng.randint(10 ** 9, 10 ** 10 - 1)}"
        last4 = account[-4:]
        rows = []
        day = dt.date(2026, 7, 1)
        num = first
        while True:
            day += dt.timedelta(days=rng.randint(1, 6))
            if day > period_end:
                break
            if rng.random() < 0.05:
                rows.append({"check_number": str(num), "date": day.isoformat(), "payee": "", "amount": "", "amount_written": "VOID",
                             "memo": "Spoiled", "bank": bank, "routing_number": routing, "account_last4": last4,
                             "micr_line": micr(num, routing, account), "status": "void", "cleared_date": "", "source_file": f"{slug}-checks-2026-q3.pdf"})
                num += 1
                continue
            payee, memo = rng.choice(PAYEES)
            amount = Decimal(rng.randint(1500, 480000)) / 100
            if rng.random() < 0.2:
                amount = Decimal(int(amount))
            clears = day + dt.timedelta(days=rng.randint(2, 14))
            status, cleared = "cleared", clears.isoformat()
            if clears > period_end:
                status, cleared = "outstanding", ""
            elif rng.random() < 0.02:
                status, cleared = "stopped", ""
            rows.append({"check_number": str(num), "date": day.isoformat(), "payee": payee, "amount": f"{amount:.2f}",
                         "amount_written": written(rng, amount), "memo": memo, "bank": bank, "routing_number": routing,
                         "account_last4": last4, "micr_line": micr(num, routing, account), "status": status,
                         "cleared_date": cleared, "source_file": f"{slug}-checks-2026-q3.pdf"})
            num += 1
        write_csv(os.path.join(OUT, "registers", f"{slug}-2026-q3.csv"), rows)
        with open(os.path.join(OUT, "json", f"{slug}-2026-q3.json"), "w", encoding="utf-8") as fh:
            json.dump({"business": biz, "fictional": True, "checks": rows}, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        for m in (7, 8, 9):
            start = dt.date(2026, m, 1)
            end = dt.date(2026, m + 1, 1) - dt.timedelta(days=1)
            paid = [r for r in rows if r["status"] == "cleared" and start <= dt.date.fromisoformat(r["cleared_date"]) <= end]
            st = {"bank": bank, "business": biz, "account_last4": last4, "period_start": start.isoformat(), "period_end": end.isoformat(),
                  "checks_paid_count": len(paid), "checks_paid_total": f"{sum(Decimal(r['amount']) for r in paid):.2f}",
                  "register_file": f"samples/registers/{slug}-2026-q3.csv", "fictional": True}
            with open(os.path.join(OUT, "statements", f"{slug}-2026-{m:02d}.json"), "w", encoding="utf-8") as fh:
                json.dump(st, fh, indent=2)
                fh.write("\n")
        outstanding = [r for r in rows if r["status"] == "outstanding"]
        index.append([slug, biz, bank, routing, last4, len(rows), sum(r["status"] == "void" for r in rows), len(outstanding),
                      f"{sum(Decimal(r['amount']) for r in outstanding):.2f}"])
    with open(os.path.join(OUT, "index.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["sample", "business", "bank", "routing_number", "account_last4", "checks", "voids", "outstanding_at_sep_30", "outstanding_total"])
        w.writerows(index)
    make_invalid()
    print(f"{len(index)} registers, {sum(r[5] for r in index)} checks")


def make_invalid():
    src = os.path.join(OUT, "registers", "juniper-lane-bakery-2026-q3.csv")
    base = list(csv.DictReader(open(src, encoding="utf-8")))
    stmt = "samples/statements/juniper-lane-bakery-2026-08.json"
    cases = []

    def add(name, rows, rule, why, statement=None):
        write_csv(os.path.join(OUT, "invalid", name), rows)
        cases.append({"file": f"samples/invalid/{name}", "must_fail": rule, "what_is_wrong": why, "statement": statement})

    def copy():
        return [dict(r) for r in base]

    live = [i for i, r in enumerate(base) if r["status"] == "cleared"]
    r = copy(); r[live[0]]["check_number"] = ""
    add("blank-check-number.csv", r, "CHK-001", "a row with no check number")
    r = copy(); r[live[1]]["amount"] = "$" + r[live[1]]["amount"]
    add("dollar-sign-in-amount.csv", r, "CHK-002", "amount written as $123.45")
    r = copy(); r[live[2]]["amount_written"] = "Two hundred fiftey and 00/100"
    add("unreadable-words.csv", r, "CHK-003", "a misspelled written amount")
    r = copy(); i = live[3]; amt = Decimal(r[i]["amount"]); r[i]["amount"] = f"{amt * 10:.2f}"
    add("figures-and-words-disagree.csv", r, "CHK-004", "figures read with a slipped decimal: ten times the written amount")
    r = copy()
    for row in r:
        row["routing_number"] = row["routing_number"][:8] + str((int(row["routing_number"][8]) + 1) % 10)
        row["micr_line"] = row["micr_line"].replace(base[0]["routing_number"], row["routing_number"])
    add("bad-routing-checksum.csv", r, "CHK-005", "last routing digit misread on every row")
    r = copy(); i = live[4]; r[i]["micr_line"] = r[i]["micr_line"].replace(f"{int(r[i]['check_number']):06d}", f"{int(r[i]['check_number']) + 100:06d}")
    add("micr-serial-mismatch.csv", r, "CHK-007", "MICR check number differs from the printed one")
    r = copy(); r[live[5]]["routing_number"] = routing_for("Some Other Bank")
    add("routing-field-mismatch.csv", r, "CHK-008", "routing field doesn't match the MICR line")
    r = copy(); r[live[6]]["account_last4"] = "0000"
    add("wrong-account.csv", r, "CHK-009", "a check from another account in this register")
    r = copy(); r.insert(live[7] + 1, dict(r[live[7]]))
    add("duplicate-check.csv", r, "CHK-010", "the same check scanned twice")
    r = copy(); del r[live[8]]
    add("gap-in-sequence.csv", r, "CHK-011", "a check missing from the register (warning)")
    r = copy(); i = live[9]; r[i]["cleared_date"] = (dt.date.fromisoformat(r[i]["date"]) - dt.timedelta(days=3)).isoformat()
    add("cleared-before-written.csv", r, "CHK-012", "a cleared date three days before the check date")
    r = copy(); voids = [i for i, x in enumerate(r) if x["status"] == "void"] or [live[10]]
    r[voids[0]].update({"status": "void", "amount": "125.00", "amount_written": "One hundred twenty-five and 00/100"})
    add("void-with-amount.csv", r, "CHK-013", "a void check still carrying an amount")
    r = copy()
    aug = [i for i, x in enumerate(r) if x["status"] == "cleared" and x["cleared_date"].startswith("2026-08")]
    r[aug[0]]["status"], r[aug[0]]["cleared_date"] = "outstanding", ""
    add("missed-cleared-check.csv", r, "CHK-014", "an August check marked outstanding though the bank paid it", stmt)
    r = copy(); r[live[11]]["payee"] = ""
    add("no-payee.csv", r, "CHK-015", "a check with no payee (warning)")
    r = copy(); r[live[12]]["cleared_date"] = ""
    add("cleared-without-date.csv", r, "CHK-016", "status cleared with no cleared date (warning)")
    with open(os.path.join(OUT, "invalid", "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(cases, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main()
