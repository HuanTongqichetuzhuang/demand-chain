"""
需求语义搜索 — 基于 TF-IDF 的关键词匹配，不依赖外部 embedding API。
使用 Python Unicode 判断 CJK 字符，兼容性好。
"""
import re
import math
from collections import defaultdict


def _is_cjk(char: str) -> bool:
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x20000 <= cp <= 0x2A6DF)


_EN_RE = re.compile(r'[a-z0-9]+')


def tokenize(text: str) -> list[str]:
    """混合中英文分词：中文 bigram（所有bigrams）+ 单个字符（全部保留），英文全词（>=2 chars），数字保留"""
    if not text:
        return []
    text = text.lower().strip()
    tokens = []

    # 1. English words & numbers — keep full tokens >= 2 chars
    for m in _EN_RE.finditer(text):
        word = m.group(0)
        if len(word) >= 2:
            tokens.append(word)

    # 2. CJK — bigrams + all singles (for more recall)
    cn_chars = [ch for ch in text if (0x4E00 <= ord(ch) <= 0x9FFF
                                       or 0x3400 <= ord(ch) <= 0x4DBF
                                       or 0x20000 <= ord(ch) <= 0x2A6DF)]

    for i in range(len(cn_chars) - 1):
        tokens.append(cn_chars[i] + cn_chars[i + 1])

    # Always include all singles — essential for short queries
    tokens.extend(cn_chars)

    return tokens


class TfidfSearch:
    def __init__(self):
        self.documents: dict[str, str] = {}
        self.index: dict[str, dict[str, float]] = {}
        self.idf: dict[str, float] = {}
        self._built = False

    def add(self, doc_id: str, text: str):
        self.documents[doc_id] = text
        self._built = False

    def build_index(self):
        N = len(self.documents)
        if N == 0:
            self._built = True
            return
        df: dict[str, int] = defaultdict(int)
        doc_tokens: dict[str, list[str]] = {}
        for doc_id, text in self.documents.items():
            tokens = tokenize(text)
            doc_tokens[doc_id] = tokens
            for term in set(tokens):
                df[term] += 1
        self.idf = {term: math.log((N + 1) / (cnt + 1)) + 1.0
                    for term, cnt in df.items()}
        self.index = {}
        for doc_id, tokens in doc_tokens.items():
            tf: dict[str, float] = defaultdict(float)
            for t in tokens:
                tf[t] += 1.0
            mx = max(tf.values()) if tf else 1.0
            self.index[doc_id] = {t: (v / mx) * self.idf.get(t, 1.0)
                                  for t, v in tf.items()}
        self._built = True

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._built:
            self.build_index()
        qtokens = tokenize(query)
        if not qtokens or not self.index:
            results: list[tuple[str, float]] = []
            ql = query.lower()
            for did, text in self.documents.items():
                if ql in text.lower():
                    results.append((did, 0.7 if not text.lower().startswith(ql) else 1.0))
            results.sort(key=lambda x: -x[1])
            return results[:top_k]

        # TF-IDF cosine-like scoring
        qvec: dict[str, float] = defaultdict(float)
        for t in qtokens:
            qvec[t] += 1.0
        max_q = max(qvec.values()) if qvec else 1.0
        q_norm = math.sqrt(sum((v / max_q) ** 2 * self.idf.get(t, 1.0) ** 2
                               for t, v in qvec.items()))

        scores: list[tuple[str, float]] = []
        for did, dvec in self.index.items():
            dot = 0.0
            d_norm = 0.0
            for t, dv in dvec.items():
                qv = qvec.get(t, 0.0) / max_q
                dot += qv * dv * self.idf.get(t, 1.0)
                d_norm += dv ** 2
            d_norm = math.sqrt(d_norm) if d_norm > 0 else 1.0
            score = dot / (q_norm * d_norm) if q_norm > 0 else 0.0

            # Substring bonus
            if query.lower() in self.documents.get(did, "").lower():
                score += 0.15
            if score > 0:
                scores.append((did, score))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


demand_search = TfidfSearch()
supplier_search = TfidfSearch()

