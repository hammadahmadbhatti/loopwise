"""Offline engine: works with no API key, no model download and no network.

It covers the seven most common languages of the platform's customers (EN, DE, ES,
FR, PT, IT, NL) with small hand-built lexicons for sentiment, category, urgency and
churn signals. It cannot translate free text; for free local translation, run the
Ollama provider. Everything it writes (theme names, briefs, answers, release notes)
is assembled from templates and the real numbers, never invented.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .base import (
    AIProvider,
    AskAnswer,
    DecisionBrief,
    DecisionOption,
    EvidenceQuote,
    FeedbackAnalysis,
    Message,
    ProviderError,
    ThemeLabel,
)
from .concepts import CONCEPTS, concept_label, concepts_in
from .prompts import language_name
from .textutil import STOPWORDS, clean_token, detect_language, first_sentence, is_content, normalize, tokenize


def _terms(block: str) -> list[str]:
    return [normalize(t.strip()) for t in block.split("|") if t.strip()]


POSITIVE = _terms(
    "love|loved|great|awesome|amazing|excellent|fantastic|helpful|easy|fast|smooth|intuitive|perfect|nice|good|"
    "happy|thanks|thank you|useful|reliable|impressed|best|recommend*|enjoy*|wonderful|brilliant|solid|clean|"
    "toll|super|gut|grossartig|hervorragend|einfach|schnell|praktisch|hilfreich|zufrieden|danke|perfekt|klasse|"
    "genial|empfehle*|liebe|lieben|gefallt|excelente|genial|bueno|buena|encanta|facil|rapido|util|perfecto|gracias|increible|"
    "recomiendo|maravilloso|contento|excellent|bien|bon|facile|rapide|utile|parfait|merci|adore|recommande|"
    "pratique|top|otimo|bom|boa|adoro|perfeito|obrigado|obrigada|incrivel|recomendo|ottimo|eccellente|bello|"
    "veloce|perfetto|grazie|fantastico|consiglio|geweldig|goed|fijn|makkelijk|snel|handig|bedankt|aanrader"
)
NEGATIVE = _terms(
    "bad|terrible|awful|horrible|hate|slow|broken|bug*|crash*|error*|fail*|frustrat*|annoy*|confus*|useless|"
    "worst|disappoint*|problem*|issue*|difficult|expensive|missing|lost|stuck|unusable|poor|laggy|freez*|"
    "glitch*|angry|ridiculous|unacceptable|waste|cancel*|refund*|doesn't work|does not work|not working|"
    "can't|cannot|impossible|annoying|buggy|nightmare|"
    "schlecht|langsam|fehler*|absturz|sturzt|kaputt|funktioniert nicht|geht nicht|nervig|argerlich|"
    "frustrierend|teuer|kompliziert|unbrauchbar|enttausch*|katastrophe|furchtbar|schrecklich|verwirrend|leider|"
    "malo|mala|lento|lenta|fallo*|falla*|no funciona|caro|cara|dificil|problema*|frustrante|confuso|inutil|"
    "decepcion*|pesimo|mauvais|lent|lente|erreur*|plante|ne fonctionne pas|marche pas|cher|chere|difficile|"
    "probleme*|nul|frustrant|decu|decevant|inutilisable|complique|ruim|erro*|falha*|nao funciona|pessimo|"
    "horrivel|travando|trava|errore|errori|non funziona|costoso|terribile|slecht|traag|fout*|werkt niet|duur|"
    "moeilijk|probleem|problemen|vervelend|frustrerend"
)
NEGATORS = set(_terms("not|no|never|don't|doesn't|isn't|wasn't|won't|nicht|kein|keine|nie|nunca|pas|jamais|nao|non|mai|niet|geen|nooit"))
_CONDITIONALS = {"would", "wurde", "ware", "gustaria", "seria", "serait", "aimerais", "gostaria", "vorrei",
                 "sarebbe", "zou"}
_SENTIMENT_TOKENS = {t for t in POSITIVE + NEGATIVE if t.isalpha()}
INTENSIFIERS = set(_terms("very|really|extremely|so|super|totally|absolutely|sehr|wirklich|muy|tres|muito|molto|heel|echt"))

CATEGORY_TERMS: dict[str, list[str]] = {
    "bug": _terms(
        "crash*|bug|bugs|buggy|error|errors|broken|doesn't work|does not work|not working|stopped working|fails|"
        "failed|failing|glitch*|freez*|exception|blank page|white screen|500|can't log in|cannot log in|"
        "won't load|fehler*|absturz|sturzt|kaputt|funktioniert nicht|geht nicht|fallo*|falla*|no funciona|"
        "erreur*|plante|ne fonctionne pas|marche pas|erro|erros|falha*|nao funciona|trava*|errore|errori|"
        "non funziona|fout|fouten|werkt niet"
    ),
    "feature_request": _terms(
        "would be nice|would love|would be great|it would be great|please add|add a|add an|feature request|wish|"
        "could you add|can you add|missing|need a|need an|support for|integration|integrate|option to|ability to|"
        "allow us|allow me|let us|let me|dark mode|export|api|roadmap|wunsche|ware schon|ware toll|hinzufugen|"
        "funktion fehlt|fehlt|moglichkeit|seria genial|seria bueno|me gustaria|agregar|anadir|falta|ce serait|"
        "j'aimerais|ajouter|il manque|seria otimo|gostaria|adicionar|sarebbe|vorrei|aggiungere|manca|zou fijn|"
        "toevoegen|graag|serait|sarebbe"
    ),
    "performance": _terms(
        "slow|slowly|slower|lag|laggy|lags|takes forever|timeout*|timed out|too long|sluggish|performance|latency|"
        "loading time|load time|langsam|ladezeit|dauert ewig|lento|lenta|tarda|lent|lente|trop long|travando|"
        "demora|traag|duurt lang"
    ),
    "pricing": _terms(
        "price|prices|pricing|expensive|cost|costs|invoice*|billing|billed|charged|charge|subscription|discount|"
        "refund|cobr*|debit*|reembolso|remboursement|teuer|preis*|rechnung|abo|kosten|caro|cara|precio*|factura|cher|chere|prix|facture|abonnement|"
        "preco|fatura|assinatura|costoso|prezzo|fattura|duur|prijs|factuur"
    ),
    "usability": _terms(
        "confus*|hard to find|can't find|cannot find|unintuitive|not intuitive|cluttered|navigation|too many clicks|"
        "complicated|unclear|hard to use|difficult to use|ui|ux|layout|verwirrend|kompliziert|unubersichtlich|"
        "finde nicht|confuso|complicado|no encuentro|complique|pas intuitif|je ne trouve|nao encontro|complicato|"
        "onduidelijk|ingewikkeld"
    ),
    "support": _terms(
        "support|customer service|support team|agent|ticket|no response|no reply|waiting for a response|helpdesk|"
        "kundenservice|keine antwort|soporte|atencion al cliente|service client|pas de reponse|suporte|atendimento|"
        "assistenza|klantenservice"
    ),
    "question": _terms(
        "how do i|how can i|how to|is there a way|is it possible|can i|does it support|wie kann|gibt es|"
        "como puedo|es posible|comment faire|est-il possible|como posso|e possivel|come posso|hoe kan"
    ),
}
_CATEGORY_WORDS = {"feature", "request", "bug", "issue", "problem", "please", "would", "love", "add", "wish"}
CATEGORY_PRIORITY = ["bug", "performance", "pricing", "usability", "support", "feature_request", "question"]

CRITICAL_TERMS = _terms(
    "data loss|lost all|lost my data|lost our data|security|hacked|breach|charged twice|double charged|outage|"
    "is down|site down|can't log in|cannot log in|can't login|unable to log in|locked out|payment fail*|"
    "payments fail*|gdpr|urgent*|asap|immediately|datenverlust|daten verloren|doppelt abgebucht|"
    "kann mich nicht anmelden|nicht einloggen|sicherheitslucke|dringend|perdi mis datos|cobro doble|"
    "no puedo entrar|cobraron dos veces|cobrado dos veces|urgente|perte de donnees|debite deux fois|impossible de me connecter|perdi meus dados|"
    "cobrado duas vezes|nao consigo entrar|non riesco ad accedere|dati persi|kan niet inloggen"
)
HIGH_TERMS = _terms(
    "blocker|blocking|blocked|can't work|cannot work|unusable|every day|production|whole team|all users|"
    "unbrauchbar|inutilizable|inutilisable|inutilizavel|inutilizzabile|onbruikbaar"
)
CHURN_TERMS = _terms(
    "cancel*|switch to|switching to|moving to|competitor|unsubscribe|refund|leaving|not renew|"
    "won't renew|will not renew|downgrade|looking for alternatives|alternatives|kundig*|wechseln|zur konkurrenz|"
    "abo beenden|cancelar|darme de baja|cambiar a|me voy|reembolso|annuler|resilier|changer pour|"
    "remboursement|mudar para|disdire|annullare|rimborso|opzeggen|overstappen"
)


def _match(term: str, norm: str, tokens: list[str]) -> int:
    """Count occurrences of a lexicon term (phrase, word or prefix*) in normalized text."""
    if term.endswith("*"):
        stem_ = term[:-1]
        return sum(1 for t in tokens if t.startswith(stem_))
    if " " in term or "'" in term or "-" in term:
        return len(re.findall(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", norm))
    return tokens.count(term)


def _hits(terms: list[str], norm: str, tokens: list[str]) -> list[str]:
    return [t for t in terms if _match(t, norm, tokens)]


def score_sentiment(text: str, rating: int | None = None) -> float:
    norm = normalize(text)
    tokens = tokenize(text)
    score = 0.0
    hits = 0
    for terms, polarity in ((POSITIVE, 1.0), (NEGATIVE, -1.0)):
        for term in terms:
            if term.endswith("*"):
                positions = [i for i, t in enumerate(tokens) if t.startswith(term[:-1])]
            elif " " in term or "'" in term:
                n = _match(term, norm, tokens)
                if n:
                    score += polarity * n
                    hits += n
                continue
            else:
                positions = [i for i, t in enumerate(tokens) if t == term]
            for pos in positions:
                if term in INTENSIFIERS and pos + 1 < len(tokens) and tokens[pos + 1] in _SENTIMENT_TOKENS:
                    continue  # "super slow": an intensifier, not praise
                lookback = tokens[max(0, pos - 2):pos]
                if polarity > 0 and any(t in _CONDITIONALS or t.endswith("'d") for t in lookback):
                    continue  # "would love a dark mode" / "serait génial": a wish, not praise
                window = tokens[max(0, pos - 3):pos]
                value = polarity
                if any(w in NEGATORS for w in window):
                    value = -value * 0.7
                if pos > 0 and tokens[pos - 1] in INTENSIFIERS:
                    value *= 1.5
                score += value
                hits += 1
    text_score = 0.0 if hits == 0 else math.tanh(score / math.sqrt(hits + 1) * 1.2)
    if text.count("!") >= 2 and text_score < 0:
        text_score = max(-1.0, text_score - 0.1)
    if rating is not None and 1 <= rating <= 5:
        rating_score = (rating - 3) / 2
        return round(0.6 * text_score + 0.4 * rating_score if hits else rating_score, 3)
    return round(text_score, 3)


def classify(text: str, sentiment: float) -> str:
    norm = normalize(text)
    tokens = tokenize(text)
    scores = {cat: len(_hits(terms, norm, tokens)) for cat, terms in CATEGORY_TERMS.items()}
    if "?" in text:
        scores["question"] += 1
    best = max(scores.values())
    if best == 0:
        return "praise" if sentiment > 0.3 else "other"
    if sentiment > 0.45 and scores["bug"] == 0 and scores["question"] == best and best == 1:
        return "praise"
    for cat in CATEGORY_PRIORITY:
        if scores[cat] == best:
            return cat
    return "other"


def urgency_of(text: str, category: str, sentiment: float, churn: bool) -> str:
    norm = normalize(text)
    tokens = tokenize(text)
    if _hits(CRITICAL_TERMS, norm, tokens):
        return "critical"
    if churn or _hits(HIGH_TERMS, norm, tokens) or (category == "bug" and sentiment < -0.45):
        return "high"
    if sentiment < -0.15 or category in ("bug", "performance", "usability", "pricing", "support"):
        return "medium"
    return "low"


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    sentiment_words = set(POSITIVE) | set(NEGATIVE) | _CATEGORY_WORDS
    seq = [c if is_content(c) and c not in sentiment_words else None for c in (clean_token(t) for t in tokenize(text))]
    toks = [t for t in seq if t]
    # bigrams only from words that were actually adjacent in the text
    bigrams = [f"{a} {b}" for a, b in zip(seq, seq[1:]) if a and b and a != b]
    counts = Counter(toks)
    ranked = sorted(counts, key=lambda t: (-counts[t], -len(t)))
    out: list[str] = []
    for bg in bigrams[:2]:
        out.append(bg)
    for t in ranked:
        if len(out) >= limit:
            break
        if not any(t in o.split() for o in out):
            out.append(t)
    return out[:limit]


def _fmt_money(v: float) -> str:
    return f"${v:,.0f}"


class HeuristicProvider(AIProvider):
    name = "heuristic"
    model = "offline-v1"

    def available(self) -> tuple[bool, str]:
        return True, "Built-in offline engine (EN/DE/ES/FR/PT/IT/NL lexicons, no translation)"

    # -- analysis ---------------------------------------------------------------
    def analyze_feedback(self, text: str, *, working_language: str, context: dict[str, Any]) -> FeedbackAnalysis:
        rating = context.get("rating")
        language, _ = detect_language(text, default=working_language)
        sentiment = score_sentiment(text, rating if isinstance(rating, int) else None)
        label = "negative" if sentiment < -0.2 else "positive" if sentiment > 0.2 else "neutral"
        norm, tokens = normalize(text), tokenize(text)
        churn = bool(_hits(CHURN_TERMS, norm, tokens))
        category = classify(text, sentiment)
        return FeedbackAnalysis(
            language=language,
            translation="",  # offline engine can't translate; Ollama/Claude/OpenAI can
            summary=first_sentence(text),
            sentiment=sentiment,
            sentiment_label=label,
            category=category,
            urgency=urgency_of(text, category, sentiment, churn),
            churn_risk=churn,
            keywords=extract_keywords(text),
        )

    def label_theme(self, samples: list[str], *, keywords: list[str]) -> ThemeLabel:
        counts = Counter(c for s in samples for c in set(concepts_in(s)) if c != "praise")
        order = {c: i for i, c in enumerate(CONCEPTS)}
        ranked = sorted(counts, key=lambda c: (-counts[c], order[c]))  # stable, hash-independent
        common = [c for c in ranked if counts[c] >= max(2, 0.4 * len(samples))]
        labels: list[str] = []
        for c in common:
            lab = concept_label(c)
            if lab not in labels:
                labels.append(lab)
        if labels:
            name = " & ".join(labels[:2])
            kw = ", ".join(keywords[:3])
            return ThemeLabel(name=name, description=f"Customers mention {name.lower()}" + (f" ({kw})." if kw else "."))
        if counts.get("praise", 0) >= max(2, 0.5 * len(samples)) or (not counts and sum(1 for s in samples if s) == 0):
            return ThemeLabel(name="Praise", description="Positive feedback and thanks.")
        kws = [k for k in keywords if k not in STOPWORDS][:3] or extract_keywords(" ".join(samples), 3)
        if not kws:
            return ThemeLabel(name="Miscellaneous feedback", description="Feedback without a clear shared topic.")
        name = kws[0].capitalize() + (f" / {kws[1]}" if len(kws) > 1 else "")
        desc = f"{len(samples)} sample comments mentioning " + ", ".join(kws) + "."
        return ThemeLabel(name=name, description=desc)

    # -- decisions --------------------------------------------------------------
    def decision_brief(self, payload: dict[str, Any]) -> DecisionBrief:
        opp = payload["opportunity"]
        m = payload["metrics"]
        quotes = payload.get("quotes", [])
        customers, mrr, score = m.get("customers", 0), m.get("mrr", 0.0), m.get("priority_score", 0.0)
        countries = m.get("countries", [])
        neg_share = m.get("negative_share", 0.0)
        churn = m.get("churn_risk", 0)
        growth = m.get("growth_pct")

        if customers < 3:
            rec = "investigate"
        elif score >= 65:
            rec = "build_now"
        elif score < 25 and customers < 5:
            rec = "decline"
        else:
            rec = "build_later"
        confidence = round(min(0.9, 0.3 + 0.1 * math.log2(1 + m.get("mentions", 0))), 2)

        trend = ""
        if growth is not None:
            trend = f" Mentions changed {growth:+.0f}% over the last 30 days."
        summary = (
            f"{customers} customer{'s' if customers != 1 else ''} ({_fmt_money(mrr)} MRR) in "
            f"{len(countries)} countr{'ies' if len(countries) != 1 else 'y'} raised \"{opp['title']}\" "
            f"in {m.get('mentions', 0)} pieces of feedback; {neg_share:.0%} of it is negative.{trend}"
        )
        segments = []
        for plan, n in sorted((m.get("plans") or {}).items(), key=lambda kv: -kv[1])[:3]:
            segments.append(f"{plan or 'Unknown plan'}: {n} customer{'s' if n != 1 else ''}")
        if countries:
            segments.append("Countries: " + ", ".join(countries[:6]))
        if m.get("languages"):
            segments.append("Languages: " + ", ".join(language_name(lang) for lang in m["languages"][:6]))

        ranked = sorted(quotes, key=lambda q: (q.get("sentiment") or 0, -(q.get("mrr") or 0)))
        evidence = [
            EvidenceQuote(
                feedback_id=q["feedback_id"],
                quote=first_sentence(q["text"], 220),
                why_it_matters=", ".join(
                    x for x in (
                        f"{q.get('plan')} plan" if q.get("plan") else "",
                        f"{_fmt_money(q['mrr'])} MRR" if q.get("mrr") else "",
                        "churn risk" if q.get("churn_risk") else "",
                        f"{q.get('urgency')} urgency" if q.get("urgency") in ("high", "critical") else "",
                    ) if x
                ) or "Representative of the theme",
            )
            for q in ranked[:4]
        ]
        risks = []
        if churn:
            risks.append(f"{churn} customer{'s' if churn != 1 else ''} signalled they may cancel or switch if this stays unsolved.")
        if neg_share > 0.5:
            risks.append("Majority-negative sentiment: leaving it unaddressed may hurt reviews and renewals.")
        if customers < 5:
            risks.append("Small sample: validate demand with a few customer interviews before committing.")
        risks.append("Opportunity cost: engineering time spent here is not spent on the next-highest priority item.")

        options = [
            DecisionOption(title="Build the full solution", pros=["Resolves the problem for every affected customer", "Strong close-the-loop story"],
                           cons=["Highest effort", "Delays other roadmap items"]),
            DecisionOption(title="Ship a minimal version first", pros=["Fast feedback from the customers who asked", "Low risk"],
                           cons=["May not satisfy power users", "Second iteration needed"]),
            DecisionOption(title="Defer and keep monitoring", pros=["No engineering cost now"],
                           cons=["Problem persists for affected customers", "Risk grows if mentions keep rising"]),
        ]
        rationale = (
            f"Priority score {score:.0f}/100 from demand, revenue at stake, pain and momentum. "
            + ("Evidence is still thin, so validate first." if rec == "investigate" else
               "The signal is strong enough to commit now." if rec == "build_now" else
               "Real but not urgent demand; schedule it behind higher-scoring items." if rec == "build_later" else
               "Low demand and low pain relative to other opportunities.")
        )
        impact = 3.0 if score >= 75 else 2.0 if score >= 55 else 1.0 if score >= 35 else 0.5
        return DecisionBrief(
            summary=summary,
            problem=opp.get("description") or f"Customers repeatedly raise: {opp['title']}.",
            affected_segments=segments,
            evidence=evidence,
            risks=risks,
            options=options,
            recommendation=rec,
            rationale=rationale,
            confidence=confidence,
            suggested_impact=impact,
            suggested_confidence=confidence,
        )

    def answer_question(self, question: str, items: list[dict[str, Any]], stats: dict[str, Any]) -> AskAnswer:
        if not items:
            return AskAnswer(
                answer="I couldn't find feedback related to that question.",
                cited_feedback_ids=[],
                follow_up_questions=["What are the most common complaints this month?"],
            )
        top = items[:3]
        lines = [
            f"Found {stats.get('count', len(items))} related pieces of feedback from "
            f"{stats.get('customers', 0)} customers in {len(stats.get('countries', []))} countries. "
            f"Sentiment: {stats.get('negative_pct', 0)}% negative, {stats.get('positive_pct', 0)}% positive.",
        ]
        if stats.get("top_categories"):
            lines.append("Most common types: " + ", ".join(f"{c} ({n})" for c, n in stats["top_categories"]) + ".")
        if stats.get("top_themes"):
            lines.append("Main themes: " + ", ".join(f"{t} ({n})" for t, n in stats["top_themes"]) + ".")
        lines.append("Most relevant feedback:")
        for it in top:
            lines.append(f"- [#{it['id']}] \"{first_sentence(it['text'], 180)}\"")
        return AskAnswer(
            answer="\n".join(lines),
            cited_feedback_ids=[it["id"] for it in top],
            follow_up_questions=[
                "Which customers with the highest MRR are affected?",
                "Is this trend growing compared with last month?",
            ],
        )

    # -- closing the loop -------------------------------------------------------
    _TEMPLATES: dict[str, tuple[str, str]] = {
        "en": ("Now live: {title}", "Hi {{name}},\n\nYou asked us for this, and it's now live: {title}.\n\n{details}Thank you for taking the time to share your feedback. It directly shaped this change.\n\nReply to this email if you have more ideas.\n\nThe {company} team"),
        "de": ("Jetzt verfügbar: {title}", "Hallo {{name}},\n\nSie hatten sich das gewünscht, und jetzt ist es da: {title}.\n\n{details}Danke, dass Sie sich die Zeit für Ihr Feedback genommen haben. Es hat diese Änderung direkt beeinflusst.\n\nAntworten Sie einfach auf diese E-Mail, wenn Sie weitere Ideen haben.\n\nIhr {company}-Team"),
        "es": ("Ya disponible: {title}", "Hola {{name}}:\n\nNos lo pediste y ya está disponible: {title}.\n\n{details}Gracias por dedicar tiempo a compartir tu opinión. Ha influido directamente en este cambio.\n\nResponde a este correo si tienes más ideas.\n\nEl equipo de {company}"),
        "fr": ("Disponible maintenant : {title}", "Bonjour {{name}},\n\nVous nous l'aviez demandé, c'est désormais disponible : {title}.\n\n{details}Merci d'avoir pris le temps de partager votre avis. Il a directement guidé ce changement.\n\nRépondez à cet e-mail si vous avez d'autres idées.\n\nL'équipe {company}"),
        "pt": ("Já disponível: {title}", "Olá {{name}},\n\nVocê nos pediu isto e já está disponível: {title}.\n\n{details}Obrigado por compartilhar sua opinião. Ela influenciou diretamente esta mudança.\n\nResponda a este e-mail se tiver mais ideias.\n\nEquipe {company}"),
        "it": ("Ora disponibile: {title}", "Ciao {{name}},\n\nCe lo avevi chiesto e ora è disponibile: {title}.\n\n{details}Grazie per aver condiviso il tuo feedback. Ha guidato direttamente questa modifica.\n\nRispondi a questa email se hai altre idee.\n\nIl team di {company}"),
        "nl": ("Nu beschikbaar: {title}", "Hallo {{name}},\n\nJe vroeg erom en het is nu beschikbaar: {title}.\n\n{details}Bedankt voor je feedback. Die heeft deze verandering direct gevormd.\n\nBeantwoord deze e-mail als je meer ideeën hebt.\n\nHet {company}-team"),
    }

    def release_note(self, payload: dict[str, Any]) -> Message:
        lang = (payload.get("language") or "en").split("-")[0]
        subject_t, body_t = self._TEMPLATES.get(lang, self._TEMPLATES["en"])
        details = (payload.get("description") or "").strip()
        if lang != "en" and lang in self._TEMPLATES:
            details = ""  # description is in the working language; don't mix languages
        body = (body_t.replace("{title}", payload["title"]).replace("{details}", f"{details}\n\n" if details else "")
                .replace("{company}", payload.get("company") or "product"))
        return Message(subject=subject_t.replace("{title}", payload["title"])[:300], body=body)

    def localize(self, message: Message, target_language: str) -> Message:
        raise ProviderError("The offline engine can't translate free text; use a release-note template instead")

    def supports_template_language(self, lang: str) -> bool:
        return lang.split("-")[0] in self._TEMPLATES
