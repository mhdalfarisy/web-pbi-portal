import os

from mantra import create_app
from mantra.config import Config

app = create_app()

if __name__ == "__main__":
    exit_code = 0
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        mode = ("SKIPPED (AUTH_DISABLED=1 in .env, signed in as Super Admin)" if Config.AUTH_DISABLED
                else "ON (email + password)")
        print(f" * Power BI Portal: http://localhost:{Config.PORT}  |  Login: {mode}"
              f"  |  Debug: {'ON (FLASK_DEBUG=1)' if Config.DEBUG else 'OFF'}")
    try:
        # Buka lewat http://localhost:<PORT> (bukan 127.0.0.1) supaya cocok dengan redirect URI di Microsoft Entra.
        # Debugger Werkzeug hanya aktif kalau FLASK_DEBUG=1 di .env (bisa menjalankan kode di server).
        app.run(host="localhost", port=Config.PORT, debug=Config.DEBUG)
    except SystemExit as exc:
        exit_code = exc.code
        raise
    finally:
        # Tampilkan penyebab server berhenti (hanya di proses utama, bukan proses reloader mode debug)
        if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            reason = ("stopped (Ctrl+C or terminal closed)" if not exit_code
                      else f"crashed (exit code {exit_code}), see the error above")
            print(f"\n * Power BI Portal server {reason}.")
            print(f" * Start it again: python run.py  then open http://localhost:{Config.PORT}")
