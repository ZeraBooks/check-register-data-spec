# Check register data spec

A check turned into data is one row: check number, date, payee, amount in figures, amount in words, memo, bank, routing number, account and the MICR line. The figures and the words must agree, and the MICR line must agree with what's printed above it. [ZeraBooks Convert](https://www.zerabooks.com/check-converter) reads scanned checks into exactly these rows and compares the written amount with the figures on every check, so a misread amount is flagged before you download Excel or CSV.

This repo is the spec behind that: a JSON Schema for one check row, 16 rules as data, 12 fictional quarterly check registers (313 checks) with the bank statements they tie to, 15 broken registers, and a Python validator.

- Schema: [`schema/check-register-row.schema.json`](schema/check-register-row.schema.json), [`schema/statement-checks.schema.json`](schema/statement-checks.schema.json)
- Rules: [`rules/check-rules.csv`](rules/check-rules.csv)
- Validator: [`cli/check_register.py`](cli/check_register.py) and [`cli/amount_words.py`](cli/amount_words.py) (Python 3.8+, standard library)
- Samples: [`samples/`](samples/), all fictional
- Release zip: [latest](https://github.com/ZeraBooks/check-register-data-spec/releases/latest)

## One check, as a row

```csv
check_number,date,payee,amount,amount_written,memo,bank,routing_number,account_last4,micr_line,status,cleared_date,source_file
2004,2026-07-04,Fairhaven Glass,692.63,Six hundred ninety-two and 63/100,Repair,Lakeshore Community Bank,554239042,1628,⑈002004⑈ ⑆554239042⑆ 4847991628⑈,cleared,2026-07-09,vega-cpa-checks-2026-q3.pdf
```

| Field | What it holds |
|---|---|
| `check_number` | The number in the top right corner. |
| `date` | Date written on the check, YYYY-MM-DD. |
| `payee` | Pay to the order of. Blank only on a void. |
| `amount` | The courtesy amount in the box, positive, two decimals, no `$`. |
| `amount_written` | The legal amount on the line, exactly as written. |
| `memo` | The memo line. Often an invoice or account number, which is what you categorize on. |
| `bank` | Drawee bank printed on the check. |
| `routing_number` | 9 digits from the MICR line. |
| `account_last4` | Last four of the account. Keep the full number only inside `micr_line`. |
| `micr_line` | The magnetic ink line as printed. ⑈ (U+2448) is the on-us symbol, ⑆ (U+2446) the transit symbol. |
| `status` | `cleared`, `outstanding`, `void` or `stopped`. |
| `cleared_date` | When the bank paid it, from the statement. |
| `source_file` | The scan it came from. |

## Why both amounts

Every check prints its amount twice. When they disagree, the words win: UCC 3-114 says words prevail over numbers. In practice a mismatch is almost always a misread, usually a slipped decimal or a 7 read as a 1. Reading only the box is how a $2,881.19 check becomes $28,811.90 in the books.

```
$ python3 cli/check_register.py samples/invalid/figures-and-words-disagree.csv
ERROR   CHK-004 line 5: check 1046: figures say 28811.90, words say 2881.19 ('Two thousand eight hundred eighty-one and 19/100 dollars')
```

`amount_words.py` reads the ways people really write the line: `and 45/100`, `& 45/100`, `and xx/100`, `and no/100`, `45 cents`, hyphens, `dollars only`, `**` fill.

## The rules

| ID | Rule |
|---|---|
| CHK-001 | Required columns present; check number, date, routing, account, MICR and status filled |
| CHK-002 | Amount positive, two decimals, digits only |
| CHK-003 | Written amount can be read |
| CHK-004 | Written amount equals the figures |
| CHK-005 | Routing number passes the ABA 3-7-1 checksum |
| CHK-006 | Routing prefix is an assigned Federal Reserve range (warning) |
| CHK-007 | MICR check number equals the printed number |
| CHK-008 | Routing field equals the MICR routing |
| CHK-009 | MICR account ends in `account_last4` |
| CHK-010 | No check number twice in one account |
| CHK-011 | No gaps in the sequence unless the missing check is listed as void or stopped (warning) |
| CHK-012 | Dates are real and no check clears before its date |
| CHK-013 | A void has no amount and `VOID` as the written amount |
| CHK-014 | Cleared checks in the period add up to the statement's checks-paid total and count |
| CHK-015 | Payee filled (warning) |
| CHK-016 | Cleared rows have a cleared date (warning) |

Why each one matters is in the rules file.

## Run it

```bash
python3 cli/check_register.py register.csv
python3 cli/check_register.py register.csv --statement august-checks-paid.json
python3 cli/check_register.py register.csv --json
```

The statement file is the checks-paid line from the bank statement:

```json
{"account_last4": "2460", "period_start": "2026-08-01", "period_end": "2026-08-31",
 "checks_paid_count": 8, "checks_paid_total": "22339.46"}
```

If the register missed a check the bank paid, CHK-014 says by how much:

```
ERROR   CHK-014 file: register cleared 7 checks for 17613.41; statement says 8 for 22339.46 (difference 4726.05)
```

Exit code 0 means no errors, 1 means errors, 2 means the file couldn't be read.

## Samples

`scripts/generate_samples.py` writes them from a fixed seed. Every business, bank and number is made up. The routing numbers start with 5, a prefix the Federal Reserve hasn't assigned, so they pass the checksum but can't match a real bank. That's why every sample shows a CHK-006 warning, and a real register shouldn't.

| Folder | Files | What |
|---|---|---|
| `samples/registers/` | 12 | July to September 2026 check registers for 12 fictional businesses: a bakery, a dental office, a law firm, an HOA, a food pantry and others. Voids, stopped checks and checks still outstanding at September 30 included. |
| `samples/json/` | 12 | The same registers as JSON, one schema row per check. |
| `samples/statements/` | 36 | Checks paid per monthly statement for each register. A check written in late July that clears in August counts in August. |
| `samples/invalid/` | 15 | One broken register per rule, with `expected.json`. |
| `samples/index.csv` | 1 | One row per register, with the outstanding checks at quarter end. |

## From scans to rows

Typing checks into a spreadsheet is where both-amounts mistakes come from. [ZeraBooks Convert](https://www.zerabooks.com/check-converter) takes a PDF of scanned checks, makes one row per check with check number, date, payee, amount, memo, written by, bank and account last 4, and compares the written amount with the figures on each one. Checks download as Excel or CSV in one **All details** layout. The same plan covers bank and card statements, at $79 a month billed annually or $149 month to month for 1,000 pages, with a 7-day trial.

## Tests

```bash
python3 scripts/generate_samples.py
python3 -m unittest discover -s tests -v
```

## License and citation

Code MIT ([`LICENSE`](LICENSE)). Samples, schemas, rules and docs CC BY 4.0 ([`LICENSE-SAMPLES`](LICENSE-SAMPLES)). See [`CITATION.cff`](CITATION.cff). `MANIFEST.json` and `checksums.txt` list every data file with its SHA-256.

Not legal advice. UCC 3-114 is cited for the general rule; how a bank handles a particular conflicting check is up to the bank.
