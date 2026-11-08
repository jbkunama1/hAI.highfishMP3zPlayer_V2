#!/usr/bin/env bash
set -Eeuo pipefail

trap 'printf "Web build failed at line %s\n" "$LINENO" >&2' ERR

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APK_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd -- "${APK_DIR}/.." && pwd)"
WEB_DIR="${APK_DIR}/www"

rm -rf -- "${WEB_DIR}"
mkdir -p -- "${WEB_DIR}"

copy_required() {
  local source="$1"
  local target="$2"
  if [[ ! -f "${REPO_DIR}/${source}" ]]; then
    printf 'Required frontend file is missing: %s\n' "${source}" >&2
    return 1
  fi
  install -m 0644 -- "${REPO_DIR}/${source}" "${WEB_DIR}/${target}"
}

# The player is the app entry point. The repository landing page is not bundled.
copy_required "samba-player.html" "index.html"
copy_required "id3-editor.html" "id3-editor.html"
copy_required "manifest.json" "manifest.json"
copy_required "sw.js" "sw.js"
copy_required "icon-192.png" "icon-192.png"
copy_required "icon-512.png" "icon-512.png"

for source in "${REPO_DIR}"/*.js; do
  [[ -f "${source}" ]] || continue
  install -m 0644 -- "${source}" "${WEB_DIR}/$(basename -- "${source}")"
done

if [[ ! -s "${WEB_DIR}/index.html" ]]; then
  printf 'Frontend output is empty: %s\n' "${WEB_DIR}/index.html" >&2
  exit 1
fi

if find "${WEB_DIR}" -type f \( -name '*.py' -o -name '*.env' -o -name '*.db' -o -name 'docker-compose*' -o -name 'Dockerfile' \) -print -quit | grep -q .; then
  printf 'Sensitive or server-only file detected in web bundle\n' >&2
  exit 1
fi

printf 'Frontend staged in %s\n' "${WEB_DIR}"
