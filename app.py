"""
Les Bonnes Affaires Belgique - application WSGI (bibliothèque standard Python uniquement).

- En local et sur Railway : lancée par server.py
- Sur PythonAnywhere : importée par le fichier WSGI (variable `application`)
"""
import base64
import json
import mimetypes
import os
import re
import secrets
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "public")
# DATA_DIR : dossier où sont gardées annonces et photos (Railway : le volume /data ; ailleurs : le projet)
DATA_DIR = os.environ.get("DATA_DIR") or ROOT
UPLOADS = os.path.join(DATA_DIR, "uploads")
DATA_FILE = os.path.join(DATA_DIR, "data", "annonces.json")

MAX_PHOTOS = 6
MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 Mo par photo (après décodage)
MAX_BODY = 25 * 1024 * 1024
CATEGORIES = ["Maison", "Électronique", "Vêtements", "Loisirs", "Véhicules", "Enfants", "Autre"]
ETATS = ["Neuf", "Très bon état", "Bon état", "Satisfaisant"]
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()  # affiché sur la page légale
# Lien de dons (Revolut : https://revolut.me/VOTRE-PSEUDO) : le bouton « Soutenir » n'apparaît que s'il est défini
DON_URL = os.environ.get("DON_URL", "").strip()
if not DON_URL.startswith("https://"):
    DON_URL = ""
DUREE_MAX_MS = 365 * 24 * 3600 * 1000  # RGPD : annonces supprimées automatiquement après 12 mois
PURGE_INTERVALLE_S = 6 * 3600

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
lock = threading.Lock()

# ---------- Administration ----------
# Mot de passe : variable d'environnement ADMIN_PASSWORD, sinon fichier data/admin_password.txt
# (généré automatiquement au premier lancement s'il n'existe pas).
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

# Protection contre les essais en rafale : 8 échecs -> blocage 15 min par adresse IP.
MAX_ECHECS, BLOCAGE_S = 8, 15 * 60
echecs = {}  # ip -> (nombre, horodatage du premier échec)

DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,(.+)$", re.S)
STATUS = {200: "200 OK", 201: "201 Created", 400: "400 Bad Request", 401: "401 Unauthorized",
          403: "403 Forbidden", 404: "404 Not Found", 405: "405 Method Not Allowed",
          413: "413 Payload Too Large", 429: "429 Too Many Requests"}


# ---------- Stockage ----------
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


_derniere_purge = 0.0


def purger_si_besoin(force=False):
    """Supprime les annonces de plus de 12 mois (au plus une fois toutes les 6 h)."""
    global _derniere_purge
    now = time.time()
    if not force and now - _derniere_purge < PURGE_INTERVALLE_S:
        return 0
    _derniere_purge = now
    limite = now * 1000 - DUREE_MAX_MS
    with lock:
        annonces = load()
        vieilles = [a for a in annonces if a["date"] < limite]
        if vieilles:
            save([a for a in annonces if a["date"] >= limite])
    for a in vieilles:
        supprimer_photos(a)
    return len(vieilles)


def public_view(a):
    """Retire le code secret avant d'envoyer une annonce au navigateur."""
    return {k: v for k, v in a.items() if k != "code"}


# ---------- Réponses ----------
def reponse(start_response, status, body, ctype, extra=()):
    start_response(STATUS.get(status, f"{status} Erreur"),
                   [("Content-Type", ctype), ("Content-Length", str(len(body))), *extra])
    return [body]


def json_rep(start_response, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return reponse(start_response, status, body, "application/json; charset=utf-8")


def not_found(start_response):
    return reponse(start_response, 404, "Page introuvable".encode("utf-8"), "text/plain; charset=utf-8")


def lire_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > MAX_BODY:
        raise ValueError("Envoi trop volumineux.")
    data = json.loads(environ["wsgi.input"].read(length) or b"{}")
    if not isinstance(data, dict):
        raise ValueError("Données invalides.")
    return data


def client_ip(environ):
    # PythonAnywhere : X-Real-IP ; Railway : X-Forwarded-For
    ip = environ.get("HTTP_X_REAL_IP") or environ.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    return ip or environ.get("REMOTE_ADDR", "?")


def verifier_admin(environ, password):
    """Renvoie None si le mot de passe est bon, sinon (statut, message)."""
    ip, now = client_ip(environ), time.time()
    with lock:
        n, t0 = echecs.get(ip, (0, now))
        if now - t0 > BLOCAGE_S:
            n, t0 = 0, now
        if n >= MAX_ECHECS:
            return 429, "Trop d'essais. Réessayez dans quelques minutes."
    given = str(password or "").strip().encode("utf-8")
    if secrets.compare_digest(given, ADMIN_PASSWORD.encode("utf-8")):
        with lock:
            echecs.pop(ip, None)
        return None
    with lock:
        echecs[ip] = (n + 1, t0)
    time.sleep(1)
    return 401, "Mot de passe incorrect."


# ---------- Routes ----------
def fichier_statique(path, start_response):
    if path == "/":
        path = "/index.html"
    full = os.path.realpath(os.path.join(PUBLIC, path.lstrip("/")))
    if not full.startswith(os.path.realpath(PUBLIC) + os.sep) or not os.path.isfile(full):
        return not_found(start_response)
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    with open(full, "rb") as f:
        return reponse(start_response, 200, f.read(), ctype, [("Cache-Control", "no-cache")])


def photo(path, start_response):
    name = os.path.basename(path)
    full = os.path.join(UPLOADS, name)
    if not re.fullmatch(r"[a-f0-9]+\.(jpg|png|webp)", name) or not os.path.isfile(full):
        return not_found(start_response)
    ext = name.rsplit(".", 1)[1]
    with open(full, "rb") as f:
        return reponse(start_response, 200, f.read(), "image/jpeg" if ext == "jpg" else f"image/{ext}",
                       [("Cache-Control", "public, max-age=31536000")])


def creer_annonce(environ, start_response):
    try:
        d = lire_json(environ)
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
        decodees = []
        for p in photos:
            m = DATA_URL.match(str(p))
            if not m:
                raise ValueError("Format de photo non accepté (JPEG, PNG ou WebP).")
            raw = base64.b64decode(m.group(2))
            if len(raw) > MAX_PHOTO_BYTES:
                raise ValueError("Une photo est trop lourde.")
            decodees.append(("jpg" if m.group(1) == "jpeg" else m.group(1), raw))
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return json_rep(start_response, 400, {"erreur": str(e) or "Données invalides."})

    fichiers = []
    for ext, raw in decodees:
        name = f"{secrets.token_hex(12)}.{ext}"
        with open(os.path.join(UPLOADS, name), "wb") as f:
            f.write(raw)
        fichiers.append(f"/uploads/{name}")

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
    return json_rep(start_response, 201, {**public_view(annonce), "code": annonce["code"]})


def supprimer_annonce(environ, start_response, ident, admin):
    try:
        body = lire_json(environ)
    except (ValueError, json.JSONDecodeError):
        body = {}
    if admin:
        refus = verifier_admin(environ, body.get("password", ""))
        if refus:
            return json_rep(start_response, refus[0], {"erreur": refus[1]})
    code = str(body.get("code", ""))
    with lock:
        annonces = load()
        a = next((x for x in annonces if x["id"] == ident), None)
        if not a:
            return json_rep(start_response, 404, {"erreur": "Annonce introuvable."})
        if not admin and not secrets.compare_digest(a["code"].encode(), code.encode()):
            return json_rep(start_response, 403, {"erreur": "Code de suppression incorrect."})
        annonces.remove(a)
        save(annonces)
    supprimer_photos(a)
    return json_rep(start_response, 200, {"ok": True})


def application(environ, start_response):
    purger_si_besoin()
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/") or "/"

    if method in ("GET", "HEAD"):
        if path == "/api/annonces":
            with lock:
                annonces = load()
            annonces.sort(key=lambda a: a["date"], reverse=True)
            return json_rep(start_response, 200, [public_view(a) for a in annonces])
        if path == "/api/meta":
            return json_rep(start_response, 200, {"categories": CATEGORIES, "etats": ETATS,
                                                  "maxPhotos": MAX_PHOTOS, "contactEmail": CONTACT_EMAIL,
                                                  "donUrl": DON_URL})
        if path.startswith("/uploads/"):
            return photo(path, start_response)
        return fichier_statique(path, start_response)

    if method == "POST":
        if path == "/api/admin/login":
            try:
                pw = lire_json(environ).get("password", "")
            except (ValueError, json.JSONDecodeError):
                pw = ""
            refus = verifier_admin(environ, pw)
            if refus:
                return json_rep(start_response, refus[0], {"erreur": refus[1]})
            return json_rep(start_response, 200, {"ok": True})
        if path == "/api/annonces":
            return creer_annonce(environ, start_response)
        return not_found(start_response)

    if method == "DELETE":
        m = re.fullmatch(r"/api/(admin/)?annonces/([a-f0-9]+)", path)
        if m:
            return supprimer_annonce(environ, start_response, m.group(2), bool(m.group(1)))
        return not_found(start_response)

    return json_rep(start_response, 405, {"erreur": "Méthode non autorisée."})
