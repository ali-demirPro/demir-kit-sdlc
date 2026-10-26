# Cost and tiers

Budget band (architect estimate): **… / month** at MVP scale.

## Services

| Service | Tier | Free quota | Current zone | Policy |
|---------|------|------------|--------------|--------|
| Example DB | free | 500 MB, 2M rows | green | dev + staging only |
| CI | free | 2000 min/mo | green | cache deps |
| … | … | … | green \| yellow \| red | … |

**Zone:** green &lt;70% quota, yellow 70–90%, red &gt;90% or blocked.

## Usage rules

- Do not enable paid features without ADR + issue.
- …

## Tier exit triggers

| Trigger | Service | Planned action | Issues |
|---------|---------|----------------|--------|
| &gt;10k MAU | Auth provider | Upgrade plan | #… |
| Need realtime | DB | Paid tier or self-host | #… |

## Next steps (when exiting free tier)

1. …
2. …
3. Rollback: …

## Review log

| Date | Reviewer | Notes |
|------|----------|-------|
| … | architect | initial baseline |
