# @xfun/client

Typed client for the xFUN API.

```bash
pnpm client:generate   # writes src/generated.d.ts from contracts/openapi.yaml
```

**The types are generated; only the fetch plumbing is written by hand.**
`src/generated.d.ts` is gitignored — checking it in would create a second place
for the API's shape to live, and it would drift.

If a response shape changes in the contract, this package stops typechecking. That
is the point.
