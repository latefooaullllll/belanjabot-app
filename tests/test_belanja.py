"""Uji tema BelanjaBot: kalkulator, aturan prioritas, pengisian slot, dan akurasi."""
from pathlib import Path

import pytest

from chatbot import kalkulator as k
from chatbot.engine import ChatbotEngine, load_themes, validate_theme

THEMES = load_themes(Path(__file__).resolve().parent.parent / "themes")


@pytest.fixture
def bot():
    return ChatbotEngine(THEMES["belanja"])


def balas(bot, pesan, ctx=None):
    h = bot.reply(pesan, ctx)
    return h["reply"], h["context"], h["intent"]


def test_tema_belanja_valid_dan_cukup_besar():
    t = THEMES["belanja"]
    assert validate_theme(t) == []
    assert len(t["intents"]) >= 10
    assert all(len(i["patterns"]) >= 5 and len(i["responses"]) >= 2 for i in t["intents"])
    assert len(t["suggestions"]) == 4


@pytest.mark.parametrize("teks, nilai", [
    ("Rp150.000", 150000), ("80rb", 80000), ("1,5 juta", 1500000),
    ("47.500", 47500), ("50000", 50000), ("Rp 2.5jt", 2500000),
])
def test_format_uang_indonesia(teks, nilai):
    _, uang = k.ekstrak(teks.lower())
    assert uang[0]["nilai"] == nilai


def test_diskon_contoh_modul(bot):
    r, ctx, intent = balas(bot, "Baju Rp150.000 diskon 20%, bayar berapa?")
    assert "20% × Rp150.000 = Rp30.000" in r
    assert "Rp150.000 − Rp30.000 = Rp120.000" in r
    assert ctx is None and intent == "hitung_diskon"


def test_potongan_memakai_hemat_walau_ada_kata_diskon(bot):
    r, _, intent = balas(bot, "Diskon 25% dari Rp80.000, hematnya berapa?")
    assert intent == "hitung_potongan" and "hemat Rp20.000" in r


def test_untung(bot):
    r, _, intent = balas(bot, "Beli batik Rp80.000, dijual Rp100.000. Untung atau rugi?")
    assert intent == "hitung_untung_rugi"
    assert "Rp100.000 − Rp80.000 = Rp20.000" in r and "untung Rp20.000" in r


def test_rugi_dan_urutan_kata_dibalik(bot):
    r, _, _ = balas(bot, "dijual 45rb, modalnya 50rb")
    assert "rugi Rp5.000" in r


def test_impas(bot):
    r, _, _ = balas(bot, "modal 70rb dijual 70rb")
    assert r == "Impas, tidak untung dan tidak rugi."


def test_kembalian(bot):
    r, _, intent = balas(bot, "Belanja Rp47.500, bayar Rp50.000, kembaliannya?")
    assert intent == "hitung_kembalian" and "Rp2.500" in r


def test_uang_kurang(bot):
    r, _, _ = balas(bot, "belanja 50.000 bayar pakai 45.000 kembaliannya berapa")
    assert r == "Uangnya kurang Rp5.000."


def test_diskon_lebih_dari_100_persen(bot):
    r, ctx, _ = balas(bot, "harga 100rb diskon 150%")
    assert r == "Diskon tidak mungkin lebih dari 100%, coba cek lagi angkanya."
    assert ctx is None


def test_angka_nol_ditolak(bot):
    r, _, _ = balas(bot, "harga 0 diskon 10%")
    assert r == "Harga harus lebih dari nol."


def test_prioritas_modal_atau_dijual_mengalahkan_diskon():
    assert k.deteksi("modal 80rb dijual diskon 10%") == "untung_rugi"
    assert k.deteksi("belanja 47500 bayar 50000 kembaliannya") == "kembalian"
    assert k.deteksi("halo") is None


def test_slot_kosong_ditanyakan_bertahap(bot):
    r1, c1, _ = balas(bot, "tolong hitung diskon")
    assert "Berapa harga barangnya sebelum diskon?" in r1
    r2, c2, _ = balas(bot, "150000", c1)
    assert r2 == "Diskonnya berapa persen?"
    r3, c3, _ = balas(bot, "20", c2)
    assert "Rp120.000" in r3 and c3 is None


def test_slot_untung_rugi_bertahap(bot):
    _, c, _ = balas(bot, "hitung untung rugi")
    r, c, _ = balas(bot, "80rb", c)
    assert r == "Dijual berapa?"
    r, c, _ = balas(bot, "100rb", c)
    assert "untung Rp20.000" in r


def test_pilihan_menu_angka(bot):
    r, c, _ = balas(bot, "3")
    assert "Total belanjanya berapa?" in r and c["handler"] == "kembalian"


def test_pesan_non_angka_membatalkan_slot(bot):
    _, c, _ = balas(bot, "hitung diskon")
    r, c2, intent = balas(bot, "terima kasih", c)
    assert intent == "terima_kasih" and c2 is None


def test_di_luar_tema_memberi_fallback(bot):
    h = bot.reply("siapa presiden indonesia")
    assert h["intent"] is None and h["reply"] in THEMES["belanja"]["fallback"]


def test_akurasi_data_uji_belanja_minimal_90_persen():
    from evaluate import baca_data, evaluasi
    akurasi, _ = evaluasi(THEMES["belanja"], baca_data("belanja"), 0.45)
    assert akurasi >= 0.9
