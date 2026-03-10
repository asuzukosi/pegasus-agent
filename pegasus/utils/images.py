from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from pegasus.tools.data import ToolImage
from pegasus.utils.paths import ensure_parent_directory


def infer_image_mime_type(path: str | Path, fallback: str = "image/png") -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    return fallback


def image_file_to_data_url(path: str | Path, mime_type: str | None = None) -> str:
    path = Path(path)
    resolved_mime_type = mime_type or infer_image_mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{resolved_mime_type};base64,{encoded}"


def tool_image_from_path(path: str | Path, mime_type: str | None = None) -> ToolImage:
    path = Path(path).resolve()
    resolved_mime_type = mime_type or infer_image_mime_type(path)
    return ToolImage(
        data_url=image_file_to_data_url(path, resolved_mime_type),
        mime_type=resolved_mime_type,
        path=path.as_posix(),
    )


def write_image_bytes(path: str | Path, content: bytes) -> Path:
    path = ensure_parent_directory(path)
    path.write_bytes(content)
    return path


def write_cv2_frame(path: str | Path, frame, params: list[int] | None = None) -> Path:
    import cv2

    path = ensure_parent_directory(path)
    if not cv2.imwrite(path.as_posix(), frame, params or []):
        raise RuntimeError(f"failed to write image to {path.as_posix()}")
    return path


def show_image(path: str | Path, window_name: str = "pegasus") -> None:
    import cv2

    image = cv2.imread(Path(path).as_posix())
    if image is None:
        return
    cv2.imshow(window_name, image)
    cv2.waitKey(1)
