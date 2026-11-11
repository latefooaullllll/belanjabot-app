"""
Kalkulator BelanjaBot: mengubah kalimat berisi angka menjadi hasil hitungan.

Mesin kemiripan (engine.py) hanya mengembalikan teks tetap, padahal BelanjaBot harus
MENGHITUNG. Modul ini menambahkan tiga kemampuan:
  1. deteksi()  : aturan prioritas kata kunci (modal/dijual > kembalian > hemat > diskon)
  2. ekstrak()  : membaca angka format Indonesia (Rp150.000, 80rb, 1,5 juta, 20%)
  3. proses()   : isi slot, tanya slot yang kosong, validasi, lalu hitung

Intent di file tema yang punya kunci "handler" dilayani modul ini.
Status percakapan (slot yang sudah terisi) dibawa lewat `context`.
"""
import re

# --------------------------------------------------------------------------- #
# 1. Aturan prioritas intent (urutan = prioritas)
# --------------------------------------------------------------------------- #
KATA_KUNCI = [
    ("untung_rugi", re.compile(r"\b(modal|dijual|menjual|jual|untung|rugi|laba|impas)\b")),
    ("kembalian", re.compile(
        r"\b(kembalian\w*|uang kembali|kembali berapa|(?:di)?bayar (?:pakai|pake|dengan))\b")),
    ("potongan", re.compile(r"\b(hemat\w*|potongan|dipotong|menghemat)\b")),
    ("diskon", re.compile(r"\b(diskon\w*|disc|harga akhir|obral)\b|%|\bpersen\b")),
]

# Pilihan menu pada sapaan: (1) Diskon (2) Untung-Rugi (3) Kembalian
MENU = {"1": "diskon", "2": "untung_rugi", "3": "kembalian"}

SLOT = {
    "diskon": ["harga", "persen"],
    "potongan": ["harga", "persen"],
    "untung_rugi": ["modal", "jual"],
    "kembalian": ["total", "bayar"],
}
TANYA = {
    "harga": "Berapa harga barangnya sebelum diskon?",
    "persen": "Diskonnya berapa persen?",
    "modal": "Modalnya berapa?",
    "jual": "Dijual berapa?",
    "total": "Total belanjanya berapa?",
    "bayar": "Uang yang dibayarkan berapa?",
}
PEMBUKA = {
    "diskon": "Siap, kita hitung diskon.",
    "potongan": "Siap, kita hitung berapa yang kamu hemat.",
    "untung_rugi": "Siap, kita hitung untung-rugi.",
    "kembalian": "Siap, kita hitung kembalian.",
}
# Kata penunjuk: angka yang muncul tepat setelah kata ini milik slot tersebut
HINT = {
    "modal": ["modal", "beli", "membeli", "kulak"],
    "jual": ["dijual", "jual", "menjual"],
    "total": ["belanja", "belanjaan", "total", "harga"],
    "bayar": ["bayar", "dibayar", "pakai", "pake", "uang"],
}

# --------------------------------------------------------------------------- #
# 2. Membaca angka
# --------------------------------------------------------------------------- #
POLA_PERSEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|persen\b)")
POLA_UANG = re.compile(
    r"(?<![\w.,])(-)?(?:rp\.?\s*)?(\d+(?:[.,]\d+)*)(?:\s*(rb|ribu|k|jt|juta)\b)?")
KALI = {"rb": 1_000, "ribu": 1_000, "k": 1_000, "jt": 1_000_000, "juta": 1_000_000}


def ke_angka(teks: str, satuan: str | None = None) -> float:
    """'150.000' -> 150000 ; '1,5' + 'juta' -> 1500000 ; '12,5' -> 12.5"""
    if "." in teks and "," in teks:
        teks = teks.replace(".", "").replace(",", ".")
    elif "." in teks:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", teks):   # titik = pemisah ribuan
            teks = teks.replace(".", "")
    elif "," in teks:
        if teks.count(",") > 1:
            teks = teks.replace(",", "")
        else:
            teks = teks.replace(",", ".")              # koma = desimal
    nilai = float(teks) * KALI.get(satuan, 1)
    return int(nilai) if nilai == int(nilai) else nilai


def ekstrak(teks: str):
    """Kembalikan (daftar persen, daftar uang). Uang berisi posisi agar bisa dipasangkan kata."""
    persen = [ke_angka(m.group(1)) for m in POLA_PERSEN.finditer(teks)]
    bersih = POLA_PERSEN.sub(lambda m: " " * len(m.group()), teks)   # posisi tetap
    uang = []
    for m in POLA_UANG.finditer(bersih):
        nilai = ke_angka(m.group(2), m.group(3))
        uang.append({"start": m.start(), "end": m.end(), "nilai": -nilai if m.group(1) else nilai})
    return persen, uang


def rp(n: float) -> str:
    n = round(n, 2)
    if n == int(n):
        s = f"{int(abs(n)):,}".replace(",", ".")
    else:
        s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if n < 0 else "") + "Rp" + s


def pct(p: float) -> str:
    return f"{p:g}".replace(".", ",") + "%"


# --------------------------------------------------------------------------- #
# 3. Deteksi intent, isi slot, hitung
# --------------------------------------------------------------------------- #
def deteksi(pesan: str) -> str | None:
    """Kunci handler menurut aturan prioritas, atau None bila bukan soal hitungan."""
    teks = pesan.lower()
    for kunci, pola in KATA_KUNCI:
        if pola.search(teks):
            return kunci
    return None


def isi_slot(kunci: str, teks: str, slots: dict) -> None:
    persen, uang = ekstrak(teks)
    urutan = SLOT[kunci]

    if kunci in ("diskon", "potongan"):
        if persen and slots.get("persen") is None:
            slots["persen"] = persen[0]
        sisa = list(uang)
        if slots.get("harga") is None and slots.get("persen") is None and len(sisa) >= 2:
            kecil = min(sisa, key=lambda a: a["nilai"])      # "diskon 20 harga 150000"
            if kecil["nilai"] <= 100:
                slots["persen"] = kecil["nilai"]
                sisa.remove(kecil)
        elif slots.get("harga") is not None and slots.get("persen") is None and sisa:
            slots["persen"] = sisa.pop(0)["nilai"]           # jawaban "20" atas "berapa persen?"
        if slots.get("harga") is None and sisa:
            slots["harga"] = sisa.pop(0)["nilai"]
        return

    terpakai = set()
    for slot in [s for s in urutan if slots.get(s) is None]:
        for hint in HINT[slot]:
            for m in re.finditer(rf"\b{hint}\b", teks):
                for i, a in enumerate(uang):
                    if i not in terpakai and 0 <= a["start"] - m.end() <= 20:
                        slots[slot] = a["nilai"]
                        terpakai.add(i)
                        break
                if slots.get(slot) is not None:
                    break
            if slots.get(slot) is not None:
                break
    sisa = [a for i, a in enumerate(uang) if i not in terpakai]
    for slot in urutan:                                       # sisanya menurut urutan
        if slots.get(slot) is None and sisa:
            slots[slot] = sisa.pop(0)["nilai"]


def validasi(kunci: str, s: dict) -> str | None:
    if any(v <= 0 for k, v in s.items() if k != "persen"):
        return "Harga harus lebih dari nol."
    if "persen" in s:
        if s["persen"] > 100:
            return "Diskon tidak mungkin lebih dari 100%, coba cek lagi angkanya."
        if s["persen"] <= 0:
            return "Diskonnya harus lebih dari 0%."
    if kunci == "kembalian" and s["bayar"] < s["total"]:
        return f"Uangnya kurang {rp(s['total'] - s['bayar'])}."
    return None


def hitung(kunci: str, s: dict) -> str:
    if kunci == "diskon":
        h, p = s["harga"], s["persen"]
        pot = p / 100 * h
        return (f"Hitung diskon:\n1. Potongan = {pct(p)} × {rp(h)} = {rp(pot)}\n"
                f"2. Harga akhir = {rp(h)} − {rp(pot)} = {rp(h - pot)}\n"
                f"Jadi kamu cukup bayar {rp(h - pot)}.")
    if kunci == "potongan":
        h, p = s["harga"], s["persen"]
        pot = p / 100 * h
        return (f"Hitung potongan:\n1. Potongan = {pct(p)} × {rp(h)} = {rp(pot)}\n"
                f"Jadi kamu hemat {rp(pot)} (harga akhir {rp(h - pot)}).")
    if kunci == "untung_rugi":
        m, j = s["modal"], s["jual"]
        selisih = j - m
        if selisih == 0:
            return "Impas, tidak untung dan tidak rugi."
        persen = f" (sekitar {pct(round(abs(selisih) / m * 100, 1))} dari modal)"
        if selisih > 0:
            kata = (f"Harga jual lebih besar dari modal, jadi pedagang untung {rp(selisih)}"
                    f"{persen}.")
        else:
            kata = (f"Harga jual lebih kecil dari modal, jadi pedagang rugi {rp(-selisih)}"
                    f"{persen}.")
        return f"Hitung untung-rugi:\n1. Selisih = {rp(j)} − {rp(m)} = {rp(selisih)}\n2. {kata}"
    t, b = s["total"], s["bayar"]                              # kembalian
    if b == t:
        return "Uang pas, tidak ada kembalian."
    return f"Hitung kembalian:\n1. Kembalian = {rp(b)} − {rp(t)} = {rp(b - t)}\nJadi kembaliannya {rp(b - t)}."


def proses(pesan: str, theme: dict, context: dict | None = None) -> dict | None:
    """Layani pesan hitungan. None bila pesan bukan urusan kalkulator (serahkan ke mesin kemiripan)."""
    tags = {i["handler"]: i["tag"] for i in theme["intents"] if i.get("handler")}
    if not tags:
        return None
    teks = pesan.lower().strip()
    ctx = context if isinstance(context, dict) and context.get("handler") in tags else None

    kunci, slots, dari_menu = deteksi(teks), {}, False
    if kunci is None and ctx:                    # jawaban atas pertanyaan slot kosong
        persen, uang = ekstrak(teks)
        if persen or uang:
            kunci = ctx["handler"]
    if kunci is None and teks in MENU:           # memilih (1)/(2)/(3) dari menu
        kunci, dari_menu = MENU[teks], True
    if kunci is None or kunci not in tags:
        return None
    if ctx and ctx["handler"] == kunci:
        slots = dict(ctx["slots"])

    if not dari_menu:
        isi_slot(kunci, teks, slots)

    for slot in SLOT[kunci]:
        if slots.get(slot) is None:
            tanya = TANYA[slot] if kunci != "potongan" or slot != "harga" else \
                "Berapa harga barangnya sebelum diskon?"
            kosong_semua = not any(slots.get(s) is not None for s in SLOT[kunci])
            teks_balas = f"{PEMBUKA[kunci]} {tanya}" if kosong_semua else tanya
            return {"reply": teks_balas, "intent": tags[kunci], "score": 1.0,
                    "context": {"handler": kunci, "slots": slots}}

    galat = validasi(kunci, slots)
    return {"reply": galat or hitung(kunci, slots), "intent": tags[kunci], "score": 1.0,
            "context": None}
