"""Cross-lingual concept dictionary for the offline engine.

Without a translation model, "langsam", "lento" and "slow" share no tokens, so the
local embedder couldn't group them. This maps common product-feedback vocabulary
in EN/DE/ES/FR/PT/IT/NL (plus a few Japanese terms) onto shared concept ids that
are added as extra features. LLM providers don't need it: they translate first.
"""

from __future__ import annotations

import re

from .textutil import normalize, tokenize

# concept id -> (display label, terms). Terms ending in * are prefixes; terms with spaces are phrases.
CONCEPTS: dict[str, tuple[str, str]] = {
    "export": ("Export", "export*|exportar*|exporter|exportieren|esportare|esporta*|exporteren|download report*|エクスポート"),
    "report": ("Reports", "report*|bericht*|informe*|rapport*|relatorio*|relatório*|rapporti|rapporten|レポート"),
    "spreadsheet": ("CSV/Excel", "csv|excel|spreadsheet*|xlsx"),
    "dashboard": ("Dashboard", "dashboard*|panel|painel|tableau de bord|cruscotto|ダッシュボード"),
    "slow": ("Performance", "slow*|lag*|timeout*|times out|time out|timed out|takes forever|langsam*|ladezeit|dauert ewig|lento|lenta|"
                            "lentisimo|tarda*|lent|lente|eternite|demora*|traag|遅|performance|loading|"
                            "laden|cargar|chargement|carregar|caricamento"),
    "charge": ("Billing", "charge*|charged|billing|billed|invoice*|abgebucht|abbuchung|rechnung*|cobr*|factura*|"
                          "debite*|facture*|fatura*|addebit*|fattura*|gefactureerd|payment*|zahlung*|pago*|paiement*"),
    "twice": ("Duplicate charge", "twice|double|duplicate|doppelt|dos veces|deux fois|duas vezes|due volte|twee keer"),
    "refund": ("Refunds", "refund*|erstatt*|ruckerstattung|reembolso|rembours*|rimborso|terugbetal*"),
    "darkmode": ("Dark mode", "dark mode|dark theme|darkmode|dunkelmodus|dark-mode|modo oscuro|mode sombre|"
                              "modo escuro|modalita scura|donkere modus|ダークモード"),
    "sso": ("Single sign-on", "sso|saml|single sign*|okta|azure ad|シングルサインオン|google workspace"),
    "password": ("Password reset", "password*|passwort*|contrasena|mot de passe|senha|parola d'ordine|wachtwoord|パスワード"),
    "login": ("Login", "log in|login|logged out|locked out|sign in|anmelden|einloggen|iniciar sesion|entrar|"
                       "connecter|connexion|accedere|inloggen|ログイン"),
    "reset": ("Password reset", "reset*|zurucksetzen|restablecer|reinitialis*|redefini*|reimposta*|herstel*"),
    "upload": ("File upload", "upload*|hochlad*|subo|subir|telecharg*|televers*|carregar arquivo|enviar arquivo|"
                              "caricare|caricamento file|uploaden|attachment*|anhang|archivo*|fichier*|arquivo*|file"),
    "crash": ("Crashes", "crash*|sturzt ab|absturz|abgesturzt|se cae|se bloquea|plante|crashe|trava*|si blocca|"
                         "crasht|loopt vast|error 500|クラッシュ"),
    "offline": ("Offline mode", "offline|sin conexion|hors ligne|hors-ligne|sem conexao|sem internet|senza connessione|"
                                "no signal|kein netz|オフライン"),
    "mobile": ("Mobile app", "mobile|iphone|android|ios app|app movil|application mobile|aplicativo|app mobile|"
                             "mobiele app|celular|モバイル"),
    "support": ("Support", "support|customer service|soporte|suporte|assistenza|kundenservice|service client|"
                           "atencion al cliente|atendimento|klantenservice|helpdesk|サポート"),
    "price": ("Pricing", "price*|pricing|expensive|cost*|preis*|teuer|precio*|caro|cara|prix|cher|chere|preco|"
                         "prezzo|costoso|prijs|duur|seat|per seat|料金"),
    "smallteam": ("Small teams", "small team*|small startup|kleine teams|equipos pequenos|petites equipes|"
                                 "equipes pequenas|piccoli team|kleine teams|3-person"),
    "slack": ("Slack/Teams", "slack|microsoft teams|ms teams"),
    "notification": ("Notifications", "notification*|alert*|benachrichtigung*|notificacion*|notificacao*|notifica*|"
                                      "melding*|通知"),
    "settings": ("Settings", "settings|einstellungen|configuracion|ajustes|parametres|parametres d'equipe|"
                             "configuracoes|impostazioni|instellingen|設定"),
    "navigation": ("Navigation", "navigation|navigat*|menu*|menü|clicks|find where|hard to find|can never find|"
                                 "finde nicht|no encuentro|je ne trouve|nao encontro|non trovo|kan niet vinden"),
    "confusing": ("Usability", "confus*|unintuitive|not intuitive|pas intuitive|cluttered|complicated|kompliziert|"
                               "verwirrend|complicado|complique|complicato|ingewikkeld|unubersichtlich"),
    "praise": ("Praise", "amazing|fantastic|excellent|excelente|eccellente|hervorragend|great job|love the product|"
                         "super support|thank you|danke|gracias|merci|obrigado|grazie|bedankt"),
}

_COMPILED: dict[str, list[tuple[str, str]]] = {}


def _compile() -> dict[str, list[tuple[str, str]]]:
    if not _COMPILED:
        for cid, (_, terms) in CONCEPTS.items():
            _COMPILED[cid] = [("prefix" if t.endswith("*") else "phrase" if (" " in t or "-" in t or "'" in t
                               or not re.fullmatch(r"[a-z0-9]+", t)) else "word", normalize(t.rstrip("*")))
                              for t in terms.split("|") if t]
    return _COMPILED


def concepts_in(text: str) -> list[str]:
    """Concept ids present in the text (each at most once)."""
    norm = normalize(text)
    tokens = set(tokenize(text))
    found = []
    for cid, terms in _compile().items():
        for kind, term in terms:
            if kind == "word" and term in tokens:
                found.append(cid)
                break
            if kind == "prefix" and (any(t.startswith(term) for t in tokens) or
                                     (not term.isascii() and term in norm)):
                found.append(cid)
                break
            if kind == "phrase" and term in norm:
                found.append(cid)
                break
    return found


def concept_label(cid: str) -> str:
    return CONCEPTS[cid][0]
