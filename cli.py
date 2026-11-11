"""Chat dengan BelanjaBot di terminal. Contoh: python cli.py [--debug]. Ketik 'keluar' untuk berhenti."""
import argparse
from pathlib import Path

from chatbot import ChatbotEngine, load_themes

BASE_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Chatbot tematik di terminal")
    parser.add_argument("--tema", default="belanja")
    parser.add_argument("--ambang", type=float, default=0.45)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    themes = load_themes(BASE_DIR / "themes")
    if args.tema not in themes:
        print(f"Tema '{args.tema}' tidak ada. Pilihan: {', '.join(themes)}")
        return
    theme = themes[args.tema]
    bot = ChatbotEngine(theme, args.ambang)
    print(f"{theme['avatar']} {theme['bot_name']}: {theme['greeting']}")
    print("(ketik 'keluar' untuk berhenti)\n")
    konteks = None
    while True:
        try:
            pesan = input("Anda: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if pesan.lower() in {"keluar", "exit", "quit"}:
            break
        hasil = bot.reply(pesan, konteks)
        konteks = hasil.get("context")
        print(f"{theme['bot_name']}: {hasil['reply']}")
        print(f"  [intent: {hasil['intent'] or 'tidak dikenali'} · skor {hasil['score']:.2f}]")
        if args.debug:
            for i, k in enumerate(bot.explain(pesan), 1):
                print(f"  {i}. {k['intent']:<20} {k['score']:.2f} pola: \"{k['pattern']}\"")
        print()
    print("Sampai jumpa!")


if __name__ == "__main__":
    main()
