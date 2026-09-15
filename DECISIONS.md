# Decisions

The things a reader would otherwise have to guess at, and what is measured rather than assumed.

## The boundary

| owner | what it owns |
|---|---|
| a caller | the words of a subject and the words of a response; nothing else |
| this contract | the decoy, both presentation orders, the closed answer set, the retest rule, the tag vocabulary, and every state change |
| the validators | two forced choices, run independently, on texts they can both read |
| a consumer | the money, bound to an address it knew before the register was consulted |

## Why a forced choice instead of a score

"Is this review good?" has no answer two strangers reliably share, and a contract that stores
one has stored a mood. "Which of these two things is this about?" has an answer that a specific
text forces and a generic text cannot force. The question was chosen because it is the one that
settles, not because it is the one a buyer would ask first.

It also means the contract never claims quality. `specific` says the work could not have been
about the nearest other subject on the register. That is a smaller claim than "this is good",
and it is one the chain can actually support.

## Why the decoy is the nearest neighbour

Any decoy makes a test; the nearest one makes a test worth passing. Told apart from a stranger,
almost anything passes. Told apart from the subject sharing every tag, only work that engaged
with something particular survives. Ties go to the earliest subject so the decoy is stable: a
later arrival cannot quietly change the test an old verdict was based on.

## Why a retest needs a strictly harder decoy

Models are not deterministic, so "ask again" is a lottery ticket. Tying the retest to a
*harder* decoy means the only way to re-open a verdict is for the register itself to have grown
a closer neighbour, which is new information, not a new roll. It also makes the standard
monotonic: on a register that grows, `specific` can only ever get harder to earn.

## Why the letter-hijack defeats itself

The two runs swap which subject is called A, so a response that demands the letter `a` points at
the real subject one way round and at the decoy the other. The outcome table turns a same-letter
pair into `unclear`. This is not a filter and it is not a list of forbidden phrases: the shape of
the question does the work, and a text that tries to steer it cannot steer both runs the same way.

Fencing still happens, by replacement rather than deletion, because a forged delimiter would be a
different attack: closing the block early rather than commanding the answer.

## Why the vocabulary is fixed in the constructor

Tags decide which decoy a response must beat. A vocabulary somebody could extend later is a
difficulty setting somebody could lower later: add a tag nobody else uses, and your subject's
nearest neighbour becomes a stranger. Fixing it in public, before any work exists, is what makes
`shared_tags` on a row mean something a year later.

## Why `test` is open to anybody

The caller chooses nothing: not the decoy, not the order, not whether a retest is allowed. An
author should not have to wait for a buyer to press it, and a buyer should not have to trust an
author to. What is not open is being paid, and that waits for the verdict.

## Why the reason is not agreed on

Two validators write different sentences about the same forced choice, and requiring them to
match would make every round fail. The stored sentence is the leader's, and the README and the
views say so. The word the contract acts on is agreed by every validator.

## Why the budget is a separate contract

The register answers a question; the budget obeys the answer. Keeping them apart means the
register can be read by anything, and the whole settlement rule fits on one page. It also keeps
the register free of value, so no judgement can move money by accident.

## Measured on GenLayer Studio Next (chain 61997, consensus v0.6), 16 September 2026

- The whole story runs: three subjects, and four responses about the same one, judged as
  specific, generic, unclear (the letter hijack) and misfiled.
- Every round settled with **3 validators agreeing**.
- Deterministic refusals land on chain with their reason. A call the contract refuses cannot be
  simulated, so `estimateTransactionFeesForWrite` fails and the default quote of about 0.1 GEN is
  used, most of it refunded; the refusal itself is unaffected. Judged writes quote about 0.0006 GEN.
- `genvm-lint check` passes its three checks on both files. Its SDK validation step cannot load
  the v0.6 runner (`5jycge4q…`) in version 0.11.0; that is the linter, not the contract.

## Not verified

- Value transfers emitted by a contract are **recorded but not executed** on Studio Next at the
  time of writing: the budget's decisions are exercised in the offline suite and its `would_pay`
  on chain, but the coins do not move on this network. The payment rule is small and readable for
  exactly that reason.
- Nothing here has been run on a production GenLayer network.
