from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pegasus.config.config import Config
from pegasus.tools.base import Tool
from pegasus.tools.data import ToolInvocation, ToolResult, ToolType
from pegasus.utils.images import tool_image_from_path, write_cv2_frame


class VisionCaptureParams(BaseModel):
    duration_seconds: int = Field(
        ...,
        ge=10,
        le=50,
        description="The capture duration in seconds. Must be between 10 and 50 seconds.",
    )
    camera_index: int = Field(0, ge=0, description="The camera device index to capture from.")
    max_frames: int = Field(
        6,
        ge=2,
        le=10,
        description="The maximum number of frames to keep for the next model turn.",
    )


class VisionCaptureTool(Tool):
    name: str = "vision_capture"
    description: str = (
        "Capture a short window of camera frames and return representative images "
        "for visual follow-up in the next model step."
    )
    type: ToolType = ToolType.READ
    schema: VisionCaptureParams = VisionCaptureParams

    def __init__(self, config: Config) -> None:
        self._config = config

    def _artifact_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._config.cwd / ".pegasus" / "artifacts" / "vision_capture" / stamp

    def _capture_frames(self, params: VisionCaptureParams) -> dict[str, Any]:
        import cv2

        window_name = f"pegasus - {params.duration_seconds}s"
        window_created = False
        cap = cv2.VideoCapture(params.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"unable to open camera index {params.camera_index}")

        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            window_created = True
            start = time.monotonic()
            sample_interval = max(0.5, params.duration_seconds / params.max_frames)
            next_sample = start
            captured_paths: list[str] = []
            frame_count = 0
            artifact_dir = self._artifact_dir()

            while True:
                ret, frame = cap.read()
                if not ret:
                    raise RuntimeError("failed to read frame from camera")

                frame_count += 1
                display_frame = cv2.resize(frame, (800, int(frame.shape[0] * 800 / frame.shape[1])))
                elapsed_seconds = max(0.0, time.monotonic() - start)
                remaining_seconds = max(0.0, params.duration_seconds - elapsed_seconds)
                cv2.rectangle(display_frame, (0, 0), (display_frame.shape[1], 48), (0, 0, 0), -1)
                cv2.putText(
                    display_frame,
                    f"capture duration: {params.duration_seconds}s",
                    (16, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display_frame,
                    f"time remaining: {remaining_seconds:.1f}s",
                    (16, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, display_frame)
                cv2.waitKey(1)

                now = time.monotonic()
                if now >= next_sample and len(captured_paths) < params.max_frames:
                    frame_index = len(captured_paths) + 1
                    frame_path = write_cv2_frame(
                        artifact_dir / f"frame_{frame_index:02d}.jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
                    )
                    captured_paths.append(frame_path.as_posix())
                    next_sample = now + sample_interval

                if now - start >= params.duration_seconds:
                    break

                time.sleep(0.03)

            return {
                "paths": captured_paths,
                "frame_count": frame_count,
            }
        finally:
            cap.release()
            if window_created:
                try:
                    cv2.destroyWindow(window_name)
                    cv2.waitKey(1)
                except Exception:
                    # fall back to a broader cleanup if the named window is already gone
                    cv2.destroyAllWindows()
                    cv2.waitKey(1)

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = VisionCaptureParams(**invocation.params)
        capture_result = self._capture_frames(params)
        image_paths = capture_result["paths"]
        if not image_paths:
            return ToolResult.error_result("vision capture completed but no frames were saved")

        images = [tool_image_from_path(path, "image/jpeg") for path in image_paths]
        output_lines = [
            f"captured camera frames for {params.duration_seconds} seconds.",
            f"saved {len(image_paths)} representative frames for the next visual reasoning step.",
            "frame files:",
        ]
        output_lines.extend(f"- {path}" for path in image_paths)
        return ToolResult.success_result(
            output="\n".join(output_lines),
            images=images,
            metadata={
                "duration_seconds": params.duration_seconds,
                "camera_index": params.camera_index,
                "frame_count": capture_result["frame_count"],
                "image_paths": image_paths,
                "image_mime_types": ["image/jpeg"] * len(image_paths),
                "visual_context_message": (
                    "camera frames from the previous tool call are attached. "
                    "use them as the latest visual scene context before deciding the next action."
                ),
            },
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"error executing vision capture tool with error: {e}")
