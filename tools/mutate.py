"""Mutate every defence and record which test killed each mutant.

A passing count is a claim. This table is evidence: each row names a change
that removes or inverts one defence in contracts/telltale.py or
contracts/fixtures/piecework.py, and the test that failed because of it. If any
mutant survives, no table is written and the exit code is 1: a defence with no
test that can fail is a defence that can be deleted by accident.

    python tools/mutate.py            # writes tests/MUTATIONS.md
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "telltale.py").read_text(encoding="utf-8")
FSRC = (ROOT / "contracts" / "fixtures" / "piecework.py").read_text(encoding="utf-8")
PYTEST = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider",
          str(ROOT / "tests" / "test_pure.py")]

# (name, before, after) against the register, or (name, before, after, "piecework").
MUTATIONS = [
    ("the fence does nothing",
     'return str(raw).replace("<", "(").replace(">", ")")', 'return str(raw)'),
    ("the fence deletes instead of replacing",
     'return str(raw).replace("<", "(").replace(">", ")")',
     'return str(raw).replace("<", "").replace(">", "")'),
    ("the response reaches the judge unfenced",
     '"<<<RESPONSE>>>\\n" + _fence(response_text)[:MAX_RESPONSE_CHARS] + "\\n<<<END RESPONSE>>>"',
     '"<<<RESPONSE>>>\\n" + str(response_text)[:MAX_RESPONSE_CHARS] + "\\n<<<END RESPONSE>>>"'),
    ("a subject reaches the judge unfenced",
     '            + _fence(body)[:MAX_BODY_CHARS]', '            + str(body)[:MAX_BODY_CHARS]'),
    ("the second forced choice shows the subjects the same way round",
     'second = gl.nondet.exec_prompt(_task(text, decoy, real), response_format="json")',
     'second = gl.nondet.exec_prompt(_task(text, real, decoy), response_format="json")'),
    ("one order is enough to call a response specific",
     '    if first_pick == PICK_A and second_pick == PICK_B:', '    if first_pick == PICK_A:'),
    ("a text that names the same letter twice passes",
     '    if first_pick == PICK_A and second_pick == PICK_B:',
     '    if first_pick == PICK_A and second_pick in (PICK_A, PICK_B):'),
    ("work about the other subject is called specific",
     '    if first_pick == PICK_B and second_pick == PICK_A:\n        return MISFILED',
     '    if first_pick == PICK_B and second_pick == PICK_A:\n        return SPECIFIC'),
    ("one order is enough to call a response generic",
     '    if first_pick == PICK_EITHER and second_pick == PICK_EITHER:',
     '    if first_pick == PICK_EITHER or second_pick == PICK_EITHER:'),
    ("the validators need not agree on the word that is stored",
     '            return str(theirs.get("outcome", "")) == str(mine["outcome"])', '            return True'),
    ("the judge may answer outside the set",
     '    if pick not in PICKS:\n        raise gl.vm.UserError(ERROR_LLM + " the judge answered outside the set: " + pick[:40])\n', ''),
    ("the stored sentence comes from the judge instead of the contract",
     '        reason = _why(outcome, decoys)', '        reason = str(real_side)[:MAX_REASON_CHARS]'),
    ("the field is any other subject rather than the nearest",
     '                if best is None or entry[1] > best[1]:', '                if best is None:'),
    ("a subject is told apart from itself",
     '            if other_id == subject_id:\n                continue\n', ''),
    ("one account may fill the whole field with subjects it wrote",
     '                if entry[2] in owners or entry[0] in taken:', '                if entry[0] in taken:'),
    ("the author may supply their own examiner",
     '            if subject.owner == author:\n                continue\n', ''),
    ("a subject sharing no tag at all is a valid decoy",
     '            if overlap < 1:\n                continue\n', ''),
    ("a test runs against a field too small to be one",
     '        if len(field) < MAX_DECOYS:', '        if False:'),
    ("a verdict can be asked again until the answer suits, or destroyed",
     '        if bool(response.tested):', '        if False:'),
    ("the same work may be resubmitted under a new name",
     '        if key in self.tried:', '        if False:'),
    ("a response may be the subject read back to itself",
     '        if _normalised(body) in _normalised(str(self.subjects[subject_id].body)):\n            _fail("a response cannot be the subject read back to itself; engage with it instead")\n', ''),
    ("beating one decoy is enough",
     '    if all(w == SPECIFIC for w in words):', '    if any(w == SPECIFIC for w in words):'),
    ("an empty field claims something",
     '    if not words:\n        return UNCLEAR\n', ''),
    ("a register grows without bound, so the field is built in unbounded work",
     '        if len(self.subject_ids) >= MAX_SUBJECTS:', '        if False:'),
    ("a validator whose own judge misbehaves escapes instead of disagreeing",
     '            try:\n                mine = leader_fn()\n            except Exception:', '            if True:\n                mine = leader_fn()\n            if False:'),
    ("tags outside the register's vocabulary are accepted",
     '            if tag not in allowed:', '            if False:'),
    ("a subject may carry no tags at all",
     '        if not tags or len(tags) > MAX_TAGS:', '        if False:'),
    ("a vocabulary of one makes every decoy a stranger",
     '        if len(words) < 2 or len(words) > MAX_VOCABULARY:', '        if False:'),
    ("an id may be written in look-alike characters",
     '    if not value or len(value) > MAX_ID_CHARS or not all(c in ID_CHARS for c in value):',
     '    if False:'),
    ("a title or a body has no cap",
     '        if not clean_body or len(clean_body) > MAX_BODY_CHARS:', '        if False:'),
    ("text the fence would rewrite is judged anyway",
     '        if "<" in body or ">" in body:\n            _fail("a response cannot contain < or >, because they are replaced before the judge "\n                  "reads it; write the comparison in words")\n', ''),
    ("untested work counts as having passed the test",
     '        return str(self.responses[key].status) == SPECIFIC',
     '        return str(self.responses[key].status) != MISFILED'),
    ("a response may be filed against a subject that does not exist",
     '        if subject_id not in self.subjects:\n            _fail("no subject named " + subject_id[:MAX_ID_CHARS])\n', ''),
    ("piecework: work about a subject a stranger owns under that name is paid",
     '        if owner != self.subject_owner.as_hex.lower():', '        if False:', "piecework"),
    ("piecework: generic work is paid",
     '        if status != "specific":', '        if False:', "piecework"),
    ("piecework: a pass against an easy field counts as any other",
     '        if shared < int(self.min_shared):', '        if False:', "piecework"),
    ("piecework: the same work is paid twice",
     '        if key in self.paid:\n            return {"do": "no", "why": "this response has already been paid"}\n', '', "piecework"),
    ("piecework: work about another subject is paid from this budget",
     '        if str(row.get("subject", "")).lower() != str(self.subject_id):', '        if False:', "piecework"),
    ("piecework: a register that cannot be read pays anyway",
     '        except Exception:\n            return {"error": "the register could not be read"}',
     '        except Exception:\n            return {"status": "specific", "author": "0xANYBODY", "subject": "refunds"}', "piecework"),
    ("piecework: a short budget pays a partial rate",
     '        if int(self.pool) < int(self.rate):', '        if False:', "piecework"),
    ("piecework: somebody other than the author is paid",
     '        payee = gl.Address(str(decision["to"]))', '        payee = self.buyer', "piecework"),
    ("piecework: anybody may reclaim what is left",
     '        if gl.message.sender_address != self.buyer:\n            _fail("only the buyer reclaims what is left")\n', '', "piecework"),
    ("piecework: the buyer may reclaim before the window ends",
     '        if days is None or days < int(self.open_days):', '        if False:', "piecework"),
    ("piecework: a budget with no readable clock is reclaimed on a guess",
     '        if not str(self.opened_at) or not now:\n            _fail("this budget has no readable clock, so its window cannot be closed")\n', '', "piecework"),
]


def _env(**extra):
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **extra)


def run(main_path: pathlib.Path, fixture_path: pathlib.Path) -> str:
    out = subprocess.run(PYTEST, env=_env(TELLTALE_SOURCE=str(main_path), PIECEWORK_SOURCE=str(fixture_path)),
                         capture_output=True, text=True, cwd=ROOT)
    if out.returncode == 0:
        return ""
    text = out.stdout + out.stderr
    if "error during collection" in text or "IndentationError" in text or "SyntaxError" in text:
        raise RuntimeError("the mutant does not even import; that is a broken anchor, not a killed defence")
    m = re.search(r"FAILED tests/test_pure\.py::(\S+)", text)
    if not m:
        raise RuntimeError("a test failed but its name could not be read:\n" + text[-800:])
    return m.group(1)


def main() -> int:
    baseline = subprocess.run(PYTEST, env=_env(), capture_output=True, text=True, cwd=ROOT)
    if baseline.returncode != 0:
        print("the unmutated suite does not pass; a mutation table over a failing suite proves nothing")
        print((baseline.stdout + baseline.stderr)[-600:])
        return 3
    rows, escaped = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for entry in MUTATIONS:
            name, old, new = entry[0], entry[1], entry[2]
            target = entry[3] if len(entry) > 3 else "register"
            base = FSRC if target == "piecework" else SRC
            if base.count(old) != 1:
                print(f"  ! anchor found {base.count(old)} times, expected once: {name}")
                return 2
            k = len(rows) + len(escaped)
            main_path = pathlib.Path(tmp) / f"telltale_{k}.py"
            fixture_path = pathlib.Path(tmp) / f"piecework_{k}.py"
            main_path.write_text(base.replace(old, new) if target == "register" else SRC, encoding="utf-8")
            fixture_path.write_text(base.replace(old, new) if target == "piecework" else FSRC, encoding="utf-8")
            killer = run(main_path, fixture_path)
            (rows if killer else escaped).append((name, killer))
            print(f"  {'killed ' if killer else 'ESCAPED'}  {name}" + (f"  <- {killer}" if killer else ""))
    if escaped:
        print(f"\n{len(escaped)} mutant(s) escaped; no table written.")
        return 1
    table = ["# Mutations", "",
             f"{len(rows)} defences in `contracts/telltale.py` and `contracts/fixtures/piecework.py`, "
             "each removed or inverted in turn, and the test that failed because of it. Generated by "
             "`tools/mutate.py`; it refuses to write this file if any mutant survives.", "",
             "| defence removed | killed by |", "|---|---|"] + [f"| {n} | `{k}` |" for n, k in rows] + [""]
    (ROOT / "tests" / "MUTATIONS.md").write_text("\n".join(table), encoding="utf-8")
    print(f"\n{len(rows)} / {len(rows)} killed · tests/MUTATIONS.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
