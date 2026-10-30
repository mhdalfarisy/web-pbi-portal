# Pendalaman 2 — Kode Inti Fondasi (Fase 1-6)

> Bagian dari [Panduan Development Berurutan](../PANDUAN_DEVELOPMENT_BERURUTAN.md). Potongan kode di bab ini **disalin
> dari repository** (28 Okt 2026); baris yang tidak relevan diganti `...` dan beberapa komentar panjang dibuang, logikanya
> tidak diubah. Setiap potongan dijelaskan per bagian: apa artinya, dan **apa yang rusak
> kalau bagian itu dihapus**. Konsep dasarnya ada di [Pendalaman 1](01_KONSEP_TEKNOLOGI.md).

## Daftar isi

1. [`config.py` — membaca `.env`](#1-configpy--membaca-env) (Fase 1)
2. [`create_app()` — merakit aplikasi](#2-create_app--merakit-aplikasi) (Fase 2, 4, 5, 6)
3. [`db.py` — koneksi & migrasi](#3-dbpy--koneksi--migrasi) (Fase 3)
4. [`accounts.py` — autentikasi & hak akses](#4-accountspy--autentikasi--hak-akses) (Fase 4)
5. [`auth.py` — session, decorator, route login](#5-authpy--session-decorator-route-login) (Fase 4)
6. [`registry.py` — sistem plug-in dashboard](#6-registrypy--sistem-plug-in-dashboard) (Fase 5)
7. [`portal.py` — contoh view yang memakai semuanya](#7-portalpy--contoh-view-yang-memakai-semuanya) (Fase 6)

---

## 1. `config.py` — membaca `.env`

File: [mantra/config.py](../../mantra/config.py)

```python
BASE_DIR = Path(__file__).resolve().parent.parent

_ENV_FILE = dotenv_values(BASE_DIR / ".env")
ENV_OVERRIDDEN = sorted(k for k, v in _ENV_FILE.items() if k in os.environ and os.environ[k] != (v or ""))
load_dotenv(BASE_DIR / ".env", override=True)


def _flag(name):
    return os.environ.get(name, "").strip() == "1"


def _env_file_flag(name):
    return (_ENV_FILE.get(name) or "").strip() == "1"
```

| Bagian | Arti | Kalau dihapus / diubah |
|---|---|---|
| `Path(__file__).resolve().parent.parent` | `mantra/config.py` → `mantra/` → root project | `.env` dicari di folder kerja terminal; menjalankan script dari folder lain gagal membaca `.env` |
| `_ENV_FILE = dotenv_values(...)` | isi file `.env` apa adanya, tanpa menyentuh `os.environ` | `_env_file_flag` dan `ENV_OVERRIDDEN` tidak punya sumber |
| `ENV_OVERRIDDEN` | nama variabel terminal yang **nilainya berbeda** dari `.env` | peringatan "Variabel environment terminal ditimpa" hilang, kebocoran `.env` project lain tidak terdeteksi |
| `load_dotenv(..., override=True)` | `.env` menang atas terminal | kredensial dari terminal/project lain diam-diam dipakai |
| `_flag(name)` | `True` hanya kalau nilainya persis `"1"` | `"0"`, `"false"`, `""` semuanya berarti mati; aman dari salah ketik |
| `_env_file_flag(name)` | sama, tapi **hanya** dari file | `AUTH_DISABLED=1` di terminal bisa mematikan login |

```python
class Config:
    PORT = int(os.environ.get("PORT") or 5001)
    DEBUG = _flag("FLASK_DEBUG")
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE")
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get("SESSION_HOURS") or 8))
    ...
    AUTH_DISABLED = _env_file_flag("AUTH_DISABLED")
    PBI_TENANT_ID = os.environ.get("PBI_TENANT_ID") or ENTRA_TENANT_ID
    ...
    CACHE_SECONDS = int(os.environ.get("CACHE_MINUTES") or 10) * 60
    ...
    DASHBOARD_STRICT = os.environ.get("DASHBOARD_STRICT", "1").strip() != "0"
    INSTANCE_DIR = BASE_DIR / "instance"
    APP_DB = INSTANCE_DIR / "mantra.db"
```

- `os.environ.get("PORT") or 5001`: `or` menangani **dua** kasus sekaligus, variabel tidak ada **dan** baris `PORT=`
  kosong. `.get("PORT", 5001)` hanya menangani yang pertama, lalu `int("")` crash.
- Nama atribut huruf besar karena `app.config.from_object(Config)` **hanya menyalin atribut huruf besar**.
- `SECRET_KEY`, `SESSION_COOKIE_*`, `PERMANENT_SESSION_LIFETIME` adalah nama yang dikenali Flask; sisanya nama milik
  MANTRA yang dibaca kode sendiri.
- `DASHBOARD_STRICT` default `True`: satu dashboard rusak menghentikan start (cocok untuk development, ketahuan cepat).

---

## 2. `create_app()` — merakit aplikasi

File: [mantra/\_\_init\_\_.py](../../mantra/__init__.py). Urutan baris di sini **adalah** urutan Fase 2-6.

```python
def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(Config.INSTANCE_DIR))
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)  # dipakai tests/ (database sementara, AUTH_DISABLED=0)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("FLASK_SECRET_KEY belum diisi di .env")

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(portal.bp)
    app.register_blueprint(chat_routes.bp)
    app.register_blueprint(admin.bp)
    registry.init_app(app)  # semua folder di mantra/dashboards/

    # Katalog dashboard di database (dipakai untuk hak akses) mengikuti dashboard yang terdaftar di kode
    conn = db.connect(app.config["APP_DB"])
    try:
        accounts.sync_dashboards(conn, registry.all_dashboards())
    finally:
        conn.close()
```

| Baris | Fase | Arti | Kalau dihapus |
|---|---|---|---|
| `Flask(__name__, instance_path=...)` | 2 | `__name__` = `"mantra"` → Flask mencari `templates/` dan `static/` di dalam package `mantra/` | template tidak ditemukan |
| `app.config.update(test_config)` | 2 | test bisa menimpa `APP_DB` ke file sementara | test menulis ke `instance/mantra.db` asli |
| `raise RuntimeError(...)` | 2 | gagal **cepat** dengan pesan jelas | app start tanpa secret; session tidak bisa ditandatangani, error muncul belakangan dan membingungkan |
| `db.init_app(app)` | 3 | migrasi + backup saat start | tabel tidak ada → semua query akun error |
| `register_blueprint(...)` | 4-6, 11 | memasang route | `url_for` ke endpoint itu `BuildError` |
| `registry.init_app(app)` | 5 | scan `mantra/dashboards/` | tidak ada dashboard sama sekali |
| `sync_dashboards` | 5 | tabel `dashboards` = daftar di kode | Admin tidak bisa memberi akses ke dashboard baru (tidak ada id-nya di DB) |
| `try / finally conn.close()` | 5 | koneksi ini dibuka **di luar** request (tidak lewat `g`), jadi ditutup manual | file DB tetap terbuka (tidak fatal, tetapi bocor) |

```python
    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            expected = session.get("_csrf", "")
            given = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected.encode(), given.encode("utf-8", "replace")):
                abort(400, "Invalid security token. Please reload the page and try again.")

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp
```

- `request.form.get("_csrf") or request.headers.get("X-CSRF-Token")`: form HTML mengirim field tersembunyi, `fetch()`
  JavaScript mengirim header. Satu pemeriksa untuk keduanya.
- `not expected`: session belum punya token (belum pernah membuka halaman) → tolak. Tanpa cek ini, token kosong vs
  token kosong dianggap sama.
- `hmac.compare_digest`: waktu perbandingan tidak bergantung pada posisi karakter yang beda (anti *timing attack*).
  `.encode()` karena `compare_digest` melempar `TypeError` (jadi HTTP 500) untuk string non-ASCII.
- `setdefault`: kalau sebuah route sudah memasang header itu sendiri, nilainya tidak ditimpa.

```python
    @app.context_processor
    def inject_globals():
        def csrf_token():
            if "_csrf" not in session:
                session["_csrf"] = secrets.token_urlsafe(32)
            return session["_csrf"]

        user = auth.current_user()
        dashboard = registry.current()
        is_admin = auth.is_admin(user)
        return {
            "csrf_token": csrf_token,
            "current_user": user,
            "user_is_admin": is_admin,
            "pending_resets": accounts.pending_reset_count() if is_admin and user["db_id"] is not None else 0,
            "dashboard": dashboard,
            "chat_enabled": bool(dashboard and dashboard.chat and providers.configured()),
            "report_favorite": bool(user and dashboard and dashboard.slug in db.favorites(user["id"])),
        }
```

- `csrf_token` dikirim sebagai **fungsi**, bukan nilai: token baru dibuat hanya kalau template benar-benar memanggil
  `{{ csrf_token() }}`.
- `registry.current()` mengembalikan dashboard milik blueprint request ini (atau `None` di halaman portal). Template
  dashboard membaca `dashboard.title`, `dashboard.pages`.
- `user["db_id"] is not None`: user mode `AUTH_DISABLED=1` tidak punya baris di DB, jadi badge dilewati.
- `chat_enabled` butuh **tiga** syarat: halaman dashboard, dashboard punya `ChatSpec`, dan provider AI terkonfigurasi.
  Inilah yang menyembunyikan tombol Ask AI saat `GEMINI_API_KEY` kosong.

```python
    def _error(code, message):
        if "/api/" in request.path or request.is_json:
            return jsonify(error=message), code
        return render_template("portal/error.html", code=code, message=message), code
```
Satu pola untuk semua error: route API mendapat JSON (`fetch()` di browser bisa membaca `data.error`), halaman biasa
mendapat HTML. Handler 400/404/500 memanggil fungsi ini.

---

## 3. `db.py` — koneksi & migrasi

File: [mantra/core/db.py](../../mantra/core/db.py)

```python
def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(path, backup_dir):
    """Pasang migrasi yang belum jalan. Mengembalikan (versi_awal, versi_akhir, path_backup_atau_None)."""
    conn = connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError(f"Database versi {version} lebih baru dari kode (versi {len(MIGRATIONS)}). "
                               "Pakai kode terbaru, atau pulihkan backup yang sesuai.")
        if version == len(MIGRATIONS):
            return version, version, None
        has_data = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0] > 0
        saved = backup(conn, backup_dir, f"before-v{len(MIGRATIONS)}") if has_data else None
        for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            try:
                conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        return version, len(MIGRATIONS), saved
    finally:
        conn.close()
```

Jalannya untuk tiga kondisi:

| Kondisi DB | `version` | Yang terjadi |
|---|---|---|
| File baru | 0 | `has_data` False → tanpa backup → migrasi 1, 2, 3 → log "dimigrasi dari versi 0 ke 3" |
| Sudah versi 3 | 3 | `return` di baris kedua; tidak ada log, tidak ada backup |
| Versi 2 + data | 2 | backup `mantra-<waktu>-before-v3.db` → hanya migrasi 3 |
| Versi 4 (kode lama, DB baru) | 4 | **tolak start**; mencegah kode lama merusak skema yang tidak dikenalnya |

- `MIGRATIONS[version:]` + `enumerate(..., start=version + 1)`: hanya migrasi yang belum jalan, dengan nomor versi
  yang benar.
- `PRAGMA user_version = {number}` **di dalam** transaksi yang sama dengan SQL migrasi: versi hanya naik kalau SQL-nya
  sukses.

```python
def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["APP_DB"])
    return g.db


def _close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
```
Satu koneksi **per request** (lazy: baru dibuka kalau dipakai), ditutup otomatis oleh `teardown_appcontext`. Karena
`current_app.config["APP_DB"]`, test yang menimpa `APP_DB` otomatis memakai DB sementara.

---

## 4. `accounts.py` — autentikasi & hak akses

File: [mantra/core/accounts.py](../../mantra/core/accounts.py)

```python
def authenticate(email, password):
    email = normalize_email(email)
    user = get_user_by_email(email) if email else None
    if user is None or not user["password_hash"]:
        check_password_hash(_DUMMY_HASH, password or "")
        audit("login_failed", "user", user["id"] if user else None, email=email, reason="invalid")
        return None, "invalid"
    if user["locked_until"] and user["locked_until"] > _now():
        audit("login_failed", "user", user["id"], email=email, reason="locked")
        return None, "locked"
    if not check_password_hash(user["password_hash"], password or ""):
        failed = user["failed_logins"] + 1
        locked = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S") \
            if failed >= MAX_FAILED_LOGINS else None
        conn = get_db()
        conn.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else failed, locked, user["id"]))
        conn.commit()
        audit("login_failed", "user", user["id"], email=email, reason="invalid", attempt=failed)
        if locked:
            audit("account_locked", "user", user["id"], email=email, minutes=LOCK_MINUTES)
        return None, "invalid"
    if not user["is_active"]:
        audit("login_failed", "user", user["id"], email=email, reason="inactive")
        return None, "inactive"
    record_login(user, method="password")
    return get_user(user["id"]), None
```

Urutan pemeriksaan **disengaja**:

1. **Email tidak terdaftar** → tetap menghitung hash palsu (`_DUMMY_HASH`). Menghitung hash itu lambat (sengaja);
   tanpa baris ini, email tidak terdaftar dijawab jauh lebih cepat, sehingga penyerang bisa menebak email mana yang ada.
2. **Terkunci** dicek **sebelum** password: saat terkunci, password benar pun ditolak.
3. **Password salah** → tambah `failed_logins`; pada kegagalan ke-5 set `locked_until` dan reset hitungan ke 0.
   Jawaban tetap `"invalid"`; pesan "locked" baru terlihat di percobaan ke-6 (terbukti di output nyata Fase 4).
4. **Nonaktif** dicek **setelah** password benar: pesan "akun nonaktif" hanya diberikan kepada orang yang tahu
   password, bukan kepada siapa saja yang menebak email.
5. Tanggal disimpan sebagai teks `"YYYY-mm-dd HH:MM:SS"`, jadi `locked_until > _now()` adalah perbandingan teks yang
   kebetulan benar karena formatnya urut.

```python
def set_password(user_id, password, must_change=False, actor=None, action="password_changed"):
    conn = get_db()
    conn.execute(
        """UPDATE users SET password_hash = ?, must_change_password = ?, password_changed_at = ?,
               session_version = session_version + 1, failed_logins = 0, locked_until = NULL,
               reset_requested_at = NULL, updated_at = ?
           WHERE id = ?""",
        (generate_password_hash(password), int(must_change), _now(), _now(), user_id))
    conn.commit()
    audit(action, "user", user_id, actor=actor)
    return get_user(user_id)["session_version"]
```
`session_version = session_version + 1` adalah **mekanisme logout paksa**: semua cookie session lama membawa `sv` lama,
dan `auth.current_user` menolaknya. `set_active` dan `set_role` melakukan hal yang sama.

```python
def allowed_slugs(user_id, is_super_admin):
    if is_super_admin:
        rows = get_db().execute("SELECT slug FROM dashboards WHERE is_active = 1")
    else:
        rows = get_db().execute(
            """SELECT d.slug FROM user_dashboard_access a
               JOIN dashboards d ON d.id = a.dashboard_id
               JOIN users u ON u.id = a.user_id
               WHERE a.user_id = ? AND d.is_active = 1 AND u.is_active = 1""", (user_id,))
    return {r["slug"] for r in rows}
```
**Default deny**: user biasa hanya mendapat slug yang punya baris di `user_dashboard_access`, dan dashboard harus
aktif. Super Admin mendapat semua yang aktif. Satu-satunya sumber kebenaran hak akses adalah fungsi ini.

```python
def audit(action, target_type=None, target_id=None, actor=None, **detail):
    """Catat aktivitas penting. JANGAN pernah memasukkan password, hash, token, atau secret ke detail."""
    ...
    conn.execute(
        "INSERT INTO audit_log (actor_id, actor_email, action, target_type, target_id, detail, ip) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (actor_id, actor_email, action, target_type, None if target_id is None else str(target_id),
         json.dumps(detail, ensure_ascii=False, default=str) if detail else None, ip))
```
`**detail` disimpan sebagai JSON, lalu `describe_audit` mengubahnya menjadi kalimat di halaman Audit Log. Semua query
memakai placeholder `?`, tidak pernah f-string dengan input user (anti SQL injection).

---

## 5. `auth.py` — session, decorator, route login

File: [mantra/core/auth.py](../../mantra/core/auth.py)

```python
def current_user():
    """User yang login (dict), atau None. Dibaca ulang dari database sekali per request."""
    if "user" in g:
        return g.user
    user = None
    if auth_disabled():
        user = _dev_user()
    elif session.get("uid") is not None:
        row = accounts.get_user(session["uid"])
        if row is not None and row["is_active"] and row["session_version"] == session.get("sv"):
            user = _session_user(row)
        else:
            session.clear()
    g.user = user
    return user
```
- `if "user" in g`: dipanggil puluhan kali per request (decorator, guard, template), DB hanya dibaca sekali.
- Tiga syarat sesi valid: user masih ada, masih aktif, dan `session_version` sama. Salah satu gagal → `session.clear()`
  (logout seketika di request berikutnya).

```python
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(_login_url())
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                accounts.audit("access_denied", "page", request.path, actor=user, required=list(roles))
                if "/api/" in request.path:
                    return jsonify(error="You do not have access."), 403
                return render_template("portal/denied.html", admin_only=True), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


admin_required = role_required("super_admin")
```
- `@wraps(view)` menjaga nama fungsi asli. Tanpa itu, semua view bernama `wrapped` dan Flask menolak mendaftarkan
  endpoint dobel.
- `role_required` **membungkus** `login_required`: belum login → redirect ke login; login tetapi role salah → 403 +
  audit.

```python
@bp.before_app_request
def require_password_change():
    endpoint = request.endpoint or ""
    if endpoint in _PASSWORD_CHANGE_ALLOWED or endpoint.endswith(".static"):
        return None
    user = current_user()
    if user and user["must_change_password"]:
        if "/api/" in request.path:
            return jsonify(error="Please change your temporary password first."), 403
        return redirect(url_for("auth.change_password", next=request.full_path.rstrip("?")))
    return None
```
`before_app_request` (bukan `before_request`) berlaku untuk **semua** blueprint, termasuk dashboard. Pengecualian:
halaman ganti password itu sendiri, logout, login, dan file static (CSS/JS halaman ganti password harus tetap termuat).

```python
def _start_session(row, sso=False):
    session.clear()  # cegah session fixation
    session.permanent = True
    session["uid"] = row["id"]
    session["sv"] = row["session_version"]
    ...
```
`session.permanent = True` membuat cookie berlaku `PERMANENT_SESSION_LIFETIME` (8 jam), bukan hilang saat browser
ditutup.

---

## 6. `registry.py` — sistem plug-in dashboard

File: [mantra/core/registry.py](../../mantra/core/registry.py)

```python
@dataclass
class Dashboard:
    slug: str                    # URL: /d/<slug>/
    title: str
    description: str
    category: str
    icon: str
    color: str
    dataset: object = None
    blueprint: Blueprint | None = None
    pages: list = field(default_factory=list)   # [(label, endpoint)] menu di header dashboard
    chat: ChatSpec | None = None
    ready: bool = True
    order: int = 100

    @property
    def url(self):
        return url_for(self.pages[0][1]) if self.ready and self.pages else None
```
`Dashboard` adalah **kontrak** antara core dan setiap folder dashboard: core tidak peduli isi dashboard, hanya membaca
atribut ini. `field(default_factory=list)` wajib untuk default list (default `[]` langsung akan dibagi semua instance).
`url` = `None` saat `ready=False`, sehingga kartu tampil "Coming soon" tanpa link (tetapi route-nya tetap ada; lihat
temuan di Checkpoint Fase 9).

```python
def _guard(dashboard):
    page_endpoints = {endpoint: label for label, endpoint in dashboard.pages}

    def check():
        is_api = "/api/" in request.path
        user = auth.current_user()
        if user is None:
            if is_api:
                return jsonify(error="Your session has expired. Please reload the page."), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not auth.can_open(user, dashboard):
            accounts.audit("access_denied", "dashboard", dashboard.slug, actor=user, path=request.path)
            if is_api:
                return jsonify(error="You do not have access to this dashboard."), 403
            return render_template("portal/denied.html", dashboard=dashboard), 403
        if request.method == "GET" and request.endpoint in page_endpoints:
            db.add_history(user["id"], dashboard.slug, f"{dashboard.title} · {page_endpoints[request.endpoint]}",
                           request.full_path.rstrip("?"))
        return None
    return check
```
- `_guard` adalah **closure**: `check()` mengingat `dashboard` miliknya. Satu fungsi pabrik, satu guard per dashboard.
- Dipasang sebagai `blueprint.before_request`, jadi berlaku untuk **halaman, API, dan file static** blueprint itu.
  Menyembunyikan kartu saja tidak cukup; guard inilah yang menolak URL yang diketik langsung.
- History hanya dicatat untuk endpoint halaman (bukan API, bukan static).

```python
def _load(app, module_name):
    from .chat import prompt  # import di sini supaya registry tidak bergantung pada mesin chat saat diimport

    module = importlib.import_module(module_name)
    dashboard = getattr(module, "DASHBOARD", None)
    if not isinstance(dashboard, Dashboard):
        raise RuntimeError(f"{module_name} tidak punya variabel DASHBOARD = Dashboard(...)")
    known = _DASHBOARDS.get(dashboard.slug)
    if known is not None and known is not dashboard:
        raise RuntimeError(f"Slug dashboard dobel: {dashboard.slug}")
    if known is None:
        if dashboard.ready and not (dashboard.blueprint and dashboard.pages):
            raise RuntimeError(f"Dashboard {dashboard.slug} ready=True tapi belum punya blueprint/pages")
        if dashboard.chat:
            prompt.load(dashboard)
        if dashboard.blueprint is not None:
            dashboard.blueprint.before_request(_guard(dashboard))
            _BY_BLUEPRINT[dashboard.blueprint.name] = dashboard
        _DASHBOARDS[dashboard.slug] = dashboard
    if dashboard.blueprint is not None:
        app.register_blueprint(dashboard.blueprint)
```
- Baris pertama `from .chat import prompt` dijalankan untuk **setiap** dashboard, sebelum mengecek `dashboard.chat`.
  Inilah alasan Langkah 9.0 (buat `prompt.py` sebelum dashboard pertama).
- `if known is None`: modul Python hanya di-import sekali per proses, jadi objek `DASHBOARD` dan blueprint-nya sama
  untuk setiap `create_app()` (test membuat app berkali-kali). Guard hanya dipasang sekali; kalau dipasang dua kali,
  setiap request mencatat History dua kali.
- `prompt.load` di sini membuat prompt yang rusak **menggagalkan start**, bukan gagal saat user bertanya.

```python
def module_names():
    from .. import dashboards
    return [f"{dashboards.__name__}.{info.name}" for info in pkgutil.iter_modules(dashboards.__path__)
            if info.ispkg and not info.name.startswith("_")]


def init_app(app):
    for name in module_names():
        try:
            _load(app, name)
        except Exception:
            if app.config["DASHBOARD_STRICT"]:
                raise
            app.logger.exception("Dashboard %s gagal dimuat dan disembunyikan", name)
```
`pkgutil.iter_modules` mendaftar subfolder yang punya `__init__.py`; awalan `_` (mis. `_template`) dilewati.
`DASHBOARD_STRICT=0` (production) membuat satu dashboard rusak hanya disembunyikan dan dicatat, dashboard lain tetap jalan.

---

## 7. `portal.py` — contoh view yang memakai semuanya

File: [mantra/portal.py](../../mantra/portal.py)

```python
@bp.get("/")
@login_required
def home():
    user = auth.current_user()
    visible = registry.visible_for(user)
    favs = db.favorites(user["id"])
    order = {slug: i for i, slug in enumerate(favs)}
    quick = sorted(visible, key=lambda d: (d.slug not in order, order.get(d.slug, 0), not d.ready, d.order))
    return render_template("portal/home.html", cards=_cards(user, quick[:QUICK_ACCESS]), total=len(visible))
```
Satu view memakai empat lapisan: `auth` (siapa), `registry` (dashboard apa yang ada), `accounts` lewat
`visible_for → can_open → allowed_slugs` (boleh dibuka?), dan `db` (favorit). Kunci sort tuple berarti: favorit dulu
(sesuai urutan ditambahkan), lalu yang `ready`, lalu `order` manifest. Python mengurutkan `False` sebelum `True`, karena
itu kondisinya ditulis terbalik (`not in`, `not d.ready`).

```python
@bp.post("/api/favorites/<slug>")
@login_required
def toggle_favorite(slug):
    user = auth.current_user()
    dashboard = registry.get(slug)
    if dashboard is None or not auth.can_open(user, dashboard):
        return jsonify(error="Dashboard not found."), 404
    return jsonify(favorite=db.toggle_favorite(user["id"], slug))
```
Dashboard tanpa akses dijawab **404, bukan 403**, supaya user tidak bisa memastikan slug dashboard lain itu ada.
CSRF untuk POST ini sudah diperiksa `csrf_protect` sebelum view jalan (header `X-CSRF-Token` dari `shell.js`).
