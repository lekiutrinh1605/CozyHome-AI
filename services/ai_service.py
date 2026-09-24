"""Gọi LLM qua lớp trừu tượng nhà cung cấp (Giai đoạn 3).

Model chính đã chốt: Gemini 3.7 Flash (Google), model ID API ổn định
`gemini-3.7-flash` (đã kiểm chứng qua tài liệu chính thức - KHÔNG dùng alias cuốn
chiếu như `gemini-flash-latest` để kết quả thử nghiệm tái lập được khi chấm lại).
Giá 0,75 USD/1 triệu token input, 3,75 USD/1 triệu token output (đến hết năm 2026).
Kiến trúc tách theo AI_PROVIDER để không khóa cứng vào một nhà cung cấp.

Biến môi trường (đọc từ .env qua python-dotenv, KHÔNG hard-code key vào file này):
    AI_PROVIDER=gemini
    AI_MODEL=gemini-3.7-flash
    GEMINI_API_KEY=...
"""
import os
import sys
import time
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(override=True)

AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.7-flash")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")

_gemini_client = None
_anthropic_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("Chưa đặt GEMINI_API_KEY (biến môi trường hoặc .env).")
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("Chưa đặt ANTHROPIC_API_KEY hoặc CLAUDE_API_KEY (biến môi trường hoặc .env).")
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _call_gemini(system_instruction, prompt_text, model, response_schema=None, timeout_s=30):
    from google.genai import types

    client = _get_gemini_client()
    config_kwargs = {"system_instruction": system_instruction}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_json_schema"] = response_schema
    config = types.GenerateContentConfig(**config_kwargs)

    candidate_models = [model]
    for alt in [
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-3.0-flash-lite",
        "gemini-3.7-pro",
        "gemini-3.5-pro",
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    max_retries = 5
    last_err = None
    for current_model in candidate_models:
        for attempt in range(max_retries):
            try:
                t0 = time.monotonic()
                resp = client.models.generate_content(model=current_model, contents=prompt_text, config=config)
                elapsed_s = time.monotonic() - t0

                return {
                    "text": resp.text,
                    "elapsed_s": elapsed_s,
                    "raw_finish_reason": getattr(getattr(resp, "candidates", [None])[0], "finish_reason", None)
                        if getattr(resp, "candidates", None) else None,
                }
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if "404" in err_msg or "NOT_FOUND" in err_msg:
                    # Model not available, break to next candidate model
                    break
                if "503" in err_msg or "UNAVAILABLE" in err_msg:
                    # Model is experiencing high demand, break to next candidate model
                    break
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    # In interactive chat, do not sleep 30s; try next candidate model or failover quickly
                    break
                raise

    if last_err is not None:
        raise last_err
    raise RuntimeError(f"Không thể kết nối Gemini API (đã thử: {candidate_models}).")


def _call_anthropic(system_instruction, prompt_text, model, response_schema=None, timeout_s=30):
    client = _get_anthropic_client()

    candidate_models = [model]
    for alt in [
        "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    max_retries = 5
    last_err = None
    for current_model in candidate_models:
        for attempt in range(max_retries):
            try:
                t0 = time.monotonic()
                resp = client.messages.create(
                    model=current_model,
                    max_tokens=4096,
                    system=system_instruction,
                    messages=[{"role": "user", "content": prompt_text}],
                    timeout=timeout_s,
                )
                elapsed_s = time.monotonic() - t0

                text = ""
                if resp.content:
                    text = "".join(block.text for block in resp.content if hasattr(block, "text"))

                return {
                    "text": text,
                    "elapsed_s": elapsed_s,
                    "raw_finish_reason": getattr(resp, "stop_reason", None),
                }
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if "404" in err_msg or "not_found" in err_msg.lower():
                    # Model not available, break to next candidate model
                    break
                if "529" in err_msg or "overloaded_error" in err_msg.lower() or "503" in err_msg:
                    wait_time = min(30.0, (2 ** attempt) + 3.0)
                    print(f"  [Anthropic Overloaded] Chờ {wait_time:.1f}s trước khi thử lại ({current_model})...", flush=True)
                    time.sleep(wait_time)
                    continue
                if "429" in err_msg or "rate_limit_error" in err_msg.lower():
                    wait_time = min(30.0, (2 ** attempt) + 3.0)
                    print(f"  [Anthropic Rate Limit] Chờ {wait_time:.1f}s trước khi thử lại ({current_model})...", flush=True)
                    time.sleep(wait_time)
                    continue
                raise
    if last_err is not None:
        raise last_err
    raise RuntimeError(f"Không thể kết nối Anthropic API (đã thử: {candidate_models}).")


def _call_openai(system_instruction, prompt_text, model, response_schema=None, timeout_s=30):
    # Nhánh dự phòng nếu đổi provider
    raise NotImplementedError("Nhánh dự phòng openai chưa triển khai.")


_PROVIDERS = {
    "gemini": _call_gemini,
    "anthropic": _call_anthropic,
    "claude": _call_anthropic,
    "openai": _call_openai,
}


def call_ai(system_instruction, prompt_text, model=None, provider=None, response_schema=None, timeout_s=30):
    """Gọi LLM và trả về {"text": str, "elapsed_s": float, ...}.

    Tham số:
      system_instruction, prompt_text: lấy từ prompt_template.build_prompt(...)
      response_schema: OUTPUT_SCHEMA (prompt_template.py) khi dùng V2/V3 để ép JSON
        qua structured output của model; None khi dùng V1 (trả lời tự do).
      provider/model: mặc định lấy từ biến môi trường AI_PROVIDER/AI_MODEL.
    """
    provider = provider or AI_PROVIDER
    model = model or AI_MODEL
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"AI_PROVIDER không hợp lệ: {provider!r} (hỗ trợ: {list(_PROVIDERS)})")
    return fn(system_instruction, prompt_text, model, response_schema=response_schema, timeout_s=timeout_s)
