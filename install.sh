#!/usr/bin/env bash
set -euo pipefail

package_name="pegasus-ai"
declare -a pipx_cmd

print_info() {
  printf '%s\n' "$1"
}

print_error() {
  printf '%s\n' "$1" >&2
}

if ! command -v python3 >/dev/null 2>&1; then
  print_error "python3 is required but was not found"
  exit 1
fi

ensure_pipx() {
  if command -v pipx >/dev/null 2>&1; then
    pipx_cmd=(pipx)
    return 0
  fi

  if python3 -m pipx --version >/dev/null 2>&1; then
    pipx_cmd=(python3 -m pipx)
    return 0
  fi

  print_info "pipx not found, installing pipx with python3 -m pip --user"
  python3 -m pip install --upgrade --user pipx
  python3 -m pipx ensurepath >/dev/null 2>&1 || true
  pipx_cmd=(python3 -m pipx)
}

if ensure_pipx; then
  print_info "installing ${package_name} with pipx"
  "${pipx_cmd[@]}" install "${package_name}" || "${pipx_cmd[@]}" upgrade "${package_name}"
  print_info "installing chromium for browser_use"
  "${pipx_cmd[@]}" run --spec playwright playwright install chromium
else
  print_info "pipx setup failed, installing ${package_name} with python3 -m pip --user"
  python3 -m pip install --upgrade --user "${package_name}"
  print_info "installing chromium for browser_use"
  python3 -m playwright install chromium
fi

print_info ""
print_info "pegasus installed successfully"
print_info "next steps:"
print_info "  export API_KEY=\"your-openrouter-key\" (get key from https://openrouter.ai/keys)"
print_info "  pegasus-cli"
