"""
Seconde Main - petit site de petites annonces d'occasion.
Lancement :  python server.py   puis ouvrir http://localhost:8000
Aucune dépendance : uniquement la bibliothèque standard de Python.
"""
import base64
import json
import os
import re
import secrets
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "public")
# DATA_DIR : dossier où sont gardées annonces et photos (sur Railway : le volume, ex. /data)
DATA_DIR = os.environ.get("DATA_DIR") or ROOT
UPLOADS = os.path.join(DATA_DIR, "uploads")
DATA_FILE = os.path.join(DATA_DIR, "data", "annonces.json")
PORT = int(os.environ.get("PORT", 8000))

MAX_PHOTOS = 6
MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 Mo par photo (après décodage)
MAX_BODY = 25 * 1024 * 1024
CATEGORIES = ["Maison", "Électronique", "Vêtements", "Loisirs", "Véhicules", "Enfants", "Autre"]
ETATS = ["Neuf", "Très bon état", "Bon état", "Satisfaisant"]
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()  # affiché sur la page légale
DUREE_MAX_MS = 365 * 24 * 3600 * 1000  # RGPD : annonces supprimées automatiquement après 12 mois

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
lock = threading.Lock()

# ---------- Administration ----------
# En ligne : définir la variable d'environnement ADMIN_PASSWORD.
# En local, si elle est absente, un mot de passe est généré dans data/admin_password.txt.
ADMIN_PASSWORD_FILE = os.path.join(DATA_DIR, "data", "admin_password.txt")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
if not ADMIN_PASSWORD:
    if os.path.exists(ADMIN_PASSWORD_FILE):
        with open(ADMIN_PASSWORD_FILE, encoding="utf-8") as f:
            ADMIN_PASSWORD = f.read().strip()
    if not ADMIN_PASSWORD:
        ADMIN_PASSWORD = secrets.token_urlsafe(12)
        with open(ADMIN_PASSWORD_FILE, "w", encoding="utf-8") as f:
            f.write(ADMIN_PASSWORD + "\n")

# Protection contre les essais de mots de passe en rafale : 8 échecs -> blocage 15 min par adresse IP.
MAX_ECHECS, BLOCAGE_S = 8, 15 * 60
echecs = {}  # ip -> (nombre, horodatage du premier échec)


def load():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(annonces):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(annonces, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA_FILE)


def supprimer_photos(a):
    for url in a.get("photos", []):
        try:
            os.remove(os.path.join(UPLOADS, os.path.basename(url)))
        except OSError:
            pass


def purger_anciennes():
    """Supprime les annonces de plus de 12 mois et leurs photos."""
    limite = time.time() * 1000 - DUREE_MAX_MS
    with lock:
        annonces = load()
        vieilles = [a for a in annonces if a["date"] < limite]
        if vieilles:
            save([a for a in annonces if a["date"] >= limite])
    for a in vieilles:
        supprimer_photos(a)
    return len(vieilles)


def purge_periodique():
    while True:
        n = purger_anciennes()
        if n:
            print(f"Purge : {n} annonce(s) de plus de 12 mois supprimée(s).", flush=True)
        time.sleep(6 * 3600)


def public_view(a):
    """Retire le code secret avant d'envoyer une annonce au navigateur."""
    return {k: v for k, v in a.items() if k != "code"}


DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,(.+)$", re.S)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC, **kwargs)

    # ---------- utilitaires ----------
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def client_ip(self):
        # Derrière Railway, la vraie adresse est dans X-Forwarded-For.
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def check_admin(self, password):
        """Renvoie None si le mot de passe admin est bon, sinon envoie l'erreur et renvoie False.
        Le mot de passe arrive dans le corps JSON (UTF-8) pour accepter les accents."""
        ip, now = self.client_ip(), time.time()
        with lock:
            n, t0 = echecs.get(ip, (0, now))
            if now - t0 > BLOCAGE_S:
                n, t0 = 0, now
            if n >= MAX_ECHECS:
                self.send_json(429, {"erreur": "Trop d'essais. Réessayez dans quelques minutes."})
                return False
        given = str(password or "").strip().encode("utf-8")
        if secrets.compare_digest(given, ADMIN_PASSWORD.encode("utf-8")):
            with lock:
                echecs.pop(ip, None)
            return None
        with lock:
            echecs[ip] = (n + 1, t0)
        time.sleep(1)
        self.send_json(401, {"erreur": "Mot de passe incorrect."})
        return False

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("Envoi trop volumineux.")
        return json.loads(self.rfile.read(length) or b"{}")

    # ---------- routes ----------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/annonces":
            with lock:
                annonces = load()
            annonces.sort(key=lambda a: a["date"], reverse=True)
            return self.send_json(200, [public_view(a) for a in annonces])
        if path == "/api/meta":
            return self.send_json(200, {"categories": CATEGORIES, "etats": ETATS, "maxPhotos": MAX_PHOTOS, "contactEmail": CONTACT_EMAIL})
        if path.startswith("/uploads/"):
            name = os.path.basename(path)
            file = os.path.join(UPLOADS, name)
            if not re.fullmatch(r"[a-f0-9]+\.(jpg|png|webp)", name) or not os.path.isfile(file):
                return self.send_error(404)
            ext = name.rsplit(".", 1)[1]
            with open(file, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg" if ext == "jpg" else f"image/{ext}")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=31536000")
            self.end_headers()
            return self.wfile.write(data)
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/api/admin/login":
            try:
                pw = self.read_json().get("password", "")
            except (ValueError, json.JSONDecodeError, AttributeError):
                pw = ""
            if self.check_admin(pw) is None:
                self.send_json(200, {"ok": True})
            return
        if urlparse(self.path).path != "/api/annonces":
            return self.send_error(404)
        try:
            d = self.read_json()
            titre = str(d.get("titre", "")).strip()[:80]
            description = str(d.get("description", "")).strip()[:3000]
            vendeur = str(d.get("vendeur", "")).strip()[:50]
            contact = str(d.get("contact", "")).strip()[:100]
            ville = str(d.get("ville", "")).strip()[:60]
            categorie = d.get("categorie") if d.get("categorie") in CATEGORIES else "Autre"
            etat = d.get("etat") if d.get("etat") in ETATS else "Bon état"
            prix = round(float(d.get("prix", 0)), 2)
            photos = d.get("photos") or []
            if not titre or not vendeur or not contact:
                raise ValueError("Titre, nom et contact sont obligatoires.")
            if d.get("accepte") not in (True, "1", 1, "on"):
                raise ValueError("Vous devez accepter les conditions d'utilisation.")
            if prix < 0 or prix > 1_000_000:
                raise ValueError("Prix invalide.")
            if not photos:
                raise ValueError("Ajoutez au moins une photo.")
            if len(photos) > MAX_PHOTOS:
                raise ValueError(f"{MAX_PHOTOS} photos maximum.")

            fichiers = []
            for p in photos:
                m = DATA_URL.match(str(p))
                if not m:
                    raise ValueError("Format de photo non accepté (JPEG, PNG ou WebP).")
                raw = base64.b64decode(m.group(2))
                if len(raw) > MAX_PHOTO_BYTES:
                    raise ValueError("Une photo est trop lourde.")
                ext = "jpg" if m.group(1) == "jpeg" else m.group(1)
                name = f"{secrets.token_hex(12)}.{ext}"
                with open(os.path.join(UPLOADS, name), "wb") as f:
                    f.write(raw)
                fichiers.append(f"/uploads/{name}")
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return self.send_json(400, {"erreur": str(e) or "Données invalides."})

        annonce = {
            "id": secrets.token_hex(6),
            "code": secrets.token_urlsafe(9),
            "titre": titre, "description": description, "prix": prix,
            "categorie": categorie, "etat": etat, "ville": ville,
            "vendeur": vendeur, "contact": contact,
            "photos": fichiers, "date": int(time.time() * 1000),
        }
        with lock:
            annonces = load()
            annonces.append(annonce)
            save(annonces)
        # Le code n'est renvoyé qu'une fois, au créateur, pour pouvoir supprimer son annonce.
        return self.send_json(201, {**public_view(annonce), "code": annonce["code"]})

    def do_DELETE(self):
        m = re.fullmatch(r"/api/(admin/)?annonces/([a-f0-9]+)", urlparse(self.path).path)
        if not m:
            return self.send_error(404)
        admin = bool(m.group(1))
        try:
            body = self.read_json()
        except (ValueError, json.JSONDecodeError):
            body = {}
        if not isinstance(body, dict):
            body = {}
        code = str(body.get("code", ""))
        if admin and self.check_admin(body.get("password", "")) is False:
            return
        with lock:
            annonces = load()
            a = next((x for x in annonces if x["id"] == m.group(2)), None)
            if not a:
                return self.send_json(404, {"erreur": "Annonce introuvable."})
            if not admin and not secrets.compare_digest(a["code"].encode(), code.encode()):
                return self.send_json(403, {"erreur": "Code de suppression incorrect."})
            annonces.remove(a)
            save(annonces)
        supprimer_photos(a)
        return self.send_json(200, {"ok": True})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print(f"Seconde Main en ligne : http://localhost:{PORT}  (données : {DATA_DIR})", flush=True)
    if os.environ.get("ADMIN_PASSWORD"):
        print(f"Administration : http://localhost:{PORT}/admin.html  (mot de passe : variable ADMIN_PASSWORD)", flush=True)
    else:
        print(f"Administration : http://localhost:{PORT}/admin.html  (mot de passe dans {ADMIN_PASSWORD_FILE})", flush=True)
    threading.Thread(target=purge_periodique, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
