#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION="$(python3 -c 'import moah_launcher; print(moah_launcher.__version__)')"
NAME="moah-project-launcher"
ROOT="$(mktemp -d)"
STAGE="${ROOT}/${NAME}_${VERSION}_all"
mkdir -p "${STAGE}/DEBIAN" \
  "${STAGE}/usr/bin" \
  "${STAGE}/usr/share/${NAME}" \
  "${STAGE}/usr/share/applications"

cp -a moah_launcher "${STAGE}/usr/share/${NAME}/"
find "${STAGE}" -type d -name __pycache__ -print0 | xargs -0r rm -rf
find "${STAGE}" -name '*.pyc' -delete
find "${STAGE}/usr/share/${NAME}" -type d -exec chmod 755 {} +
find "${STAGE}/usr/share/${NAME}" -type f -exec chmod 644 {} +

cat > "${STAGE}/usr/bin/${NAME}" << 'EOF'
#!/usr/bin/python3
import sys

sys.path.insert(0, "/usr/share/moah-project-launcher")
from moah_launcher.__main__ import main

raise SystemExit(main())
EOF
chmod 755 "${STAGE}/usr/bin/${NAME}"

install -m 644 packaging/moah-project-launcher.desktop \
  "${STAGE}/usr/share/applications/moah-project-launcher.desktop"
desktop-file-validate packaging/moah-project-launcher.desktop

cat > "${STAGE}/DEBIAN/control" << EOF
Package: ${NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.11), python3-pyqt6
Maintainer: MOAH Project Launcher <noreply@localhost>
Description: Launcher local de projetos para o Cursor
 Encontra projetos nas pastas escolhidas e abre cada pasta no Cursor.
 Toda a operação é local, sem login e sem serviços externos.
EOF

mkdir -p dist
OUT="dist/${NAME}_${VERSION}_all.deb"
rm -f "${OUT}"
dpkg-deb --root-owner-group -Zxz --build "${STAGE}" "${OUT}"
rm -rf "${ROOT}"
echo "Pacote gerado: ${OUT}"
