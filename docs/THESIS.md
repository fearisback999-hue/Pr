# Part 0 — The honest operating thesis

> Read this before anything else. It shapes every decision in the codebase. These
> five truths are encoded directly into how the engine is built — where it stops,
> what it refuses to promise, and which knobs it exposes.

### 1. A winner is a signal caught in time, not a thing you find.
The repeatable edge is **detecting steep sales acceleration while competition is still
low**, then moving before the window closes. Catching the wave early beats finding a
"perfect" product late.
→ *In code:* `detection/` computes momentum **and** a saturation index, and always
emits a `window_days` runway estimate. The trigger fires on *high momentum + low-but-rising
saturation*, never on raw sales.

### 2. The product is ~30% of the outcome.
Creative volume, the offer, fulfillment speed, and distribution are the other 70%. A
system that stops at "here's a product" is a fraction of the job.
→ *In code:* the pipeline does not stop at a score. It assembles an **attack packet** —
economics + offer math, psychology spine, supplier scoring, a full creative kit, and a
distribution plan.

### 3. No system predicts. It shifts odds and compresses time.
Every "winning product" dataset is survivorship-biased and lagging. Most products you
test will lose money. The model is: **test many, most fail, a few winners pay for all
the failures.** This is structural, not a flaw to engineer away.
→ *In code:* the engine ranks and times opportunities; it never claims certainty.
`reports/` states odds and runway, not guarantees.

### 4. The data is rented, so it is not your moat.
Anyone can buy Kalodata and Higgsfield. Your durable advantages are **detection speed,
creative throughput, fast fulfillment, and a scoring model tuned to your own results.**
→ *In code:* `feeds/` are swappable adapters (the rented part). The moat lives in
`feedback/` — recalibrating the Part-3 weights to what actually predicted *your* winners.

### 5. This will not make you rich by itself.
What it reliably produces is a **skill and an asset**: data pipelines, AI orchestration,
real ecommerce economics, and a repeatable system. The profitable store is the upside on
top of that, not the guaranteed outcome. **Build for the asset, treat the windfall as a
bonus.**

---

## The builder's trap (Part 12 — read twice)

Building the machine is the comfortable, fun, technical part. Talking to customers,
eating losing tests, doing creator outreach, handling a refund — that is the
uncomfortable part, and it is where the actual learning and money are. **Do not spend
all your time perfecting the engine and never running the store.** The engine feels like
progress while it quietly lets you avoid the part that teaches you the business.

## Iron rule of automation

Never automate anything you have not run manually first. Automation scales whatever
process you feed it, including your mistakes, and you cannot debug a process you never
learned. The CLI is built so you can run each stage by hand before trusting the cron.
