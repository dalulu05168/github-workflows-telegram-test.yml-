"""Best-effort Chinese translation of public RSS text, without keys or billing.

Uses Google's public web translation endpoint, not the paid Cloud Translation
API. This endpoint has no published availability guarantee; callers must retain
the original source and clearly handle failure. Never send credentials or private
chat content here. Cache entries are keyed by the exact source text and target.
"""
import hashlib
import html
import json
import os
import re
import tempfile
from pathlib import Path

import requests

ENDPOINT = "https://translate.googleapis.com/translate_a/single"


class TranslationUnavailable(RuntimeError):
    pass


class FreeTranslator:
    def __init__(self, transport=None, cache_dir=None, max_requests=40):
        self.transport = requests if transport is None else transport
        directory = os.getenv("TRANSLATION_CACHE_DIR") if cache_dir is None else cache_dir
        self.cache_dir = Path(directory) if directory else None
        self.memory = {}
        self.remaining = max_requests
        self.unavailable = False

    def __call__(self, text):
        if not isinstance(text, str) or len(text) > 5000:
            raise TranslationUnavailable("Unsupported translation input")
        if not text.strip():
            return text
        if re.search(r"[\u4e00-\u9fff]", text) and not re.search(r"[A-Za-z]", text):
            return text
        key = hashlib.sha256(("zh-CN\0" + text).encode("utf-8")).hexdigest()
        if key in self.memory:
            return self.memory[key]
        path = self.cache_dir / (key + ".json") if self.cache_dir else None
        if path:
            try:
                if not path.is_file() or path.stat().st_size > 100_000:
                    raise ValueError("No usable translation cache")
                cached = json.loads(path.read_text(encoding="utf-8"))
                if (cached.get("source") == text and cached.get("target") == "zh-CN"
                        and isinstance(cached.get("translation"), str)
                        and 0 < len(cached["translation"]) <= 20_000):
                    self.memory[key] = cached["translation"]
                    return self.memory[key]
            except (OSError, ValueError, AttributeError):
                pass  # A damaged cache is a miss, never a reason to drop news.
        if self.remaining <= 0 or self.unavailable:
            raise TranslationUnavailable("Free translation unavailable for this run")
        self.remaining -= 1
        try:
            response = self.transport.get(
                ENDPOINT, params={"client": "gtx", "sl": "auto", "tl": "zh-CN",
                                  "dt": "t", "q": text}, timeout=15)
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise ValueError("Oversized translation response")
            payload = response.json()
            segments = payload[0]
            if not isinstance(segments, list) or not segments:
                raise ValueError("Missing translation segments")
            # Every source segment must be accounted for; reject partial results.
            if any(not isinstance(s, list) or len(s) < 2
                   or not isinstance(s[0], str) or not isinstance(s[1], str)
                   for s in segments):
                raise ValueError("Invalid translation segments")
            if "".join(s[1] for s in segments) != text:
                raise ValueError("Translation did not cover the complete source")
            translated = html.unescape("".join(s[0] for s in segments)).strip()
            if not translated or len(translated) > 20_000:
                raise ValueError("Invalid translated text")
            if translated == text and re.search(r"[A-Za-z]", text) and not re.search(r"[\u4e00-\u9fff]", text):
                raise ValueError("Service returned untranslated input")
        except (requests.RequestException, ValueError, TypeError, IndexError, KeyError):
            self.unavailable = True  # No repeated hammering after quota/network failure.
            raise TranslationUnavailable("Free translation failed; retain original text") from None
        self.memory[key] = translated
        if path:
            temporary = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                                 suffix=".tmp", delete=False) as handle:
                    temporary = handle.name
                    json.dump({"source": text, "target": "zh-CN", "translation": translated},
                              handle, ensure_ascii=False)
                os.replace(temporary, path)
            except OSError:
                pass  # Successful translation remains usable without disk caching.
            finally:
                if temporary:
                    try:
                        Path(temporary).unlink(missing_ok=True)
                    except OSError:
                        pass
        return translated
