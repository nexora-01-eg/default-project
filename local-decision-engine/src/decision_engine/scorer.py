"""Offline scoring backend: TF-IDF cosine over the option set + cue-group priors.

Zero downloads, zero VRAM, deterministic, fully offline. Two signals:

1. TF-IDF cosine: tokens weighted by distinctiveness across the options in the
   same question, so shared vocabulary stops drowning the signal. Light
   ASCII stemming (charged/charge -> charg) closes the morphological gap.
2. Cue groups: small, domain-general keyword sets (spam, severity, value,
   uncertainty, routing, time-pressure, physical/digital, success/failure,
   simplicity/complexity, totality). Keywords match whole tokens — never
   substrings (so "no" cannot match inside "not"). Weights are fixed;
   nothing is fitted to any dataset.

Honest scope: strong on clear-cut classification / filtering with well-named
options; weak on multi-step reasoning — route low-confidence answers to
fallback/review (see engine.DecisionEngine.decide_with_fallback).
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .primitives import softmax

_TOKEN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)

_STOP = frozenset("""
the a an and or of to in on for with is are was were be been it its this that
these those as at by from into over after before between but nor can
will would should could there their they them he she we you i me my our your
his her our ours yours any each few more most other some such only own
than too very s t d ll m re ve don doesn isn aren wasn weren hasn haven
what which who whom whose when where why how whether either neither both
option options following choose select best one two three category type kind
question answer decide decision classify classification does is are need needs
want wants would like take get got give use used using also just
even ever never always often much many lot thing things something someone
anyone may might shall must per via etc eg ie am pm
task tasks agent agents handle handled handled-by decision decisions output outputs
input inputs result results
من في على إلى أن إن أو و ثم هل ما لا لم لن ليس كل بعض غير بين مع عن بعد قبل
هذا هذه ذلك تلك التي الذي الذين كما لكن بل حتى إذا لو قد تم يتم تكون يكون
أي هي هو هم نحن أنت أنا هناك كان كانت يكون تكون يوجد ضد دون عايز عايزة كده
زي ده دي اللي اللى إلي علي
""".split())
# NOTE: no/not/yes/true/false are deliberately NOT stopwords: in yes/no
# questions negation carries the whole signal.

# (state cues, option-positive keywords, option-negative keywords, w_pos, w_neg)
# Keywords match whole tokens (multiword phrases need every token present).
_GROUPS = [
    ("spam-noise",
     frozenset("congratulations prize lottery crypto btc double click unsubscribe "
               "promo promotion advertisement followers cheap free money winner "
               "lorem ipsum filler placeholder فارغ فارغة تجريبي تجريبية "
               "اربح مجاني دعاية اعلان ربحت spam".split()),
     frozenset("spam noise irrelevant promo junk low دعاي عشوائي تجاهل".split()),
     frozenset("real urgent high genuine paying فعل حقيقي عاجل".split()),
     1.0, 1.0),
    ("severe",
     frozenset("urgent asap critical crash crashed down outage deleted breach hacked hack "
               "attack blocked blocking catastrophe emergency immediately production "
               "customers payment charged twice bug error fail failed charged عاجل عاجلة "
               "فورا فوراً الآن خطر اختراق عطل كارثة حرج".split()),
     frozenset("urgent high critical block severe real retry فعل حقيقي عاجل مهم".split()),
     frozenset("minor low trivial polish background irrelevant بسيط".split()),
     0.55, 0.55),
    ("totality",
     frozenset("all every entire total totally completely wiped deleted lost كل جميع كامل".split()),
     frozenset("block catastroph critical total high".split()),
     frozenset("minor low workaround".split()),
     0.4, 0.2),
    ("mild",
     frozenset("typo small minor trivial polish thanks thank nice footer tweak whenever "
               "someday later background colors palette theme font icon dark checking "
               "status fyi بسيط صغير شكرا لاحقا بعدين".split()),
     frozenset("minor low trivial polish background local بسيط".split()),
     frozenset("urgent high critical block severe real فعل حقيقي عاجل".split()),
     0.55, 0.55),
    ("value",
     frozenset("budget pay paid paying hiring hire hired freelance client customer order "
               "contract invoice price cost salary service website store app logo video "
               "design build create setup booking photography menu project proposal salary "
               "مشروع عميل ميزانية سعر ادفع دفع مطلوب خدمة متجر موقع تطبيق تصميم فيديو "
               "حجز كاش مرتب".split()),
     frozenset("real genuine paying opportunity فعل حقيقي".split()),
     frozenset("spam irrelevant noise دعاي عشوائي".split()),
     0.4, 0.4),
    ("uncertain",
     frozenset("maybe might perhaps possibly unclear unsure someday sometime future "
               "mention mentioned cousin idea yet ممكن لسه ربما غير واضح بعدين".split()),
     frozenset("maybe unclear clarification review uncertain يحتاج توضيح".split()),
     frozenset("real definitely certain paying فعل حقيقي مؤكد yes worth".split()),
     0.7, 0.5),
    ("multifile",
     frozenset("files module refactor endpoint scaffold microservice codebase implement "
               "feature service auth".split()),
     frozenset("multi-file large general coding".split()),
     frozenset("research internet git".split()),
     0.9, 0.3),
    ("git",
     frozenset("git commit revert squash merge conflict push branch history checkout diff".split()),
     frozenset("git".split()),
     frozenset("research internet".split()),
     0.9, 0.3),
    ("research",
     frozenset("latest announced announcement research online competitor features "
               "released release week internet search pricing".split()),
     frozenset("research internet network remote-free".split()),
     frozenset("git multi-file local".split()),
     0.9, 0.3),
    ("planning",
     frozenset("plan planning migration coordinate coordination orchestration monorepo "
               "strategy roadmap".split()),
     frozenset("orchestration planning complex coordination".split()),
     frozenset("git research".split()),
     0.9, 0.3),
    ("time-pressure",
     frozenset("tomorrow tonight demo meeting deadline eod evening schedule week "
               "before monday tuesday wednesday thursday friday saturday sunday "
               "january february march april may june july august september october "
               "november december today غدا اجتماع عرض موعد قبل".split()),
     frozenset("medium normal pressure".split()),
     frozenset("blocking".split()),
     0.5, 0.3),
    ("physical",
     frozenset("plumber cleaning sink pipe electrician carpenter painter shop office "
               "clinic photographer delivery driver repair fix kitchen".split()),
     frozenset("physical offline".split()),
     frozenset("online digital".split()),
     0.8, 0.8),
    ("digital",
     frozenset("website online app mobile software landing payment gps digital api "
               "chatbot courses tracking".split()),
     frozenset("online digital".split()),
     frozenset("physical offline".split()),
     0.8, 0.8),
    ("success",
     frozenset("pass passed passing success successful complete completed done works "
               "working fixed green".split()),
     frozenset("accept complete success".split()),
     frozenset("retry broken empty".split()),
     0.7, 0.5),
    ("failure",
     frozenset("empty broken missing error fail failed timeout partial exit".split()),
     frozenset("retry broken".split()),
     frozenset("accept complete".split()),
     0.7, 0.5),
    ("hallucination",
     frozenset("uncertain hallucinated nonexistent missing wrong mismatch exist "
               "ghost phantom".split()),
     frozenset("review uncertain human".split()),
     frozenset("accept".split()),
     0.7, 0.4),
    ("simple-task",
     frozenset("spam category ticket filter routing route priority classify".split()),
     frozenset("local fast simple".split()),
     frozenset("llm large deep writing".split()),
     0.6, 0.6),
    ("complex-task",
     frozenset("summarize write blog post contract code coding program analysis deep "
               "essay page pages reason".split()),
     frozenset("llm large writing coding deep".split()),
     frozenset("local fast simple".split()),
     0.6, 0.6),
    ("ai-topic",
     frozenset("ai model models llm gpt transformer neural diffusion inference gpu "
               "arxiv chatbot open-weights parameters architecture benchmark dataset "
               "نموذج ذكاء اصطناعي".split()),
     frozenset("worth summarizing yes ai".split()),
     frozenset("noise irrelevant".split()),
     1.0, 0.6),
    ("non-ai-topic",
     frozenset("football league match soccer weather forecast sunny rain gossip "
               "celebrity actor watches vegetables market prices recipe travel "
               "طقس مباراة كرة اخبار الفن خضار سوق".split()),
     frozenset("noise irrelevant".split()),
     frozenset("worth summarizing yes".split()),
     1.0, 1.0),
    ("learning",
     frozenset("teach learn learning tutorial course lesson lessons explain how-to "
               "يعلم تعلم شرح درس".split()),
     frozenset("maybe unclear review human".split()),
     frozenset("spam real".split()),
     0.6, 0.4),
]

_SHORT_POS = frozenset("irrelevant spam noise low review unclear no".split())
_SHORT_NEG = frozenset("real urgent high genuine paying فعل حقيقي عاجل".split())


def _ar_normalize(tok: str) -> str:
    """Strip the Arabic definite article so الخضار matches خضار."""
    if len(tok) > 4 and tok.startswith("ال"):
        return tok[2:]
    return tok


def _stem(tok: str) -> str:
    if tok.isascii() and len(tok) > 4 and not tok.endswith(("ss", "us", "is")):
        for suf in ("ing", "ed", "es", "s"):
            if tok.endswith(suf) and len(tok) - len(suf) >= 3:
                return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list:
    out = []
    for t in _TOKEN.findall(text or ""):
        low = t.lower()
        if low in _STOP:
            continue
        if not low.isascii():
            low = _ar_normalize(low)
            if low in _STOP:
                continue
            out.append(low)
        else:
            out.append(_stem(low))
    return out


def _kw_tokens(phrase: str) -> list:
    return [_stem(t.lower()) for t in _TOKEN.findall(phrase) if t.lower() not in _STOP]


def _matches(opt_tokens: set, phrase: str) -> bool:
    parts = _kw_tokens(phrase)
    return bool(parts) and all(p in opt_tokens for p in parts)


def _idf(option_counters: list, background: Counter) -> dict:
    n = len(option_counters) + 1
    df = Counter()
    for c in option_counters:
        for t in c:
            df[t] += 1
    for t in background:
        df[t] += 1
    return {t: 1.0 + math.log(n / f) for t, f in df.items()}


def _cosine(a: Counter, b: Counter, w: dict) -> float:
    dot = sum(w.get(t, 1.0) * ca * b.get(t, 0) for t, ca in a.items())
    na = math.sqrt(sum((w.get(t, 1.0) * ca) ** 2 for t, ca in a.items()))
    nb = math.sqrt(sum((w.get(t, 1.0) * cb) ** 2 for t, cb in b.items()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _cue_tilt(state: set, opt_tokens: set) -> float:
    tilt = 0.0
    for _name, cues, pos, neg, wp, wn in _GROUPS:
        if state & cues:
            if any(_matches(opt_tokens, k) for k in pos):
                tilt += wp
            if any(_matches(opt_tokens, k) for k in neg):
                tilt -= wn
    return tilt


def score_options(state: str, instructions: str, option_texts: list,
                  temperature: float = 0.5) -> list:
    """One probability per option, aligned with option order."""
    if len(option_texts) == 1:
        return [1.0]
    state_c = Counter(tokenize(state))
    instr_c = Counter(tokenize(instructions))
    opt_cs = [Counter(tokenize(o)) for o in option_texts]
    opt_toks = [set(c) for c in opt_cs]
    w = _idf(opt_cs, instr_c)
    state_set = set(state_c)
    short = len(state_c) <= 2  # near-empty input carries no positive signal
    logits = []
    for oc, ot in zip(opt_cs, opt_toks):
        s = _cosine(state_c, oc, w) + 0.15 * _cosine(instr_c, oc, w)
        # NOTE: cue matching uses option tokens only. Instruction words are
        # shared by all options, so letting them trigger tilts (e.g. "real"
        # in "Is this a real ...?") would distort every option at once.
        s += _cue_tilt(state_set, ot)
        if short:
            if any(_matches(ot, k) for k in _SHORT_POS):
                s += 0.6
            if any(_matches(ot, k) for k in _SHORT_NEG):
                s -= 0.6
        logits.append(s + 1e-6)
    return softmax(logits, temperature=temperature or 0.5)
