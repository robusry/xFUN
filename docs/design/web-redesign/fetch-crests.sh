#!/usr/bin/env bash
# Pull the club crests the mockup references from ESPN's public logo CDN.
# They are trademarked, so the repo does not commit them; fetch locally instead.
set -euo pipefail
cd "$(dirname "$0")"

declare -A ids=(
  [ars]=359 [liv]=364 [mci]=382 [tot]=367 [che]=363 [mun]=360
  [new]=361 [bre]=337 [bha]=331 [eve]=368 [bur]=379 [shu]=398
  [rma]=86 [get]=2922 [int]=110 [tor]=239
)

for k in "${!ids[@]}"; do
  curl -fsS "https://a.espncdn.com/i/teamlogos/soccer/500/${ids[$k]}.png" -o "$k.png"
  echo "fetched $k.png"
done
