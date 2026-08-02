# web

⚠️ **PLACEHOLDER-ish.** Real code, one page, hardcoded date window.

Vite + React. One page: matches ranked by composed score, with the contributing
model scores and the calibration cohort.

```bash
pnpm install
pnpm client:generate   # types from contracts/openapi.yaml
pnpm web:dev           # http://localhost:5173
```

Needs the API running — `./scripts/demo.sh`.

## The cohort is displayed on purpose

A score of 91 means "91st percentile among the matches in this window", not "91
out of 100". Under a season cohort the same match scores differently. Showing a
bare number would train people to read it as an absolute rating, which it is not.

## Not built

Routing, date picker, filtering, availability display beyond "unknown". The date
window is hardcoded to match the fixtures. See
[docs/STUBS.md](../../docs/STUBS.md).
