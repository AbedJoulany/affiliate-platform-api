# Product A MVP — Implementation Roadmap

> **Document status:** Active roadmap. Updated 2026-10-26 for the Codex handover.  
> **Repository:** `AbedJoulany/affiliate-platform-api`  
> **Development baseline:** `main`, after PR #5 (`feat: integrate Manual Telegram MVP Phase 1`) was merged.  
> **Verification source:** PR merge and passing CI were confirmed by the project owner; a live Telegram delivery has **not** been confirmed.  
> **Next gate:** Live Manual Telegram Verification; then Recommendation Engine.

### Naming convention

- **Completed foundation — Manual Telegram MVP (historically called “Phase 1”):** implementation merged via PR #5. This is **not** the same as Roadmap Phase 1.
- **Roadmap Phase 0:** Live Manual Verification (pending).
- **Roadmap Phase 1:** Recommendation Engine (not started).
- **Roadmap Phases 2–11:** subsequent work as numbered below.
- A merged PR and green mocked CI do **not** substitute for a live provider test.

### Current delivery status

| Deliverable | Status | Evidence / next action |
| --- | --- | --- |
| Product B removal | Merged | Historical migrations `001–017` retained |
| Manual Telegram MVP code | Merged | PR #5 integrated into `main` |
| PR #5 CI | Passed (owner-confirmed) | Backend, frontend and E2E checks reported green; check workflow records for exact details |
| Live Telegram publishing | Pending | Run end-to-end verification with real credentials and confirm message delivery |
| Recommendation Engine | Not started | Begin only after the Phase 0 verification gate, or explicitly record an exception |
| Onboarding / Facebook / Automation | Planned | Follow roadmap phases |

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

> الترقيم التالي يخص **Roadmap** فقط؛ لا تخلطه مع اسم مرحلة Manual Telegram MVP السابقة. حالة Phase 0: pending. حالة Phase 1 وما بعدها: not started.

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

إثبات أن Phase 1 تعمل فعلياً، وليس فقط عبر الاختبارات.

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

## الهدف

إضافة Facebook كـ Publisher ثانٍ بدون Queue ثانية.

```text
Queue Item
 ↓
Provider
 ├── Telegram
 └── Facebook
```

## Connection

```text
OAuth
 ↓
Facebook User
 ↓
Pages
 ↓
Select Page
 ↓
Store Page Token
```

لا تخزن credentials في frontend.

## Database

غالباً جدول:

```text
facebook_pages
```

بالحد الأدنى:

```text
id
workspace_id
page_id
page_name
access_token
token_expires_at
is_active
created_at
updated_at
```

## Queue

نحافظ على Queue واحدة. قد يكون التصميم:

```text
provider = telegram
channel_id = ...

provider = facebook
facebook_page_id = ...
```

التصميم النهائي يتبع النماذج الحالية.

## Publisher

إذا كان مناسباً:

```text
Publisher
 ├── TelegramPublisher
 └── FacebookPublisher
```

## Facebook MVP

يدعم:
- text
- image
- affiliate URL / link
- publish
- retry
- failure handling

خارج النطاق:
- Reels
- Stories
- comments
- advanced insights
- campaign management

---

# 9. Phase 4 — Operational Dashboard

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

الخيار المفضل:

> Extend `workspace_settings`.

لا ننشئ Automation Settings table إلا إذا كانت بنية settings الحالية غير مناسبة.

---

# 11. Phase 6 — Auto Discovery

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

Automation لا ينشر مباشرة.

```text
Automation
 ↓
QueueService.create()
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

وبعد Queue يصبح المسار واحداً.

---

# 14. Phase 9 — Safety & Idempotency

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
001 → 017
```

لا تعدل.

أي schema change جديد يبدأ بعد 017.

المحتمل:
- Recommendation: غالباً بدون migration.
- Facebook: `facebook_pages` + أي queue/provider columns مطلوبة.
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

**Goal:** إثبات أن Manual Telegram MVP يعمل فعلياً.

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

**Completion:** المستخدم يحصل على توصيات بناءً على معاييره.

---

## Phase 2 — Onboarding

**Goal:** تشغيل مستخدم جديد بدون bootstrap يدوي.

**Work:**
1. registration
2. workspace creation
3. membership
4. settings
5. Telegram setup

**Completion:** مستخدم جديد يستطيع البدء.

---

## Phase 3 — Facebook

**Goal:** إضافة Facebook إلى نفس Queue.

**Work:**
1. OAuth
2. Page selection
3. token storage
4. publisher
5. queue integration
6. retry/failure
7. UI
8. tests

**Completion:** Queue واحدة تنشر إلى Telegram أو Facebook.

---

## Phase 4 — Dashboard

**Goal:** operational visibility.

**Work:**
- failed count
- publishing state
- recent failures
- recommendation summary
- channel status

**Completion:** المستخدم يعرف حالة النظام بسهولة.

---

## Phase 5 — Automation Configuration

**Goal:** حفظ سياسة Automation.

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

**Completion:** Automation Run ينتج Top N منتجات صالحة.

---

## Phase 7 — Auto Content

**Goal:** إنشاء المحتوى تلقائياً.

**Completion:** كل منتج صالح ينتج Queue Item أو failure مستقل.

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
[ ] User can register
[ ] User receives a workspace
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
[ ] Queue resolves Telegram channel
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
[ ] Manual Telegram E2E verification passes
```

---

# 25. MVP Definition of Done — Facebook

```text
[ ] User can connect Facebook
[ ] User can select a Page
[ ] Page token is stored securely
[ ] Token expiration is handled
[ ] User can select Facebook as provider
[ ] Queue supports Facebook
[ ] Facebook publisher works
[ ] Images work
[ ] Affiliate URL works
[ ] Failed Facebook posts are visible
[ ] Facebook retry works
[ ] Facebook publishing is idempotent
[ ] Integration tests pass
[ ] Manual live Facebook verification passes
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
