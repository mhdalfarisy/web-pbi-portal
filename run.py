from mantra import create_app

app = create_app()

if __name__ == "__main__":
    # Buka lewat http://localhost:5000 (bukan 127.0.0.1) supaya cocok dengan redirect URI di Microsoft Entra
    app.run(host="localhost", port=5000, debug=True)
