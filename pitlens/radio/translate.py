"""Team radio transcripts into Simplified Chinese.

Two engines:

* ``offline`` (default): Argos Translate's English->Chinese model run directly
  with CTranslate2 (about 70 MB, downloaded once, free, no account). Small
  translation models don't know F1, so the jargon is swapped for placeholders
  before translating and for the right Chinese term afterwards ("box, box"
  is 进站，进站, not 盒子).
* ``claude``: Claude via the Anthropic API, for clearly better translations of
  noisy, jargon-heavy radio. Needs the ``anthropic`` package and an API key
  (ANTHROPIC_API_KEY or an ``ant auth login`` profile); each clip costs a
  fraction of a cent.

Translations are stored next to the transcript, per engine, so each clip is
translated once.
"""

import re
import zipfile

import requests

from pitlens.radio import transcribe
from pitlens.session import CACHE_DIR

ARGOS_URL = "https://argos-net.com/v1/translate-en_zh-1_9.argosmodel"
ARGOS_DIR = CACHE_DIR / "translate" / "en_zh"
CLAUDE_MODEL = "claude-opus-5-5"

_NUMBER_WORDS = {
    w: str(i) for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty".split()
    )
}

# (English pattern, Chinese) in order of priority; longer phrases first.
GLOSSARY = [
    (r"\bbox,?\s+box\b", "进站，进站"),
    (r"\bpit lane\b", "维修通道"),
    (r"\bpit wall\b", "维修墙"),
    (r"\bpit stop\b", "进站"),
    (r"\b(?:box|pit)\b", "进站"),
    (r"\bstay out\b", "留在赛道上"),
    (r"\blift and coast\b", "提前收油滑行"),
    (r"\bovertake mode\b", "超车模式"),
    (r"\bvirtual safety car\b|\bVSC\b", "虚拟安全车"),
    (r"\bsafety car\b", "安全车"),
    (r"\bdeg(?:radation)?\b", "轮胎衰退"),
    (r"\bundercut\b", "undercut"),
    (r"\bovercut\b", "overcut"),
    (r"\bcopy(?: that)?\b", "收到"),
    (r"\bpush now\b", "现在全力推"),
    (r"\bkeep pushing\b", "继续全力推"),
    (r"\bpush\b", "全力推"),
    (r"\bgap\b", "差距"),
    (r"\bsoft(?:s| tyres?)\b", "软胎"),
    (r"\bmedium(?:s| tyres?)\b", "中性胎"),
    (r"\bhard(?:s| tyres?)\b", "硬胎"),
    (r"\b(?:inters|intermediates?)\b", "半雨胎"),
    (r"\bfull wets?\b|\bwets\b", "全雨胎"),
    (r"\bDRS\b", "DRS"),
]


def _numbers_to_digits(text: str) -> str:
    return re.sub(r"\bturn (" + "|".join(_NUMBER_WORDS) + r")\b", lambda m: f"turn {_NUMBER_WORDS[m.group(1).lower()]}",
                  text, flags=re.I)


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Swap F1 terms for placeholders (ZX1, ZX2...) the model copies through unchanged."""
    mapping: dict[str, str] = {}

    def hold(zh: str) -> str:
        key = f"ZX{len(mapping) + 1}"
        mapping[key] = zh
        return f" {key} "

    text = _numbers_to_digits(text)
    text = re.sub(r"\bP(\d{1,2})\b", lambda m: hold(f"第{m.group(1)}位"), text)
    text = re.sub(r"\bturn (\d{1,2})\b", lambda m: hold(f"{m.group(1)}号弯"), text, flags=re.I)
    for pattern, zh in GLOSSARY:
        text = re.sub(pattern, lambda m, zh=zh: hold(zh), text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(), mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    return re.sub(r"ZX\s?(\d+)", lambda m: mapping.get(f"ZX{m.group(1)}", ""), text)


_CJK = "\u4e00-\u9fff"


def tidy(zh: str) -> str:
    """Clean up model output: stray "(英语)" notes, spaces inside Chinese, ASCII punctuation."""
    zh = re.sub(r"\s*[(（]英语[)）]\s*", "", zh)
    zh = re.sub(rf"(?<=[{_CJK}，。！？])\s+|\s+(?=[{_CJK}，。！？])", "", zh)
    zh = re.sub(rf"(?<=[{_CJK}]),|,(?=[{_CJK}])", "，", zh)
    zh = re.sub(rf"(?<=[{_CJK}])\.(?!\d)", "。", zh)
    zh = re.sub(rf"(?<=[{_CJK}])\?", "？", zh)
    zh = re.sub(rf"(?<=[{_CJK}])!", "！", zh)
    return zh.strip()


def only_placeholders(text: str) -> bool:
    return re.fullmatch(r"[\sZX\d.,!?]*", text) is not None and "ZX" in text


def sentences(text: str) -> list[str]:
    """Small translation models handle one sentence at a time; longer input gets cut short."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


class OfflineTranslator:
    name = "offline"

    def __init__(self):
        import ctranslate2
        import sentencepiece

        model_dir = self._ensure_model()
        self.translator = ctranslate2.Translator(str(model_dir / "model"), device="cpu", compute_type="int8")
        self.sp = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "sentencepiece.model"))

    @staticmethod
    def _ensure_model():
        found = list(ARGOS_DIR.glob("*/model/model.bin"))
        if found:
            return found[0].parent.parent
        ARGOS_DIR.mkdir(parents=True, exist_ok=True)
        archive = ARGOS_DIR.parent / "en_zh.argosmodel"
        with requests.get(ARGOS_URL, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
        with zipfile.ZipFile(archive) as z:
            z.extractall(ARGOS_DIR)
        archive.unlink()
        return next(ARGOS_DIR.glob("*/model/model.bin")).parent.parent

    def translate(self, text: str, driver_first_name: str | None = None) -> str:
        parts = [protect(s) for s in sentences(text)]
        # Sentences that are nothing but F1 terms ("Box, box.") need no model at all.
        todo = [i for i, (p, _) in enumerate(parts) if not only_placeholders(p)]
        results = self.translator.translate_batch(
            [self.sp.encode(parts[i][0], out_type=str) for i in todo], beam_size=4, max_decoding_length=256
        ) if todo else []
        translated = {i: self.sp.decode(r.hypotheses[0]).replace("▁", "") for i, r in zip(todo, results)}
        out = []
        for i, (protected, mapping) in enumerate(parts):
            zh = translated.get(i, re.sub(r"\s*\.\s*$", "。", protected))
            out.append(tidy(restore(zh, mapping)))
        return "".join(out)


CLAUDE_SYSTEM = (
    "You translate Formula 1 team radio from English into natural Simplified Chinese, the way Chinese F1 "
    "broadcasts and fans would say it. The English comes from automatic speech recognition of noisy radio, so it "
    "may contain misheard words: translate the meaning the speaker most likely intended, and keep anything "
    "unintelligible short rather than inventing content. Use standard F1 terms: box / pit = 进站, stay out = "
    "留在赛道上, deg = 轮胎衰退, lift and coast = 提前收油滑行, push = 全力推, copy = 收到, P2 = 第2位, "
    "turn 3 = 3号弯, safety car = 安全车, VSC = 虚拟安全车, softs/mediums/hards/inters = 软胎/中性胎/硬胎/半雨胎. "
    "Keep driver and team names in their common Chinese forms. Reply with the translation only."
)


class ClaudeTranslator:
    name = "claude"

    def __init__(self):
        import anthropic

        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY, or an `ant auth login` profile

    def translate(self, text: str, driver_first_name: str | None = None) -> str:
        who = f"Radio between {driver_first_name} and their race engineer:\n\n" if driver_first_name else ""
        response = self.client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},  # a short translation needs little deliberation
            # If a request is ever declined, let the API retry it on a suitable fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=CLAUDE_SYSTEM,
            messages=[{"role": "user", "content": who + text}],
        )
        if response.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in response.content if b.type == "text").strip()


def available_engines() -> list[str]:
    engines = []
    try:
        import ctranslate2  # noqa: F401
        import sentencepiece  # noqa: F401

        engines.append("offline")
    except ImportError:
        pass
    try:
        import anthropic  # noqa: F401

        engines.append("claude")
    except ImportError:
        pass
    return engines


def make(engine: str = "offline"):
    return ClaudeTranslator() if engine == "claude" else OfflineTranslator()


def cached(url: str, engine: str | None = None) -> str | None:
    """A stored translation for a clip: the given engine's, or the best one available."""
    zh = (transcribe.cached(url) or {}).get("zh") or {}
    if engine:
        return zh.get(engine)
    return zh.get("claude") or zh.get("offline")


def translate_clip(url: str, translator, driver_first_name: str | None = None) -> str | None:
    """Translate a clip's stored transcript (transcribe it first), caching the result."""
    record = transcribe.cached(url) or {}
    text = record.get("text")
    if not text:
        return None
    zh = record.get("zh") or {}
    if translator.name not in zh:
        zh[translator.name] = translator.translate(text, driver_first_name)
        transcribe.save(url, {**record, "zh": zh})
    return zh[translator.name]
