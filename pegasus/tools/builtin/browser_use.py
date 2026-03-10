from __future__ import annotations

import asyncio
import io
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from pegasus.config.config import Config
from pegasus.tools.base import Tool
from pegasus.tools.data import ToolInvocation, ToolResult, ToolType
from pegasus.utils.images import show_image, tool_image_from_path
from pegasus.utils.paths import ensure_parent_directory


class BrowserUseAction(str, Enum):
    OPEN = "open"
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    WAIT = "wait"
    STATE = "state"
    CLOSE = "close"

    def __str__(self) -> str:
        return self.value


class BrowserUseParams(BaseModel):
    action: str = Field(
        ...,
        description="The browser action to perform. Actions are: open, click, type, press, scroll, wait, state, close",
    )
    url: str | None = Field(None, description="The url to open when action is 'open'.")
    element_id: int | None = Field(
        None,
        description="The clickable element id from the latest annotated screenshot. Used by click and type actions.",
    )
    text: str | None = Field(None, description="The text to type when action is 'type'.")
    key: str | None = Field(None, description="The key to press when action is 'press'.")
    direction: str = Field(
        "down",
        description="The scroll direction for scroll actions. Valid values are up, down, left, right.",
    )
    amount: int = Field(800, ge=50, le=4000, description="The scroll distance in pixels.")
    wait_seconds: float = Field(
        1.0,
        ge=0.1,
        le=30.0,
        description="How long to wait when action is 'wait' or after certain browser interactions.",
    )
    clear_first: bool = Field(
        True,
        description="Whether to clear the existing field contents before typing.",
    )


class BrowserUseTool(Tool):
    name: str = "browser_use"
    description: str = (
        "Control a live browser using clickable ids from an annotated screenshot. "
        "Each call returns a fresh screenshot with clickable elements overlaid so the next model step can use the latest visual browser state."
    )
    type: ToolType = ToolType.NETWORK
    schema: BrowserUseParams = BrowserUseParams
    WINDOW_WIDTH = 1440
    WINDOW_HEIGHT = 960
    VIEWPORT_WIDTH = 1280
    VIEWPORT_HEIGHT = 840

    def __init__(self, config: Config) -> None:
        self._config = config
        self._instance_id = uuid4().hex[:8]
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._step = 0

    async def _ensure_page(self):
        from playwright.async_api import async_playwright

        async with self._lock:
            if self._page is not None and not self._page.is_closed():
                return self._page
            self._page = None
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[f"--window-size={self.WINDOW_WIDTH},{self.WINDOW_HEIGHT}"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": self.VIEWPORT_WIDTH, "height": self.VIEWPORT_HEIGHT}
            )
            self._page = await self._context.new_page()
            await self._page.bring_to_front()
            return self._page

    def _artifact_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self._config.cwd / ".pegasus" / "artifacts" / "browser_use" / self._instance_id / stamp

    def _safe_label(self, value: str) -> str:
        safe = re.sub(r"[^0-9a-zA-Z._-]+", "_", value).strip("_")
        return safe or "state"

    async def _wait_for_page_ready(self, page, timeout_ms: int = 10000) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return

    async def _get_clickable_elements(self, page) -> list[dict[str, Any]]:
        return await page.evaluate(
            """() => {
                const results = [];
                const selectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [onclick]';
                let visibleIndex = 0;
                document.querySelectorAll(selectors).forEach((el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const centerX = Math.min(Math.max(rect.left + rect.width / 2, 0), Math.max(window.innerWidth - 1, 0));
                    const centerY = Math.min(Math.max(rect.top + rect.height / 2, 0), Math.max(window.innerHeight - 1, 0));
                    const topElement = document.elementFromPoint(centerX, centerY);
                    const occluded = !!topElement && topElement !== el && !el.contains(topElement);
                    const hidden =
                        rect.width < 2 ||
                        rect.height < 2 ||
                        rect.bottom < 0 ||
                        rect.right < 0 ||
                        rect.top > window.innerHeight ||
                        rect.left > window.innerWidth ||
                        style.visibility === 'hidden' ||
                        style.display === 'none' ||
                        occluded;
                    if (hidden) {
                        el.removeAttribute('data-pegasus-tool-id');
                        return;
                    }
                    el.setAttribute('data-pegasus-tool-id', String(visibleIndex));
                    results.push({
                        index: visibleIndex,
                        tag: (el.tagName || '').toLowerCase(),
                        type: el.type || '',
                        text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 80),
                        x: Math.round(rect.left),
                        y: Math.round(rect.top),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                    });
                    visibleIndex += 1;
                });
                return results;
            }"""
        )

    def _element_color(self, tag: str) -> str:
        return {
            "input": "blue",
            "textarea": "blue",
            "select": "purple",
            "button": "red",
            "a": "green",
        }.get(tag, "orange")

    def _render_elements(self, elements: list[dict[str, Any]], limit: int = 40) -> str:
        if not elements:
            return "no clickable elements found."
        lines = ["clickable elements:"]
        for element in elements[:limit]:
            label = element.get("text") or "(no text)"
            tag = element.get("tag") or "unknown"
            lines.append(f'- id={element["index"]} tag={tag} text="{label}"')
        if len(elements) > limit:
            lines.append(f"...truncated to {limit} of {len(elements)} elements")
        return "\n".join(lines)

    async def _dismiss_blocking_overlay(self, page) -> list[str]:
        selectors = [
            "#onetrust-accept-btn-handler",
            "button[aria-label*='accept' i]",
            "button[aria-label*='agree' i]",
            "button[aria-label*='close' i]",
            "button:has-text('accept all')",
            "button:has-text('accept')",
            "button:has-text('agree')",
            "button:has-text('got it')",
            "button:has-text('continue')",
            "button:has-text('close')",
        ]
        dismissed: list[str] = []
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if await locator.count() == 0:
                    continue
                if not await locator.is_visible():
                    continue
                await locator.click(timeout=1500)
                dismissed.append(selector)
                await asyncio.sleep(0.3)
                break
            except Exception:
                continue
        if dismissed:
            return dismissed
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            dismissed.append("keyboard:escape")
        except Exception:
            return dismissed
        return dismissed

    async def _click_locator(self, page, locator, timeout_ms: int = 5000) -> None:
        try:
            await locator.click(timeout=timeout_ms)
            return
        except Exception as e:
            if "intercepts pointer events" not in str(e).lower():
                raise
        dismissed = await self._dismiss_blocking_overlay(page)
        if dismissed:
            await locator.click(timeout=timeout_ms)
            return
        raise RuntimeError("click was blocked by an overlay intercepting pointer events")

    async def _capture_state_payload(self, page, action_label: str) -> tuple[str, list[Any], dict[str, Any]]:
        await self._wait_for_page_ready(page)
        elements = await self._get_clickable_elements(page)
        raw_screenshot = await page.screenshot(type="png")
        image = Image.open(io.BytesIO(raw_screenshot)).convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        for element in elements:
            x = element["x"]
            y = element["y"]
            width = element["width"]
            height = element["height"]
            label = str(element["index"])
            color = self._element_color(element.get("tag", ""))
            draw.rectangle([x, y, x + width, y + height], outline=color, width=2)
            badge_width = max(18, len(label) * 8 + 6)
            draw.rectangle([x, y + height, x + badge_width, y + height + 16], fill=color)
            draw.text((x + 3, y + height + 2), label, fill="white", font=font)

        artifact_dir = self._artifact_dir()
        self._step += 1
        screenshot_path = ensure_parent_directory(
            artifact_dir / f"{self._step:03d}_{self._safe_label(action_label)}_annotated.png"
        )
        image.save(screenshot_path)
        show_image(screenshot_path, "browser use")

        output_lines = [
            f"browser action completed: {action_label}",
            f"url: {page.url}",
            f"annotated screenshot: {screenshot_path.as_posix()}",
            self._render_elements(elements),
        ]
        if await page.title():
            output_lines.insert(2, f"title: {await page.title()}")
        metadata = {
            "browser_instance_id": self._instance_id,
            "url": page.url,
            "title": await page.title(),
            "image_paths": [screenshot_path.as_posix()],
            "image_mime_types": ["image/png"],
            "clickable_count": len(elements),
            "action": action_label,
            "visual_context_message": (
                "browser screenshot from the previous tool call is attached. "
                "use the latest page state and clickable ids from the screenshot before deciding the next browser action."
            ),
        }
        return "\n".join(output_lines), [tool_image_from_path(screenshot_path, "image/png")], metadata

    async def _error_with_state(self, message: str) -> ToolResult:
        if self._page is None:
            return ToolResult.error_result(message)
        try:
            output, images, metadata = await self._capture_state_payload(self._page, "error_state")
            return ToolResult.error_result(message, output=output, images=images, metadata=metadata)
        except Exception:
            return ToolResult.error_result(message)

    async def _get_target_locator(self, element_id: int):
        if self._page is None:
            raise RuntimeError("browser is not open")
        locator = self._page.locator(f'[data-pegasus-tool-id="{element_id}"]').first
        if await locator.count() == 0:
            raise ValueError(f"element id {element_id} is not available in the current page state")
        return locator

    async def _execute(self, invocation: ToolInvocation) -> ToolResult:
        params = BrowserUseParams(**invocation.params)

        if params.action == BrowserUseAction.CLOSE:
            await self.close()
            return ToolResult.success_result(
                "browser session closed",
                metadata={"action": "close", "browser_instance_id": self._instance_id},
            )

        page = await self._ensure_page()

        try:
            if params.action == BrowserUseAction.OPEN:
                if not params.url:
                    return ToolResult.error_result("url is required when action is 'open'")
                await page.goto(params.url)
                await self._wait_for_page_ready(page)
                output, images, metadata = await self._capture_state_payload(page, f"open_{params.url}")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.CLICK:
                if params.element_id is None:
                    return ToolResult.error_result("element_id is required when action is 'click'")
                locator = await self._get_target_locator(params.element_id)
                await self._click_locator(page, locator)
                await asyncio.sleep(params.wait_seconds)
                output, images, metadata = await self._capture_state_payload(page, f"click_{params.element_id}")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.TYPE:
                if params.element_id is None:
                    return ToolResult.error_result("element_id is required when action is 'type'")
                if params.text is None:
                    return ToolResult.error_result("text is required when action is 'type'")
                locator = await self._get_target_locator(params.element_id)
                await self._click_locator(page, locator)
                if params.clear_first:
                    await locator.fill(params.text)
                else:
                    await locator.type(params.text)
                await asyncio.sleep(params.wait_seconds)
                output, images, metadata = await self._capture_state_payload(page, f"type_{params.element_id}")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.PRESS:
                if not params.key:
                    return ToolResult.error_result("key is required when action is 'press'")
                await page.keyboard.press(params.key)
                await asyncio.sleep(params.wait_seconds)
                output, images, metadata = await self._capture_state_payload(page, f"press_{params.key}")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.SCROLL:
                delta_x = 0
                delta_y = 0
                direction = params.direction.strip().lower()
                if direction == "down":
                    delta_y = params.amount
                elif direction == "up":
                    delta_y = -params.amount
                elif direction == "right":
                    delta_x = params.amount
                elif direction == "left":
                    delta_x = -params.amount
                else:
                    return ToolResult.error_result("invalid scroll direction. valid values are: up, down, left, right")
                await page.mouse.wheel(delta_x, delta_y)
                await asyncio.sleep(params.wait_seconds)
                output, images, metadata = await self._capture_state_payload(page, f"scroll_{direction}")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.WAIT:
                await asyncio.sleep(params.wait_seconds)
                output, images, metadata = await self._capture_state_payload(page, "wait")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            if params.action == BrowserUseAction.STATE:
                output, images, metadata = await self._capture_state_payload(page, "state")
                return ToolResult.success_result(output=output, images=images, metadata=metadata)

            return ToolResult.error_result(
                f"invalid action: {params.action}. valid actions are: {', '.join(action.value for action in BrowserUseAction)}"
            )
        except Exception as e:
            return await self._error_with_state(f"error executing browser action '{params.action}': {e}")

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            return await self._execute(invocation)
        except Exception as e:
            return ToolResult.error_result(f"error executing browser use tool with error: {e}")

    async def close(self) -> None:
        if self._page is not None:
            await self._page.close()
            self._page = None
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
