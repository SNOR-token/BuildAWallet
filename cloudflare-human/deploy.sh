#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! npx --yes wrangler d1 list --json > .d1-list.json; then
  echo 'Wrangler cannot access Cloudflare. Run: npx wrangler login' >&2
  exit 1
fi

match_count=$(python3 - <<'PYCOUNT'
import json
with open('.d1-list.json') as source:
    print(sum(row.get('name') == 'buildawallet' for row in json.load(source)))
PYCOUNT
)
if [ "$match_count" -gt 1 ]; then
  echo 'Multiple D1 databases named buildawallet; resolve this before deploying.' >&2
  exit 1
fi
if [ "$match_count" -eq 0 ]; then
  npx --yes wrangler d1 create buildawallet
  npx --yes wrangler d1 list --json > .d1-list.json
fi

python3 - <<'PY'
import json
from pathlib import Path
entries = json.loads(Path('.d1-list.json').read_text())
matches = [entry for entry in entries if entry.get('name') == 'buildawallet']
if len(matches) != 1:
    raise SystemExit('Expected exactly one D1 database named buildawallet')
identifier = matches[0].get('uuid') or matches[0].get('id')
if not identifier:
    raise SystemExit('D1 database ID missing from Wrangler output')
config = Path('wrangler.jsonc').read_text().replace('00000000-0000-4000-8000-000000000001', identifier)
Path('wrangler.deploy.jsonc').write_text(config)
PY

./prepare.sh
npx --yes wrangler d1 migrations apply buildawallet --remote --config wrangler.deploy.jsonc
uv run pywrangler deploy --config wrangler.deploy.jsonc

curl --fail --silent --show-error https://buildawallet.xyz/api/start > /dev/null
curl --fail --silent --show-error https://buildawallet.xyz/healthz
curl --fail --silent --show-error https://buildawallet.xyz/api/stats > /dev/null

# This unauthenticated probe must never receive Studio HTML or a missing-config 503.
studio_status=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-redirs 0 https://buildawallet.xyz/studio)
case "$studio_status" in
  302|303|401|403) ;;
  *) echo "Studio Access check failed (HTTP $studio_status). Verify Pages Access and ACCESS_TEAM_DOMAIN / ACCESS_AUD." >&2; exit 1 ;;
esac
