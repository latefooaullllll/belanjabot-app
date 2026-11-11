"""Uji integrasi route Flask (test client)."""
import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.db")}).test_client()


def test_halaman_utama_dan_chat(client):
    assert "BelanjaBot" in client.get("/").get_data(as_text=True)
    assert client.get("/chat/belanja").status_code == 200
    assert client.get("/chat/tidak-ada").status_code == 404


def test_api_chat_hitung_diskon(client):
    d = client.post("/api/chat", json={"message": "Baju Rp150.000 diskon 20%", "theme": "belanja"}).get_json()
    assert "Rp120.000" in d["reply"] and "context" not in d


def test_slot_terbawa_antar_request_lewat_sesi(client):
    client.post("/api/chat", json={"message": "hitung kembalian", "theme": "belanja"})
    client.post("/api/chat", json={"message": "47500", "theme": "belanja"})
    d = client.post("/api/chat", json={"message": "50000", "theme": "belanja"}).get_json()
    assert "Rp2.500" in d["reply"]


@pytest.mark.parametrize("payload", [{"message": "", "theme": "belanja"},
                                     {"message": "halo", "theme": "salah"},
                                     {"message": "a" * 501, "theme": "belanja"}, {}])
def test_input_tidak_valid_400(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 400


def test_riwayat_dan_hapus(client):
    client.post("/api/chat", json={"message": "halo", "theme": "belanja"})
    assert len(client.get("/api/history/belanja").get_json()) == 2
    client.delete("/api/history/belanja")
    assert client.get("/api/history/belanja").get_json() == []


def test_admin_key(tmp_path):
    c = create_app({"TESTING": True, "DATABASE": str(tmp_path / "a.db"), "ADMIN_KEY": "x"}).test_client()
    assert c.get("/admin/belanja").status_code == 403
    assert c.get("/admin/belanja?key=x").status_code == 200
