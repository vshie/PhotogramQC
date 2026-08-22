#!/usr/bin/env bash
# Assemble a versioned download for one CI target.
# Usage: package-release.sh <target> <version>
#   target: windows-x64 | macos-arm64 | linux-x86_64 | linux-arm64
set -euo pipefail

target="${1:?target is required}"
version="${2:?version is required}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dist="$root/dist"
out="$root/dist-release"
name="PhotogramQC-${version}-${target}"

mkdir -p "$out"
rm -rf "$out/$name" "$out/$name".*

_stage_macos_app() {
  local app="$dist/PhotogramQC.app"
  if [[ ! -d "$app" ]]; then
    local bin=""
    if [[ -f "$dist/PhotogramQC" ]]; then
      bin="$dist/PhotogramQC"
    elif [[ -f "$dist/PhotogramQC.exe" ]]; then
      bin="$dist/PhotogramQC.exe"
    fi
    if [[ -z "$bin" ]]; then
      echo "ERROR: no macOS app or PhotogramQC binary in dist/" >&2
      ls -la "$dist" >&2 || true
      exit 1
    fi
    app="$dist/PhotogramQC.app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
    cp "$bin" "$app/Contents/MacOS/PhotogramQC"
    chmod +x "$app/Contents/MacOS/PhotogramQC"
    cat > "$app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>PhotogramQC</string>
  <key>CFBundleDisplayName</key><string>PhotogramQC</string>
  <key>CFBundleIdentifier</key><string>com.vshie.photogramqc</string>
  <key>CFBundleVersion</key><string>${version}</string>
  <key>CFBundleShortVersionString</key><string>${version}</string>
  <key>CFBundleExecutable</key><string>PhotogramQC</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
  fi
  mkdir -p "$out/$name"
  cp -R "$app" "$out/$name/PhotogramQC.app"
  cp "$root/scripts/macos-first-open.txt" "$out/$name/HOW-TO-OPEN.txt"
  (cd "$out" && zip -r "${name}.zip" "$name")
  rm -rf "$out/$name"
}

_stage_linux() {
  local bin="$dist/PhotogramQC"
  if [[ ! -f "$bin" ]]; then
    echo "ERROR: dist/PhotogramQC not found" >&2
    ls -la "$dist" >&2 || true
    exit 1
  fi
  mkdir -p "$out/$name"
  cp "$bin" "$out/$name/PhotogramQC"
  chmod +x "$out/$name/PhotogramQC"
  cp "$root/scripts/linux-run.txt" "$out/$name/HOW-TO-RUN.txt"
  tar -C "$out" -czf "$out/${name}.tar.gz" "$name"
  rm -rf "$out/$name"
}

_stage_windows() {
  local exe="$dist/PhotogramQC.exe"
  if [[ ! -f "$exe" ]]; then
    echo "ERROR: dist/PhotogramQC.exe not found" >&2
    ls -la "$dist" >&2 || true
    exit 1
  fi
  cp "$exe" "$out/${name}.exe"
}

case "$target" in
  macos-*) _stage_macos_app ;;
  linux-*) _stage_linux ;;
  windows-*) _stage_windows ;;
  *)
    echo "ERROR: unknown target: $target" >&2
    exit 1
    ;;
esac

echo "Packaged:"
ls -la "$out"
