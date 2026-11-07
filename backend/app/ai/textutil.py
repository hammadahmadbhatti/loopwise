"""Language-agnostic text helpers used by the offline engine and the local embedder."""

from __future__ import annotations

import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0  # deterministic language detection

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

STOPWORDS = set(
    """
    a an the and or but if then else of to in on at by for with from up down out over under again further
    is are was were be been being am do does did doing have has had having i me my we our you your he she it
    its they them their this that these those there here what which who whom when where why how all any both
    each few more most other some such only own same so than too very can will just should now also still
    really please thanks thank would could get got make made use using used want need like one two lot much
    even every app product please hi hello dear team guys im ive dont doesnt cant isnt wont thats not way
    time times try since last new today yesterday day days week weeks month months year able thing things
    something anything everything someone maybe already always sometimes often
    der die das und oder aber wenn dann ein eine einer eines einem einen ist sind war waren sein bin bist hat
    haben hatte ich mich mir wir uns ihr sie es er man mit von zu zum zur im in auf an bei fur aus nach uber
    unter auch noch nur sehr schon wie was wer wo warum dass doch mal bitte kann konnen konnte wurde wird
    werden nicht kein keine hallo danke dem den des seit letzten letzte letzter immer jetzt heute
    el la los las un una unos unas y o pero si es son era fue ser estoy esta estan he ha han hay yo me mi
    nosotros tu su sus con de del al en por para que como muy mas tambien ya no lo le les se hola gracias este
    esta estos estas dos veces mes cada siempre
    le la les un une des et ou mais si est sont etait etre suis ai avez a ont je me moi nous vous il elle ils
    elles avec de du au aux en dans sur pour par que qui comme tres plus aussi ne pas ce cette ces bonjour merci
    o a os as um uma e ou mas se sao era ser estou esta eu meu minha nos voce seu sua com de do da dos das em
    no na por para que como muito mais tambem nao ola obrigado obrigada
    il lo la gli le un una e o ma se sono era essere sto io mi noi voi con di del della in su per che come
    molto piu anche non ciao grazie
    de het een en of maar als dan is zijn was waren ben heb heeft ik mij wij jullie hij zij het met van voor
    op in uit naar dat die wat hoe zeer ook nog niet geen hallo bedankt
    """.split()
)


def normalize(text: str) -> str:
    """Lowercase, fold accents (über -> uber, ß -> ss) and unify apostrophes."""
    text = text.replace("ß", "ss").replace("’", "'").replace("`", "'")
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize(text))


_ELISIONS = ("l'", "d'", "j'", "qu'", "n'", "s'", "c'", "m'", "t'", "un'", "dell'", "all'", "nell'")


def clean_token(token: str) -> str:
    """Strip French/Italian elisions (l'application -> application) and stray apostrophes."""
    for prefix in _ELISIONS:
        if token.startswith(prefix) and len(token) > len(prefix) + 1:
            token = token[len(prefix):]
            break
    return token.replace("'", "")


def is_content(token: str) -> bool:
    return len(token) > 2 and token not in STOPWORDS and not token.isdigit()


def content_tokens(text: str) -> list[str]:
    return [c for c in (clean_token(t) for t in tokenize(text)) if is_content(c)]


def stem(token: str) -> str:
    """Very light, multilingual suffix stripping so 'exports'/'exporting'/'exported' group together."""
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s", "en", "er", "e"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def detect_language(text: str, default: str = "und") -> tuple[str, float]:
    sample = text.strip()
    if len(re.findall(r"\w+", sample)) < 2:
        return default, 0.0
    try:
        best = detect_langs(sample)[0]
        return best.lang.lower(), float(best.prob)
    except LangDetectException:
        return default, 0.0


def first_sentence(text: str, limit: int = 160) -> str:
    clean = " ".join(text.split())
    match = re.split(r"(?<=[.!?。！？])\s", clean, maxsplit=1)
    sentence = match[0] if match else clean
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"
