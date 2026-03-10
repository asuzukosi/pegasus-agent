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

set_pipx_command() {
  if command -v pipx >/dev/null 2>&1; then
    pipx_cmd=(pipx)
    return 0
  fi

  if python3 -m pipx --version >/dev/null 2>&1; then
    pipx_cmd=(python3 -m pipx)
    return 0
  fi

  return 1
}

install_pipx_with_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    return 1
  fi

  print_info "pipx not found, installing pipx with homebrew"
  brew install pipx
}

install_pipx_with_pip() {
  print_info "pipx not found, installing pipx with python3 -m pip --user"

  if python3 -m pip install --upgrade --user pipx; then
    return 0
  fi

  print_info "retrying pipx installation with --break-system-packages"
  python3 -m pip install --upgrade --user --break-system-packages pipx
}

ensure_pipx() {
  if set_pipx_command; then
    return 0
  fi

  if install_pipx_with_brew && set_pipx_command; then
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
    return 0
  fi

  if install_pipx_with_pip && set_pipx_command; then
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
    return 0
  fi

  return 1
}

if ensure_pipx; then
  print_info "installing ${package_name} with pipx"
  "${pipx_cmd[@]}" install "${package_name}" || "${pipx_cmd[@]}" upgrade "${package_name}"
  print_info "installing chromium for browser_use"
  "${pipx_cmd[@]}" run --spec playwright playwright install chromium
else
  print_error "unable to install pipx automatically"
  print_error "install pipx manually and rerun this script"
  print_error "recommended options:"
  print_error "  brew install pipx"
  print_error "  python3 -m pip install --user --break-system-packages pipx"
  exit 1
fi

print_info ""
print_info "pegasus installed successfully"
print_info "next steps:"
print_info "  export API_KEY=\"your-openrouter-key\" (get key from https://openrouter.ai/keys)"
print_info "  pegasus-cli"
