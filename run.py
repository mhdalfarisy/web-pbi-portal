import os

from mantra import create_app
from mantra.config import Config

app = create_app()

if __name__ == "__main__":
    exit_code = 0
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        mode = ("DILEWATI (AUTH_DISABLED=1 di .env, masuk sebagai Super Admin)" if Config.AUTH_DISABLED
                else "AKTIF (email + password)")
        print(f" * MANTRA: http://localhost:{Config.PORT}  |  Login: {mode}")
    try:
        # Buka lewat http://localhost:<PORT> (bukan 127.0.0.1) supaya cocok dengan redirect URI di Microsoft Entra
        app.run(host="localhost", port=Config.PORT, debug=True)
    except SystemExit as exc:
        exit_code = exc.code
        raise
    finally:
        # Mode debug berhenti tanpa pesan; tampilkan penyebabnya (hanya di proses utama, bukan proses reloader)
        if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            reason = ("dihentikan (Ctrl+C atau terminal ditutup)" if not exit_code
                      else f"crash (exit code {exit_code}), lihat error di atas")
            print(f"\n * Server MANTRA berhenti: {reason}.")
            print(f" * Jalankan lagi: python run.py  lalu buka http://localhost:{Config.PORT}")
