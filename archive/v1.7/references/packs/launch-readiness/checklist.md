# launch-readiness pack

Commercial + store prep before **human** submit. Reviewer or script; never auto-submit.

## Positioning & GTM

- [ ] `docs/product/positioning.md` exists and matches current MVP scope
- [ ] `docs/product/gtm-lite.md` launch slice matches what is built
- [ ] `marketing.site` hero CTA URL resolves (staging or prod)
- [ ] Promo / i18n keys consistent: marketing ↔ app (per `gtm-lite` table)

## Monetization

- [ ] `docs/product/monetization-brief.md` present if any paid surface
- [ ] Paywall copy does not contradict `monetization-brief` tiers
- [ ] Human acknowledged pricing on issue (comment or decision)

## Store / ASC / Play (if in scope)

- [ ] Listing draft complete (title, subtitle, description)
- [ ] Screenshots match HIG / store guidelines (spot check)
- [ ] Privacy policy URL live and linked
- [ ] Age rating / data safety answers consistent with app behavior

## Analytics

- [ ] North star event defined in `analytics-growth.md`
- [ ] At least funnel events implemented or ticketed for launch CP

## Labels

- [ ] Issue has `commercial-baseline-done` when profile requires **and** `commercial_baseline` not in `factory.waived_baselines` / not `pilot_mode` without MVO files (`envision-handoff.md`)
- [ ] `scope_triage` launch items marked keep are shipped or explicitly waived

## Output

```json
{ "pass": true, "findings": [] }
```

Pass = all blockers checked; minors documented in findings with waiver link to human `ask`.
