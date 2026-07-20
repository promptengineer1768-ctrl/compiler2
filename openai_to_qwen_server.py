"""OpenAI-compatible API server bridging to Qwen via Playwright browser UI.

Uses a copy of the real Edge browser profile (avoids profile lock) and drives
the Qwen web UI to get past Alibaba's WAF. The browser session is reused;
each chat request types into the composer and scrapes the response.

Tool calling: Qwen web chat does not natively support tool/function calling.
We inject an XML tool contract into the prompt, then parse any
<tool_calls>...</tool_calls> emitted by the model into OpenAI-style tool_calls.

Run:
    python openai_to_qwen_server.py

Then point any OpenAI-compatible client at http://localhost:8000/v1
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, BrowserContext, Page

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("qwen-bridge")

app = FastAPI(title="OpenAI-to-Qwen Bridge (UI)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EDGE_USER_DATA = Path.home() / "AppData/Local/Microsoft/Edge/User Data"

# Dedicated thread + event loop for Playwright (avoids uvicorn loop conflicts).
_browser_loop: asyncio.AbstractEventLoop | None = None
_browser_thread: threading.Thread | None = None
_browser_ctx: BrowserContext | None = None
_page: Page | None = None
_profile_dir: Path | None = None


def _start_browser_thread() -> None:
    """Start a background thread with its own asyncio loop for Playwright."""
    global _browser_loop, _browser_thread
    if _browser_thread is not None and _browser_thread.is_alive():
        return
    if _browser_loop is not None:
        return

    def _run() -> None:
        global _browser_loop
        loop = asyncio.new_event_loop()
        _browser_loop = loop
        asyncio.set_event_loop(loop)
        loop.run_forever()

    _browser_thread = threading.Thread(target=_run, daemon=True)
    _browser_thread.start()
    # Wait for loop to be ready
    while _browser_loop is None:
        time.sleep(0.05)


def _run_async(coro: Any) -> Any:
    """Run a coroutine on the browser thread's event loop and return the result."""
    if _browser_loop is None:
        _start_browser_thread()
    future = asyncio.run_coroutine_threadsafe(coro, _browser_loop)
    return future.result(timeout=180)


def _copy_profile() -> Path:
    """Copy the real Edge profile to a temp dir to avoid lock conflicts."""
    tmp = Path(tempfile.mkdtemp(prefix="edge_qwen_"))
    dst = tmp / "Default"

    def ignore(src: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for n in names:
            low = n.lower()
            if (
                low.endswith(".journal")
                or "cookie" in low
                or low.startswith("session_")
                or low.startswith("tabs_")
                or low.endswith(".db-wal")
                or "cache.db" in low
            ):
                ignored.add(n)
        return ignored

    shutil.copytree(EDGE_USER_DATA / "Default", dst, dirs_exist_ok=True, ignore=ignore)
    return dst


def _ensure_browser() -> Page:
    global _browser_ctx, _page, _profile_dir
    if _page is not None:
        return _page

    async def _init() -> Page:
        global _browser_ctx, _page, _profile_dir
        log.warning("Copying Edge profile...")
        _profile_dir = _copy_profile()

        log.warning("Launching browser...")
        pw = await async_playwright().start()
        _browser_ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(_profile_dir),
            headless=True,
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        _page = _browser_ctx.pages[0] if _browser_ctx.pages else await _browser_ctx.new_page()

        log.warning("Navigating to chat.qwen.ai...")
        try:
            await _page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log.warning("Nav error (continuing): %s", e)
        await _page.wait_for_timeout(3000)
        log.warning("Browser ready. Title: %s", await _page.title())
        return _page

    return _run_async(_init())


def _build_tool_contract(tools: list[dict]) -> str:
    """Build an XML tool contract to inject into the user prompt."""
    if not tools:
        return ""
    lines = [
        "You have access to the following tools. To use a tool, respond EXACTLY with:",
        '<tool_calls>[{"name":"<tool_name>","arguments":{...json...}}]</tool_calls>',
        "Do not include any other text when calling a tool. Available tools:",
    ]
    for t in tools:
        fn = t.get("function", {})
        lines.append(f"- {fn.get('name')}: {fn.get('description', '')}")
        lines.append(f"  schema: {json.dumps(fn.get('parameters', {}))}")
    return "\n".join(lines)


_TOOL_CALL_RE = re.compile(r"<tool_calls>\s*(.*?)\s*</tool_calls>", re.DOTALL)

# Qwen web UI model identifiers supported by the bridge.
_MODEL_LABELS: dict[str, str] = {
    "qwen3.7-plus": "Qwen3.7-Plus",
    "qwen3.7-max": "Qwen3.7-Max",
    "qwen3.8-max-preview": "Qwen3.8-Max-Preview",
}
_SUPPORTED_MODELS = list(_MODEL_LABELS.keys())


def _resolve_model(model: str) -> str:
    """Map a requested model name to a supported Qwen UI model id."""
    m = (model or "").strip().lower()
    if m in _MODEL_LABELS:
        return m
    # Accept display-style names too (e.g. "Qwen3.7-Plus").
    inv = {v.lower(): k for k, v in _MODEL_LABELS.items()}
    if m in inv:
        return inv[m]
    # Default to the plus model if unknown.
    return "qwen3.7-plus"


async def _select_model(page: Page, model_id: str) -> None:
    """Select the model in the Qwen UI dropdown before sending."""
    label = _MODEL_LABELS.get(model_id, _MODEL_LABELS["qwen3.7-plus"])
    try:
        header = page.locator(".header-left").first
        if await header.count() == 0:
            return
        current = (await header.inner_text()).strip()
        if current == label:
            return
        await header.click()
        await page.wait_for_timeout(1500)
        item = page.locator(f"text={label}").first
        if await item.count() > 0:
            await item.click()
            await page.wait_for_timeout(1000)
    except Exception as e:
        log.warning("Model select failed (%s): %s", model_id, e)


def _parse_tool_calls(text: str) -> tuple[str, list[dict] | None]:
    """Extract tool calls from model output. Returns (clean_text, tool_calls)."""
    match = _TOOL_CALL_RE.search(text)
    if not match:
        return text, None
    raw = match.group(1).strip()
    try:
        calls = json.loads(raw)
    except json.JSONDecodeError:
        return text, None
    if not isinstance(calls, list):
        calls = [calls]
    tool_calls = []
    for i, c in enumerate(calls):
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": c.get("name", ""),
                "arguments": json.dumps(c.get("arguments", {})),
            },
        })
    # Strip the tool_calls block from visible text
    clean = text[: match.start()].strip()
    return clean, tool_calls


def _call_qwen(
    model: str, messages: list[dict], max_tokens: int | None, tools: list[dict] | None = None
) -> tuple[str, list[dict] | None]:
    """Send the conversation via the Qwen UI and return (text, tool_calls)."""
    page = _ensure_browser()

    async def _do() -> tuple[str, list[dict] | None]:
        # Build the user turn: last user message + tool contract if tools present.
        last_user = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user = m["content"] or ""
                break

        # Select the requested model in the UI dropdown.
        await _select_model(page, _resolve_model(model))

        if tools:
            contract = _build_tool_contract(tools)
            if contract:
                last_user = f"{last_user}\n\n{contract}"

        composer = page.locator("textarea").first
        if await composer.count() == 0:
            raise HTTPException(502, "Qwen composer not found")

        await composer.fill(last_user)
        await page.wait_for_timeout(400)

        send_btn = page.locator("button[type='submit']").first
        if await send_btn.count() > 0:
            await send_btn.click()
        else:
            await composer.press("Enter")

        await page.wait_for_timeout(4000)
        await page.wait_for_timeout(12000)

        msgs = page.locator("[class*='message-assistant'], [class*='assistant']")
        count = await msgs.count()
        if count == 0:
            main_text = await page.locator("main, #app").first.inner_text()
            text = main_text[-2000:]
        else:
            text = await msgs.nth(count - 1).inner_text()

        clean, tool_calls = _parse_tool_calls(text)
        return clean, tool_calls

    return _run_async(_do())


# ---------------------------------------------------------------------------
# Request / response models (OpenAI-compatible)
# ---------------------------------------------------------------------------


class Message(BaseModel):
    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class FunctionDef(BaseModel):
    name: str
    description: str = ""
    parameters: dict = {}


class Tool(BaseModel):
    type: str = "function"
    function: FunctionDef


class ChatCompletionRequest(BaseModel):
    model: str = "qwen3.7-plus"
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = 2048
    stream: bool = False
    tools: list[Tool] | None = None
    tool_choice: Any | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[dict] | None = None


class Choice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "qwen3.7-plus"
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> ChatCompletionResponse:
    qwen_messages = [{"role": m.role, "content": m.content or ""} for m in req.messages]
    tools = [t.model_dump() for t in (req.tools or [])]
    resolved = _resolve_model(req.model)
    try:
        text, tool_calls = _call_qwen(resolved, qwen_messages, req.max_tokens, tools or None)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Bridge error")
        raise HTTPException(502, f"Qwen bridge error: {e}")

    finish = "tool_calls" if tool_calls else "stop"
    return ChatCompletionResponse(
        model=resolved,
        choices=[Choice(
            message=ChoiceMessage(content=text, tool_calls=tool_calls),
            finish_reason=finish,
        )],
    )


@app.post("/v1/chat/mock")
async def chat_mock(req: ChatCompletionRequest) -> ChatCompletionResponse:
    last = req.messages[-1].content or ""
    return ChatCompletionResponse(
        model=f"{req.model} (mock)",
        choices=[Choice(message=ChoiceMessage(content=f"[mock echo] {last}"))],
    )


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": "qwen3.7-plus", "object": "model", "owned_by": "qwen",
             "description": "High-performance LLM with text + multimodal (vision/audio)."},
            {"id": "qwen3.7-max", "object": "model", "owned_by": "qwen",
             "description": "Flagship 3.7 series, text-only (no vision)."},
            {"id": "qwen3.8-max-preview", "object": "model", "owned_by": "qwen",
             "description": "Preview of upcoming flagship Qwen3.8, SOTA performance."},
        ],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    # Start the browser event loop first, then pre-warm the browser.
    _start_browser_thread()
    threading.Thread(target=_ensure_browser, daemon=True).start()


@app.on_event("shutdown")
async def shutdown():
    global _browser_ctx, _page, _profile_dir
    if _browser_loop is not None:
        _browser_loop.call_soon_threadsafe(_browser_loop.stop)
    _browser_ctx = None
    _page = None
    if _profile_dir:
        shutil.rmtree(_profile_dir, ignore_errors=True)
        _profile_dir = None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
