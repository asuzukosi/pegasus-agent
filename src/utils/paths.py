from pathlib import Path


def resolve_path(base: str | Path, path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return Path(base).resolve() / path

def display_path_rel_to_cwd(path: str, cwd: Path| None) -> str:
    try:
        p = Path(path)
    except Exception:
        return path
    if cwd:
        try:
            return str(p.relative_to(cwd))
        except ValueError:
            return str(p)
        except Exception:
            return str(p)
    return str(p)

def is_binary_file(path: str | Path) -> bool:
    try:
        with open(path, "rb") as file:
            chunk = file.read(8192)
            return b"\x00" in chunk or b"\xFF" in chunk
    except (OSError, IOError):
        return False