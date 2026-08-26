# web

⚠️ **PLACEHOLDER-ish.** Real code, one page, no routing or filtering.

Vite + React. One page: matches ranked by composed score, with the contributing
model scores and the calibration cohort.

```bash
pnpm install
pnpm client:generate   # types from contracts/openapi.yaml — REQUIRED
pnpm web:dev           # http://localhost:5173
```

`pnpm client:generate` is not optional: the generated types are gitignored, and
without them `web:dev` still serves with every type silently `any`.

Needs the API already running, with something in the store:

```bash
uv run python scripts/pipeline.py            # acquire and score; needs network
uv run uvicorn xfun_api:app --port 8000      # in another terminal
```

**Both ports are load-bearing.** The page reads `VITE_API_URL`, defaulting to
`http://localhost:8000`, and the API allows cross-origin requests from
`http://localhost:5173` and nothing else (`packages/api/src/xfun_api/main.py`).
Moving either one without the other gets you a CORS error in the browser console and
an empty page. To point the page at an API elsewhere:

```bash
VITE_API_URL=http://localhost:9000 pnpm web:dev
```

## The cohort is displayed on purpose

A score of 91 means "91st percentile among the matches in this window", not "91
out of 100". Under a season cohort the same match scores differently. Showing a
bare number would train people to read it as an absolute rating, which it is not.

## Not built

Routing, date picker, filtering, availability display beyond "unknown". The page
requests no dates and renders whatever window the API reports, so it follows the last
pipeline run. See [docs/STUBS.md](../../docs/STUBS.md).
