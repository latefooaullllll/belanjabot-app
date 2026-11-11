# BelanjaBot: cara menjalankan (Windows PowerShell)

1. Ekstrak zip ini, lalu buka foldernya (yang berisi app.py) di VS Code.
2. Di terminal VS Code (Ctrl + `):

    python -m venv venv
    venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python app.py

3. Buka http://127.0.0.1:5000/chat/belanja

Jika PowerShell menolak mengaktifkan venv, jalankan sekali:
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Perintah lain:
    pytest -v                                  # 32 uji otomatis
    python evaluate.py --tema belanja          # akurasi
    python evaluate.py --tema belanja --sweep  # akurasi pada berbagai ambang
    python cli.py --debug                      # chat di terminal
