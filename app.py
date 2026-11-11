"""
BelanjaBot - aplikasi web chatbot tematik dengan Flask.
Jalankan: python app.py   lalu buka http://127.0.0.1:5000
"""
import os
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, session

from chatbot import ChatbotEngine, ChatHistory, load_themes

BASE_DIR = Path(__file__).resolve().parent


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "ganti-dengan-kunci-rahasia"),
        DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "chat_history.db")),
        THEMES_DIR=str(BASE_DIR / "themes"),
        THRESHOLD=float(os.environ.get("THRESHOLD", "0.45")),
        ADMIN_KEY=os.environ.get("ADMIN_KEY", ""),
        MAX_LEN=500,
    )
    if config:
        app.config.update(config)

    themes = load_themes(app.config["THEMES_DIR"])
    engines = {tid: ChatbotEngine(t, app.config["THRESHOLD"]) for tid, t in themes.items()}
    history = ChatHistory(app.config["DATABASE"])

    def get_session_id() -> str:
        if "sid" not in session:
            session["sid"] = uuid.uuid4().hex
        return session["sid"]

    def get_theme_or_404(theme_id: str) -> dict:
        if theme_id not in themes:
            abort(404, description=f"Tema '{theme_id}' tidak ditemukan")
        return themes[theme_id]

    def check_admin():
        kunci = app.config["ADMIN_KEY"]
        if kunci and request.args.get("key") != kunci:
            abort(403, description="Kunci admin salah atau tidak ada")

    @app.route("/")
    def index():
        return render_template("index.html", themes=themes.values())

    @app.route("/chat/<theme_id>")
    def chat_page(theme_id):
        return render_template("chat.html", theme=get_theme_or_404(theme_id))

    @app.route("/admin/<theme_id>")
    def admin_page(theme_id):
        check_admin()
        theme = get_theme_or_404(theme_id)
        return render_template("admin.html", theme=theme,
                               summary=history.summary(theme_id),
                               stats=history.stats(theme_id),
                               unknown=history.unknown_questions(theme_id),
                               threshold=app.config["THRESHOLD"])

    @app.get("/api/themes")
    def api_themes():
        return jsonify([{"id": t["id"], "name": t["name"], "description": t["description"]}
                        for t in themes.values()])

    @app.post("/api/chat")
    def api_chat():
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()
        theme_id = data.get("theme", "")
        if theme_id not in engines:
            return jsonify({"error": "Tema tidak valid"}), 400
        if not message:
            return jsonify({"error": "Pesan tidak boleh kosong"}), 400
        if len(message) > app.config["MAX_LEN"]:
            return jsonify({"error": f"Pesan maksimal {app.config['MAX_LEN']} karakter"}), 400
        sid = get_session_id()
        ctx_key = f"ctx_{theme_id}"                      # slot yang menunggu dilengkapi
        result = engines[theme_id].reply(message, session.get(ctx_key))
        session[ctx_key] = result.pop("context", None)   # simpan di sesi, bukan ke browser
        history.add(sid, theme_id, "user", message, result["intent"], result["score"])
        history.add(sid, theme_id, "bot", result["reply"], result["intent"], result["score"])
        return jsonify(result)

    @app.post("/api/explain")
    def api_explain():
        data = request.get_json(silent=True) or {}
        theme_id = data.get("theme", "")
        if theme_id not in engines:
            return jsonify({"error": "Tema tidak valid"}), 400
        message = str(data.get("message", ""))[: app.config["MAX_LEN"]]
        return jsonify({"threshold": app.config["THRESHOLD"],
                        "candidates": engines[theme_id].explain(message)})

    @app.get("/api/history/<theme_id>")
    def api_history(theme_id):
        get_theme_or_404(theme_id)
        return jsonify(history.get(get_session_id(), theme_id))

    @app.delete("/api/history/<theme_id>")
    def api_clear_history(theme_id):
        get_theme_or_404(theme_id)
        history.clear(get_session_id(), theme_id)
        session.pop(f"ctx_{theme_id}", None)
        return jsonify({"status": "ok"})

    @app.get("/api/stats/<theme_id>")
    def api_stats(theme_id):
        check_admin()
        get_theme_or_404(theme_id)
        return jsonify(history.stats(theme_id))

    @app.errorhandler(403)
    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": err.description}), err.code
        return render_template("404.html", message=err.description, code=err.code), err.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
