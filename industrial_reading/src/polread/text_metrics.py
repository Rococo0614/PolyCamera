"""String-level metrics with explicit, versionable normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata


@dataclass(frozen=True)
class TextNormalization:
    """Normalization applied before the reported normalized OCR metrics.

    Raw OCR output must always be retained separately. ``whitespace`` accepts
    ``preserve``, ``collapse`` or ``remove``. ``allowed_characters`` is an
    optional literal character set rather than an OCR dictionary correction.
    """

    unicode_form: str = "NFKC"
    uppercase: bool = True
    whitespace: str = "collapse"
    allowed_characters: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_text(text: str, config: TextNormalization | None = None) -> str:
    cfg = config or TextNormalization()
    if cfg.whitespace not in {"preserve", "collapse", "remove"}:
        raise ValueError(f"Unsupported whitespace mode: {cfg.whitespace}")
    value = unicodedata.normalize(cfg.unicode_form, str(text))
    if cfg.uppercase:
        value = value.upper()
    if cfg.whitespace == "collapse":
        value = re.sub(r"\s+", " ", value).strip()
    elif cfg.whitespace == "remove":
        value = re.sub(r"\s+", "", value)
    if cfg.allowed_characters is not None:
        allowed = set(cfg.allowed_characters)
        value = "".join(character for character in value if character in allowed)
    return value


def levenshtein_distance(reference: list[str] | str, prediction: list[str] | str) -> int:
    """Return insertion/deletion/substitution edit distance."""

    ref = list(reference)
    pred = list(prediction)
    if len(ref) < len(pred):
        ref, pred = pred, ref
    previous = list(range(len(pred) + 1))
    for row, ref_item in enumerate(ref, start=1):
        current = [row]
        for column, pred_item in enumerate(pred, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (ref_item != pred_item),
                )
            )
        previous = current
    return previous[-1]


def _error_rate(reference: list[str] | str, prediction: list[str] | str) -> float:
    denominator = len(reference)
    distance = levenshtein_distance(reference, prediction)
    if denominator == 0:
        return 0.0 if distance == 0 else float(distance)
    return float(distance / denominator)


def evaluate_text(
    reference: str,
    prediction: str,
    *,
    normalization: TextNormalization | None = None,
) -> dict[str, object]:
    """Evaluate raw and normalized exact-read, CER and WER.

    The normalized strings are returned for auditing. No dictionary, regex or
    expected business value is used to correct the OCR output.
    """

    cfg = normalization or TextNormalization()
    ref_raw = str(reference)
    pred_raw = str(prediction)
    ref = normalize_text(ref_raw, cfg)
    pred = normalize_text(pred_raw, cfg)
    char_edits = levenshtein_distance(ref, pred)
    ref_words = ref.split()
    pred_words = pred.split()
    word_edits = levenshtein_distance(ref_words, pred_words)
    return {
        "raw_exact_read": ref_raw == pred_raw,
        "normalized_exact_read": ref == pred,
        "reference_normalized": ref,
        "prediction_normalized": pred,
        "char_edits": int(char_edits),
        "reference_characters": len(ref),
        "cer": _error_rate(ref, pred),
        "word_edits": int(word_edits),
        "reference_words": len(ref_words),
        "wer": _error_rate(ref_words, pred_words),
    }
