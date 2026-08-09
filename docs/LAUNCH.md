# Launch — the first 30 days on $2,000

The playbook (`playbook`) lists all 47 steps grouped by topic. This document
puts them in **time order**, with the money attached, for a solo operator
starting today. Follow it top to bottom. Check steps off as you go:

    python -m tt_engine.cli playbook              # where am I
    python -m tt_engine.cli playbook-check <id>   # mark one done

---

## The money: how $2,000 splits

Sized with `capital` until it returns **zero warnings**. This is the envelope:

    capital --capital 2000 --test-budget 150 --daily-ad 15 --daily-cogs 7
    → payout float $308 · deployable $1,392 · 9 concurrent tests · runway 3.0mo

| Bucket | Amount | Rule |
|---|---:|---|
| Reserve | $300 | Never spent. It is what makes month 2 exist. |
| Payout float | $310 | Cash in transit — TikTok holds payouts ~14 days. Not spendable. |
| Tools (month 1) | $150 | Market data + generation subscriptions. |
| Samples | $60 | 3 products × ~$20. Mandatory, see Rule 3. |
| **Product tests** | **$1,180** | **~7 tests at $150.** This is the only money that buys information. |

**Test budget is $150, not $250.** At $250/test the same $2,000 drops to a
1.5-month runway and `capital` throws warnings. $150 × more shots beats
$250 × fewer shots, because you are buying *attempts*, not outcomes.

**Do not raise daily ad spend above ~$15/day during testing.** That single
number is what holds the runway at 3 months. Scale spend comes out of a
winner's revenue, never out of the loan.

---

## Five rules that do not bend

1. **The 48-hour kill timer wins every argument.** Below break-even for 48
   straight hours is KILL, even when you feel it turning. `validate` makes
   the call; you execute it.
2. **No landed cost, no score.** The engine refuses to score economics on a
   guessed supplier cost, and so should you.
3. **Hold the product before you fund it.** Order the sample. Photos lie.
   A quality problem found by a customer costs a refund spiral; found by you
   it costs $20.
4. **Log spend and revenue every single day a test runs.** Skipping one day
   breaks the consecutive-day math the kill timer depends on.
5. **AIGC disclosure on everything.** Non-negotiable. `export-creatives`
   blocks any asset missing it, on purpose.

---

## Day 1 — today. Cost: $0

Everything today is paperwork and long-lead applications. Start the slow
things first so they cook while you work.

- [ ] **Deposit the $2,000 into a dedicated business bank account.** Not
      personal. Every dollar in and out goes through this one account.
      → `playbook-check biz-bank`
- [ ] **Get an EIN** — free, instant, IRS.gov, ~15 minutes. Never pay a
      third party for this. Do it in one sitting; the session times out.
      → `biz-ein`
- [ ] **Decide the structure** — sole prop is fastest; LLC separates
      personal assets. Most start sole prop and form the LLC when revenue is
      real. → `biz-structure`
- [ ] **Apply for TikTok Shop Seller** — *this is the long pole, 1–3
      business days*. Have ready: 18+, US address, a fresh email/phone not
      used on another account, government ID, proof of address, bank + tax
      details that all match. → `tt-seller`
- [ ] **Create a TikTok Ads Manager account** (separate login from Seller
      Center). → `ads-account`
- [ ] **Open a supplier-platform account** — CJ Dropshipping, Zendrop, or
      AutoDS. Free to join. → `sup-account`
- [ ] **Start a bookkeeping sheet.** Today, before the first transaction.
      → `biz-books`

Read tonight, while approvals process: `tt-restricted` (what you may never
sell) and `tt-ai-disclosure` (the labeling rule). Fifteen minutes each, and
they are the two rules that most commonly kill a new shop.

---

## Days 2–4 — find candidates. Cost: ~$40 (data)

This is the highest-leverage work in the whole month. A great product with
mediocre creative beats great creative on a bad product, every time.

- [ ] **Get real market data in.** Subscribe to a data source and import,
      or scout by hand for free.
      `import-csv exports/kalodata.csv --source kalodata` → `data-in`
- [ ] **Learn where to look:** `scout`, `ideas`, and `organic` cover the
      free surfaces and the four lanes that actually sell.
- [ ] **Rank what you found:** `daily` then `find --top 5`.
- [ ] **Pull scorecards** on anything close to the bar: `scorecard <id>`.
- [ ] **Choose exactly 3 candidates.** Not one — a single bet has no
      information value. Not ten — you cannot source or film ten.
      → `first-test-verdict`

Momentum needs a multi-day series. One day of data tells you nothing.

---

## Days 3–7 — sourcing and samples. Cost: ~$60

Start this the moment you have candidates. Samples ship slowly and they
gate everything downstream.

- [ ] **Get a real landed-cost quote** from the supplier for each of the 3.
      Unit cost + shipping cost, actual numbers.
      `add-supplier <id> --cost X --ship-cost Y` → `sup-real-quote`
- [ ] **Order all 3 samples today.** They take 5–10 days. Ordering them
      late is the single most common way this timeline slips a week.
      → `sup-sample`
- [ ] **Check supplier shipping** against the SLA: tracking to "In Transit"
      within 2 business days, "Delivered" within 6. Run
      `health --ship-days 4 --refund-rate 0.03` to see the throttle risk
      before it happens. → `tt-shipping`
- [ ] **Confirm carrier compliance** if shipping cross-border — TikTok
      requires a whitelisted carrier.

`sourcing-guide` lists US-warehouse and fast-shipping suppliers; shipping
time is 25% of the supplier score for a reason.

---

## Days 5–10 — build creative while samples ship. Cost: ~$110 (tools)

Free until the moment you type `--confirm`. Use that.

- [ ] **Run the psychology pass** on real comments/reviews for your top
      candidate: `psych <id> --file comments.txt` → `psych-run`
- [ ] **Pick your actor** from the roster: `personas`, or the Actors tab in
      `serve`. One face per account. → `soul-id`
- [ ] **Wire generation** — `HIGGSFIELD_API_KEY` + `HF_KEY` in `.env`, and
      `pip install higgsfield-client`. Until this is set, everything
      dry-runs (which is the safe default, not a failure).
      → `higgsfield-configure`
- [ ] **Draft the specs, then read them before you spend.**
      `draft new <product> --actor <slug>` → `draft show <id>` → edit the
      prompt/actor/product parts independently → approve.
      This step exists so you fix mistakes for free instead of at credit
      cost. → `creative-plan`
- [ ] **Generate only after the draft reads right:** `creative <id> --confirm`.
      Expect roughly **1 usable clip in 4** — that ratio is normal and it is
      already priced into the plan. → `creative-generate`
- [ ] **Export with disclosure intact:** `export-creatives <id>`.
      → `creative-export`
- [ ] **Run the phone test** on every clip: `authenticity`. Watch it at arm's
      length, muted, at full speed, the way a real viewer will. If anything
      makes you look twice, cut it — do not "fix" it.

If faces are not landing, drop a rung on the ladder rather than shipping
something uncanny: `shot-mode face_light`, or `shot-mode faceless` for
chest-down / hands / POV with voiceover. A clean faceless video outperforms
an almost-right face every time.

---

## Days 10–12 — samples arrive. This is a real gate.

- [ ] **Hold each product.** Quality, fit, function, packaging. Does it do
      the thing the video is about to claim it does?
- [ ] **Kill anything that disappoints you in your hands, right now**, before
      any ad money. This costs $20 and saves $150 plus a refund spiral.
- [ ] **Film your own footage with the real product** where you can — real
      hands on a real object is the cheapest realism you will ever buy.
- [ ] **Create the live listing** — title, price, images, description. Every
      claim run through the compliance guardrail: no medical or absolute
      claims. AI-generated backgrounds need disclosure too. → `listing-live`
- [ ] **Set price from the margin floor**, not vibes — your scorecard already
      shows break-even ROAS and max allowable CAC. → `offer-set`
- [ ] **Set your affiliate commission** — Open Collaboration typically
      10–15%, targeted 18–25%. Locked for 30 days once a creator picks it up.
      → `affiliate-rate`

---

## Days 12–20 — the first test. Cost: $150 per product

- [ ] **Verify the Pixel and Events API are both firing** before spending a
      dollar. Wrong tracking means every kill/scale decision downstream is
      measuring the wrong thing. Aim for Event Match Quality 6+.
      → `ads-pixel`
- [ ] **Launch small and spread**: a few hooks and creators at small per-ad-set
      budgets, not one big bet on one video. → `ads-launch`
- [ ] **Watch the funnel in order**: 3-second view rate → CTR → add-to-cart
      → ROAS. A break early in that chain is a creative problem; a break at
      the end is an offer or price problem. They have different fixes.
- [ ] **Log it daily, without exception**:
      `log-test <id> --spend X --revenue Y` → `log-daily`
- [ ] **At 48 hours, let the engine decide**:
      `validate <id>` then `log-result <id> --decision kill|scale`
      → `decide`

A killed test loses about $120, not the full $150 — the timer is what caps
it. Killing fast is not failure; it is the mechanism working.

---

## Days 20–30 — iterate, then compound

- [ ] **Kill → next candidate.** Same loop, product #2 and #3. You budgeted
      ~7 tests. Use them methodically, one at a time.
- [ ] **Scale → raise 20–30% at a time**, re-running `validate` after each
      raise. A SCALE verdict is not a blank check. → `scale-steps`
- [ ] **Diversify creative before scaling hard** — a single-creative scale
      dies to fatigue fast. → `scale-angles`
- [ ] **Confirm the supplier can carry the volume** before you buy it.
      → `scale-supply`
- [ ] **Open collaboration / invite creators** on anything working.
      → `creator-outreach`
- [ ] **Reconcile payouts against your books** and set aside a tax reserve
      from every payout. → `recon-monthly`, `tax-reserve`
- [ ] **Run `report-monthly`** — which sub-scores actually predicted your
      winners. Suggestions only; you approve any change.

---

## What month one is actually for

Expected value for month one is **negative by design** (`month-one` shows
about −$385 at this size). You are not buying profit. You are buying:

- real landed costs and real conversion data on 3 real products
- a working shop, ads account, pixel, supplier pipeline, and creative loop
- reps at the one skill that compounds — killing losers fast
- an **option on a winner**, which is where all the money actually is

Most first tests lose. That is the base rate, not a personal verdict.

---

## The ladder to $100k months

`scale` itemizes the $100k month honestly: ~74 orders/day at $45 AOV, ~3
concurrent winners, ~$20k/mo in ads, 60+ active affiliates, ~30 videos/week
— and **$41,783 of working capital to run that month**.

That number is the point. $2,000 does not buy a $100k month; it buys the
first rung. The ladder is:

1. **Month 1** — $2,000 finds a product that clears break-even. Expect to
   lose a few hundred dollars learning which one.
2. **Months 2–3** — reinvest the winner's profit into scaling *that*
   product. This is where the first real money appears.
3. **Months 4+** — a portfolio of ~3 winners with $25k+ ceilings each,
   funded by retained profit, not by the loan.

Each rung is funded by the one below it. Skipping a rung by borrowing more
is how this goes badly. The loan gets you onto rung one — that is its whole
job, and it is enough for that job.

---

## When you are stuck

    python -m tt_engine.cli playbook          # where am I, what's next
    python -m tt_engine.cli autopilot preflight # what's blocking me
    python -m tt_engine.cli serve             # everything on one dashboard
    python -m tt_engine.cli ask "..."         # ask the engine directly
