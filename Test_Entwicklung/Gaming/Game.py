# swift_hunt.py
# LAN-Schnitzeljagd (opt-in) – Taylor-Swift-Edition
from flask import Flask, request, session, redirect, url_for, render_template_string, flash
import unicodedata
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")

# ---- Hilfsfunktionen ----
def normalize(s: str) -> str:
    """Kleinschreibung + Diakritika entfernen + Trim, für robuste Vergleiche."""
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.split())

def contains_any(name: str, targets: set[str]) -> bool:
    n = normalize(name)
    return any(t in n for t in targets)

# ---- Rätsel-Definitionen ----
# Typen:
#  - "mc": Multiple Choice (choices, answer)
#  - "text": Freitext (answer_checker) – eigene Prüf-Logik
RIDDLES = [
    {
        "title": "Rätsel 1/5",
        "type": "mc",
        "question": "Auf welchem Album erschien der Song „Love Story“ ursprünglich?",
        "choices": ["Fearless", "Red", "Speak Now", "Midnights"],
        "answer": "Fearless",
        "hint": "Das Album gewann 2010 den Grammy als Album des Jahres.",
        "explain": "„Love Story“ erschien zuerst auf „Fearless“ (2008).",
    },
    {
        "title": "Rätsel 2/5",
        "type": "text",
        "question": "Wie lautet Taylors Glückszahl?",
        "placeholder": "Zahl eingeben …",
        "answer_checker": lambda txt: normalize(txt) in {"13"},
        "hint": "Diese Zahl taucht bei ihr sehr oft auf – z. B. als Easter Egg.",
        "explain": "Ihre Glückszahl ist 13.",
    },
    {
        "title": "Rätsel 3/5",
        "type": "mc",
        "question": "Unter welchem Pseudonym schrieb Taylor 2016 bei „This Is What You Came For“ mit?",
        "choices": ["Nils Sjöberg", "Rebecca Hart", "Ella Raines", "Archer Payne"],
        "answer": "Nils Sjöberg",
        "hint": "Skandinavisch klingender Name.",
        "explain": "Das Pseudonym war „Nils Sjöberg“.",
    },
    {
        "title": "Rätsel 4/5",
        "type": "text",
        "question": "Nenne mindestens einen Namen ihrer Katzen.",
        "placeholder": "z. B. Olivia …",
        # Akzeptiere 'Meredith Grey', 'Olivia Benson', 'Benjamin Button' (oder Kurzformen)
        "answer_checker": lambda txt: contains_any(
            txt,
            {"meredith", "olivia", "benjamin"}  # Kurzformen reichen
        ),
        "hint": "Zwei sind nach TV-Detektivinnen benannt.",
        "explain": "Ihre Katzen heißen Meredith Grey, Olivia Benson und Benjamin Button.",
    },
    {
        "title": "Finale 5/5",
        "type": "mc",
        "question": "Wie heißt die Rekordtour 2023–2025?",
        "choices": ["The Eras Tour", "The Reputation Tour", "Speak Now Tour", "Lover Fest"],
        "answer": "The Eras Tour",
        "hint": "Alle Schaffensphasen auf einer Bühne.",
        "explain": "„The Eras Tour“ – die Tour durch alle Schaffensphasen.",
    },
]

# ---- Templates (einfach & im Code eingebettet) ----
BASE_HTML = """
<!doctype html>
<html lang="de">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LAN Schnitzeljagd – Taylor Swift</title>
<style>
  :root { --bg:#0b1220; --card:#121a2b; --muted:#90a4b0; --acc:#7aa2ff; --good:#3ad29f; --bad:#ff6b6b;}
  *{box-sizing:border-box} body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;background:linear-gradient(180deg,#0b1220,#0b1220 30%,#0f1630);color:#e9f1f6}
  .wrap{max-width:880px;margin:20px auto;padding:16px}
  .card{background:var(--card);border:1px solid #1d2741;border-radius:16px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
  h1{font-size:28px;margin:0 0 10px}
  h2{font-size:20px;margin:14px 0}
  p{color:#cfe2ef;line-height:1.5}
  a{color:var(--acc);text-decoration:none}
  .btn{display:inline-block;background:var(--acc);color:#071324;border:none;padding:10px 16px;border-radius:12px;font-weight:600;cursor:pointer}
  .btn.outline{background:transparent;color:var(--acc);border:1px solid var(--acc)}
  .row{display:flex;gap:12px;flex-wrap:wrap}
  .choice{display:block;padding:12px;border:1px solid #26304e;border-radius:12px;cursor:pointer}
  .choice input{margin-right:8px}
  .hint{color:var(--muted);font-style:italic;margin-top:6px}
  .flash{margin:8px 0;padding:10px;border-radius:10px}
  .ok{background:rgba(58,210,159,.15);border:1px solid var(--good)}
  .err{background:rgba(255,107,107,.12);border:1px solid var(--bad)}
  footer{margin-top:16px;color:#9bb1bf}
  input[type=text]{width:100%;padding:12px;border-radius:10px;border:1px solid #26304e;background:#0c1426;color:#e9f1f6}
  .meta{color:#9bb1bf}
  .progress{height:8px;background:#0c1426;border:1px solid #26304e;border-radius:999px;overflow:hidden;margin:10px 0 2px}
  .bar{height:100%;background:var(--acc);width:{{progress}}%}
  .confetti{position:fixed;inset:0;pointer-events:none;overflow:hidden}
  .confetti span{position:absolute;font-size:24px;animation:drop 2.5s linear infinite}
  @keyframes drop{0%{transform:translateY(-10vh) rotate(0)}100%{transform:translateY(110vh) rotate(360deg)}}
</style>
<div class="wrap">
  <div class="card">
    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% if msgs %}
        {% for cat,msg in msgs %}
          <div class="flash {{'ok' if cat=='ok' else 'err'}}">{{msg}}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
  <footer>Opt-in Browser-Spiel im LAN • Nichts wird am System verändert • <a href="{{ url_for('reset') }}">Zurücksetzen</a></footer>
</div>
</html>
"""

INDEX_HTML = """
{% extends base %}
{% block content %}
  <h1>LAN-Schnitzeljagd: Taylor Swift 🎤</h1>
  <p>Kurzer Pausen-Spaß fürs Studium: 5 Fragen zu Taylor Swift. Öffne diese Adresse im Heimnetz (z. B. <span class="meta">http://DEINE-IP:5000</span>) und spiele im Browser mit.</p>
  <div class="progress"><div class="bar"></div></div>
  <div class="row">
    <form action="{{ url_for('start') }}" method="post">
      <button class="btn">Jetzt starten</button>
    </form>
    <a class="btn outline" href="{{ url_for('rules') }}">Regeln & Hinweise</a>
  </div>
{% endblock %}
"""

RULES_HTML = """
{% extends base %}
{% block content %}
  <h1>Regeln & Hinweise</h1>
  <ul>
    <li>Opt-in: Nur wer die Seite öffnet, spielt mit. Kein Eingriff ins System.</li>
    <li>Es gibt Multiple-Choice und Freitext-Antworten.</li>
    <li>Du kannst pro Frage einen Hinweis anzeigen.</li>
  </ul>
  <form action="{{ url_for('start') }}" method="post"><button class="btn">Los geht’s</button></form>
{% endblock %}
"""

RIDDLE_HTML = """
{% extends base %}
{% block content %}
  <div class="progress"><div class="bar"></div></div>
  <h1>{{ r['title'] }}</h1>
  <h2>{{ r['question'] }}</h2>

  {% if r['type']=='mc' %}
    <form action="{{ url_for('answer', rid=rid) }}" method="post">
      {% for c in r['choices'] %}
        <label class="choice"><input type="radio" name="choice" value="{{ c }}" required> {{ c }}</label>
      {% endfor %}
      <div class="row" style="margin-top:10px">
        <button class="btn">Antwort prüfen</button>
        <a class="btn outline" href="{{ url_for('riddle', rid=rid, hint=1) }}">Hinweis</a>
      </div>
    </form>
  {% else %}
    <form action="{{ url_for('answer', rid=rid) }}" method="post">
      <input type="text" name="text" placeholder="{{ r['placeholder'] }}" autofocus required>
      <div class="row" style="margin-top:10px">
        <button class="btn">Antwort prüfen</button>
        <a class="btn outline" href="{{ url_for('riddle', rid=rid, hint=1) }}">Hinweis</a>
      </div>
    </form>
  {% endif %}

  {% if show_hint %}
    <p class="hint">💡 Hinweis: {{ r['hint'] }}</p>
  {% endif %}

  {% if explain %}
    <p class="hint">ℹ️ {{ explain }}</p>
  {% endif %}
{% endblock %}
"""

FINISH_HTML = """
{% extends base %}
{% block content %}
  <h1>Geschafft! 🎉</h1>
  <p>Du hast <b>{{ correct }}</b> von <b>{{ total }}</b> Fragen korrekt beantwortet.</p>
  <div class="progress"><div class="bar"></div></div>
  <div class="row" style="margin-top:12px">
    <a class="btn" href="{{ url_for('reset') }}">Nochmal spielen</a>
    <a class="btn outline" href="{{ url_for('index') }}">Zur Startseite</a>
  </div>
  <div class="confetti">
    {% for i in range(60) %}
      <span style="left:{{ (i*13)%100 }}%; animation-delay:-{{ (i%10)/10 }}s">✨</span>
    {% endfor %}
  </div>
{% endblock %}
"""

# ---- Routes ----
@app.route("/")
def index():
    progress = progress_pct()
    return render_template_string(INDEX_HTML, base=BASE_HTML, progress=progress)

@app.post("/start")
def start():
    session["idx"] = 0
    session["correct"] = 0
    session["seen_hint"] = False
    return redirect(url_for("riddle", rid=0))

@app.get("/rules")
def rules():
    return render_template_string(RULES_HTML, base=BASE_HTML, progress=progress_pct())

@app.get("/reset")
def reset():
    session.clear()
    flash("Zurückgesetzt. Viel Spaß!","ok")
    return redirect(url_for("index"))

@app.get("/riddle/<int:rid>")
def riddle(rid: int):
    idx = session.get("idx", 0)
    if rid != idx:
        # halte Reihenfolge konsistent
        return redirect(url_for("riddle", rid=idx)) if idx < len(RIDDLES) else redirect(url_for("finish"))
    r = RIDDLES[rid]
    show_hint = request.args.get("hint") == "1"
    if show_hint:
        session["seen_hint"] = True
    return render_template_string(
        RIDDLE_HTML,
        base=BASE_HTML,
        r=r, rid=rid,
        show_hint=show_hint,
        explain=None,
        progress=progress_pct()
    )

@app.post("/answer/<int:rid>")
def answer(rid: int):
    if rid >= len(RIDDLES):  # safety
        return redirect(url_for("finish"))

    r = RIDDLES[rid]
    correct = False
    given = ""

    if r["type"] == "mc":
        given = request.form.get("choice","")
        correct = normalize(given) == normalize(r["answer"])
    else:
        given = request.form.get("text","")
        try:
            correct = bool(r["answer_checker"](given))
        except Exception:
            correct = False

    if correct:
        session["correct"] = int(session.get("correct", 0)) + 1
        flash("Richtig! " + r["explain"], "ok")
    else:
        flash("Leider falsch. " + r["explain"], "err")

    # Weiter
    session["idx"] = int(session.get("idx", 0)) + 1
    if session["idx"] >= len(RIDDLES):
        return redirect(url_for("finish"))
    return redirect(url_for("riddle", rid=session["idx"]))

@app.get("/finish")
def finish():
    total = len(RIDDLES)
    correct = int(session.get("correct", 0))
    # Fortschritt auf 100 % setzen
    return render_template_string(FINISH_HTML, base=BASE_HTML, correct=correct, total=total, progress=100)

def progress_pct() -> int:
    idx = int(session.get("idx", 0))
    total = len(RIDDLES)
    pct = int(round(100 * min(idx, total) / total)) if total else 0
    return pct

if __name__ == "__main__":
    # Im LAN erreichbar – z. B. http://0.0.0.0:5000  →  http://DEINE-IP:5000
    app.run(host="0.0.0.0", port=5000, debug=False)
