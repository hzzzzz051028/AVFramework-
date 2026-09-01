#!/usr/bin/env bash
# Build the isolated UxPlay AirPlay receiver used by the RK3588 compatibility POC.
# Requires network access on the build host and the packages documented below.
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/screencast/vendor/uxplay}"
UXPLAY_REPOSITORY="${UXPLAY_REPOSITORY:-https://github.com/FDH2/UxPlay.git}"
# Pinned after a successful Orange Pi 5 Pro build on 2026-09-01.
UXPLAY_REVISION="${UXPLAY_REVISION:-aec205d49302df8d4eb291b9e927ed428b2d0166}"

for required in cmake make g++ pkg-config git; do
  command -v "$required" >/dev/null || {
    echo "Missing build tool: $required" >&2
    exit 1
  }
done

for package in libssl-dev libplist-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev; do
  dpkg -s "$package" >/dev/null 2>&1 || {
    echo "Missing package: $package" >&2
    exit 1
  }
done

build_dir="$(mktemp -d /tmp/screencast-uxplay.XXXXXX)"
trap 'rm -rf "$build_dir"' EXIT

git clone "$UXPLAY_REPOSITORY" "$build_dir/source"
git -C "$build_dir/source" checkout --detach "$UXPLAY_REVISION"

# Ubuntu 20.04 exports libplist 2.1 as pkg-config module "libplist", while
# upstream checks only "libplist-2.0" for the feature-level API probe.
# Keep support for distributions using the latter module name as a fallback.
python3 - "$build_dir/source/lib/CMakeLists.txt" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace(
    '   pkg_check_modules ( PLIST_21 libplist-2.0>=2.1.0 )',
    '   pkg_check_modules ( PLIST_21 libplist>=2.1.0 )\n'
    '   if ( NOT PLIST_21_FOUND )\n'
    '     pkg_check_modules ( PLIST_21 libplist-2.0>=2.1.0 )\n'
    '   endif()',
)
text = text.replace(
    '   pkg_check_modules ( PLIST_23 libplist-2.0>=2.3.0 )',
    '   pkg_check_modules ( PLIST_23 libplist>=2.3.0 )\n'
    '   if ( NOT PLIST_23_FOUND )\n'
    '     pkg_check_modules ( PLIST_23 libplist-2.0>=2.3.0 )\n'
    '   endif()',
)
path.write_text(text)

renderer = path.parent.parent / 'renderers' / 'video_renderer.c'
text = renderer.read_text()
old = '                    g_string_append(launch, decoder);'
new = '''                    g_string_append(launch, decoder);
                    /* Keep compressed H.264 intact.  Only discard stale,
                     * decoded raw frames if KMS falls behind. */
                    g_string_append(launch, " ! queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream ");'''
if old not in text:
    raise SystemExit('UxPlay decoder insertion point changed; refusing to build an unverified patch')
renderer.write_text(text.replace(old, new, 1))
PY

cmake -S "$build_dir/source" -B "$build_dir/build" \
  -DNO_X11_DEPS=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_ROOT"
cmake --build "$build_dir/build" --parallel 2
sudo cmake --install "$build_dir/build"
"$INSTALL_ROOT/bin/uxplay" -h | head -3
echo "UxPlay POC installed to $INSTALL_ROOT"
