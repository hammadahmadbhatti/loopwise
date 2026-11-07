import pytest

from app.ai.concepts import concepts_in
from app.ai.heuristic import HeuristicProvider, score_sentiment

H = HeuristicProvider()


@pytest.mark.parametrize("text,rating,lang,label,category,urgency,churn", [
    ("The app crashes every time I try to export a report to CSV. Very frustrating!", None, "en", "negative", "bug", "high", False),
    ("Would love a dark mode, my eyes hurt at night", None, "en", "neutral", "feature_request", "low", False),
    ("Die App ist super langsam seit dem letzten Update, das Laden dauert ewig.", 2, "de", "negative", "performance", "medium", False),
    ("Me cobraron dos veces este mes, necesito un reembolso urgente o voy a cancelar.", 1, "es", "negative", "pricing", "critical", True),
    ("J'adore l'application, très facile à utiliser. Merci!", 5, "fr", "positive", "praise", "low", False),
    ("Your pricing is way too expensive for small teams, we are switching to a competitor.", None, "en", "negative", "pricing", "high", True),
    ("Password reset emails never arrive, I'm locked out and can't log in.", 1, "en", "negative", "bug", "critical", False),
    ("How do I invite my team members?", None, "en", "neutral", "question", "low", False),
    ("Le mode sombre serait génial, et l'export PDF aussi s'il vous plaît !", None, "fr", "neutral", "feature_request", "low", False),
    ("It would be great to have an export to PDF", None, "en", "neutral", "feature_request", "low", False),
])
def test_offline_analysis(text, rating, lang, label, category, urgency, churn):
    a = H.analyze_feedback(text, working_language="en", context={"rating": rating})
    assert (a.language, a.sentiment_label, a.category, a.urgency, a.churn_risk) == (lang, label, category, urgency, churn)
    assert a.translation == ""  # offline engine never pretends to translate
    assert -1 <= a.sentiment <= 1


def test_negation_and_intensifiers():
    assert score_sentiment("not bad at all") > score_sentiment("bad")
    assert score_sentiment("super slow") < score_sentiment("slow") < 0


def test_rating_blends_with_text():
    assert score_sentiment("ok", rating=5) == 1.0
    assert score_sentiment("great tool", rating=1) < score_sentiment("great tool")


def test_concepts_cross_language():
    assert "slow" in concepts_in("Das Dashboard ist extrem langsam")
    assert "slow" in concepts_in("El panel está lentísimo")
    assert {"charge", "twice"} <= set(concepts_in("J'ai été débité deux fois"))
    assert "darkmode" in concepts_in("Graag een donkere modus")
    assert "sso" in concepts_in("SAMLによるシングルサインオン")


def test_theme_label_uses_concepts():
    label = H.label_theme(["Dashboard is so slow", "Das Dashboard ist langsam", "slow dashboard loading"], keywords=["dashboard"])
    assert label.name == "Dashboard & Performance"  # equal counts: dictionary order decides, never hash order
    label = H.label_theme(["Reports time out", "Das Dashboard ist langsam", "slow dashboard"], keywords=[])
    assert label.name == "Performance & Dashboard"  # more items mention speed than the dashboard


def test_release_note_templates_are_localized():
    payload = {"title": "CSV export", "description": "Export any report.", "company": "Acme"}
    de = H.release_note({**payload, "language": "de"})
    en = H.release_note({**payload, "language": "en"})
    assert de.subject.startswith("Jetzt verfügbar") and "{{name}}" in de.body
    assert "Export any report." in en.body and "Export any report." not in de.body
