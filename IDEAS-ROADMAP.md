# NOVA Doer & Bazaar — product roadmap

This roadmap expands the existing NOVA Doer MVP into a task-completion product and a small-business marketplace. It is a plan, not a claim that every integration listed below is already implemented. Build and validate one recurring user problem at a time; do not launch 20 half-finished bots.

## Product promise

**«هر فایل یا لینکی داری بفرست؛ بگو چه نتیجه‌ای می‌خواهی؛ NOVA کار را انجام می‌دهد.»**

The differentiator is an explicit task and deliverable, not an open-ended chat. “Do it” should accept a multi-step request such as: read this PDF, summarize it, write 30 source-grounded questions, create flashcards, then make a seven-day study schedule. The assistant must disclose missing capabilities and never claim external actions it did not perform.

## Status today

The standalone `assistant_service.py` Mini App MVP has task prompts for do-it, study, rewrite, translate, compare, answer, OCR, transcription and summarization; it accepts selected PDFs, text/CSV, images and audio; verifies Telegram Mini App `initData`; enforces 10 free monthly operations by default; and does not intentionally retain input or result. Optional web search requires provider configuration. See `ASSISTANT.md` for setup and limitations.

This is **not yet** a full Telegram message bot for incoming files. It does not convert Word/PDF/video formats, fetch arbitrary URLs itself, persist a user's job history, offer paid plans, charge Telegram Stars, connect PayPal, create affiliate commissions, or include live inventory/order management. Existing bot and Mini App services remain separate.

## 20 ideas, grouped into a product sequence

Each item below is a product opportunity, not a guaranteed revenue source. Validate willingness to pay with interviews and a small pilot before adding costly integrations.

| # | Opportunity | Initial safe MVP / value | Revenue hypothesis | Priority |
|---|---|---|---|---|
| 1 | NOVA Doer AI task assistant | Turn a user request plus files into a specified deliverable/workflow | Monthly credits and paid usage tiers | P0 |
| 2 | File conversion & extraction | Start with supported PDF/text/image/audio extraction; add conversions only when a reliable sandboxed converter is deployed | Credits per conversion/batch | P1 |
| 3 | Resume & job-search helper | CV review, tailored draft, interview practice; user approves all applications | One-time packs / subscription | P2 |
| 4 | Small-business sales assistant | Product copy, lead notes, quote drafts and opt-in follow-up templates; no unattended messaging | Monthly workspace subscription | P2 |
| 5 | Telegram storefront builder | Product catalogue, order inquiry and owner-managed stock; verified checkout is a separate milestone | Setup/service fee plus support | P1 |
| 6 | Channel management assistant | Draft, schedule and analyze posts; human approval before publication | Monthly creator plan | P2 |
| 7 | Summarization | Summaries for user-provided files/text/URLs with source-grounded key points | Credits or bundle | P0 |
| 8 | Social content studio | Platform-specific campaign/caption/calendar drafts | Credit pack / subscription | P1 |
| 9 | OCR & document extraction | Extract visible text from supported images/PDF pages and flag uncertainty | Credits per page/batch | P1 |
| 10 | Personal learning coach | Source-grounded quiz, flashcards, spaced practice and study plan | Student subscription / class seats | P1 |
| 11 | Smart reminders | User-authorized reminders with confirmation, time-zone handling and delete controls | Free quota plus paid tier | P3 |
| 12 | Personal finance helper | User-entered budgets and calculations; no bank credentials or investment advice | Premium planning tools | P3 |
| 13 | Price comparison | Compare products from supplied offers first; live price checks only through permitted, attributable sources | Affiliate referrals after disclosure | P3 |
| 14 | Appointment booking | Request/availability workflow with explicit provider integration and confirmation | Per-seat subscription / booking fee | P3 |
| 15 | Freelance services marketplace | Request briefs, verified provider profiles and transparent milestones/dispute process | Clearly disclosed marketplace fee | P3 |
| 16 | Smart search | Web research with citations, dates, source links and uncertainty | Premium search credits | P1 |
| 17 | PDF & document studio | Extract, summarize, translate and generate original documents; conversions require vetted tooling | Credit packs | P1 |
| 18 | Group/community assistant | Rules, onboarding and moderation suggestions; destructive moderation requires permissions and owner-configured safeguards | Per-group subscription | P2 |
| 19 | Monitoring & alerts | User-selected public sources and thresholds with opt-in notifications | Paid monitored sources/limits | P3 |
| 20 | Services marketplace | First-party software/content services, then carefully vetted third-party listings and referrals | Project fee plus disclosed commission | P2 |

## Release plan and validation gates

### Phase A — prove repeated use (P0)

1. Keep the task-first Mini App as the single front door. Offer templates for PDF study pack, voice-to-summary, image OCR, link research, writing/translation and multi-file comparison.
2. Add job progress, clear errors, cancellation where possible, and a user-controlled recent-jobs history only after an explicit retention choice and delete/export controls.
3. Measure activation, repeat use, completion rate, average provider cost per successful job, latency and credit exhaustion. Do not equate registrations or AI calls with revenue.
4. Test with a small invited cohort. Continue only tasks used repeatedly and whose quality/cost can be supported.

### Phase B — keep unit economics controllable

- Track provider cost by task, model and input-size band. Estimate costs before accepting large uploads or multi-step jobs; apply per-user, per-file, page/token and daily limits.
- Keep a small free monthly allowance. Trial plan candidates (not live prices): **Free** for a limited number of operations; **Pro** for larger files, stronger models and web research; **Power** for batches, automation and API access. Set actual quota/price only after cost measurement and testing.
- Display which actions consume credits and the estimated cost/limits before starting. Refund reserved credits on failed jobs and record usage idempotently.
- Fail closed on missing payment-provider configuration. Do not imply that stars are cash or that a user has paid from a screenshot.

### Phase C — monetization and commerce (not implemented yet)

- For digital services sold inside Telegram, implement Telegram Stars using server-verified successful-payment events, unique orders, idempotent fulfillment, entitlement checks, refund/support paths and subscription expiry management. Test duplicate webhooks and failed fulfillment.
- For a web checkout, integrate only an eligible merchant processor through hosted checkout/server-side APIs and signed webhooks. PayPal requires merchant eligibility and regional availability; an email address alone is not checkout. Never put provider secrets in frontend or Git.
- Launch own services first: website/app builds, Telegram bots/Mini Apps, storefronts, workflow automation, content packages and consulting. Treat each as a quote/request until scope, price, dates, cancellation and support are agreed.
- Add physical goods only after the owner provides authentic product names, photos, inventory, shipping/return terms, tax and fulfillment details. Never invent stock, prices, testimonials or guarantees.
- Affiliate program only after written terms and tested attribution: commission base, refund/chargeback adjustments, eligibility, payout threshold/date, disclosure text and anti-fraud review. No percentage or earnings guarantee is advertised before approval.

### Phase D — external integrations and automation

Add reminders, bookings, posting, store orders, monitoring and group actions only after users grant the minimum required permissions, see a confirmation for consequential actions, and can revoke access. No unsolicited bulk messages, automatic purchases, job applications, channel posts or moderation bans. Use official APIs and respect provider/platform policies.

## Metrics and go/no-go checklist

- Is there a clearly named user and a repeated problem?
- Does the workflow produce a useful, verifiable output more often than it fails?
- Is cost per completed task below the tested amount users are willing to pay, with room for fees/refunds/support?
- Can the service explain where input data goes, how long it is retained, and how to delete it?
- Are content rights, privacy, local laws, tax, consumer protection and payment eligibility reviewed for the target region?
- Are payments, retries, refunds, affiliate attribution and support records auditable?

A positive answer to market-size statistics is not a forecast of NOVA's users or revenue. Verify third-party figures from original, current sources before using them in public marketing.
