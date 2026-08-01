# docs/

Start here if you are new to the project.

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | The tiers, the contracts between them, and why scoring is batch rather than on-demand |
| [workflow.md](workflow.md) | Branches, pull requests, commits, and how a change reaches `main` |
| [zones.md](zones.md) | When a change needs specs and when it does not, plus both contribution paths |
| [STUBS.md](STUBS.md) | Every placeholder in the repository and the change that replaces it |

## Reading order

If you have ten minutes, read `architecture.md` and then run the demo:

```bash
./scripts/demo.sh
```

If you are about to contribute, read `workflow.md` and `zones.md` first — they
determine whether your change needs an OpenSpec change and how it gets merged.

If you are wondering whether something is real: **`STUBS.md`**. This repository is
currently a walking skeleton, and knowing what is placeholder is the difference
between building on the structure and building on sand.

## The specs

Behavioral requirements live in `openspec/specs/`, not here. These documents explain
and orient; the specs are normative. Where they disagree, the specs win and this
directory has a bug.
