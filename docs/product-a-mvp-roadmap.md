# Product A MVP — Implementation Roadmap

> **Document status:** Canonical active roadmap, reconciled through merged Phase 9B.4 (PR #30).
> **Repository:** `AbedJoulany/affiliate-platform-api`
> **Development baseline:** `main` at `39343022fb848117eafec722b4b9c0237e242e69` (PR #30 merge).
> **Verification source:** merged PRs and CI are implementation evidence; Phase 4.5 adds a traceable validation record. Controlled live provider checks remain separate from mocked tests and CI.
> **Current development phase:** Phase 9B.5 — AI usage and reservation operations is planned, not started. Unattended execution remains disabled.

### Naming convention

- **Completed foundation — Manual Telegram MVP (historically called “Phase 1”):** implementation merged via PR #5. This is **not** the same as Roadmap Phase 1.
- **Roadmap Phase 0:** partially verified; controlled live failure/retry remains pending.
- **Roadmap Phase 1:** implemented and merged via PR #7.
- **Roadmap Phase 2:** implemented and merged via PR #8; public onboarding is deferred.
- **Roadmap Phase 3:** 3A, 3B, and 3C.1 implemented via PRs #9–#11; Phase 3C.2 implemented and CI-verified via PR #13; Phase 3C.3 implemented and merged via PR #15.
- **Roadmap Phase 4:** implemented through PRs #17–#19; final validation is documented separately and remains partially verified where local PostgreSQL or staging evidence is unavailable.
- **Roadmap Phase 5:** implemented and merged through PRs #21–#22; execution remains deferred.
- **Roadmap Phase 6B:** catalog-first, bounded, read-only discovery preview is implemented and merged via PR #23; no execution or persistence is enabled.
- **Roadmap Phase 7B:** safe, explicitly triggered content-generation preview is implemented and merged via PR #24; no unattended execution or persistence is enabled.
- **Roadmap Phase 8B:** explicit, member-authorized preparation of up to two `SCHEDULED` Queue items is merged via PR #25; `execution_available` remains false.
- **Roadmap Phase 8C.3:** durable run foundation and disabled periodic dispatcher merged in PR #26; execution remains gated off.
- **Roadmap Phase 9B.4:** durable AI usage reservations and fail-closed request/token budget enforcement merged in PR #30, migration `022`; no monetary cap, operator reservation UI/API, uncertain-outcome reconciliation, or execution activation.
- **Roadmap Phase 9B.5:** planned only; workspace-scoped run/reservation visibility, safe review, pre-submission-only release, audit records, and operator UI.
- **Roadmap Phase 10:** not started; observability remains future work.
- **Roadmap Phases 6C, 7C, remaining activation hardening, and 9–11:** planned as described below.
- A merged PR and green mocked CI do **not** substitute for a live provider test.

### Current delivery status

| Deliverable | Status | Evidence / next action |
| --- | --- | --- |
| Product B removal | Merged | Historical migrations `001–017` retained and protected |
| Manual Telegram MVP foundation | Merged | PR #5 |
| Recommendation Engine | Implemented | PR #7; deterministic scoring, filters, explanations, and Top N |
| Manual MVP Polish | Implemented | PR #8; recommended mode, channel guidance, and permission refresh |
| Facebook Page Connection | Implemented | PR #9; migration `018`; real Page connection operator-verified |
| Facebook Publishing Backend | Implemented | PR #10; migration `019`; controlled text/photo/scheduled Facebook publishing operator-verified; permission readiness remains operationally separate |
| Facebook Destination Selection | Implemented | PR #11; provider-aware AI Studio and Queue frontend |
| Queue Display & Safe Ambiguous Retry | Implemented & CI Verified | PR #13; provider-aware destination/attempt display, explicit ambiguous retry confirmation, and duplicate-click protection |
| Phase 3C.3 publishing safety and controlled live validation | Implemented & CI Verified | PR #15, merge commit `b0593f8a72c8ec2866793e8df2d70d04070272bc`; live text/photo/scheduled Facebook publishing was operator-verified separately |
| Phase 4.2 Dashboard backend snapshot | Implemented & CI Verified | PR #17; workspace-scoped operational metrics, reporting windows, readiness, and attention items |
| Phase 4.3 Dashboard UI | Implemented & CI Verified | PR #18; operational KPIs, attention navigation, loading/error/empty states, and Queue deep linking |
| Phase 4.4 Dashboard realtime & reliability | Implemented & CI Verified | PR #19, merge commit `75f2003bffb278fc915db33c68dc8223d51bf72b`; shared operational SSE, invalidation, reconnect, fallback polling, and reporting rollover |
| Phase 4.5 final validation & documentation | Validation documented; partially verified | This closeout records automated evidence and remaining PostgreSQL/staging gaps; it does not claim full production readiness |
| Phase 5B Automation Configuration backend | Implemented & CI Verified | PR #21, merge commit `a76f6a4ddd7bcf340afc887815eaf1d5100e19e4`; migration `020`; no automation execution |
| Phase 5C Automation Configuration frontend | Implemented & CI Verified | PR #22; Arabic RTL workspace-scoped GET/PATCH UI; saved intent only; no automation execution |
| Phase 6B Catalog-First Automation Discovery | Implemented & merged | PR #23, merge commit `8a83e951060a37a3cb10d891eb99d95ee3c1962e`; bounded, workspace-scoped, read-only preview |
| Phase 7B Safe Automated Content Generation Preview | Implemented & CI Verified | PR #24, merge commit `b06657d91b83fe9ad003a8cb407d1508d6e59bcd`; explicit paid preview for at most two server-selected products; sequential, stateless, validated, no Queue or publishing |
| Phase 8B Automation → Scheduled Queue | Implemented & merged | PR #25, merge commit `e53fd5c0dbc9452b968736d861c5c3248ef88408`; explicit preparation uses the existing Queue/Scheduler; execution remains disabled |
| Phase 8C.3 Disabled Orchestration Foundation | Implemented & merged | PR #26; migration `021`; dispatcher remains disabled by the closed execution gate |
| Phase 9B.4 AI Usage Accounting & Budget Enforcement | Implemented & CI verified | PR #30; migration `022`; durable request/token reservations, trusted-usage settlement, uncertain reservation retention; not a monetary cap |
| Phase 9B.5 AI Usage & Reservation Operations | Planned; not started | Operator APIs/UI and audited safe review; no uncertain release or retry |
| Phase 10 Automation Observability | Not started | Future roadmap work |
| Phase 0 live Telegram verification | Partially verified | Manual publish, image/link delivery, and scheduling verified; failure/retry pending |
| PR #11 CI | Passed | Backend, frontend, and E2E checks completed successfully |
| PR #12 documentation synchronization | Completed | Documentation-only roadmap synchronization |
| PR #13 CI | Passed | Backend 423, frontend 220 Vitest, Playwright 13; TypeScript, lint, production build, and Ruff passed |
| PR #15 CI | Passed | Backend, frontend, and E2E jobs passed; Phase 3C.3 regression coverage merged |
| PR #17 CI | Passed | Dashboard backend snapshot checks completed successfully |
| PR #18 CI | Passed | Dashboard UI checks completed successfully |
| PR #19 CI | Passed | Backend, frontend, and E2E jobs passed for realtime/reliability changes |

---

## 1. الهدف

بناء **Affiliate Marketing Assistant** عملي وقابل للاستخدام من البداية إلى النهاية:

```text
Discover → Filter → Evaluate → Recommend → Select
→ Generate → Review/Edit → Queue → Schedule → Publish
```

قنوات النشر المستهدفة:
- Telegram
- Facebook

بعد استقرار المسار اليدوي، نضيف **Automation Mode** فوق الخدمات والـ Queue الحالية، وليس كنظام مستقل.

---

## 2. الوضع الحالي

بعد إزالة Product B ودمج **Manual Telegram MVP foundation** عبر PR #5، يتضمن الكود المكونات التالية (التشغيل الحقيقي يحتاج Live Verification):

```text
AliExpress Discovery
        ↓
Product Catalog
        ↓
Product Scoring
        ↓
AI Content Generation
        ↓
Queue
        ↓
Scheduling
        ↓
Telegram Publishing
```

تغييرات Manual Telegram MVP المدمجة عالجت على مستوى الكود أهم مشاكل Telegram:

```text
Product
 ↓
AI
 ↓
Affiliate URL
 ↓
Queue
 ↓
Default Telegram Channel
 ↓
Schedule / Publish
 ↓
Telegram
 ↓
Published / Failed
 ↓
Retry
```

---

## 3. المراحل المتبقية

> الترقيم التالي يخص **Roadmap** فقط؛ لا تخلطه مع اسم مرحلة Manual Telegram MVP السابقة. حالة Phase 0: partially verified. حالة Phase 1 وPhase 2 وPhase 3C.1 وPhase 3C.2 وPhase 3C.3 وPhase 5B وPhase 5C: implemented؛ Phase 4.2 وPhase 4.3 وPhase 4.4 implemented and CI verified، وPhase 4.5 توثق التحقق النهائي، وPhase 6B قيد التحقق كـ preview للقراءة فقط.

```text
Phase 0  — Live Manual Verification
Phase 1  — Recommendation Engine
Phase 2  — Manual MVP Polish / Onboarding
Phase 3  — Facebook Publishing
Phase 4  — Operational Dashboard
Phase 5  — Automation Configuration
Phase 6  — Auto Discovery
Phase 7  — Auto Content Generation
Phase 8  — Automation → Queue
Phase 9  — Safety / Idempotency Hardening
Phase 10 — Automation Observability
Phase 11 — Full MVP Validation
```

---

# 4. Target Architecture

## Manual Mode

```text
User
 ↓
Discovery
 ↓
Filters
 ↓
Evaluation
 ↓
Recommendation
 ↓
Product
 ↓
AI Marketing
 ↓
Review / Edit
 ↓
Queue
 ↓
Schedule
 ↓
Publisher
 ├── Telegram
 └── Facebook
 ↓
Result
```

## Automation Mode

Automation هو Orchestrator فوق الخدمات الحالية:

```text
Automation Scheduler
        ↓
Automation Service
        ↓
Discovery Service
        ↓
Filters
        ↓
Scoring
        ↓
Recommendation
        ↓
Deduplication
        ↓
Top N
        ↓
AI Content Service
        ↓
Queue Service
        ↓
Existing Scheduler
        ↓
Publisher
 ├── Telegram
 └── Facebook
```

القاعدة الأساسية:

> Automation يقرر ماذا ومتى نضع في Queue، بينما Queue/Scheduler/Publisher مسؤولون عن النشر.

---

# 5. Phase 0 — Live Manual Verification

## الهدف

إثبات أن Manual Telegram MVP تعمل فعلياً، وليس فقط عبر الاختبارات.

## المسار

```text
Login
 ↓
Set Telegram default channel
 ↓
Discovery
 ↓
Select Product
 ↓
Generate Content
 ↓
Review / Edit
 ↓
Queue
 ↓
Schedule / Publish Now
 ↓
Telegram
 ↓
Verify Result
```

## الاختبارات

### Affiliate URL

- المنتج لديه `affiliate_url`.
- AI context يستقبل `affiliate_url`.
- Queue item يحتوي `button_url` المناسب.
- Telegram يستخدم affiliate URL.
- `product_url` لا يستخدم كـ CTA.

### Default Channel

- يوجد Telegram channel فعال.
- هو default workspace channel.
- Queue بدون `channel_id` يستخدمه تلقائياً.

### Publish

- الرسالة تصل Telegram.
- الصورة تصل إن وجدت.
- CTA يعمل.
- Queue يصبح `published`.

### Failure / Retry

```text
Publish
 ↓
Failure
 ↓
Failed
 ↓
Retry
 ↓
New Attempt
```

## Completion Criteria

لا نبدأ المرحلة التالية قبل نجاح المسار اليدوي الحقيقي.

---

# 6. Phase 1 — Recommendation Engine

## الهدف

تحويل scoring الحالي إلى Recommendation حقيقية بدون ML.

```text
Candidates
 ↓
Hard Filters
 ↓
Score
 ↓
Rank
 ↓
Top N
```

## المعايير

```text
keywords
min_price
max_price
min_rating
min_orders
min_discount
min_commission
max_commission
```

## Scoring

نفحص `app/aliexpress/scoring.py` ونُعيد استخدام أدوات التطبيع المناسبة، لكن **نحافظ على معنى الـ catalog score الحالي**. نفضل Recommendation Scorer منفصلاً (في ملف مستقل أو طبقة واضحة) ما لم يثبت الفحص أن التوسعة لا تغيّر السلوك القديم.

مثال مبدئي:

```text
Rating       30%
Orders       20%
Discount     15%
Price        10%
Commission   25%
```

الأوزان النهائية تحدد بعد فحص الكود الحالي.

المهم:

> `commission_rate` يصبح جزءاً حقيقياً من الـ score.

## Storage

في النسخة الأولى يُفضّل حساب التوصيات دون حفظ نتائجها أو إنشاء جدول جديد. إذا احتجنا إلى حفظ معايير المستخدم لاحقًا، ندرس `workspace_settings` بعد فحص البنية الحالية. لا تُنشأ migration بلا ضرورة.

## Frontend

إضافة:
- commission filters
- recommendation indicator
- score explanation
- Top N
- recommended badge

## Tests

Unit:
- commission filter
- price filter
- rating filter
- orders filter
- discount filter
- score calculation
- ranking
- Top N

Integration:

```text
Discovery
 ↓
Filters
 ↓
Scoring
 ↓
Recommendations
```

---

# 7. Phase 2 — Manual MVP Polish / Onboarding

## الهدف

تشغيل مستخدم حقيقي بدون bootstrap يدوي غير ضروري.

الخيار المفضل:

```text
Register
 ↓
Create User
 ↓
Create Workspace
 ↓
Create Membership
 ↓
Create Workspace Settings
```

Onboarding بسيط:

```text
Register
 ↓
Create Workspace
 ↓
Configure Affiliate / AliExpress
 ↓
Configure Telegram
 ↓
Start Discovering
```

لا نبني Wizard كبيراً.

---

# 8. Phase 3 — Facebook Publishing

Phase 3 is divided into connection, backend publishing, frontend destination
selection, and controlled live verification. The Queue remains shared with Telegram.

## الهدف

إضافة Facebook كـ Publisher ثانٍ بدون Queue ثانية.

```text
Queue Item
 ↓
Provider
 ├── Telegram
 └── Facebook
```

## Phase 3A — Facebook Page Connection

```text
Manual Page ID + Page Access Token
  ↓
Server-side validation
  ↓
Encrypted Page token storage
```

لا تخزن credentials في frontend. OAuth وFacebook Login خارج نطاق MVP.

## Database

الجدول المطبق:

```text
facebook_pages
```

بالحد الأدنى:

```text
id
workspace_id
page_id
page_name
    encrypted_access_token
token_expires_at
is_active
created_at
updated_at
```

## Phase 3B — Facebook Publishing Backend

يدعم الـ backend نشر text وphoto إلى Page نشطة ومتحقق منها، مع Queue/Celery
مشتركة، حفظ `provider_message_ref`، وسجل محاولات provider-aware.

## Phase 3C.1 — Frontend Destination Selection

يدعم AI Studio وQueue اختيار Telegram channel أو Facebook Page، ويحافظ على
الوجهات في الجدولة الجماعية المختلطة. اختيار الوجهة لا ينشر وحده.

## Phase 3C.2 — Queue Display & Safe Ambiguous Retry

**Status: Implemented & CI Verified via PR #13.**

يشمل التنفيذ عرض provider والوجهة والنتيجة الخاصة بكل provider في Queue، وإظهار
سجل محاولات النشر، وتمييز `failed` عن `ambiguous`، وإجبار المشغل على فحص Facebook
والتأكيد الصريح قبل إعادة محاولة نتيجة غير مؤكدة. كما يشمل حماية النقر المكرر،
والتوافق مع Queue القديمة الخاصة بـ Telegram، والحفاظ على أولوية affiliate URL.
لا توجد إعادة تلقائية لمحاولات Facebook الغامضة.

**CI evidence:** Backend: 423 tests passed; frontend: 220 Vitest tests passed;
Playwright: 13 tests passed; TypeScript, lint, production build, and Ruff passed.
هذه النتائج لا تثبت live Facebook publishing.

## Phase 3C.3 — Controlled Live Publishing Validation & Publishing Safety Hardening

**Status: Implemented & CI Verified via PR #15.** تم التحقق اليدوي المنفصل من
Facebook text publishing وFacebook photo publishing مع caption وFacebook scheduled
publishing، مع ظهور حالة `published` وسجل المحاولة ومرجع provider في Queue.

يشمل التنفيذ حماية Queue items المنشورة داخل مسار claim المقفول حتى بعد انتهاء نافذة
24 ساعة، ومنع إنشاء محاولة أو استدعاء provider جديد لها، وجعل أخطاء Facebook غير
الغامضة — ومنها HTTP 429 — نهائية للمحاولة الحالية حتى لا يعيدها scheduler بلا حدود.
تبقى النتائج الغامضة بلا إعادة تلقائية وتتطلب فحص المشغل والتأكيد الصريح قبل retry.
كما يعرض Queue provider المحفوظ لكل محاولة تاريخية، ويحافظ على سلوك Telegram وأولوية
affiliate URL. لا ندعي exactly-once delivery؛ قد يتطلب قبول provider قبل حفظ النتيجة
تحقيقاً يدوياً.

**CI evidence:** PR #15 passed Backend, Frontend, and E2E GitHub Actions jobs.
Regression tests cover published-item protection داخل وبعد نافذة idempotency، scheduled
Facebook success، 429/401/403 handling، sanitized permission errors، active-attempt and
ambiguous-retry safeguards، and historical provider display. PostgreSQL concurrent
row-lock integration remains an open verification item، وكذلك Telegram live
failure/retry verification.

Live Facebook validation here refers to the prior operator-observed text/photo/scheduled
publishing checks; no new provider calls were made during PR #15.

## Queue

نحافظ على Queue واحدة. قد يكون التصميم:

```text
provider = telegram
channel_id = ...

provider = facebook
facebook_page_id = ...
```

التصميم المطبق يستخدم `QueueItem.provider`, `channel_id`, و`facebook_page_id`.

## Publisher

Publisher layer:

```text
Publisher
 ├── TelegramPublisher
 └── FacebookPublisher
```

## Facebook MVP

يدعم backend Phase 3A/3B:
- text
- image
- affiliate URL / link
- publish
- retry/failure handling مع حماية idempotency
- ambiguous outcome يحتاج تأكيداً صريحاً قبل إعادة المحاولة

خارج النطاق:
- Reels
- Stories
- comments
- advanced insights
- campaign management

---

# 9. Phase 4 — Operational Dashboard

**Status:** Phase 4.2, Phase 4.3, and Phase 4.4 are implemented and CI verified
through PRs #17, #18, and #19. Phase 4.5 is the final validation and documentation
closeout; it records what is proven and what still requires PostgreSQL or staging
verification. Phase 4 is not claimed to be fully production-ready.

**MVP scope:** products, recommendations, Queue status, provider/destination,
scheduled/published/failed/ambiguous attempts, channel/Page readiness, and the
current automation state once automation exists.

**Dependencies:** existing Dashboard, Queue attempt history, SSE/polling, and
workspace authorization. No advanced click/conversion analytics.

**Implemented evidence:** the backend snapshot preserves the existing response
fields and adds workspace-local reporting boundaries, current Queue/provider
publishing metrics, distinct daily failure metrics, unresolved ambiguous attempts,
bounded attention items, destination readiness, and an explicit automation
placeholder. The UI consumes the authoritative snapshot, deep-links to Queue
details (including items outside the first list page), and shares one authenticated
operational Queue SSE subscription with bounded polling fallback.

**Validation limits:** automated CI covers the merged backend, frontend, and E2E
changes. Local Windows validation in Phase 4.5 may be limited by the available
Python/Docker runtime and Next.js native tooling. PostgreSQL aggregation queries,
reverse-proxy SSE behavior, and staging workspace/timezone checks must be reported
separately when not executed. No live provider publishing is part of this closeout.

**Acceptance:** the operator can identify what is queued, scheduled, published,
failed, ambiguous, and whether automation is enabled, without exposing tokens.

Dashboard ليس Analytics System.

يجب أن يجيب عن:

```text
What products are available?
What is recommended?
What is queued?
What is scheduled?
What was published?
What failed?
Is automation enabled?
When did automation last run?
```

يعرض:

```text
Products
Recommended
Queued
Scheduled
Published
Failed
```

ومع Automation:

```text
Automation: Enabled

Last Run: Successful

Discovered: 25
Selected: 5
Generated: 5
Queued: 5
Published: 4
Failed: 1
```

لا نضيف click/conversion analytics.

---

# 10. Phase 5 — Automation Configuration

**Status:** Phase 5B backend configuration and Phase 5C frontend configuration are
implemented, merged, and CI verified through PRs #21 and #22. Execution remains
deferred.

**MVP scope:** enabled state, discovery filters, products per run, posts per day,
workspace timezone/schedule, provider/destination, and AI content overrides. The
backend uses a dedicated one-to-one `automation_policies` table and reuses
`workspace_settings` for timezone and inheritance defaults.

**Deferred:** complex rule builders, billing, subscriptions, and SaaS onboarding.

**Dependencies:** Recommendation Engine, validated destinations, daily limits, and
safe pause/disable behavior.

**Phase 5B acceptance:** an operator can save, inspect, update, and disable one
workspace-scoped policy through `GET/PATCH /api/v1/automation/config`, with
revision conflicts, destination readiness, virtual disabled defaults, and no
execution side effects. `execution_available` is always false in this phase.

**Phase 5C scope:** the authenticated `/automation/settings` page consumes the
same workspace-scoped GET/PATCH contract. It provides Arabic RTL configuration
for discovery filters, daily schedule preferences, one Telegram or Facebook
destination, and nullable AI content overrides. It displays revision conflicts,
destination readiness warnings, and the distinction between saved `enabled`
intent and `execution_available: false`. Saving never starts discovery, AI,
Queue, Celery, or provider work. Phase 6B preview is a separate read-only
capability and does not make the policy executable.

تبدأ بعد استقرار Manual MVP.

## Configuration

```text
enabled

keywords

min_price
max_price
min_rating
min_orders
min_discount
min_commission

products_per_run
posts_per_day

schedule

provider / channel

content language
content tone
content type
```

## Storage

Phase 5B uses the dedicated `automation_policies` table introduced by migration
`020`. It has one row per workspace, nullable Telegram/Facebook destination
foreign keys with `ON DELETE SET NULL`, explicit numeric/range constraints, and
an integer `revision` for optimistic concurrency. Existing workspaces receive
virtual disabled defaults until the first PATCH; no policy rows are backfilled.

The policy stores configuration intent only. It does not add an automation worker,
Celery Beat schedule, Queue creation, AI generation, discovery, or provider call.
The existing Dashboard automation placeholder remains `not_configured`.

`GET /api/v1/automation/config` is readable by authorized workspace members.
`PATCH /api/v1/automation/config` is owner/admin-only, requires the current
revision for existing rows, and validates the complete merged configuration.
`enabled=true` requires an eligible persisted destination, but still cannot make
the policy executable during Phase 5B. Nullable AI fields inherit workspace
settings; no secrets are stored in the policy.

---

# 11. Phase 6 — Auto Discovery

**Status:** Phase 6B catalog-first discovery preview is implemented on the current
feature branch; automatic execution is not implemented.

**Phase 6B scope:** authenticated `POST /api/v1/automation/discovery/preview`
reuses the persisted global catalog and the existing deterministic Recommendation
Engine. It applies active-product and valid-affiliate-URL eligibility, workspace
queue/history exclusions, a 1000-candidate inspection cap, deterministic ranking,
and Top N selection. Numeric filters and an optional PostgreSQL `ILIKE` prefilter
for ASCII keyword tokens run before the cap; exact all-token Python `casefold()`
matching across title, description, category, and store name remains authoritative.
Non-ASCII searches retain the bounded deterministic window because PostgreSQL
`ILIKE` is not universally equivalent to Python Unicode `casefold()`. A
truncated response ranks only the inspected slice and does not claim global Top N
optimality. The response reports the policy revision, UTC selection time,
truncation, ranking scope, exclusion counts, and preview-only warnings.

The preview is workspace-scoped through `X-Workspace-Id`, is readable by
authorized members, and returns `execution_available: false`. It does not create
run records, modify policy revisions, create Queue items, call AliExpress/AI or
provider APIs, invoke Celery, or activate automation. Products with missing or
invalid affiliate URLs are excluded; `product_url` is never used as a fallback.

**Remaining Phase 6 scope:** live AliExpress refresh, run persistence, Celery
execution, AI generation, Queue creation, scheduling, publishing, and later
observability remain future work.

**Acceptance:** a run produces only eligible, ranked products and records per-run
selection failures without publishing directly.

## الهدف

تشغيل Discovery تلقائياً.

```text
Celery Beat
 ↓
Automation Task
 ↓
Load Settings
 ↓
Discovery
 ↓
Hard Filters
 ↓
Score
 ↓
Rank
 ↓
Deduplication
 ↓
Top N
```

## Celery

Task رئيسي:

```text
run_due_automations
```

## AutomationService

مثلاً:

```text
AutomationService.run(workspace_id)
```

المسؤوليات:
1. تحميل configuration.
2. Discovery.
3. Filtering.
4. Scoring.
5. Ranking.
6. Deduplication.
7. Selection.

لا يتعامل مباشرة مع Telegram/Facebook.

---

# 12. Phase 7 — Auto Content Generation

**Phase 7B status:** implemented and CI verified in merged PR #24. Phase 7B is
an explicitly triggered, paid-AI preview only. It
re-runs Phase 6B selection server-side, processes at most two products
sequentially, returns stateless structured results, validates canonical affiliate
URLs and generated output, and keeps `execution_available: false`.

The endpoint does not create Queue items, schedule posts, publish, invoke Celery,
persist generated content, or activate unattended automation. Redis duplicate
protection is short-lived and does not claim exactly-once generation or billing.

**MVP scope:** reuse `AIContentService`, resolve nullable policy preferences from
workspace settings, validate content and affiliate URLs, sanitize provider errors,
and isolate per-product failures.

**Acceptance:** each eligible product produces validated content or an isolated
failure; no provider call exposes credentials or bypasses the Queue; the request
requires explicit cost acknowledgment and a matching policy revision; maximum
batch size is two products.

إعادة استخدام:

```text
AIContentService
```

Target:

```text
Selected Products
 ↓
Generate Content
 ↓
Validate
 ↓
Queue
```

إذا فشل منتج واحد:

```text
Product 1 → success
Product 2 → success
Product 3 → failed
Product 4 → success
Product 5 → success
```

لا يفشل الـ Run بالكامل.

---

# 13. Phase 8 — Automation → Queue

**Phase 8B status:** merged via PR #25 (merge commit
`e53fd5c0dbc9452b968736d861c5c3248ef88408`). The implementation is explicitly triggered,
member-authorized operation. It does not activate unattended automation and
always returns `execution_available: false`.

`POST /api/v1/automation/queue/prepare` requires the saved policy revision,
`acknowledge_ai_cost: true`, `confirm_scheduled_publishing: true`, and an
idempotency key. It server-side reuses Phase 6B discovery and Phase 7B content
generation, processes at most two products sequentially, revalidates the
current product and canonical affiliate URL, and creates only `SCHEDULED`
Queue items through the existing QueueService.

Scheduling uses the saved workspace timezone and daily policy limit, persists
UTC timestamps, handles DST gaps/folds deterministically, counts existing
scheduled and published items for the selected workspace/provider/destination,
and rejects stale policy or unavailable destination state. Final allocation uses
a PostgreSQL transaction-scoped advisory lock, re-reads occupancy, and inserts
the Queue row before commit, so concurrent automation requests cannot commit
conflicting reservations for the same destination scope. Scheduled rows count
by `scheduled_at`; published rows count by authoritative `published_at`, even
when both timestamps exist. Each product has an independent result; a
duplicate/history conflict or unavailable slot does not roll back previously
committed successful items.

Scheduled items may later be published by the existing Queue scheduler when
due. This is an explicit side effect of the approved operation, not proof that
unattended automation is enabled. No automation Celery task, parallel Queue,
run table, or publishing adapter is introduced. The short-lived Phase 7B Redis
guard remains bounded protection rather than durable exactly-once Queue
creation. Manual Queue creation does not participate in the automation
daily-limit lock, so the automation quota is not claimed as a system-wide
manual-plus-automation quota.

**Acceptance evidence:** Linux backend verification after the scheduling
hardening passed (484 tests passed, 20 skipped), focused PostgreSQL migration,
timestamp, workspace, destination, and concurrency tests passed (16 tests), the
real Redis guard tests passed (4 tests), and Ruff passed. CI and the pull request
remain the release gate.

```text
Automation
 ↓
POST /automation/queue/prepare
 ↓
QueueService.create_automation_scheduled()
 ↓
Scheduled Queue Item
 ↓
Existing Beat
 ↓
Existing Publisher
```

وبذلك:

```text
Manual:
User → Queue

Automation:
AutomationService → Queue
```

**Phase 8C.3 — Disabled orchestration foundation:** migration `021` adds
workspace/policy/local-date run identity and per-product checkpoints. The unique
key excludes policy revision, and PostgreSQL `ON CONFLICT DO NOTHING` makes the
daily claim atomic. Each successful product's generated content and canonical
affiliate URL are committed to its run item before the next provider call, so a
completed generation can resume at Queue creation. A run without an uncertain
AI call has a bounded five-minute recovery window after lease expiry; older
incomplete runs are marked missed rather than caught up. A worker lease that
expires after generation began is marked uncertain and requires operator review;
AI generation is never automatically repeated after an uncertain outcome.

Celery Beat registers one global dispatcher. In this phase its global execution
setting defaults off, the emergency stop defaults on, and workspace activation
and budget-enforcement capabilities are deliberately unavailable. The dispatcher
returns before opening a database session, so it does not claim runs, call AI,
create Queue items, or contact providers. `execution_available` remains false.
When separately approved activation is implemented, the dispatcher will inspect
only the current workspace-local daily slot, use the existing DST resolver, and
record an overdue slot as missed instead of catching up a backlog. Existing
manual Phase 8B preparation and the shared Queue publisher remain unchanged.

**Phase 8C.3 status:** merged in PR #26; focused local pytest was blocked by
the Windows Python 3.13 async runtime. The PostgreSQL migration/concurrency and
backend regression suites are assigned to GitHub CI. Activation, operator
run-history UI, observability, and controlled live validation remain
pending. No live AI or publishing calls were made.

وبعد Queue يصبح المسار واحداً.

---

# 14. Phase 9 — Safety & Idempotency

**Status:** partial provider-aware foundation exists from Phase 3B. Automation-
specific safeguards remain to be implemented.

**MVP scope:** product/Queue deduplication, concurrent-run safety, stale and
ambiguous attempt handling, affiliate fail-closed behavior, daily limits, and
safe pause/disable.

**Acceptance:** repeated or concurrent runs cannot create unintended duplicate
Queue items or provider posts, and missing affiliate URLs are skipped by
unattended automation.

هذه المرحلة إلزامية قبل unattended automation.

## Product Deduplication

عدم اختيار نفس المنتج في كل Run.

فحص:
- queued
- scheduled
- published

ضمن نافذة زمنية مناسبة.

مثال مبدئي:

```text
Do not reuse product for 7 days
```

## Queue Deduplication

منع duplicate Queue items لنفس:

```text
Product
+
Provider
+
Time Window
```

## Content Deduplication

الحفاظ على content hash الحالي.

## Publisher Idempotency

Retry لا يؤدي إلى نشر الرسالة مرتين.

## Stale Attempts

```text
started > threshold
 ↓
stale/failed
 ↓
retry available
```

## Failed Items

فشل منتج واحد لا يوقف Automation Run.

## Affiliate Fail-Closed

Automation:

```text
affiliate_url missing
 ↓
skip product
```

Manual:

```text
affiliate_url missing
 ↓
allow no-CTA post
```

ولا نستخدم `product_url` كبديل صامت.

---

# 15. Phase 10 — Automation Observability

**Status:** not implemented.

**MVP scope:** minimal run identity, status, counts, failures, timestamps, and
operator-visible diagnostics. Begin recording run outcomes when automation begins;
do not postpone all observability to this phase.

**Acceptance:** the operator can inspect the latest run and understand whether
products were discovered, generated, queued, published, or failed.

إذا لم تكف Queue history، ننشئ جدولاً صغيراً:

```text
automation_runs
```

الحد الأدنى:

```text
id
workspace_id
started_at
finished_at
status

products_discovered
products_selected
contents_generated
queue_items_created
published
failed

error_summary
```

Lifecycle:

```text
started
 ↓
discovering
 ↓
selecting
 ↓
generating
 ↓
queuing
 ↓
completed
```

أو:

```text
completed_with_errors
```

---

# 16. Background Jobs

## Existing

نحافظ على:
- publishing
- AliExpress refresh
- categories
- heartbeat
- queue events

## New

الحد الأدنى:

```text
run_due_automations
```

وstale-attempt cleanup فقط إذا تعذر دمجه في queue maintenance الحالي.

لا نضيف Auto Publish Task منفصل.

---

# 17. API Changes

## Recommendation

يفضل تعديل endpoints الحالية لدعم:

```text
min_commission
max_commission
recommended
```

بدلاً من إنشاء API جديدة بلا حاجة.

## Settings

```text
GET /api/v1/workspace-settings
PATCH /api/v1/workspace-settings
```

مع توسيع الحقول عند الحاجة.

## Facebook

قد تشمل:

```text
GET  /facebook/connect
GET  /facebook/callback
GET  /facebook/pages
POST /facebook/pages/select
DELETE /facebook/pages/{id}
```

الأسماء النهائية تتبع convention الحالي.

## Automation

قد تشمل:

```text
GET  /automation/settings
PATCH /automation/settings
GET  /automation/runs
POST /automation/run
```

`POST /automation/run` مفيد للاختبار اليدوي قبل Celery.

---

# 18. Frontend Changes

## Discovery

- commission filter
- recommendation indicator
- score explanation
- Top N

## AI

الحفاظ على:
- generate
- edit
- improve
- regenerate

مع الحفاظ على affiliate URL.

## Queue

الحفاظ على:
- provider
- channel
- status
- schedule
- retry

## Channels

```text
Channels
 ├── Telegram
 └── Facebook
```

## Automation

واجهة بسيطة:

```text
Automation

[ Enabled ]

Keywords

Price
Commission
Rating
Orders
Discount

Products per run
Posts per day

Publishing channel

Content style

[ Save ]
```

ثم:

```text
Last Run
Status
Selected
Generated
Queued
Published
Failed
```

---

# 19. Database Migration Strategy

Migrations الحالية:

```text
001 → 019
```

لا تعدل migrations `001–019`.

أي schema change جديد يبدأ بعد `019`.

المحتمل:
- Recommendation: غالباً بدون migration.
- Facebook: `facebook_pages` (`018`) + queue/provider columns (`019`) مطبقة.
- Automation: `automation_runs`.

لكل migration:
- purpose
- columns
- indexes
- constraints
- foreign keys
- downgrade
- data migration إن وجدت

لا تنشئ migration إذا كان التغيير يمكن تنفيذه بالschema الحالية.

---

# 20. Testing Strategy

## Backend Unit

Recommendation:

```text
test_commission_filter
test_price_filter
test_rating_filter
test_orders_filter
test_discount_filter
test_product_score
test_product_ranking
test_top_n
```

Affiliate:

```text
test_affiliate_url_is_used
test_product_url_is_not_used_as_cta
test_missing_affiliate_url
```

Queue:

```text
test_default_channel
test_failed_status
test_retry
test_retry_creates_new_attempt
test_duplicate_queue_prevention
```

Automation:

```text
test_automation_filters_products
test_automation_scores_products
test_automation_selects_top_n
test_automation_deduplicates
test_automation_continues_after_product_failure
```

## Integration

```text
Discovery → Recommendation
Product → AI → Queue
Queue → Telegram
Queue → Facebook
Automation → Discovery → Recommendation → AI → Queue
```

## E2E

Manual:

```text
Login
 ↓
Workspace
 ↓
Discovery
 ↓
Select
 ↓
Generate
 ↓
Edit
 ↓
Queue
 ↓
Schedule
 ↓
Publish
```

Automation:

```text
Configure
 ↓
Run
 ↓
Discover
 ↓
Select
 ↓
Generate
 ↓
Queue
 ↓
Scheduler
 ↓
Publish
```

Third-party APIs تكون mocked في CI.

Live verification منفصل لـ Telegram وFacebook.

---

# 21. Documentation

بعد كل مرحلة، حدّث فقط الوثائق التي أصبحت غير مطابقة:

```text
README
docs/06-api-integration.md
docs/08-implementation-roadmap.md
docs/10-production-readiness.md
```

لا نعيد كتابة documentation بلا حاجة.

---

# 22. Explicitly Out of Scope

- SaaS
- billing
- subscriptions
- plans
- payments
- enterprise tenancy
- mobile apps
- additional social networks
- advanced analytics
- click/conversion tracking
- ML recommendation
- AI agents
- autonomous browser agents
- complex event-driven architecture
- advanced content CMS
- influencer management
- campaign management
- affiliate network marketplace

---

# 23. Implementation Sequence

## Phase 0 — Live Verification

**Status:** partially verified. Manual Telegram publishing, image/affiliate-link
delivery, and scheduling were verified by the operator. Controlled live failure
and retry remain pending.

**Goal:** إكمال التحقق الحقيقي، وليس فقط عبر الاختبارات.

**Completion:**

```text
Discovery
 → AI
 → Queue
 → Schedule/Publish
 → Telegram
```

---

## Phase 1 — Recommendation Engine

**Status:** implemented and merged via PR #7.

**Goal:** تحويل scoring إلى recommendation.

**Work:**
1. commission filters
2. commission score
3. hard filters
4. ranking
5. Top N
6. recommendation settings
7. frontend
8. tests

**Completion:** المستخدم يحصل على توصيات حتمية وقابلة للتفسير بناءً على معاييره. **Implemented via PR #7.**

---

## Phase 2 — Onboarding

**Status:** Manual MVP Polish implemented and merged via PR #8. Public registration,
self-service workspace creation, and SaaS onboarding are explicitly deferred.

**Goal:** تحسين المسار اليدوي للمشغل الحالي.

**Work:**
1. recommended default discovery mode
2. Telegram setup guidance and permission refresh
3. validation, loading, and empty states
4. AI Studio handoff regression coverage

**Completion:** المشغل الحالي يستطيع بدء المسار اليدوي مع وضع Discovery الموصى به وإرشادات القنوات. Public registration وself-service onboarding مؤجلان.

---

## Phase 3 — Facebook

**Status:** Phase 3A, 3B, and 3C.1 implemented and merged via PRs #9–#11.
Phase 3C.2 is implemented and CI verified via PR #13; Phase 3C.3 is implemented and
CI verified via PR #15.

**Goal:** إضافة Facebook إلى نفس Queue.

**Work completed:** manual Page connection, encrypted token storage, Page
validation, text/photo publisher, provider-aware Queue/Celery integration,
frontend destination selection, and automated tests.

**Remaining:** PostgreSQL concurrency verification and Telegram live failure/retry
verification. OAuth and Facebook Login remain out of scope.

**Completion target:** Queue واحدة تنشر إلى Telegram أو Facebook، مع استكمال عرض الحالات وإعادة المحاولة الآمنة والتحقق الحي.

---

## Phase 4 — Dashboard

**Goal:** operational visibility without introducing a separate analytics or
publishing pipeline.

**Phase 4.2 — Backend snapshot:** implemented and CI verified via PR #17.

**Phase 4.3 — Dashboard UI:** implemented and CI verified via PR #18. The UI
shows authoritative KPIs, recent activity, attention items, readiness states,
and safe Queue deep links.

**Phase 4.4 — Realtime & reliability:** implemented and CI verified via PR #19.
Dashboard and Queue share the authenticated operational SSE lifecycle, use
workspace-scoped invalidation and bounded polling fallback, and revalidate at
the server-provided reporting-day boundary.

**Phase 4.5 — Final validation:** the closeout documents the acceptance matrix,
automated evidence, and remaining PostgreSQL/staging limitations. It does not
claim live publishing, exactly-once delivery, or full production readiness.

**Completion status:** implementation is complete; final validation is recorded
as partially verified until the explicitly listed operational gaps are exercised.

---

## Phase 5 — Automation Configuration

**Goal:** حفظ سياسة Automation.

**Phase 5B backend and Phase 5C frontend:** implemented, merged, and CI verified
through PRs #21 and #22 with migration `020`, workspace-scoped
`GET/PATCH /api/v1/automation/config`, virtual disabled defaults, destination
readiness, revision conflicts, and the Arabic RTL settings page. It stores
configuration intent only; execution remains unavailable.

**Completion:** المستخدم يستطيع إعداد:

```text
criteria
+
frequency
+
quantity
+
channel
+
content style
```

---

## Phase 6 — Auto Discovery

**Goal:** اكتشاف المنتجات تلقائياً.

**Phase 6B status:** the catalog-first discovery preview is implemented on the
current feature branch, with execution and Queue integration deferred. The
preview returns only bounded, active products with valid affiliate URLs after
workspace history exclusions and deterministic Recommendation Engine ranking.

---

## Phase 7 — Auto Content

**Goal:** إنشاء المحتوى تلقائياً.

**Phase 7B completion target:** each eligible selected product returns validated
content or an isolated failure without creating a Queue item. Queue integration
remains Phase 8 work.

---

## Phase 8 — Automation Queue

**Goal:** إدخال المنتجات تلقائياً إلى Queue.

**Completion:** Automation يستخدم `QueueService` نفسه.

---

## Phase 9 — Safety

**Goal:** منع spam والـ duplicates.

**Completion:** Automation يعمل بشكل متكرر بدون duplicate publishing غير مقصود.

---

## Phase 10 — Observability

**Goal:** معرفة نتائج Automation.

**Completion:** المستخدم يرى آخر Run وحالته ونتائجه.

---

## Phase 11 — Full Validation

**Status:** not implemented.

**MVP scope:** full manual and automated workflow validation, provider-specific
live delivery, failure/recovery, duplicate prevention, workspace isolation,
deployment configuration, backup/recovery, and safe automation pause.

**Acceptance:** the complete workflow is demonstrated with authorized test
destinations and documented evidence. Mocked CI alone is insufficient for MVP
completion.

اختبار:

```text
Manual
+
Automation
+
Telegram
+
Facebook
+
Retries
+
Deduplication
```

---

# 24. MVP Definition of Done — Manual

```text
[ ] Operator bootstrap/login flow is documented and usable
[ ] User can login
[ ] User can configure Telegram
[ ] User can discover products
[ ] User can filter products
[ ] Commission filtering works
[ ] Products receive deterministic scores
[ ] Commission affects scoring
[ ] User receives recommendations
[ ] User can select a product
[ ] Affiliate URL is preserved
[ ] AI receives affiliate URL
[ ] User can generate content
[ ] User can edit content
[ ] User can improve/regenerate content
[ ] User can queue content
[ ] Queue resolves the configured Telegram channel or validated Facebook Page
[ ] Queue contains affiliate CTA
[ ] Queue contains image when available
[ ] User can schedule content
[ ] Telegram publishing works
[ ] Publishing failures are visible
[ ] Failed items can be retried
[ ] Retry creates a new attempt
[ ] Duplicate publishing is prevented
[ ] product_url is never silently used as affiliate CTA
[ ] Dashboard exposes operational failures
[ ] Backend tests pass
[ ] Frontend tests pass
[ ] Manual Telegram core flow is verified; controlled failure/retry remains pending
```

---

# 25. MVP Definition of Done — Facebook

```text
[ ] User can connect Facebook through manual Page ID + Page Access Token setup
[ ] User can select a Page
[ ] Page token is stored securely
[ ] Token expiration is handled
[ ] User can select Facebook as provider
[ ] Queue supports Facebook
[ ] Facebook publisher works
[ ] Images work
[ ] Affiliate URL works
[ ] Failed Facebook posts are visible
[x] Facebook retry is safe for definitive failures; ambiguous retry requires explicit confirmation
[ ] Strict exactly-once Facebook delivery (not claimed; ambiguous provider outcomes require operator investigation)
[x] Integration tests and CI checks pass
[x] Controlled live Facebook text/photo/scheduled verification passes (operator-observed)
```

---

# 26. MVP Definition of Done — Automation

```text
[ ] User can enable Automation
[ ] User can configure criteria
[ ] User can configure product count
[ ] User can configure publishing schedule
[ ] User can select publishing channel
[ ] Scheduled Automation runs
[ ] Products are discovered
[ ] Hard filters are applied
[ ] Products are scored
[ ] Products are ranked
[ ] Top N are selected
[ ] Previously used products are deduplicated
[ ] AI generates content
[ ] Affiliate URL is validated
[ ] Queue items are created
[ ] Existing scheduler publishes them
[ ] Telegram publishing works
[ ] Facebook publishing works
[ ] One product failure does not stop the run
[ ] Duplicate posts are prevented
[ ] Stale publishing attempts are recoverable
[ ] Automation run status is recorded
[ ] Dashboard shows last run
[ ] Automation can be manually triggered
[ ] Automation tests pass
[ ] Unattended test run succeeds
```

---

# 27. Final Architecture

```text
                    ┌─────────────────┐
                    │      User       │
                    └────────┬────────┘
                             │
                 ┌───────────▼───────────┐
                 │      Next.js UI       │
                 └───────────┬───────────┘
                             │
                    ┌────────▼────────┐
                    │     FastAPI     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   Discovery             Recommendation       AI Content
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                        ┌────▼────┐
                        │  Queue  │
                        └────┬────┘
                             │
                        ┌────▼────┐
                        │Scheduler│
                        └────┬────┘
                             │
                     ┌───────▼────────┐
                     │    Publisher   │
                     └───────┬────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                Telegram          Facebook
```

Automation:

```text
                 ┌────────────────────┐
                 │ Automation Trigger │
                 └──────────┬─────────┘
                            │
                    ┌───────▼────────┐
                    │ Automation     │
                    │ Orchestrator   │
                    └───────┬────────┘
                            │
                ┌───────────▼───────────┐
                │ Existing Product A    │
                │ Services              │
                ├───────────────────────┤
                │ Discovery             │
                │ Recommendation        │
                │ AI Content            │
                │ Queue                 │
                └───────────┬───────────┘
                            │
                            ▼
                       Existing
                       Scheduler
                            │
                            ▼
                       Publishers
```

---

# 28. Final Recommendation

## 1. ماذا ننفذ أولاً؟

أولاً:

> **Live verification لـ Manual Telegram MVP foundation المدمجة عبر PR #5 (Roadmap Phase 0).**

ثم:

> **Recommendation Engine (Roadmap Phase 1).**

## 2. ماذا لا ننفذ الآن؟

لا نبدأ بـ:
- Automation
- AI agents
- ML
- advanced Facebook features
- analytics
- SaaS
- billing
- additional networks

## 3. ماذا نحافظ عليه؟

```text
Product
affiliate_url
commission_rate

Discovery Service
AliExpress client
Scoring
AIContentService
QueueService
Celery
Redis
TelegramPublisher
Dashboard
Auth
Workspace
SSE
```

## 4. ماذا نوسع؟

نوسع:

```text
scoring
workspace settings
queue
publisher layer
AI context
dashboard
Celery
```

بدلاً من إعادة بناء النظام.

## 5. ما الجداول الجديدة الضرورية؟

### Recommendation

يفضل عدم إنشاء جدول؛ نستخدم:

```text
workspace_settings
```

### Facebook

غالباً:

```text
facebook_pages
```

### Automation

غالباً:

```text
automation_runs
```

ولا نضيف Content table إلا إذا أثبت الاستخدام الفعلي أن server-side history/revisions مطلوبة.

## 6. ما Celery Tasks الجديدة الضرورية؟

الأساسي:

```text
run_due_automations
```

وstale-attempt cleanup فقط إذا تعذر دمجه في queue maintenance الحالي.

لا نحتاج Auto Publish Task منفصل.

## 7. أصغر Architecture تدعم Manual + Automation

```text
Discovery
    ↓
Recommendation
    ↓
AI Content
    ↓
Queue
    ↓
Scheduler
    ↓
Publisher
```

Manual:

```text
User → selects product → Queue
```

Automation:

```text
AutomationService → selects product → Queue
```

## 8. أكبر 5 مخاطر تقنية

1. Facebook OAuth/permissions.
2. Duplicate publishing.
3. Automation spam.
4. AI failures.
5. External API/token failures.

## 9. أكبر 5 مخاطر منتج

1. Recommendation quality.
2. Content quality.
3. Product availability.
4. Audience fit.
5. Automation trust.

لذلك:

> Automation يأتي بعد نجاح Manual MVP، وليس قبله.

---

# 29. المبدأ النهائي

الهدف ليس بناء architecture مثالية.

الهدف:

> **Build the smallest reliable Affiliate Marketing Assistant MVP that a real user can use end-to-end, then layer Automation on top of the same services and queue.**

المعادلة:

```text
Good Product
      +
Good Affiliate Opportunity
      +
Good Marketing Content
      +
Reliable Publishing
      =
Useful Affiliate Assistant
```

ثم:

```text
Same System
      +
Automation Orchestrator
      =
Auto Affiliate Assistant
```


---

# 30. Codex Execution Protocol (2026-10-26)

- اقرأ `AGENTS.md` قبل بدء أي عمل، ثم هذه الوثيقة، ثم افحص الكود الفعلي.
- هذه الوثيقة تحدد **الهدف والخطة**، أما الكود والاختبارات الحالية فتحدد **ما نُفّذ فعليًا**. أبلغ عن أي اختلاف ولا تفترض اكتمال ميزة بسبب وجودها هنا.
- لكل مرحلة: **inspect → propose scoped plan → implement only after approval → test → report → request approval before commit/push/PR**.
- ابدأ كل فرع ميزة من `main` المحدث بعد التأكد من نظافة working tree؛ لا تبدأ على فرع الدمج القديم.
- اختبارات CI لا تعوض اختبار نشر Telegram/Facebook الحقيقي؛ لا تضع علامة اكتمال على Live Verification قبل تأكيد التسليم.
- لا تلمس migrations `001–017`، وأي migration جديدة تبدأ بعد `017`.
- Recommendation Engine: حافظ على catalog scoring القديم، واجعل recommendation score مستقلاً وقابلاً للتفسير والاختبار؛ عالج القيم الناقصة وtie-breaking بشكل حتمي.
- لا تُنشئ نظام Queue أو Publisher جديدًا للأتمتة؛ استخدم الخدمات الموجودة.
- حدّث حالة هذه الوثيقة بعد قبول كل مرحلة، مع الإشارة إلى PR والاختبارات والتحقق العملي.
