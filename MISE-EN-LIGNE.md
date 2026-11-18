# Mettre Seconde Main en ligne

Deux hébergements possibles :
- **PythonAnywhere** (gratuit) : voir la section tout en bas.
- **Railway** (≈ 5 $/mois après l'essai) : sections 1 à 4.

# Option payante : Railway

Le projet est prêt : il ne reste que les étapes qui demandent **vos** comptes.
Durée : environ 15 minutes. Coût : environ 5 $/mois chez Railway.

## 1. Mettre le code sur GitHub

1. Créez un compte gratuit sur https://github.com.
2. Cliquez sur **New repository**, nommez-le `seconde-main` et ne cochez **aucune** case (ni README, ni .gitignore). Puis cliquez sur **Create repository**.
3. Dans un terminal ouvert dans le dossier du projet, tapez (en remplaçant `VOTRE-PSEUDO`) :

```powershell
git remote add origin https://github.com/VOTRE-PSEUDO/seconde-main.git
```

```powershell
git push -u origin main
```

Une fenêtre GitHub s'ouvre la première fois pour vous connecter.

## 2. Créer le site sur Railway

1. Allez sur https://railway.com et connectez-vous **avec GitHub**.
2. Cliquez sur **New Project** → **Deploy from GitHub repo** → choisissez `seconde-main`.
   Railway détecte Python et lance `python server.py` tout seul (fichier `railway.json`).

## 3. Ajouter un volume (indispensable)

Sans volume, **les annonces et les photos sont effacées** à chaque mise à jour.

1. Dans le projet, faites un clic droit sur le service → **Attach Volume**.
2. Chemin de montage (*Mount path*) : `/data`
3. Ouvrez le service → onglet **Variables** → **New Variable** :
   - Nom : `DATA_DIR`
   - Valeur : `/data`
4. Ajoutez une deuxième variable pour protéger la page d'administration :
   - Nom : `ADMIN_PASSWORD`
   - Valeur : un mot de passe long et unique (au moins 16 caractères), que vous gardez pour vous.

5. Ajoutez une troisième variable pour la page légale (mentions légales / RGPD) :
   - Nom : `CONTACT_EMAIL`
   - Valeur : l'adresse e-mail où l'on peut vous joindre (signalements, demandes RGPD).
     Conseil : créez une adresse dédiée au site, elle sera visible publiquement.

Railway redéploie le site automatiquement.

La page d'administration sera à l'adresse `https://VOTRE-SITE/admin.html`.
En local, son mot de passe est généré automatiquement dans `data/admin_password.txt`.

## 4. Obtenir l'adresse publique

Onglet **Settings** → **Networking** → **Generate Domain**.
Vous obtenez une adresse du type `seconde-main-production.up.railway.app` : c'est votre site !

*Facultatif :* pour un nom à vous (ex. `secondemain.fr`), achetez le domaine (≈ 10 €/an chez OVH, Gandi…),
puis dans **Networking** → **Custom Domain**, suivez les instructions pour le relier.

## Mettre à jour le site plus tard

Après chaque modification :

```powershell
git add -A
```

```powershell
git commit -m "Mise à jour"
```

```powershell
git push
```

Railway republie le site en une minute environ.

---

# Option gratuite : PythonAnywhere

Adresse obtenue : `https://VOTRE-PSEUDO.pythonanywhere.com` (HTTPS inclus).
Limite du compte gratuit : se connecter au moins **une fois tous les 3 mois** et cliquer sur
**« Run until 3 months from today »** dans l'onglet **Web**, sinon le site est mis en pause.

## 1. Récupérer le code
Onglet **Consoles** → **Bash**, puis :

```bash
git clone https://github.com/menacebks/seconde-main.git
```

## 2. Créer le site
Onglet **Web** → **Add a new web app** → **Manual configuration** → **Python 3.13**.

## 3. Brancher le code
Dans l'onglet **Web**, cliquez sur le lien du **WSGI configuration file** et remplacez tout son contenu par :

```python
import os, sys
chemin = os.path.expanduser("~/seconde-main")
sys.path.insert(0, chemin)
os.environ["CONTACT_EMAIL"] = "votre-adresse@exemple.fr"   # affichée sur la page légale
from app import application
```

Cliquez sur **Save**, puis sur le bouton vert **Reload** de l'onglet **Web**.

## 4. Mot de passe admin
Au premier lancement, un mot de passe est créé dans le fichier
`seconde-main/data/admin_password.txt` (onglet **Files**). Ouvrez-le pour le lire,
ou remplacez son contenu par le mot de passe de votre choix, puis **Reload**.

## Mettre à jour le site
Après un `git push` depuis votre ordinateur, dans une console Bash PythonAnywhere :

```bash
cd ~/seconde-main && git pull
```

puis **Reload** dans l'onglet **Web**.
