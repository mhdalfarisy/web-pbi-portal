from mantra import create_app
from mantra.config import Config

app = create_app()

if __name__ == "__main__":
    # Buka lewat http://localhost:<PORT> (bukan 127.0.0.1) supaya cocok dengan redirect URI di Microsoft Entra
    app.run(host="localhost", port=Config.PORT, debug=True)
