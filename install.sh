#!/usr/bin/env bash
set -euo pipefail

package_name="pegasus-ai"
declare -a python_cmd
declare -a pipx_cmd

print_info() {
  printf '%s\n' "$1"
}

print_error() {
  printf '%s\n' "$1" >&2
}

set_python_command() {
  if command -v python3 >/dev/null 2>&1; then
    python_cmd=(python3)
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    python_cmd=(python)
    return 0
  fi

  if command -v py >/dev/null 2>&1; then
    python_cmd=(py -3)
    return 0
  fi

  return 1
}

detect_platform() {
  case "$(uname -s)" in
    Darwin)
      printf '%s\n' "macos"
      ;;
    Linux)
      if [ -f /etc/os-release ]; then
        if grep -qi '^id=ubuntu$' /etc/os-release || grep -qi '^id_like=.*ubuntu' /etc/os-release; then
          printf '%s\n' "ubuntu"
          return
        fi
      fi
      printf '%s\n' "linux"
      ;;
    MINGW*|MSYS*|CYGWIN*)
      printf '%s\n' "windows"
      ;;
    *)
      if [ "${OS:-}" = "Windows_NT" ]; then
        printf '%s\n' "windows"
      else
        printf '%s\n' "unknown"
      fi
      ;;
  esac
}

run_with_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  return 1
}

if ! set_python_command; then
  print_error "python is required but was not found"
  exit 1
fi

set_pipx_command() {
  if command -v pipx >/dev/null 2>&1; then
    pipx_cmd=(pipx)
    return 0
  fi

  if "${python_cmd[@]}" -m pipx --version >/dev/null 2>&1; then
    pipx_cmd=("${python_cmd[@]}" -m pipx)
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

install_pipx_with_apt() {
  if [ "$(detect_platform)" != "ubuntu" ] || ! command -v apt-get >/dev/null 2>&1; then
    return 1
  fi

  print_info "pipx not found, installing pipx with apt"
  run_with_sudo apt-get update
  run_with_sudo apt-get install -y pipx
}

install_pipx_on_windows() {
  if [ "$(detect_platform)" != "windows" ]; then
    return 1
  fi

  print_info "pipx not found, installing pipx on windows with python"
  "${python_cmd[@]}" -m pip install --upgrade --user pipx
}

install_pipx_with_pip() {
  print_info "pipx not found, installing pipx with python -m pip --user"

  if "${python_cmd[@]}" -m pip install --upgrade --user pipx; then
    return 0
  fi

  print_info "retrying pipx installation with --break-system-packages"
  "${python_cmd[@]}" -m pip install --upgrade --user --break-system-packages pipx
}

print_manual_pipx_install_help() {
  case "$(detect_platform)" in
    macos)
      print_error "recommended action for macos:"
      print_error "  brew install pipx"
      ;;
    ubuntu)
      print_error "recommended action for ubuntu:"
      print_error "  sudo apt-get update && sudo apt-get install -y pipx"
      ;;
    windows)
      print_error "recommended action for windows:"
      print_error "  py -3 -m pip install --user pipx"
      ;;
    *)
      print_error "recommended action:"
      print_error "  python -m pip install --user --break-system-packages pipx"
      ;;
  esac
}

ensure_pipx() {
  if set_pipx_command; then
    return 0
  fi

  if install_pipx_with_brew && set_pipx_command; then
    "${pipx_cmd[@]}" ensurepath >/dev/null 2>&1 || true
    return 0
  fi

  if install_pipx_with_apt && set_pipx_command; then
    "${pipx_cmd[@]}" ensurepath >/dev/null 2>&1 || true
    return 0
  fi

  if install_pipx_on_windows && set_pipx_command; then
    "${pipx_cmd[@]}" ensurepath >/dev/null 2>&1 || true
    return 0
  fi

  if install_pipx_with_pip && set_pipx_command; then
    "${pipx_cmd[@]}" ensurepath >/dev/null 2>&1 || true
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
  print_manual_pipx_install_help
  exit 1
fi

print_info ""
print_info "pegasus installed successfully"
print_info "next steps:"
print_info "  export API_KEY=\"your-openrouter-key\" (get key from https://openrouter.ai/keys)"
print_info "  pegasus-cli"
