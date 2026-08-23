# Web redesign mockup: Match Picker

An interactive design mockup for the `packages/web` page, produced 2026-08-23.
Design reference only. No code changes in this folder, and nothing here runs in
the build.

The live, clickable prototype lives on a Claude design canvas (league tabs
filter, per-match "Why?" expanders, cohort switcher). Ask Rob for the share
link. `Main.dc.html` and `canvas.json` are the canvas source files, kept here
so the mockup can be re-seeded and edited later. They use the canvas editor's
Design Component format and will not render standalone in a browser.

## Design decisions

| Decision | Value |
|---|---|
| Layout | Cream sheet (`#FDFBF6`), 40px corners, floating on a light pink field (`#F7E3EC`) |
| Primary accent | Deep raspberry `#B23A72`, light pink tint `#FCE1EC` |
| UI purple | `#5B4A9E` (All-matches tab, cohort chips), tint `#EDE9F7` |
| League hues | Premier League pink, La Liga lemon (`#8A6A00` / `#FBF0C8`), Serie A mint (`#17795A` / `#D6F2E3`) |
| Score bands | 75+ coral (`#B23F16` / `#FFE3D8`), 50 to 74 butter (`#8A6A00` / `#FFF1C6`), under 50 sky (`#2F6BAE` / `#DCEBFB`), unscored grey with a "?" |
| Type | Fredoka (display, scores, wordmark) + Figtree (body), both Google Fonts |
| Wordmark | Text only: "x" in `#B23A72`, "FUN" in `#5B4A9E`. Tagline: "We find the soccer worth yelling at." |
| Copy rules | No em dashes, no rhetorical questions, 5th-grade reading level |

Kept on purpose from the current page (they are product decisions, not
placeholders): the percentile-cohort explainer, the placeholder-models banner,
the unscored match shown with its skip reason, and the
"where to watch: unknown" state.

## Data in the mockup

Matches come from `contracts/fixtures/snapshots/`. The scores and model
weights are demo values in the fixture style. The real models predict nothing
yet; see `docs/STUBS.md`. Broadcasters follow actual US league rights (NBC,
Peacock, USA Network, ESPN+, Paramount+).

## Club crests

Deliberately not committed. Club crests are trademarked, so this repo does not
redistribute them. The mockup references them by filename (`ars.png`,
`liv.png`, ...). To rebuild the full mockup locally, run `./fetch-crests.sh`
in this folder; it pulls each crest from ESPN's public logo CDN. Shipping
crests in the real product needs a licensing decision first.

## If the team likes it

Implementation would target `packages/web` (Zone C, hand-edit freely, no
specs). Fonts, the candy palette tokens, and the card layout translate
directly to `styles.css`; the tabs and expanders are small state additions to
`App.tsx`.
