# Application Challenge: Pattern + Build Plan for My Product Idea

*Susana Rivera — Pursuit Cycle 2*

Content Finder was my build-for-a-role project for a content coordinator. The product I'm actually leaning toward for myself comes straight out of my accounting background, and this challenge is my chance to think it through the same way — one user, one question, one pattern, and a realistic plan to ship a first version.

---

## Part 1 — Pick your pattern

### The user and their question

**The user:** an accounting manager at a small company (roughly 30–100 employees) who reviews employee expense reports before the monthly close. In most small companies this is one person, they inherited the chart of accounts from whoever set up QuickBooks years ago, and they are the last line of defense between "employee picked a category from a dropdown" and "the P&L is wrong."

**The one question they need answered:** *"Which of this month's expense transactions are coded to the wrong account, so I can fix them before I close the books?"*

I'm choosing this because I've lived it. Employees code a client dinner to "Office Supplies" because it's the first thing in the list. Software subscriptions land in "Dues & Memberships." Nobody catches it until someone asks why office supplies doubled quarter over quarter — and then the accounting manager spends an evening re-reading three months of memos.

### Which pattern fits — and why not the other three

**Classification** is the fit. The core job is taking each transaction and assigning it a judgment: *probably coded right* or *probably coded wrong, and here's the likely correct account*. That's a per-record labeling decision, which is exactly what classification is.

Why not the others:

- **Summarization** would tell her "you spent $4,200 on Office Supplies this month." True, and useless for this question — a correct total built on miscoded rows is still wrong underneath. She doesn't need the shape of the data compressed; she needs specific rows pulled out of it.
- **Extraction** is about pulling structured fields out of unstructured input — vendor and amount out of a receipt photo, for example. That's a real problem (and probably a version-two feature), but her transactions already *have* structured fields. The fields aren't missing; one of them is wrong.
- **Trend detection** answers "is this changing over time?" — expenses drifting up, a vendor getting more expensive. Her question isn't about direction over time, it's about correctness right now, this month, before close. Trend detection over *cleaned* data is where this product could go later, but it's downstream of getting the coding right.

The tell, for me, is the verb in the user's question. "Which transactions are wrong?" is a sorting-into-buckets question. If she'd asked "how much did we spend?" that's summarization; "what did we buy?" from receipts is extraction; "is spending going up?" is trend detection.

### What the output looks like on screen

One screen: a **review queue**. A table of *only the flagged transactions*, sorted with the highest-confidence flags on top. Each row shows exactly six things:

| Field | Why it's there |
|---|---|
| **Date** | She works in close periods; date anchors the row |
| **Vendor** | Usually enough to know what the purchase was |
| **Amount** | Determines whether a miscode is worth chasing |
| **Coded as** | The account the employee picked |
| **Suggested account** | The tool's best guess at the right one |
| **Why flagged** | One plain sentence: *"Vendor 'Figma' has been coded Software 11 of 12 times"* |

Above the table, one number: **"14 of 312 transactions flagged this month."** Next to each row, two buttons: **Accept suggestion** and **Keep original** — and a CSV export of her decisions formatted so it can go straight back into QuickBooks as a reclassifying journal entry. Content Finder taught me the export is not an afterthought: the deliverable in a real workflow is the file the user hands to the next step, so column labels and filenames have to speak the user's language.

What I'd deliberately leave out:

- **The 298 clean transactions.** The whole value is *not* making her scan the full ledger. If she wants everything, QuickBooks already exists.
- **A raw confidence score.** "87.3%" invites false precision and arguments with a number. Sorting by confidence and writing the plain-English reason gives her the same information without pretending to decimal-point accuracy.
- **Charts and spending dashboards.** Tempting, and wrong for this screen — this is a work queue, not an analytics page. Every chart is an invitation to stop doing the task.
- **Employee names, by default.** The question is "is the coding right," not "who keeps getting it wrong." Leaving names off the main view keeps the tool from becoming a gotcha machine, which matters a lot for whether people trust it. (It's in the detail view if she needs it.)

---

## Part 2 — Build it out loud

### Stack and hosting

**Streamlit + pandas, deployed on Streamlit Community Cloud** — the same stack as Content Finder, and that's a deliberate choice, not a lazy one. I now know the entire path from empty repo to a live URL on this stack: how caching works, how uploads behave, how the app feels on a phone, what breaks on deploy. For a first working version, a stack where I can tell when something is wrong beats a fancier stack where I can't.

**Data in:** CSV export from QuickBooks (every accounting tool exports the same basic shape: date, vendor, memo, amount, account). No API integration in version one — the file-upload flow I already built for Content Finder covers it, and it sidesteps OAuth entirely.

**Classification, first version:** history-based rules in pandas, not an LLM. "This vendor's past transactions went to account X ninety percent of the time; this one didn't" catches a big share of real miscodes, runs instantly, costs nothing, and — crucially — I can verify it by hand. An LLM reading vendor names and memos is the version-two upgrade *if* the rules plateau. Start with the thing I can check.

**Fake data first.** Same play as Week 3: I'll build a fictional company's expense ledger — a few hundred transactions, realistic chart of accounts, with a known list of deliberately planted miscodes. Swapping in real data later required zero code changes on Content Finder because the sample mirrored the real schema exactly, and it gives me something better than realism: **an answer key.** I'll know the tool's true hit rate because I planted the errors myself.

### What I'd ask an AI coding tool to scaffold vs. what I'd handle myself

Rough sequence:

1. **First — data loading and cleaning.** Ask the AI to scaffold the upload, parsing, and type-cleaning (dates to dates, amounts to numbers, blanks to nulls). **I verify this myself, row by row against the source file.** Content Finder had three rows with duration misfiled into the rating column, and I only caught it by checking the app's counts against the same data in Snowflake. Everything downstream is garbage if this layer is wrong, and the AI can't know my data is lying — only I can.
2. **Second — the flagging logic.** Ask the AI to generate the vendor-history mechanics (group by vendor, compute each vendor's dominant account, flag deviations). **I own the judgment calls inside it:** the flagging threshold, the minimum history a vendor needs before we trust its pattern, what happens with brand-new vendors. Those aren't coding decisions, they're accounting decisions — the AI genuinely doesn't know whether a first-time vendor should be flagged, and I do.
3. **Third — the review-queue screen and export.** Ask the AI to scaffold the table, the accept/keep buttons, and the CSV download. **I own every word on the screen.** The wording passes on Content Finder — renaming tabs, rewriting the "why flagged" style of copy, relabeling export columns — moved peer-test results more than any algorithm change. An accounting manager decides in about four seconds whether a flag is credible, and the sentence explaining it is what she's judging.

The pattern across all three: **the AI scaffolds structure; I own correctness and judgment.** It writes the pandas groupby faster than I can; it cannot decide what "wrong" means in accounting terms, and it won't notice when the data itself is dirty.

### Where I expect to get stuck — and how I'd know to change course

**The flagging accuracy is the risk, specifically false positives.** Getting the app to *run* isn't the hard part anymore — I've shipped this stack. The hard part is that vendor-history rules have obvious failure modes: Amazon legitimately maps to five different accounts, a new vendor has no history at all, and a vendor that was *consistently miscoded* in the past teaches the rules that the miscode is correct.

Here's the thing I keep coming back to: **a review queue that cries wolf is worse than no tool.** If she opens it three months in a row and most flags are noise, she stops opening it — and unlike a search tool with a weak result, a flagging tool that's ignored is fully dead.

So I'd set the tripwire *before* building, because I know from experience that mid-build I'll be tempted to rationalize: **on the planted-error test set, at least 7 of every 10 flags must be real miscodes, and at least 8 of every 10 planted errors must get caught.** Then peer-test the same way Content Finder went through three retest rounds — put a messy realistic ledger in front of testers playing the accounting manager and watch whether they trust the queue.

How I'd tell *push through* from *change course*:

- **Push through** if failures are specific and enumerable — one vendor type misfires, new vendors need a separate rule. That's tuning; iterate.
- **Change course** if failures are diffuse — precision stuck below the tripwire after two or three tuning rounds, with no pattern to the misses. That means vendor history alone doesn't carry enough signal, and more threshold-fiddling is pushing on a wall. The pivot is already scoped: add the memo field and an LLM pass as a *second opinion* on the rule-flagged rows only — which keeps costs near zero and keeps the explainable rules as the first gate.
- **The deeper fallback**, if even that can't hit the bar: shrink the promise. Flag only the five most miscoded expense categories instead of the whole chart of accounts. A narrow tool she trusts beats a broad one she ignores — that's the single clearest lesson peer testing taught me, and it's the reasoning I'd lean on every time this build forces a choice between impressive and reliable.
