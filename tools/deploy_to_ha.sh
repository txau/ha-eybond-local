#!/usr/bin/env bash
# Deploy local EyeBond Local tree to the Home Assistant host.
# Flow: SSH mux (password once) → rsync stage as user → one `sudo bash install.sh`.
#
# Usage:
#   ./tools/deploy_to_ha.sh
#   ./tools/deploy_to_ha.sh --no-restart
#
# Optional tools/deploy.env (gitignored) — see deploy.env.example.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/custom_components/eybond_local"

if [[ -f "${ROOT}/tools/deploy.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/tools/deploy.env"
  set +a
fi

HA_HOST="${HA_HOST:-}"
HA_USER="${HA_USER:-$(id -un)}"
HA_CONFIG="${HA_CONFIG:-/srv/homeassistant/.homeassistant}"
HA_CONTAINER="${HA_CONTAINER:-homeassistant}"
DEPLOY_BACKUP="${DEPLOY_BACKUP:-1}"
DO_RESTART=1

for arg in "$@"; do
  case "$arg" in
    --no-restart) DO_RESTART=0 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "${SRC}/manifest.json" ]]; then
  echo "ERROR: missing ${SRC}/manifest.json" >&2
  exit 1
fi

if [[ -z "${HA_HOST}" ]]; then
  echo "ERROR: HA_HOST is empty. Set it in tools/deploy.env." >&2
  exit 1
fi

DEST_COMPONENT="${HA_CONFIG}/custom_components/eybond_local"
STAMP="$(date +%Y%m%d%H%M%S)"
STAGE_REMOTE="/tmp/eybond_local_deploy_${STAMP}_${USER}"
CTRL_DIR="${ROOT}/.local"
mkdir -p "${CTRL_DIR}"
CTRL="${CTRL_DIR}/ssh_mux_%r@%h_%p"
SSH_BASE=(ssh -o ControlMaster=auto -o "ControlPath=${CTRL}" -o ControlPersist=120)
RSYNC_RSH="ssh -o ControlMaster=auto -o ControlPath=${CTRL} -o ControlPersist=120"

VERSION="$(python3 -c "import json; print(json.load(open('${SRC}/manifest.json'))['version'])" 2>/dev/null || echo unknown)"
GIT_DESC="$(git -C "${ROOT}" describe --always --dirty 2>/dev/null || echo nogit)"

echo "Source : ${SRC}"
echo "Version: ${VERSION} (${GIT_DESC})"
echo "Target : ${HA_USER}@${HA_HOST}:${DEST_COMPONENT}"
echo "Stage  : ${STAGE_REMOTE}"
echo "Restart: ${DO_RESTART} (container ${HA_CONTAINER})"
echo

cleanup_mux() {
  "${SSH_BASE[@]}" -O exit "${HA_USER}@${HA_HOST}" 2>/dev/null || true
}
trap cleanup_mux EXIT

echo "Opening SSH session (SSH password once if needed)..."
"${SSH_BASE[@]}" -fNM "${HA_USER}@${HA_HOST}"

echo "Staging files as ${HA_USER} (no sudo)..."
"${SSH_BASE[@]}" "${HA_USER}@${HA_HOST}" "rm -rf $(printf '%q' "${STAGE_REMOTE}") && mkdir -p $(printf '%q' "${STAGE_REMOTE}")"
rsync -a --delete -e "${RSYNC_RSH}" "${SRC}/" "${HA_USER}@${HA_HOST}:${STAGE_REMOTE}/eybond_local/"

# Build remote install script with baked-in paths (sudo can use the TTY).
INSTALL_LOCAL="$(mktemp)"
trap 'rm -f "${INSTALL_LOCAL}"; cleanup_mux' EXIT
cat >"${INSTALL_LOCAL}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
HA_CONFIG=$(printf '%q' "${HA_CONFIG}")
DEST=$(printf '%q' "${DEST_COMPONENT}")
STAGE=$(printf '%q' "${STAGE_REMOTE}")
STAMP=$(printf '%q' "${STAMP}")
CONTAINER=$(printf '%q' "${HA_CONTAINER}")
DO_RESTART=$(printf '%q' "${DO_RESTART}")
DEPLOY_BACKUP=$(printf '%q' "${DEPLOY_BACKUP}")

mkdir -p "\${HA_CONFIG}/custom_components"

if [[ "\${DEPLOY_BACKUP}" == "1" && -d "\${DEST}" ]]; then
  mv "\${DEST}" "\${DEST}.bak.\${STAMP}"
  echo "Backed up -> \${DEST}.bak.\${STAMP}"
fi

rm -rf "\${DEST}"
mv "\${STAGE}/eybond_local" "\${DEST}"
rm -rf "\${STAGE}"

find "\${DEST}" -type d -exec chmod 755 {} +
find "\${DEST}" -type f -exec chmod 644 {} +

test -f "\${DEST}/protocol_catalogs/register_schemas/sumry_ges_7530/base.json"
echo "OK: sumry_ges_7530 schema present"
python3 -c "import json; print('manifest', json.load(open('\${DEST}/manifest.json'))['version'])"

if [[ "\${DO_RESTART}" == "1" ]]; then
  docker restart "\${CONTAINER}"
  echo "Restarted container \${CONTAINER}"
else
  echo "Skipped restart"
fi
EOF

rsync -a -e "${RSYNC_RSH}" "${INSTALL_LOCAL}" "${HA_USER}@${HA_HOST}:${STAGE_REMOTE}/install.sh"
"${SSH_BASE[@]}" "${HA_USER}@${HA_HOST}" "chmod +x $(printf '%q' "${STAGE_REMOTE}/install.sh")"

echo "Installing with sudo (sudo password once if needed)..."
"${SSH_BASE[@]}" -t "${HA_USER}@${HA_HOST}" "sudo $(printf '%q' "${STAGE_REMOTE}/install.sh")"

echo "Done. Give HA ~30–60s, then check Runtime Driver State / battery sensors."
