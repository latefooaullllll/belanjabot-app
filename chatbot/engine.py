"""
Mesin chatbot berbasis aturan (rule-based).

Alur kerja:
  1. Praproses : huruf kecil -> buang tanda baca -> normalisasi kata tidak baku
                 -> buang kata henti (stopword).
  2. Pencocokan: setiap pola pada setiap intent diberi skor kemiripan
                 (gabungan Jaccard, kemiripan karakter/difflib, dan cakupan).
  3. Keputusan : intent dengan skor tertinggi dipilih jika skornya >= ambang batas;
                 jika tidak, chatbot memberi respons fallback.
  4. (BARU)    : intent bertanda "handler" di file tema (mis. BelanjaBot) dilayani
                 kalkulator.py: deteksi prioritas, isi slot, hitung.
"""
import json
import random
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from . import kalkulator

# Kamus normalisasi kata tidak baku -> baku (silakan ditambah sesuai tema)
NORMALISASI = {
    "gak": "tidak", "ga": "tidak", "nggak": "tidak", "enggak": "tidak", "tdk": "tidak",
    "gimana": "bagaimana", "gmn": "bagaimana", "bgmn": "bagaimana",
    "dmn": "dimana", "brp": "berapa", "berapakah": "berapa",
    "yg": "yang", "dgn": "dengan", "utk": "untuk", "buat": "untuk",
    "sy": "saya", "aku": "saya", "gue": "saya", "gw": "saya",
    "kak": "", "min": "", "dong": "", "sih": "", "nih": "", "ya": "", "yah": "",
    "makasih": "terima kasih", "thanks": "terima kasih", "thx": "terima kasih",
    "hai": "halo", "hi": "halo", "hello": "halo", "hallo": "halo",
}
# Tambahan tema belanja (kata tidak baku / bentuk berimbuhan -> kata dasar)
NORMALISASI.update({
    "disc": "diskon", "diskonnya": "diskon", "hematnya": "hemat", "kembaliannya": "kembalian",
    "kembalinya": "kembalian", "kmbalian": "kembalian", "pake": "pakai", "bayarnya": "bayar",
    "untungnya": "untung", "ruginya": "rugi", "modalnya": "modal", "hrg": "harga",
    "harganya": "harga", "brapa": "berapa", "berapaan": "berapa", "duit": "uang",
    "potongannya": "potongan", "artinya": "arti",
})

# Kata henti (stopword) bahasa Indonesia yang sederhana
STOPWORDS = {
    "yang", "di", "ke", "dari", "dan", "atau", "itu", "ini", "untuk", "dengan",
    "adalah", "apa", "saya", "mau", "ingin", "tolong", "bisa", "boleh", "kah",
    "pada", "akan", "juga", "ada", "tentang", "mohon", "info", "informasi",
}

# Bobot tiga ukuran kemiripan (jumlahnya harus 1)
BOBOT_JACCARD, BOBOT_FUZZY, BOBOT_CAKUPAN = 0.4, 0.3, 0.3

KUNCI_WAJIB_TEMA = ["id", "name", "bot_name", "avatar", "color", "description",
                    "greeting", "suggestions", "fallback", "intents"]


def preprocess(teks: str) -> list[str]:
    """Ubah kalimat mentah menjadi daftar token yang sudah dinormalisasi."""
    teks = teks.lower()
    teks = re.sub(r"[^a-z0-9\s]", " ", teks)          # buang tanda baca & emoji
    tokens = []
    for kata in teks.split():
        kata = NORMALISASI.get(kata, kata)
        for k in kata.split():                         # normalisasi bisa jadi 2 kata
            if k and k not in STOPWORDS:
                tokens.append(k)
    return tokens


def similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Skor kemiripan 0..1 antara token pesan (a) dan token pola (b)."""
    if not tokens_a or not tokens_b:
        return 0.0
    set_a, set_b = set(tokens_a), set(tokens_b)
    # 1) Jaccard: proporsi kata yang sama dari seluruh kata gabungan
    jaccard = len(set_a & set_b) / len(set_a | set_b)
    # 2) Kemiripan karakter: tahan terhadap salah ketik ("jadwl" ~ "jadwal")
    fuzzy = SequenceMatcher(None, " ".join(tokens_a), " ".join(tokens_b)).ratio()
    # 3) Cakupan: berapa bagian kata pola yang muncul di pesan
    cakupan = len(set_a & set_b) / len(set_b)
    return round(BOBOT_JACCARD * jaccard + BOBOT_FUZZY * fuzzy + BOBOT_CAKUPAN * cakupan, 4)


def validate_theme(theme: dict) -> list[str]:
    """Periksa struktur file tema. Kembalikan daftar masalah (kosong = valid)."""
    masalah = [f"kunci '{k}' tidak ada" for k in KUNCI_WAJIB_TEMA if k not in theme]
    if masalah:
        return masalah
    if not theme["fallback"]:
        masalah.append("daftar 'fallback' kosong")
    tags, pola_milik = set(), {}
    for i, intent in enumerate(theme["intents"]):
        for k in ("tag", "patterns", "responses"):
            if k not in intent:
                masalah.append(f"intent ke-{i + 1}: kunci '{k}' tidak ada")
        tag = intent.get("tag", f"#{i + 1}")
        if tag in tags:
            masalah.append(f"tag '{tag}' dipakai lebih dari sekali")
        tags.add(tag)
        if not intent.get("patterns"):
            masalah.append(f"intent '{tag}': patterns kosong")
        if not intent.get("responses"):
            masalah.append(f"intent '{tag}': responses kosong")
        for pola in intent.get("patterns", []):
            kunci = " ".join(preprocess(pola))
            if not kunci:
                masalah.append(f"intent '{tag}': pola '{pola}' kosong setelah praproses")
            elif kunci in pola_milik and pola_milik[kunci] != tag:
                masalah.append(f"pola '{pola}' ada di intent '{pola_milik[kunci]}' dan '{tag}'")
            pola_milik.setdefault(kunci, tag)
    return masalah


def load_themes(folder: str | Path) -> dict[str, dict]:
    """Baca semua file tema *.json di folder dan kembalikan dict {id_tema: data}."""
    themes = {}
    for path in sorted(Path(folder).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        masalah = validate_theme(data)
        if masalah:
            raise ValueError(f"File tema {path.name} tidak valid:\n- " + "\n- ".join(masalah))
        themes[data["id"]] = data
    return themes


class ChatbotEngine:
    """Satu objek engine melayani satu tema."""

    def __init__(self, theme: dict, threshold: float = 0.45):
        self.theme = theme
        self.threshold = threshold
        # Praproses semua pola sekali saja saat engine dibuat (lebih cepat)
        self._patterns = [
            (intent["tag"], pola, preprocess(pola))
            for intent in theme["intents"]
            for pola in intent["patterns"]
        ]
        self._responses = {i["tag"]: i["responses"] for i in theme["intents"]}
        # {kunci handler: tag intent}, kosong untuk tema biasa (kampus, kuliner, wisata)
        self._handlers = {i["handler"]: i["tag"] for i in theme["intents"] if i.get("handler")}

    def explain(self, pesan: str, top: int = 3) -> list[dict]:
        """Kandidat intent terbaik beserta pola dan skornya (untuk belajar/debug)."""
        tokens = preprocess(pesan)
        terbaik = {}
        for tag, pola, pola_tokens in self._patterns:
            skor = similarity(tokens, pola_tokens)
            if tag not in terbaik or skor > terbaik[tag]["score"]:
                terbaik[tag] = {"intent": tag, "pattern": pola, "score": skor}
        return sorted(terbaik.values(), key=lambda x: x["score"], reverse=True)[:top]

    def _intent_informasi(self, pesan: str, context: dict | None = None) -> bool:
        """Dahulukan intent informasi jika pesan tidak berisi angka."""
        if context or re.search(r"\\d", pesan):
            return False
        kandidat = self.explain(pesan, top=1)
        return (bool(kandidat) and kandidat[0]["score"] >= self.threshold
                and kandidat[0]["intent"] not in self._handlers.values())

    def classify(self, pesan: str) -> tuple[str | None, float]:
        """Kembalikan (tag_intent, skor). Tag None jika di bawah ambang."""
        if self._handlers and not self._intent_informasi(pesan):
            kunci = kalkulator.deteksi(pesan)
            if kunci in self._handlers:
                return self._handlers[kunci], 1.0
        kandidat = self.explain(pesan, top=1)
        if not kandidat:
            return None, 0.0
        best = kandidat[0]
        if best["score"] < self.threshold:
            return None, best["score"]
        return best["intent"], best["score"]

    def _isi_placeholder(self, teks: str) -> str:
        """Ganti placeholder dinamis, misalnya {waktu} dan {tanggal}."""
        now = datetime.now()
        return (teks.replace("{waktu}", now.strftime("%H:%M"))
                    .replace("{tanggal}", now.strftime("%d-%m-%Y"))
                    .replace("{nama_bot}", self.theme["bot_name"]))

    def reply(self, pesan: str, context: dict | None = None) -> dict:
        """Proses pesan pengguna dan kembalikan respons lengkap.

        `context` hanya dipakai tema berkalkulator: slot yang sudah terisi dari giliran
        sebelumnya. Hasil selalu memuat kunci "context" untuk disimpan pemanggil.
        """
        if not pesan or not pesan.strip():
            return {"reply": "Pesannya masih kosong. Silakan ketik pertanyaan Anda.",
                    "intent": None, "score": 0.0, "context": None}
        if self._handlers and not self._intent_informasi(pesan, context):
            hasil = kalkulator.proses(pesan, self.theme, context)
            if hasil:
                return hasil
        tag, skor = self.classify(pesan)
        if tag is None:
            teks = random.choice(self.theme["fallback"])
        else:
            teks = random.choice(self._responses[tag])
        return {"reply": self._isi_placeholder(teks), "intent": tag, "score": skor,
                "context": None}
