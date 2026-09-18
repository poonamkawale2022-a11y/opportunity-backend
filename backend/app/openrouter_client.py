"""OpenRouter LLM gateway: chat completions + real tool-calling loop + fallback."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Optional

import httpx

from .config import get_settings, model_candidates
from .schemas import AGENT_TOOLS


def _headers() -> dict:
    s = get_settings()
    h = {"Authorization": f"Bearer {s.OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    if s.OPENROUTER_SITE_URL:
        h["HTTP-Referer"] = s.OPENROUTER_SITE_URL
    if s.OPENROUTER_SITE_NAME:
        h["X-OpenRouter-Title"] = s.OPENROUTER_SITE_NAME
    return h


class OpenRouterError(Exception):
    def __init__(self, msg: str, status: int = 0):
        super().__init__(msg)
        self.status = status


def chat(messages: list[dict], model: str = "", tools: list[dict] | None = None,
         tool_choice: Any = None, response_format: dict | None = None,
         max_tokens: int = 1500, temperature: float = 0.3,
         timeout: Optional[int] = None) -> dict:
    s = get_settings()
    if not s.OPENROUTER_API_KEY:
        raise OpenRouterError("OPENROUTER_API_KEY is not configured", status=401)
    tried: list[str] = []
    errors: list[str] = []
    for m in ([model] if model else []) + [c for c in model_candidates() if c != model]:
        tried.append(m)
        body: dict[str, Any] = {"model": m, "messages": messages,
                                "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format is not None:
            body["response_format"] = response_format
        t0 = time.time()
        try:
            with httpx.Client(timeout=timeout or s.OPENROUTER_TIMEOUT_S) as c:
                r = c.post(f"{s.OPENROUTER_BASE_URL}/chat/completions",
                           headers=_headers(), json=body)
            latency = round((time.time() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                data["_latency_ms"] = latency
                data["_model"] = m
                return data
            if r.status_code in (429, 500, 502, 503, 504):
                errors.append(f"{m}: {r.status_code}")
                continue  # fallback to next model
            raise OpenRouterError(f"OpenRouter {r.status_code}: {r.text[:400]}",
                                  status=r.status_code)
        except OpenRouterError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            errors.append(f"{m}: transport {e}")
            continue
    raise OpenRouterError(f"All models failed ({', '.join(tried)}): {'; '.join(errors)}", status=502)


def minimal_ping() -> dict:
    t0 = time.time()
    try:
        data = chat([{"role": "user", "content": "Reply with exactly: ok"}],
                    max_tokens=10, temperature=0)
        ch = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        return {"ok": True, "model": data.get("_model"), "content": ch,
                "usage": data.get("usage", {}),
                "latency_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_json(text: str) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


def agent_loop(system: str, user: str, executors: dict[str, Callable[[dict], Any]],
               tools: list[dict] | None = None, max_iterations: int = 0,
               context: dict | None = None, history: list[dict] | None = None) -> dict:
    """Real LLM tool loop: LLM -> tool_calls -> execute -> feed back -> repeat."""
    s = get_settings()
    max_iterations = max_iterations or s.MAX_AGENT_ITERATIONS
    tool_log: list[dict] = []
    messages: list[dict] = [{"role": "system", "content": system}]
    for m in (history or [])[-10:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:2000]})
    messages.append({"role": "user", "content": user})
    calls = 0
    final_text = ""
    for _ in range(max_iterations):
        try:
            data = chat(messages, tools=tools or AGENT_TOOLS, tool_choice="auto")
        except OpenRouterError as e:
            return {"ok": False, "error": str(e), "tool_calls": tool_log,
                    "final": final_text, "fallback": True}
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        tcs = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         **({"tool_calls": tcs} if tcs else {})})
        if not tcs:
            final_text = msg.get("content") or ""
            return {"ok": True, "tool_calls": tool_log, "final": final_text,
                    "model": data.get("_model")}
        for tc in tcs:
            if calls >= s.MAX_TOOL_CALLS_PER_RUN:
                break
            calls += 1
            fn = (tc.get("function") or {}).get("name", "")
            raw_args = (tc.get("function") or {}).get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                args = {}
            t0 = time.time()
            try:
                fn_impl = executors.get(fn)
                result = fn_impl(args, context or {}) if fn_impl else {"error": f"unknown tool {fn}"}
                status = "ok"
            except Exception as e:
                result = {"error": str(e)}
                status = "error"
            latency = round((time.time() - t0) * 1000)
            tool_log.append({"tool": fn, "args": args, "status": status,
                             "latency_ms": latency})
            messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                             "name": fn,
                             "content": json.dumps(result, default=str)[:6000]})
    if not final_text and tool_log:
        # tools ran but the loop ran out of turns: one final no-tool call
        # to phrase the results instead of dying with "max iterations reached"
        try:
            done = chat(messages + [{"role": "user", "content":
                "Summarize what the tool results above found in 3-5 short lines. Plain words, no jargon."}],
                max_tokens=500, temperature=0.2)
            final_text = ((done.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        except Exception:
            pass
    return {"ok": True, "tool_calls": tool_log, "final": final_text or "max iterations reached"}
