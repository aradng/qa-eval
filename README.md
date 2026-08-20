# QA Engineering Exercise — notional totals service

A working service is in this repo. **You are not building it. You are testing
it.**

Six phases, in order, each adding requirements to the same codebase. Read the
setup below, run the smoke tests, then start at phase 1.

## Setup

```bash
./setup.sh
```

That builds and starts Postgres, Redis and Redpanda in one compose stack,
creates the schema, installs a local virtualenv, and runs the phase 0 smoke
tests. It needs Docker and [uv](https://docs.astral.sh/uv/).

| | |
|---|---|
| service | http://localhost:58000/docs |
| Postgres | `postgresql://qa:qa@localhost:55432/qa` |
| Redis | `redis://localhost:56379/0` |
| Kafka | `localhost:59092` |
| schema registry | http://localhost:58081 |

```bash
.venv/bin/pytest -m phase0        # run one phase
docker compose logs -f app        # service logs
docker compose down -v && ./setup.sh   # start clean
```

Host ports are deliberately unusual so the stack does not collide with anything
else you run.

## What the service does

Trades live in Postgres. A change-data-capture connector reads the write-ahead
log and emits one event per changed row — there is **no producer application**,
so the event shape is derived from the table's DDL by the connector and nothing
in this repo declares it.

`app/consumer.py` reads those events in batches and maintains a running notional
total per product: in Postgres, and mirrored into Redis for fast reads.
`app/api.py` serves those totals and accepts queries over them.
`app/freeze.py` seals trade PnL on a schedule.

Read those three files before you start. Comments in them describe behaviour you
cannot see from the code alone — when the transaction commits, what a raised
exception does to message delivery. Those comments are accurate.

| File | What it holds |
|---|---|
| `app/consumer.py` | the event handler, the totals upsert, the cache mirror |
| `app/api.py` | totals endpoint, query endpoint, served JSON Schema |
| `app/freeze.py` | edit windows, the sweep, the sweep lock |
| `app/db.py` | session and transaction lifetime, the after-commit hook |
| `app/cache.py` | Redis access, optimistic concurrency, conflict |
| `app/schemas.py` | the query model and the schema served to clients |
| `app/config.py` | the feature flags |
| `migrations/` | four migrations, none applied by default |

## Ground rules

- **Do not change the system to make your tests pass.** If you do change its
  behaviour — reorder two calls, add a lock, make a write idempotent — expect to
  be asked why, and have a test that shows the difference it makes.
- You may add **test seams** to the system code (an injection point, a hook you
  can patch) where you need one. Say what you added.
- **Real infrastructure, not mocks.** Postgres and Redis are running; use them.
  Most of what the later phases ask you to characterise *is* store behaviour —
  transaction rollback, commit visibility, optimistic-concurrency conflicts. Mock
  the store and you are testing your mock's version of those semantics, so any
  conclusion you draw is about your fake.
  The exception is **message delivery**: phase 2 needs faults injected on demand
  and deterministically, and no real broker gives you that. Simulate delivery;
  keep everything it talks to real. The principle, and we will ask you to state
  it: **fake only what you need to control.**
- **Feature flags arm faults.** With every flag off, the service is correct as
  far as we know, and the suite is green. Each flag turns on **one real fault at
  runtime** — nothing crashes, nothing logs a warning, the wrong number simply
  appears. Your job is a test that catches it.
  Each phase names the flag it is about. For that flag, your suite must be
  **green in both states**: passing normally when the fault is disarmed, and
  passing *because the catching test is an expected failure* when it is armed.
  `tests/test_demo_flag.py` works the pattern through on a throwaway fault so
  you are not guessing at the shape. `./bin/ci` runs the configurations; add
  yours to it as you go.
- **Budget: 8 hours, hard stop.** Estimates are guidance. Most candidates reach
  phase 3; 4 and 5 are stretch. Stop at the cap, and tell us which phase you
  stopped in and what you would have done next. Three phases done well beats six
  done thinly.
- Commit per phase if you can. You will walk us through it live, 60–90 minutes.
- Using an AI assistant is allowed and expected.

### The flags

All default to off. None of them changes an error path — each changes behaviour,
and the consequence shows up as a wrong value somewhere.

| Flag | What turning it on changes | Phase |
|---|---|---|
| `SCHEMA_DOC_MODE` | the served query schema switches to the serialization view, the one you would publish to document responses | 1 |
| `SKIP_BEFORE_IMAGE` | the consumer ignores the `before` image, treating every event as an insert | 2 |
| `MIRROR_AFTER_COMMIT` | the cache mirror runs after the transaction commits instead of before | 2 |
| `CACHE_INCR` | the mirror increments the cached value instead of overwriting it with the recomputed total | 3 |
| `SEAL_ON_CLOCK` | a closed window counts as sealed without waiting for the sweep to record it | 5 |
| `DEMO_HEALTH_BUG` | not one of the faults you are looking for — the worked example in `tests/test_demo_flag.py` | — |

Two of them belong to phase 2.

---

## Phase 0 — make sure it runs

Already written, in `tests/test_smoke.py`. Run it. If it passes, the stack is
healthy and you can start.

## Phase 1 — the contract boundary

**~2h.**

A frontend validates user input against `GET /total/query/schema` before POSTing
to `/total/query`. So the schema is a promise: **anything it accepts, the POST
must accept.**

- Show whether the service keeps that promise. Your evidence has to come from
  the schema the service actually serves, not from your reading of the models.
- Anywhere it does not, say who is wrong: the schema or the endpoint.
- Whatever you build has to be able to live in CI and stay useful there.

**Flag: `SCHEMA_DOC_MODE`.** Disarmed, the promise holds. Armed, it does not.
Your harness must catch the violation in the armed configuration and report
nothing in the disarmed one, and `./bin/ci` must be green either way. Skipping
the armed configuration does not count.

## Phase 2 — delivery faults

**~3h.**

The consumer runs under at-least-once delivery.

At-least-once means a message can arrive more than once, and can arrive again
after the handler has already done some of its work.

- **Characterise what the system guarantees.** Can Postgres and Redis be made to
  agree atomically? If not, what is the strongest property that does hold, and
  for how long can a reader of `/total/{product}` see a wrong number?
- List the ways delivery can go wrong, and for each, say whether *this* system
  can actually experience it. The ones you rule out matter as much as the ones
  you keep — we will ask you why.
- **Every weakness you claim has to be reproducible on demand.** Two runs, same
  result, no retries and no waiting for luck. A weakness you can trigger counts;
  one you assert does not.

How you get delivery under your control is your problem to solve, and the
solution is part of what we are assessing.

**Flags: `SKIP_BEFORE_IMAGE` and `MIRROR_AFTER_COMMIT`.** Answer all of the above
for each, armed and disarmed. One of them is much easier to catch than the other.

Do not assume a flag's consequence from its description. Both of these do
something the one-line summary does not tell you.

## Phase 3 — concurrency

**~2h.**

Two consumers process events for the same product at the same time.

- Show what happens when their reads and writes interleave.
- Whatever you find has to be **reproducible on demand** — a named interleaving
  you can trigger twice and get the same answer, not a race you happened to hit
  under load. Getting there without giving up the real stores is the interesting
  part of this phase.
- Say what your phase 2 conclusions look like now. If any no longer hold, say
  which.

**Flag: `CACHE_INCR`.** This one interacts with `MIRROR_AFTER_COMMIT` — cover all
four combinations of the two, and say what each one buys and costs. This is the
only place in the exercise where a full cross-product is expected.

## Phase 4 — schema evolution

**~3h.** Stretch.

The table changes. Nothing in this repo declares the event contract, so a
migration is the only artifact you have. Four are waiting in `migrations/`, none
applied.

- A schema registry is the source of truth for the event contract. One is running
  at http://localhost:58081.
- A CI check fails the build when a migration changes the emitted event in a way
  that breaks the consumer.
- Tests proving the check passes and fails for the right reasons.
- Report what your check compares against what, and what it cannot see.
- A verdict per migration, asserted by your tests:
    - **M1** — add `broker text null`.
    - **M2** — drop `side`; direction is now implied by the sign of `volume`.
    - **M3** — widen `volume` to `numeric(18,6)`.
    - **M4** — data only: rescale `volume` from barrels to metric tons and
      `price` from `$/bbl` to `$/mt`. No DDL changes.
- Some of these will break tests you wrote in phases 0 and 2. Fix them, and be
  ready to explain what you changed and why it was necessary.

Run this phase in the **default flag configuration only.** You do not need the
migration set crossed with the flag matrix.

## Phase 5 — time and sealing

**~3h.** Stretch. Expect to leave things unfinished.

Trade PnL is recomputed on every price edit until a sweep seals it. Once sealed,
the recorded PnL never changes again. `now()` in `app/freeze.py` is the only clock
the service reads.

The rules are: a trade is editable, editable-by-supervisor-only, or not
editable, depending on how old it is; and sealed or not, depending on whether a
sweep has reached it. Those two things move independently.

- Show that the rules hold for **any order of events**, not only the orders you
  thought to write down. Price edits, sweeps and the passage of time can happen
  in any sequence.
- If you find an order that breaks them, reduce it to the shortest one that
  still does.
- Say what you did **not** cover.

**Flag: `SEAL_ON_CLOCK`.** Run the model against both states. The model should be
parameterised by configuration, not forked into two models.

### And finally

Four flags is sixteen configurations, and you should not be running sixteen.
**State which configurations your suite actually runs, and why the rest are not
worth the time.** An argument that two flags do not interact is a fine reason to
skip their cross-product — be ready to defend it.

---

Out of scope throughout: real deployment, more than one table, consumer rebalance
and partition-assignment simulation, multi-process coordination, auth beyond a
role string, notifications, frontend code. Fixing what you find is not required —
reporting it is.
