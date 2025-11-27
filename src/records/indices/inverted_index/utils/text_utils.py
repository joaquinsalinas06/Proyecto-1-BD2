import re
import unicodedata
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

try:
    _STOPWORDS = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords", quiet=True)
    _STOPWORDS = set(stopwords.words("english"))

_STEMMER = SnowballStemmer("english")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_STEMMED_STOPWORDS = {_STEMMER.stem(w) for w in _STOPWORDS}

def _normalize(text: str) -> str:
    text = text.lower()
    # text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text

def bow(
        text: str
        ) -> dict[str, int]:
    """
    1) Normaliza (minúsculas)
    2) Tokeniza limpiando lo no alfanumérico
    3) Stemming
    4) Filtra stopwords (stemmeadas)
    5) Cuenta frecuencias -> {stem: tf}
    """
    text = _normalize(text) 
    raw_tokens = _NON_ALNUM.sub(" ", text).split()

    stems = []
    for w in raw_tokens:
        if not w:
            continue
        s = _STEMMER.stem(w)
        if s in _STEMMED_STOPWORDS:
            continue
        stems.append(s)

    return dict(Counter(stems))
