# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

"""Piecework: a budget that only pays for work that passed the test.

This is the consequence, and it is the reason the register's verdict is worth
reaching consensus about. A buyer puts money behind one subject and a rate per
accepted response. Anybody may then present a response for payment, and this
contract asks the register one free question, synchronously, with no model and
no validator: did this response tell the subject apart from its hardest decoy?

    specific  -> the author the register recorded is paid the rate, once
    anything else -> nobody is paid, and the reason is readable

The buyer binds three things before any money moves: the register address, the
subject id, and the address they independently know to own that subject. A
subject id is first come first served on a register, so the id alone is never
authority. If the subject under that name turns out to belong to somebody else,
this budget pays nobody and the buyer can take the money back.

The remainder is only reclaimable after the window the buyer set, so a buyer
cannot watch the work arrive and close the budget before it is tested.

It is a fixture: small on purpose, and here to be read.
"""

import json
import typing

import genlayer as gl


ZERO = "0x0000000000000000000000000000000000000000"

MIN_DAYS = 1
MAX_DAYS = 365


def _fail(message: str) -> typing.NoReturn:
    raise gl.vm.UserError("[EXPECTED] " + message)


def _now() -> str:
    """The one clock validators agree on: the message's own datetime."""
    try:
        value = getattr(gl.message, "datetime", None)
        if not value:
            raw = getattr(gl.message, "raw", None)
            value = raw.get("datetime") if hasattr(raw, "get") else None
        return str(value) if value else ""
    except Exception:
        return ""


def _instant_seconds(stamp: str) -> int:
    """Seconds since 1970-01-01 for an ISO-8601 UTC instant, integers only."""
    text = str(stamp).strip()
    if len(text) < 10:
        return -1
    try:
        year = int(text[0:4])
        month = int(text[5:7])
        day = int(text[8:10])
        hour = int(text[11:13]) if len(text) >= 13 else 0
        minute = int(text[14:16]) if len(text) >= 16 else 0
        second = int(text[17:19]) if len(text) >= 19 else 0
    except Exception:
        return -1
    if year < 1970 or month < 1 or month > 12 or day < 1 or day > 31:
        return -1
    days = 0
    for y in range(1970, year):
        days += 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    lengths = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    for m in range(1, month):
        days += lengths[m - 1]
    days += day - 1
    return ((days * 24 + hour) * 60 + minute) * 60 + second


def _days_between(earlier: str, later: str) -> typing.Optional[int]:
    """Whole days from one ISO instant to another; None if either cannot be read."""
    a, b = _instant_seconds(earlier), _instant_seconds(later)
    if a < 0 or b < 0:
        return None
    return (b - a) // 86400


class Piecework(gl.contract.Contract):
    register: gl.Address       # the Telltale register that runs the test
    subject_id: str            # the subject this budget buys work about
    subject_owner: gl.Address  # who the buyer knows owns it, bound before any money moved
    buyer: gl.Address
    rate: gl.u256              # paid per accepted response
    opened_at: str
    open_days: gl.u32
    pool: gl.u256
    paid_total: gl.u256
    paid: gl.storage.TreeMap[str, bool]
    paid_ids: gl.storage.DynArray[str]

    def __init__(self, register: str, subject_id: str, subject_owner: str,
                 rate: int, open_days: int) -> None:
        self.register = gl.Address(register)
        cleaned = str(subject_id).strip().lower()
        if not cleaned:
            _fail("a budget names the subject it buys work about")
        try:
            rate_value = int(rate)
        except Exception:
            _fail("the rate is a whole number of attoGEN")
        if rate_value <= 0:
            _fail("the rate is greater than zero")
        try:
            days = int(open_days)
        except Exception:
            _fail("the window is a whole number of days")
        if days < MIN_DAYS or days > MAX_DAYS:
            _fail("the window is " + str(MIN_DAYS) + " to " + str(MAX_DAYS) + " days")
        self.subject_id = cleaned
        self.subject_owner = gl.Address(str(subject_owner).strip())
        self.buyer = gl.message.sender_address
        self.rate = gl.u256(rate_value)
        self.opened_at = _now()
        self.open_days = gl.u32(days)
        self.pool = gl.u256(0)
        self.paid_total = gl.u256(0)

    @gl.public.write.payable
    def fund(self) -> str:
        """Add to the budget. Anybody may. This never raises; see Bond.fund."""
        value = gl.message.value
        if value == gl.u256(0):
            return json.dumps({"ok": False, "reason": "send an amount greater than zero"})
        self.pool = gl.u256(int(self.pool) + int(value))
        return json.dumps({"ok": True, "pool": str(int(self.pool))})

    # ------------------------------------------------------------- the decision

    def _row(self, response_id: str) -> dict:
        try:
            register = gl.contract.get_at(self.register)
            return json.loads(str(register.view().response(str(response_id))))
        except Exception:
            return {"error": "the register could not be read"}

    def _bound(self) -> str:
        """"" when the register's subject is the one the buyer bound, else why not."""
        try:
            register = gl.contract.get_at(self.register)
            row = json.loads(str(register.view().subject(str(self.subject_id))))
        except Exception:
            return "the register could not be read"
        if not isinstance(row, dict) or "error" in row:
            return "the register holds no subject under that name"
        owner = str(row.get("owner", ZERO)).lower()
        if owner != self.subject_owner.as_hex.lower():
            return ("the subject under that name belongs to " + owner
                    + ", not to the account this budget was tied to")
        return ""

    def _decision(self, response_id: str) -> dict:
        key = str(response_id).strip().lower()
        if key in self.paid:
            return {"do": "no", "why": "this response has already been paid"}
        missing = self._bound()
        if missing:
            return {"do": "no", "why": missing}
        row = self._row(key)
        if not isinstance(row, dict) or "error" in row:
            return {"do": "no", "why": "the register holds no response under that name"}
        if str(row.get("subject", "")).lower() != str(self.subject_id):
            return {"do": "no", "why": "that response is about another subject"}
        status = str(row.get("status", ""))
        if status != "specific":
            return {"do": "no", "why": "the register says this response is " + (status or "untested")}
        if int(self.pool) < int(self.rate):
            return {"do": "no", "why": "the budget is down to " + str(int(self.pool))
                                       + " and the rate is " + str(int(self.rate))}
        return {"do": "yes", "to": str(row.get("author", ZERO)),
                "why": "told apart from " + str(row.get("decoy", "")) + ", which shares "
                       + str(row.get("shared_tags", 0)) + " tag(s)"}

    @gl.public.write
    def pay(self, response_id: str) -> str:
        """Pay the author of a response the register accepted. Anybody may trigger it.

        Deliberately open: the money can only reach the address the register
        recorded as the author, at the rate fixed when the budget opened, once
        per response. Letting anyone press it means an author is never waiting
        on the buyer's goodwill for work the validators already accepted.
        """
        key = str(response_id).strip().lower()
        decision = self._decision(key)
        if decision["do"] != "yes":
            _fail(str(decision["why"]))
        payee = gl.Address(str(decision["to"]))
        if payee.as_hex.lower() == ZERO:
            _fail("the register names no author for that response")
        amount = self.rate
        self.paid[key] = True
        self.paid_ids.append(key)
        self.pool = gl.u256(int(self.pool) - int(amount))
        self.paid_total = gl.u256(int(self.paid_total) + int(amount))
        gl.contract.get_at(payee).emit_transfer(value=amount)
        return json.dumps({"ok": True, "response": key, "paid": payee.as_hex,
                           "amount": str(int(amount)), "why": str(decision["why"]),
                           "pool": str(int(self.pool))})

    @gl.public.write
    def reclaim(self) -> str:
        """Take back what is left, after the window the buyer set. Buyer only."""
        if gl.message.sender_address != self.buyer:
            _fail("only the buyer reclaims what is left")
        if int(self.pool) == 0:
            _fail("there is nothing left in this budget")
        now = _now()
        if not str(self.opened_at) or not now:
            _fail("this budget has no readable clock, so its window cannot be closed")
        days = _days_between(str(self.opened_at), now)
        if days is None or days < int(self.open_days):
            _fail("the budget is open for " + str(int(self.open_days)) + " day(s) and "
                  + str(days if days is not None else 0) + " have passed")
        amount = self.pool
        self.pool = gl.u256(0)
        gl.contract.get_at(self.buyer).emit_transfer(value=amount)
        return json.dumps({"ok": True, "returned": str(int(amount)), "to": self.buyer.as_hex})

    # -------------------------------------------------------------------- views

    @gl.public.view
    def would_pay(self, response_id: str) -> str:
        """What `pay` will do, readable for free before anybody signs."""
        decision = self._decision(str(response_id))
        if decision["do"] == "yes":
            return "author " + str(decision.get("to", "")) + ": " + str(decision["why"])
        return "nobody: " + str(decision["why"])

    @gl.public.view
    def status(self) -> str:
        return json.dumps({
            "register": self.register.as_hex,
            "subject": str(self.subject_id),
            "subject_owner": self.subject_owner.as_hex,
            "buyer": self.buyer.as_hex,
            "rate": str(int(self.rate)),
            "opened_at": str(self.opened_at),
            "open_days": int(self.open_days),
            "pool": str(int(self.pool)),
            "paid_total": str(int(self.paid_total)),
            "paid": [str(i) for i in self.paid_ids],
        })
