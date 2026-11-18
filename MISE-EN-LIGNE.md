# Mettre Seconde Main en ligne (Railway)

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
