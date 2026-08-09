"""How to actually DO every playbook step.

`playbook.py` says what each step is and why it matters. This says what to click,
what to type, and how you know you're done — the gap between "register the business"
and knowing which of six tabs to open.

Kept separate from the step definitions on purpose: instructions change when a
platform moves a button, the steps themselves rarely do. A test asserts every step
id here has instructions and every id has a step, so the two can never drift apart.

Legal/tax items describe what to go figure out, not what to do — requirements vary
by country, state, and situation. Verify with a licensed professional.
"""

from __future__ import annotations

DONE_WHEN = "done when"

# step_id -> (ordered instructions, "you are done when …")
HOW_TO: dict[str, tuple[tuple[str, ...], str]] = {

    # ── 0. Business foundation ────────────────────────────────────────────────
    "biz-structure": ((
        "Decide between sole proprietorship (no filing, no fee, you ARE the business) "
        "and an LLC (a filing fee, an annual report, and a legal wall between the "
        "business's debts and your personal assets).",
        "If you go LLC: search '<your state> secretary of state business filing', file "
        "the Articles of Organization on the state's own site, and pay the state fee "
        "directly. Skip the ad-funded middlemen charging $300 to submit a $100 form.",
        "Most people start sole prop and convert once revenue is real. Converting later "
        "is normal and not expensive.",
        "If returns, chargebacks, or product-liability worry you at all, spend 10 "
        "minutes with an accountant before deciding. That conversation is cheap.",
    ), "you can state, in one sentence, what your business structure is."),

    "biz-ein": ((
        "Go to IRS.gov and search 'apply for an EIN online'. Use only the irs.gov "
        "domain — every other 'EIN service' charges for something the IRS gives free.",
        "Have ready: your legal name, SSN/ITIN, business name (your own name is fine "
        "for sole prop), address, and what the business does.",
        "Finish it in ONE sitting. The session dies after 15 minutes idle and cannot "
        "be resumed — you start over.",
        "Save the CP 575 confirmation letter as a PDF the moment it appears. You will "
        "be asked for it by the bank and by TikTok.",
    ), "you have a 9-digit EIN and the PDF saved somewhere you can find it."),

    "biz-bank": ((
        "Open a business checking account. Any bank with no monthly fee and a decent "
        "app is fine — this is a plumbing decision, not a strategic one.",
        "Bring: EIN letter, ID, and your LLC formation docs if you formed one.",
        "Deposit the entire starting capital into it. Nothing business-related ever "
        "touches your personal account again — not one ad charge, not one sample.",
        "Get the debit card and put it on the ad account and supplier account, so "
        "spend flows through one place you can actually audit.",
    ), "your capital sits in an account that holds nothing but business money."),

    "biz-tax-reg": ((
        "Understand the concept first: economic nexus means once you cross a state's "
        "sales threshold, that state expects you to register and remit sales tax.",
        "Check whether TikTok Shop acts as a marketplace facilitator for your states — "
        "it collects and remits on your behalf in many, which covers a lot but not "
        "automatically all of your obligations.",
        "Register in your HOME state first if required; that is the one you will "
        "almost certainly trip.",
        "This is the single most worthwhile hour of professional advice you can buy "
        "early. Ask an accountant what YOUR obligations are, not the internet.",
    ), "you know which states you owe anything in, and who is collecting it."),

    "biz-books": ((
        "Pick one: a spreadsheet with date / description / category / amount, or a "
        "tool like Wave (free) or QuickBooks. Either works. Starting is what matters.",
        "Create the categories now: ad spend, COGS, samples, tools/subscriptions, "
        "platform fees, revenue.",
        "Log every transaction the same week it happens. Not the same month.",
        "The engine's `capital` gives you cash-flow math — that is decision support, "
        "not bookkeeping. You still need the ledger.",
    ), "every dollar so far is recorded, and you could hand it to an accountant today."),

    # ── 1. Platform accounts ──────────────────────────────────────────────────
    "tt-seller": ((
        "Go to seller-us.tiktok.com and register. Use an email and phone NOT already "
        "attached to another TikTok Shop account.",
        "Prepare, as clean uncropped files under 10MB (JPG/PNG/PDF): government ID "
        "(passport, driver's license, state ID, or green card), proof of address "
        "(utility bill or bank statement), EIN or SSN, and bank details.",
        "Every name and address must match across all documents. A mismatched middle "
        "initial is a genuine, common rejection cause.",
        "Submit and wait 1–3 business days. Do not submit a second application while "
        "the first is pending — that reads as duplicate-account behaviour.",
        "If rejected, read the stated reason and fix exactly that. It is usually one "
        "document, not a judgment on you.",
    ), "your Seller Center dashboard opens without a verification banner."),

    "tt-payout": ((
        "In Seller Center → Finance → Bank Account, add the SAME business account "
        "from `biz-bank`.",
        "Verify it (usually micro-deposits, 1–2 days) so the first payout is not held.",
        "Confirm the payout schedule shown, so you know the real lag between a sale "
        "and cash — that lag is exactly what the payout float in `capital` covers.",
    ), "Seller Center shows a verified payout account, not a pending one."),

    "tt-shipping": ((
        "Seller Center → Settings → Shipping. Set your handling time honestly — "
        "promising 1 day and shipping in 3 damages you far more than promising 3.",
        "Set the return window (30 days is the common default).",
        "Learn the two clocks now: you get 2 business days to approve/deny a return "
        "under $100, 4 days for $100+, and a missed window auto-approves the refund. "
        "Cancellations must be refunded within 5 calendar days.",
        "Run `health --ship-days 4 --refund-rate 0.03` to see how ship time and refunds "
        "translate into account-health throttling before it happens to you.",
    ), "your handling time matches what your supplier can genuinely do."),

    "tt-restricted": ((
        "Open TikTok Shop's prohibited and restricted products policy and read it "
        "once, properly. Fifteen minutes.",
        "Note the two tiers: PROHIBITED (never sellable — weapons, drugs, alcohol, "
        "vape, most animal products, recalled goods) and RESTRICTED (sellable only "
        "with prior approval).",
        "Write down the categories you were considering that appear on either list. "
        "Cross them off your candidate pool now, before you source a sample.",
        "Re-check before each new category. This policy changes.",
    ), "you can name the restricted categories relevant to your niche from memory."),

    "tt-ai-disclosure": ((
        "Learn the line: content that is fully AI-generated or substantially "
        "AI-altered (changed background, added synthetic element, altered appearance) "
        "must be labeled. Colour grading and cropping do not count.",
        "Critical and widely missed: an AI-generated BACKGROUND behind a real product "
        "photo in a Shop listing still needs disclosure.",
        "For paid ads, tick the 'AI Disclosure' box in Ads Manager at creation time.",
        "The engine enforces this on its side — `export-creatives` refuses any asset "
        "missing the disclosure in its metadata. Do not try to route around that.",
    ), "you would label your own content correctly without looking anything up."),

    # ── 2. Capital ────────────────────────────────────────────────────────────
    "cap-plan": ((
        "Run `capital --capital <your real number> --test-budget 150 --daily-ad 15 "
        "--daily-cogs 7`.",
        "Read the warnings, not just the headline. Fewer than 3 concurrent tests or "
        "under 3 months runway means the plan is too thin to survive the losing tests "
        "that pay for a winner.",
        "Adjust the INPUTS until the warnings clear — that is your real operating "
        "envelope. Do not adjust your interpretation until the warnings feel fine.",
        "Remember the take rate is not 6%. Add ~1–3.8% payment processing and any "
        "affiliate commission on top.",
    ), "`capital` runs clean with no warnings at numbers you can actually afford."),

    "cap-per-test": ((
        "Pick your per-product test budget BEFORE you look at a specific product. "
        "$150 is the number the $2k plan is built on.",
        "Write it down somewhere you will see it while spending.",
        "The rule that makes it real: when the 48h timer says kill, you kill, even at "
        "$40 spent, even at $150 spent, even when it feels like it is about to turn.",
    ), "you have a number, and it was chosen before any product was in mind."),

    # ── 3. Supplier setup ─────────────────────────────────────────────────────
    "sup-account": ((
        "Pick one to start: CJ Dropshipping (free, strongest supply-chain support), "
        "Zendrop (easiest fulfillment, automation behind paid tiers), or AutoDS "
        "(largest catalog, strongest automation, flat pricing).",
        "Register and connect it to your TikTok Shop through the platform's own "
        "official integration.",
        "Check the shipping origin. US-warehouse inventory ships in days; China-direct "
        "ships in weeks and will fail the SLA.",
        "If shipping cross-border, confirm the carrier is on TikTok's whitelist — an "
        "off-list carrier is a compliance problem, not just a slow one.",
        "See `sourcing-guide` for the US-warehouse and fast-handling options.",
    ), "you can search the catalog and see real per-unit costs with your account."),

    "sup-real-quote": ((
        "Message the supplier or read the product page for the ACTUAL unit cost and "
        "the ACTUAL shipping cost to your customer's country.",
        "Run `add-supplier <product_id> --cost X --ship-cost Y` with those real "
        "numbers.",
        "Never enter a placeholder. The engine refuses to score economics without a "
        "real landed cost, and that refusal is the feature — a guessed cost produces "
        "a confident, wrong margin.",
        "Get quotes for all three candidates before deciding between them.",
    ), "`scorecard <id>` shows margin, break-even ROAS, and max CAC instead of a gate."),

    "sup-auto-fulfill": ((
        "Connect fulfillment through the supplier platform's OWN official TikTok Shop "
        "integration (CJ, AutoDS, and Zendrop all have one). You authorize it once, at "
        "connection time.",
        "This engine will never place a supplier order for you — an order-placing bot "
        "is automatic spending, which is the one thing it refuses to do.",
        "Place the first 3–5 orders while watching the integration work. Confirm "
        "tracking numbers actually sync back to TikTok.",
        "Only then let it run unattended, and reconcile against payouts monthly.",
    ), "an order you placed flowed to the supplier and its tracking synced back."),

    "sup-sample": ((
        "Order one of every candidate to your own address. Pay for it. This is the "
        "$20 that protects the $150.",
        "When it arrives: check build quality, the fit or function, the packaging, and "
        "whether it does the thing your ad is about to claim.",
        "Film your own real footage while you have it in hand — real hands on a real "
        "object is the cheapest realism available to you.",
        "Kill anything that disappoints you. Your disappointment is a preview of the "
        "refund rate.",
    ), "you have physically held every product you are about to spend ad money on."),

    # ── 4. Find a product ─────────────────────────────────────────────────────
    "data-in": ((
        "Either subscribe to a data source and export a CSV, or scout by hand for "
        "free — `scout` lists the free surfaces and how to read them.",
        "Import with `import-csv <file.csv> --source kalodata|fastmoss|generic`.",
        "For a hand-found product: `add --name '...' --category ... --price ...`, then "
        "`add-metric <id> --units ... --price ...` for each day you observe.",
        "Momentum needs a multi-day series. One day of data is noise, and the engine "
        "will tell you so rather than scoring it.",
    ), "`board` shows real products with more than one day of data."),

    "first-test-verdict": ((
        "Run `daily` to score everything, then `find --top 5` for the ranked shortlist.",
        "Run `scorecard <id>` on anything close to the bar. Read every sub-score and "
        "every gate — it is deliberately not a black box.",
        "TEST means the gates cleared AND the score beat the threshold. WATCH means "
        "wait. KILL means move on, and moving on is free.",
        "Pick three TEST-or-close candidates. Not one, not ten.",
    ), "you have three specific products with scorecards you have actually read."),

    # ── 5. Listing & offer ────────────────────────────────────────────────────
    "listing-live": ((
        "In Seller Center → Products → Add Product: title, price, images, video, "
        "description, variants.",
        "Write the title the way a buyer searches, not the way a supplier names it. "
        "'Blue light glasses for screen headaches', not 'TR90 Anti-Blue Radiation'.",
        "Run every claim through the compliance rule: no medical claims, no absolutes, "
        "no invented certifications. TikTok and the FTC both enforce this.",
        "If any image has an AI-generated background, disclose it — this is the most "
        "commonly missed disclosure case.",
    ), "the listing is live, buyable, and you would defend every claim on it."),

    "offer-set": ((
        "Open `scorecard <id>` and find break-even ROAS and max allowable CAC.",
        "Set the price so the margin supports a realistic CAC — if break-even ROAS is "
        "above about 2.5, the price is too low for paid traffic to ever work.",
        "Check the price against what is already selling. Being 20% cheaper is a "
        "strategy; being 60% cheaper reads as fake.",
        "Set the price from those numbers, then stop adjusting it emotionally.",
    ), "your price came from the margin floor and you can explain it in numbers."),

    # ── 6. Psychology & creative ──────────────────────────────────────────────
    "psych-run": ((
        "Collect 20–50 real comments or reviews about this product or its close "
        "competitors. Copy them into a plain text file.",
        "Run `psych <id> --file comments.txt`.",
        "Read the spine it produces — ONE clear trigger, not five vague ones. That "
        "sentence becomes the backbone of every hook and script.",
        "With ANTHROPIC_API_KEY set you get the LLM pass; without it a deterministic "
        "fallback. It always tells you which one you got.",
    ), "you can state the single emotional trigger in one sentence."),

    "soul-id": ((
        "Run `personas` to see the roster. Each actor is a markdown bible: look, "
        "rooms, voice, speech quirks, and their own account.",
        "Pick ONE actor per account and keep them there. Mixing faces on one account "
        "reads as inconsistent to viewers and to the algorithm.",
        "Create a new one with `persona-new <NAME> --account @handle`, then edit the "
        "generated file in docs/persona/.",
        "Set HIGGSFIELD_SOUL_ID in .env to pin the store persona. The engine warns you "
        "if existing creatives disagree.",
    ), "every account has exactly one actor, and you know which."),

    "creative-plan": ((
        "Create a draft: `draft new <product-id> --actor <slug>`.",
        "Read it: `draft show <id>`. Three separately editable parts — ACTOR, PRODUCT, "
        "PROMPT — plus the shot mode, and the assembled preview of exactly what would "
        "be sent.",
        "Edit any single part without disturbing the others: `draft set <id> --prompt "
        "'...'` or `--actor <slug>` or `--mode faceless`.",
        "This entire step is free. Fix everything here, because the next step is where "
        "money moves.",
        "`draft approve <id>` when the preview reads right.",
    ), "the assembled preview says exactly what you want, with nothing to fix."),

    "higgsfield-configure": ((
        "Set HIGGSFIELD_API_KEY and HF_KEY in .env, then `pip install "
        "higgsfield-client`.",
        "BEFORE generating anything, arm the spend guards: TT_GENERATION_UNIT_COST "
        "(your real per-clip cost) and TT_MAX_BATCH_SPEND (a dollar ceiling that "
        "refuses even with --confirm).",
        "Verify with `spend-check` — it shows every guard as armed or unset.",
        "Alternative path: run it from a Claude Code session with the Higgsfield MCP "
        "connected, which authenticates by OAuth and needs no key at all.",
    ), "`spend-check` shows unit cost and ceiling armed, not UNSET."),

    "creative-generate": ((
        "Generate exactly ONE clip first: `draft generate <spec-id> --confirm`.",
        "Check the real charge against what `spend-check` predicted. Only run a full "
        "batch once those two numbers agree.",
        "For a batch: `creative <id> --confirm`. It shows the estimated spend before "
        "it submits anything.",
        "Expect roughly 1 usable clip in 4. That ratio is normal and already priced in "
        "— it is not a sign something is broken.",
        "If a run is interrupted, run `creative-recover` rather than generating again. "
        "Re-generating pays twice for the same clip.",
    ), "you have generated assets and the cost matched the estimate."),

    "creative-export": ((
        "Run `export-creatives <id>`.",
        "Anything missing its AIGC disclosure is BLOCKED, by design. Do not look for a "
        "way around it — that block is what keeps the shop off enforcement radar.",
        "Watch every clip on a phone at arm's length, muted, at full speed. That is "
        "how it will actually be seen.",
        "Cut anything that makes you look twice. Do not try to fix an uncanny clip; "
        "the fix rate is worse than the regeneration rate.",
    ), "you have exported clips you would post under your own name."),

    # ── 7. Paid traffic ───────────────────────────────────────────────────────
    "ads-account": ((
        "Create a TikTok Ads Manager account at ads.tiktok.com — a separate login "
        "from Seller Center.",
        "Complete business verification and add the business payment method (the card "
        "from `biz-bank`).",
        "Set an account-level daily spend cap immediately. This is your last line of "
        "defence against a misconfigured campaign.",
        "Link it to your TikTok Shop so Spark Ads can run against your real posts.",
    ), "the ads account is verified, funded, and has a daily cap set."),

    "ads-pixel": ((
        "Set up BOTH the browser Pixel and the server-side Events API. TikTok's own "
        "docs treat these as two channels, not alternatives — the Events API catches "
        "what ad-blockers and iOS hide.",
        "Fire a test event and confirm it appears in Events Manager.",
        "Check Event Match Quality: below 4 meaningfully hurts optimization. Aim 6+ on "
        "every conversion event and 8+ on your primary one.",
        "Do not spend a dollar until a real purchase event has been observed end to "
        "end. Wrong tracking means every kill/scale call afterwards is measuring the "
        "wrong thing.",
    ), "a real test purchase showed up correctly in Events Manager."),

    "ads-launch": ((
        "Create the campaign with small per-ad-set budgets across several hooks and "
        "creators — not one large budget on one video.",
        "Use Spark Ads against your organic posts where you can; they carry the "
        "engagement the post already earned.",
        "Set the campaign daily budget to your per-test number, so overspend is "
        "structurally impossible rather than a matter of vigilance.",
        "Let it run at least 24 hours before judging anything. Early hours are noise.",
    ), "the campaign is live and cannot spend more than your test budget."),

    "log-daily": ((
        "Every day the test runs: `log-test <id> --spend X --revenue Y`.",
        "Take both numbers from Ads Manager and Seller Center for the SAME window. "
        "Mismatched windows produce a fake ROAS.",
        "Do not skip a day. The kill timer counts CONSECUTIVE hours below break-even "
        "— a gap breaks the math, not just your streak.",
        "Set a phone alarm. This is the step people quietly stop doing, and it is the "
        "one that makes every other number real.",
    ), "there is one log entry for every day the test has been running."),

    "decide": ((
        "Run `validate <id>`. It reports hours below break-even against the 48-hour "
        "kill rule.",
        "KILL: `log-result <id> --decision kill`, pause the campaign, move on. A "
        "killed test at ~$120 is the system working.",
        "SCALE: `log-result <id> --decision scale`, then raise budget 20–30% and "
        "re-validate after each raise.",
        "Do not override the verdict. Feeling optimistic at hour 47 is exactly the "
        "condition the rule exists to overrule.",
    ), "the decision is logged and you acted on it the same day."),

    # ── 8. Creator / affiliate ────────────────────────────────────────────────
    "affiliate-rate": ((
        "Set the rate in Seller Center → Affiliate. Open Collaboration typically "
        "10–15%; Targeted Collaboration 18–25%; up to 50% for proven top performers.",
        "By category: beauty/health 10–25%, fashion/home 8–18%, electronics 3–8% — "
        "thin electronics margins cannot fund high commissions.",
        "Check the rate against your scorecard's margin. If the commission plus fees "
        "plus COGS exceeds your price, you are paying for sales.",
        "Whatever you set is locked for that creator for 30 days once they pick it up. "
        "Choose deliberately.",
    ), "the rate is set and your margin still works with it applied."),

    "creator-outreach": ((
        "Open your product to Open Collaboration so any eligible creator can pick it "
        "up without negotiation.",
        "For targeted outreach: `packet <id>` builds the pitch, and the dashboard's "
        "Creators page lists the marketplaces with current pricing.",
        "Message creators who already post in your category with real engagement — "
        "not the largest accounts you can find.",
        "Keep it short: what the product is, the commission, and an offer to send one "
        "free. Nothing here is automated, deliberately.",
    ), "you have contacted at least 10 relevant creators by hand."),

    "send-samples": ((
        "Send free product to whoever actually responds and posts.",
        "Track who posts and what it converted — creator performance varies far more "
        "than follower count predicts.",
        "Double down on whoever converts. Do not spread thinly across everyone who "
        "said yes.",
        "This relationship stays human on purpose. It is the one place automation is "
        "deliberately not built.",
    ), "samples are out and you know which creators actually posted."),

    # ── 9. Scale ──────────────────────────────────────────────────────────────
    "scale-steps": ((
        "Raise budget 20–30% at a time, no more. Large jumps reset the algorithm's "
        "learning and often kill a working ad set.",
        "Re-run `validate <id>` after each raise. A SCALE verdict is not a blank cheque "
        "— it is permission for the next increment only.",
        "If ROAS drops below break-even after a raise, step back down. That is normal, "
        "not failure.",
        "Wait 24–48 hours between raises so each one produces readable data.",
    ), "budget has grown in steps and ROAS held above break-even at each one."),

    "scale-angles": ((
        "Run another `creative` batch with new hooks before you are forced to. "
        "Fatigue is the tax on scale and it arrives faster than expected.",
        "Vary the ANGLE, not just the footage — problem-first, result-first, "
        "comparison, objection-handling.",
        "Use `draft variants <product>` to spin one spec per roster actor and test the "
        "same concept across different faces. Your own actors, your own content.",
        "Watch for 3-second view rate falling on an ad that used to work. That is the "
        "fatigue signal.",
    ), "at least three genuinely different angles are live for the winner."),

    "scale-supply": ((
        "Ask your supplier directly: current stock, reorder lead time, and MOQ at your "
        "projected daily volume.",
        "Compute days of cover: stock ÷ current daily orders. Under 14 days at your "
        "scaled rate is a stockout waiting to happen.",
        "Line up a second supplier for the same product before you need one.",
        "A stockout mid-scale burns the exact momentum you just paid to build, and it "
        "does not come back cheaply.",
    ), "you know your days of cover and have a backup supplier identified."),

    # ── 10. Etsy POD ──────────────────────────────────────────────────────────
    "pod-shop": ((
        "Open an Etsy shop, then connect a POD provider: Printify (free tier, up to 5 "
        "stores), Gelato (regional printing, cheaper base costs), or Printful (widest "
        "catalog, most consistent quality).",
        "Connect the provider to Etsy BEFORE designing anything, so mockups generate "
        "into live listings directly.",
        "Order one sample of your own design. Print quality and colour shift are real "
        "and only visible in hand.",
    ), "a test listing is live and you have held a printed sample."),

    "pod-plan": ((
        "Run `pod --target <monthly profit> --profit <per-sale profit>`.",
        "Compute per-sale profit with Etsy's real fee stack: $0.20 listing, 6.5% "
        "transaction on item+shipping, and 3% + $0.25 processing — roughly 9.5% + "
        "$0.45 on a typical sale.",
        "If you clear $10,000/year, the 12–15% Offsite Ads fee becomes mandatory on "
        "sales it drives. Model that before you rely on the number.",
        "The default sales-per-listing rate is a cold-start guess. Re-run this with "
        "YOUR measured number after 30 days.",
    ), "you know how many listings your profit target actually requires."),

    "pod-publish": ((
        "Publish the first batch at the cadence the planner sized.",
        "Use searchable titles and all available tags. Etsy is a search engine first.",
        "Track for a full 30 days without changing things. Etsy listings take weeks to "
        "find their traffic.",
        "Re-run `pod` with your real sales-per-listing, then plan the next batch off "
        "measurement instead of the default.",
    ), "the batch is live and you have a 30-day date in the calendar to review it."),

    # ── 11. Financial hygiene ─────────────────────────────────────────────────
    "recon-monthly": ((
        "Once a month, export the payout report from Seller Center and compare it "
        "against your own revenue records.",
        "They will not match 1:1 — fees, refunds, holds, and adjustments all net out. "
        "Find and understand each difference.",
        "Reconcile ad spend against the card statement too.",
        "Numbers you have not reconciled are numbers you are deciding on blind.",
    ), "last month's payouts are explained line by line."),

    "tax-reserve": ((
        "Ask your accountant what percentage applies to YOUR structure and income. "
        "Do not use an internet number.",
        "Move that percentage out of the operating account on every payout — a "
        "separate savings account works.",
        "Automate the transfer so it is not a monthly act of willpower.",
        "Treat it as already spent. It is not runway and it is not profit.",
    ), "a reserve account exists and it grows automatically with every payout."),

    "account-health": ((
        "Check both scores in Seller Center weekly. They are separate: Shop "
        "Performance Score (0–5, needs 30+ delivered orders in 90 days to generate, "
        "throttles reach when low) and Account Health Rating (0–1,000, "
        "violation-based, low means enforcement).",
        "Run `health --ship-days <your real> --refund-rate <your real>` to model where "
        "your levers are heading before a throttle lands.",
        "Fix the input, not the score: ship faster, answer faster, refund cleanly.",
        "One unresolved violation compounds. Deal with it the week it appears.",
    ), "you have seen both scores this week and know which direction they moved."),

    "monthly-report": ((
        "Run `report-monthly` at month end.",
        "Read which sub-scores actually predicted your winners versus your losers. "
        "That is the whole value — the engine grading its own judgment against reality.",
        "It only ever suggests. Apply a weight change with `recalibrate --apply`, and "
        "only when the sample is big enough to mean something.",
        "Do not recalibrate off two tests. You will be fitting noise.",
    ), "you have read the report and decided, deliberately, whether to apply it."),

    # ── 12. Systemize ─────────────────────────────────────────────────────────
    "sop-docs": ((
        "Write down three checklists: how you source a product, how you run a test, "
        "and how you brief a creative.",
        "Keep them in the repo next to docs/OPERATING.md so they live with the tool.",
        "Write them as instructions to yourself on a bad day — tired, distracted, "
        "wanting to skip the sample.",
        "Update them the moment reality contradicts them.",
    ), "someone else could run one full test cycle from your notes."),

    "reinvest-split": ((
        "Decide the percentage of profit that gets reinvested versus drawn, and decide "
        "it BEFORE a big win makes the decision emotionally.",
        "A common early split is 70/30 reinvest/draw while still scaling.",
        "Write it down with today's date. Revisit quarterly, never mid-win.",
        "The point is that the decision was made calmly. The exact number matters less.",
    ), "the split is written down and dated."),

    "revisit-runbook": ((
        "Re-read docs/OPERATING.md monthly.",
        "Ask one question per manual step: has this earned automation yet? The iron "
        "rule holds — never automate what you have not run by hand many times.",
        "Ask the reverse too: is anything automated that has been quietly producing "
        "bad decisions?",
        "Run `audit` and work the criticals. That is the fastest read on drift.",
    ), "the runbook matches how you actually work today."),
}


def how_to(step_id: str) -> tuple[tuple[str, ...], str]:
    """Instructions + the done-condition for one step. Empty tuple if unknown."""
    return HOW_TO.get(step_id, ((), ""))


def render_how(step_id: str, title: str = "") -> str:
    steps, done = how_to(step_id)
    if not steps:
        return ""
    head = f"How to do it — {title}" if title else "How to do it"
    lines = [head, ""]
    lines += [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
    if done:
        lines += ["", f"  ✓ {DONE_WHEN.upper()}: {done}"]
    return "\n".join(lines)
