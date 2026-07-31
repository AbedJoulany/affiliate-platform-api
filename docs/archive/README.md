# Archived Documentation

On **2026-07-29**, root-level `ARCHITECTURE.md` and `HANDOFF.md` were consolidated into the standard `01`–`10` documentation suite under `/docs`.

Content migration map:

| Legacy file | Primary destination |
| --- | --- |
| `ARCHITECTURE.md` | `01-project-overview.md`, `02-frontend-architecture.md`, `10-production-readiness.md` |
| `HANDOFF.md` | `01-project-overview.md`, `06-api-integration.md`, `08-implementation-roadmap.md`, `10-production-readiness.md` |

Do not recreate standalone architecture/handoff files — update the numbered suite instead.

---

On **2026-07-29**, the `docs/planning/publishing-reliability-status-truth-roadmap.md` milestone proposal was reviewed, approved, and merged into `08-implementation-roadmap.md` §3 (replacing the Phase A/B/C ordering with `A.1 → A.2 → B → C' → D → E`). The original proposal is archived here as [`publishing-reliability-status-truth-roadmap.md`](./publishing-reliability-status-truth-roadmap.md) for historical reference only — `08-implementation-roadmap.md` is the source of truth for this milestone going forward.
