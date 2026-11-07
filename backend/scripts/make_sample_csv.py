"""Generate tests/fixtures/sample_feedback.csv: realistic multilingual feedback for a B2B SaaS product.

Deterministic (fixed seed). Dates are spread over the 90 days before --anchor (default: today),
with a deliberate spike of dashboard-performance complaints in the final week.

    python scripts/make_sample_csv.py [--anchor 2026-11-07] [--out tests/fixtures/sample_feedback.csv]
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

# Fictional people. Emails use subdomains of example.com (reserved by IANA, null MX), so nothing can ever be
# delivered to a real inbox even if SMTP is switched on with this data.
CUSTOMERS = [
    # email, name, company, country, plan, mrr
    ("anna@northwind.example.com", "Anna Becker", "Northwind GmbH", "Germany", "Enterprise", 2400),
    ("lukas@kranwerk.example.com", "Lukas Hoffmann", "Kranwerk", "Germany", "Pro", 199),
    ("sophie@bauhaus-labs.example.com", "Sophie Wagner", "Bauhaus Labs", "Germany", "Pro", 199),
    ("jonas@alpenlogistik.example.com", "Jonas Gruber", "Alpen Logistik", "Austria", "Starter", 49),
    ("mia@zuriwerk.example.com", "Mia Keller", "Zuriwerk", "Switzerland", "Enterprise", 1800),
    ("carlos@solmedia.example.com", "Carlos Ruiz", "Sol Media", "Spain", "Pro", 199),
    ("lucia@andesfin.example.com", "Lucía Torres", "Andes Finanzas", "Chile", "Enterprise", 1500),
    ("diego@mercadoverde.example.com", "Diego Hernández", "Mercado Verde", "Mexico", "Starter", 49),
    ("valentina@pampa.example.com", "Valentina Gómez", "Pampa Digital", "Argentina", "Pro", 199),
    ("camille@lumiere.example.com", "Camille Martin", "Lumière Studio", "France", "Pro", 199),
    ("hugo@atelier-nord.example.com", "Hugo Bernard", "Atelier Nord", "France", "Starter", 49),
    ("chloe@montreal-ux.example.com", "Chloé Tremblay", "Montréal UX", "Canada", "Enterprise", 1200),
    ("joao@ipanema.example.com", "João Silva", "Ipanema Tech", "Brazil", "Pro", 199),
    ("beatriz@lisboa.example.com", "Beatriz Costa", "Lisboa Cloud", "Portugal", "Starter", 49),
    ("rafael@saopaulo.example.com", "Rafael Souza", "SP Commerce", "Brazil", "Enterprise", 2100),
    ("giulia@milano.example.com", "Giulia Rossi", "Milano Design", "Italy", "Pro", 199),
    ("marco@torinodata.example.com", "Marco Bianchi", "Torino Data", "Italy", "Starter", 49),
    ("daan@grachten.example.com", "Daan de Vries", "Grachten BV", "Netherlands", "Pro", 199),
    ("emma@utrecht.example.com", "Emma Jansen", "Utrecht Analytics", "Netherlands", "Enterprise", 1600),
    ("yuki@sakura.example.com", "Yuki Tanaka", "Sakura Systems", "Japan", "Enterprise", 2000),
    ("haruto@kyoto.example.com", "Haruto Sato", "Kyoto Craft", "Japan", "Pro", 199),
    ("sarah@acme.example.com", "Sarah Johnson", "Acme Corp", "United States", "Enterprise", 2500),
    ("mike@brightpath.example.com", "Mike Chen", "BrightPath", "United States", "Pro", 199),
    ("olivia@greenleaf.example.com", "Olivia Brown", "Greenleaf", "United States", "Starter", 49),
    ("james@redwood.example.com", "James Miller", "Redwood Labs", "United States", "Pro", 199),
    ("emily@harbor.example.com", "Emily Davis", "Harbor Freight Tech", "United States", "Enterprise", 2200),
    ("noah@summit.example.com", "Noah Wilson", "Summit AI", "United States", "Pro", 199),
    ("ava@pinecrest.example.com", "Ava Moore", "Pinecrest", "United States", "Free", 0),
    ("liam@northstar.example.com", "Liam Taylor", "Northstar Dev", "Canada", "Pro", 199),
    ("isla@thistle.example.com", "Isla Campbell", "Thistle & Co", "United Kingdom", "Pro", 199),
    ("oliver@londonbridge.example.com", "Oliver Smith", "LondonBridge", "United Kingdom", "Enterprise", 1900),
    ("amelia@kiwiworks.example.com", "Amelia Walker", "KiwiWorks", "New Zealand", "Starter", 49),
    ("jack@outback.example.com", "Jack Thompson", "Outback Ops", "Australia", "Pro", 199),
    ("priya@chennai.example.com", "Priya Raman", "Chennai Soft", "India", "Pro", 199),
    ("arjun@bangalore.example.com", "Arjun Mehta", "Bangalore Labs", "India", "Starter", 49),
    ("fatima@lahoretech.example.com", "Fatima Khan", "Lahore Tech", "Pakistan", "Starter", 49),
    ("ahmed@dubaiventures.example.com", "Ahmed Al Mansoori", "Dubai Ventures", "United Arab Emirates", "Enterprise", 1700),
    ("lars@fjord.example.com", "Lars Hansen", "Fjord AS", "Norway", "Pro", 199),
    ("elin@stockholm.example.com", "Elin Johansson", "Stockholm Studio", "Sweden", "Free", 0),
    ("kofi@accra.example.com", "Kofi Mensah", "Accra Digital", "Ghana", "Free", 0),
    ("zanele@capetown.example.com", "Zanele Dlamini", "Cape Town Co", "South Africa", "Starter", 49),
    ("tom@freeuser.example.com", "Tom Baker", "", "United States", "Free", 0),
    ("nina@freelance.example.com", "Nina Schulz", "", "Germany", "Free", 0),
    ("pablo@estudio.example.com", "Pablo Martín", "Estudio Pablo", "Spain", "Free", 0),
    ("lea@paris-free.example.com", "Léa Dubois", "", "France", "Free", 0),
]

# theme -> list of (language, text, rating or None)
THEMES: dict[str, list[tuple[str, str, int | None]]] = {
    "export": [
        ("en", "Please add a way to export reports to CSV. We copy numbers into spreadsheets by hand every week.", 3),
        ("en", "We really need CSV export for the monthly reports, our finance team asks for it constantly.", None),
        ("en", "Exporting dashboards to PDF or Excel would save us hours. Is this on the roadmap?", 3),
        ("en", "Can't share reports with my boss because there is no export to PDF. Would love that feature.", None),
        ("en", "Missing CSV export is the main reason we still use our old reporting tool alongside yours.", 2),
        ("de", "Bitte eine Export-Funktion für Berichte als CSV oder Excel hinzufügen. Wir kopieren alles manuell.", 3),
        ("de", "Ein PDF-Export der Berichte fehlt uns sehr, das wäre schön für unsere Kunden.", None),
        ("es", "Sería genial poder exportar los informes a CSV o Excel. Ahora lo hacemos a mano.", 3),
        ("fr", "J'aimerais pouvoir exporter les rapports en CSV ou PDF pour notre comptabilité.", None),
        ("pt", "Seria ótimo poder exportar os relatórios para CSV. Hoje copiamos tudo manualmente.", 4),
        ("nl", "Het zou fijn zijn om rapporten naar CSV of Excel te exporteren.", None),
    ],
    "dashboard_slow": [
        ("en", "The dashboard has become extremely slow since last week, it takes over 30 seconds to load.", 1),
        ("en", "Dashboard loading is painfully slow now. Our whole team is waiting on it every morning.", 2),
        ("en", "Reports page times out constantly. This slowness is blocking our weekly review.", 1),
        ("en", "Why is the dashboard so slow lately? Loading charts takes forever.", 2),
        ("en", "Performance of the analytics dashboard got much worse after the update. Super slow.", 2),
        ("de", "Das Dashboard ist seit dem letzten Update extrem langsam, das Laden dauert ewig.", 1),
        ("de", "Die Ladezeit der Berichte ist unerträglich langsam geworden.", 2),
        ("pt", "O painel está muito lento, demora mais de um minuto para carregar os gráficos.", 1),
        ("es", "El panel está lentísimo desde la última actualización, tarda muchísimo en cargar.", 2),
        ("fr", "Le tableau de bord est devenu très lent, le chargement prend une éternité.", 2),
        ("ja", "ダッシュボードの読み込みが非常に遅くなりました。毎朝待たされています。", 2),
    ],
    "billing_double": [
        ("en", "I was charged twice for this month's subscription. Please refund the duplicate payment urgently.", 1),
        ("en", "Our invoice shows a double charge for November. This needs to be fixed immediately or we cancel.", 1),
        ("en", "Billing charged our card twice after upgrading the plan. Very frustrating.", 1),
        ("es", "Me cobraron dos veces este mes, necesito un reembolso urgente o voy a cancelar.", 1),
        ("fr", "J'ai été débité deux fois pour l'abonnement ce mois-ci, merci de me rembourser.", 1),
        ("de", "Uns wurde das Abo doppelt abgebucht. Bitte dringend erstatten.", 1),
    ],
    "dark_mode": [
        ("en", "Would love a dark mode, my eyes hurt when working late at night.", 4),
        ("en", "Dark mode please! Everything else is great.", 5),
        ("en", "Any plans for a dark theme? The bright white UI is hard on the eyes.", 4),
        ("de", "Ein Dark Mode wäre toll, besonders abends.", 4),
        ("it", "Vorrei una modalità scura, sarebbe molto più comoda di sera.", 4),
        ("nl", "Graag een donkere modus toevoegen, dat zou fijn zijn.", 4),
    ],
    "sso": [
        ("en", "We need SSO with Okta or Azure AD before we can roll this out to the whole company.", 3),
        ("en", "Single sign-on via Google Workspace is a must for our security team. Please add SAML SSO.", 3),
        ("en", "Our IT department won't approve the tool without SAML single sign-on support.", 2),
        ("de", "Ohne SSO über Azure AD können wir das Tool nicht unternehmensweit einführen.", 3),
        ("ja", "SAMLによるシングルサインオンに対応してほしいです。セキュリティ部門の要件です。", 3),
    ],
    "password_reset": [
        ("en", "Password reset emails never arrive, I'm locked out of my account and can't log in.", 1),
        ("en", "Can't log in: the reset password link expired immediately. Urgent, my team is blocked.", 1),
        ("en", "The password reset email goes nowhere. Checked spam too. I cannot log in at all.", 1),
        ("pt", "Não consigo entrar, o email de redefinição de senha nunca chega.", 1),
        ("de", "Ich kann mich nicht anmelden, die E-Mail zum Zurücksetzen des Passworts kommt nie an.", 1),
    ],
    "mobile_offline": [
        ("en", "The mobile app needs an offline mode, our field technicians often have no signal.", 3),
        ("en", "Offline mode for the iPhone app would be huge for us when visiting customer sites.", 3),
        ("es", "Necesitamos que la app móvil funcione sin conexión, nuestros técnicos trabajan en el campo.", 3),
        ("fr", "Un mode hors ligne dans l'application mobile serait très utile sur le terrain.", 3),
    ],
    "support_praise": [
        ("en", "Your support team is amazing. Fixed my issue within an hour. Thank you!", 5),
        ("en", "Fantastic customer service, Maria was super helpful and patient.", 5),
        ("en", "Love the product, the onboarding was smooth and easy. Great job!", 5),
        ("de", "Super Support, sehr schnelle und hilfreiche Antwort. Danke!", 5),
        ("es", "Excelente atención al cliente, muy rápidos y amables. ¡Gracias!", 5),
        ("fr", "Service client excellent, réponse rapide et utile. Merci beaucoup !", 5),
        ("pt", "Suporte excelente, resolveram meu problema muito rápido. Obrigado!", 5),
        ("it", "Assistenza eccellente, veloci e gentilissimi. Grazie!", 5),
    ],
    "pricing_small_teams": [
        ("en", "Your pricing is way too expensive for small teams. We are looking at alternatives.", 2),
        ("en", "The jump from Starter to Pro is too expensive for a 3-person team. Thinking about switching to a competitor.", 2),
        ("en", "Love the tool but the price per seat is too high for a small startup like ours.", 3),
        ("de", "Für kleine Teams ist der Preis leider viel zu teuer. Wir überlegen zu kündigen.", 2),
        ("es", "El precio es demasiado caro para equipos pequeños.", 2),
        ("pt", "O preço é caro demais para equipes pequenas, estamos pensando em cancelar.", 2),
    ],
    "slack": [
        ("en", "A Slack integration for notifications would be great, so the team sees new alerts instantly.", 4),
        ("en", "Please integrate with Slack and Microsoft Teams for alerts.", 4),
        ("en", "Can you add Slack notifications when a report is ready?", 4),
        ("de", "Eine Slack-Integration für Benachrichtigungen wäre sehr hilfreich.", 4),
    ],
    "navigation": [
        ("en", "The settings menu is confusing, I can never find where to manage users.", 2),
        ("en", "Navigation is unintuitive. Too many clicks to get to the team settings.", 3),
        ("en", "Hard to find the billing page, the menu layout is cluttered and confusing.", 3),
        ("fr", "La navigation n'est pas intuitive, je ne trouve jamais les paramètres d'équipe.", 3),
        ("it", "Il menu delle impostazioni è complicato e confuso.", 3),
    ],
    "upload_crash": [
        ("en", "The app crashes every time I upload a file larger than 10MB.", 1),
        ("en", "Uploading attachments crashes the app on Safari. Error 500 every time.", 1),
        ("en", "File upload is broken, it fails with an error after reaching 90%.", 2),
        ("de", "Die App stürzt beim Hochladen größerer Dateien jedes Mal ab.", 1),
        ("es", "La aplicación se cae cada vez que subo un archivo grande. Error constante.", 1),
    ],
}

# How recent each theme is: (min_days_ago, max_days_ago)
RECENCY = {
    "dashboard_slow": (0, 6),  # emerging issue this week
    "billing_double": (1, 20),
    "password_reset": (2, 40),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--anchor", default=date.today().isoformat())
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "tests/fixtures/sample_feedback.csv"))
    args = parser.parse_args()
    anchor = datetime.fromisoformat(args.anchor).replace(hour=12)
    rng = random.Random(42)
    by_lang: dict[str, list] = {}
    country_lang = {
        "Germany": "de", "Austria": "de", "Switzerland": "de", "Spain": "es", "Chile": "es", "Mexico": "es",
        "Argentina": "es", "France": "fr", "Canada": "fr", "Brazil": "pt", "Portugal": "pt", "Italy": "it",
        "Netherlands": "nl", "Japan": "ja",
    }
    for c in CUSTOMERS:
        lang = country_lang.get(c[3], "en")
        if c[3] == "Canada" and c[1].startswith("Liam"):
            lang = "en"
        by_lang.setdefault(lang, []).append(c)

    rows = []
    for theme, entries in THEMES.items():
        for lang, text, rating in entries:
            pool = by_lang.get(lang) or by_lang["en"]
            cust = rng.choice(pool)
            lo, hi = RECENCY.get(theme, (0, 89))
            created = anchor - timedelta(days=rng.randint(lo, hi), hours=rng.randint(0, 10), minutes=rng.randint(0, 59))
            source = rng.choice(["widget", "survey", "support", "app_review", "email"])
            rows.append({
                "text": text, "email": cust[0], "name": cust[1], "company": cust[2], "country": cust[3],
                "plan": cust[4], "mrr": cust[5], "rating": rating or "", "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
                "source": source,
            })
    rng.shuffle(rows)
    rows.sort(key=lambda r: r["created_at"])
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
