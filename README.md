# Assistant IA de productivité e-commerce

Application de démonstration qui permet d’interroger les données e-commerce Olist en langage naturel, par texte ou par dictée vocale, et d’obtenir des réponses chiffrées. Le projet associe une interface Django, une API FastAPI qui transforme les questions en SQL, et une base PostgreSQL.

## Fonctionnalités

- **Questions en langage naturel** : le service IA génère une requête PostgreSQL, la valide, l’exécute et résume les résultats en français.
- **Dictée vocale** : la reconnaissance vocale du navigateur transcrit la question en français avant son envoi.
- **Interface Django** : connexion par compte, gestion des commandes et tickets, chatbot, tableau de bord et historique des interactions.
- **Feedback** : les utilisateurs peuvent évaluer les réponses avec 👍 ou 👎.
- **Accès différenciés** : les rôles administrateur/directeur, SAV et vendeur ont accès aux données autorisées pour leur profil. Les vendeurs consultent leurs propres données.
- **Garde-fous SQL** : seules des requêtes de lecture autorisées sont acceptées, le nombre de lignes est plafonné à 200 et le délai d’exécution PostgreSQL est limité à 10 secondes.

La dictée utilise l’API de reconnaissance vocale du navigateur : elle est disponible notamment dans Chrome et Edge, nécessite l’autorisation du microphone et une connexion Internet. La question transcrite reste modifiable avant envoi.

## Architecture et technologies

- **Interface et application métier** : Django, Python 3.12
- **API IA** : FastAPI et Uvicorn
- **Base de données** : PostgreSQL 16, image incluant pgvector
- **Modèle de langage** : API NVIDIA compatible OpenAI, modèle configurable
- **Données de démonstration** : jeux de données CSV Olist fournis dans `data/`
- **Lancement des services** : Docker Compose

Le service IA utilise par défaut le modèle `meta/llama-3.3-70b-instruct`. Il faut disposer d’une clé NVIDIA donnant accès au modèle choisi. Le nom du modèle peut être modifié avec `NVIDIA_MODEL`.

## Prérequis

- Git
- Docker Desktop récent, avec Docker Compose, démarré
- Une clé API NVIDIA valide
- Une connexion Internet pour l’API de modèle et, si elle est utilisée, la dictée vocale

Il n’est pas nécessaire d’installer Python ou PostgreSQL localement : les dépendances applicatives sont installées dans les conteneurs.

## Installation et premier démarrage

Les commandes ci-dessous sont données pour PowerShell, depuis le dossier du dépôt.

### 1. Récupérer le dépôt

```powershell
git clone <URL_DU_DEPOT>
cd <NOM_DU_DEPOT>
```

Remplacez `<URL_DU_DEPOT>` par l’URL Git du projet et `<NOM_DU_DEPOT>` par le dossier créé par `git clone`.

### 2. Créer le fichier `.env`

À la racine du dépôt, créez un fichier nommé `.env`. Il est ignoré par Git afin de ne pas publier les secrets. Ajoutez-y les variables suivantes et remplacez les valeurs d’exemple :

```dotenv
POSTGRES_DB=sales_ai
POSTGRES_USER=postgres
POSTGRES_PASSWORD=remplacer-par-un-mot-de-passe-de-base-de-donnees

AI_DB_PASSWORD=remplacer-par-un-mot-de-passe-pour-le-compte-ia
AI_INTERNAL_TOKEN=remplacer-par-un-jeton-long-et-aleatoire

NVIDIA_API_KEY=remplacer-par-votre-cle-nvidia
NVIDIA_MODEL=meta/llama-3.3-70b-instruct
```

`POSTGRES_DB`, `POSTGRES_USER` et `POSTGRES_PASSWORD` configurent le compte administrateur de la base utilisé par Django. `AI_DB_PASSWORD` est le mot de passe du compte en lecture seule utilisé par l’API IA. Pour que la connexion fonctionne, la valeur choisie pour `AI_DB_PASSWORD` doit être identique au mot de passe affecté au rôle `ai_login` dans [`db/roles.sql`](./db/roles.sql). Modifiez ce fichier avant de poursuivre si nécessaire.

`AI_INTERNAL_TOKEN` doit être une valeur secrète identique dans les conteneurs Django et IA ; Docker Compose la transmet aux deux services depuis le même `.env`. `NVIDIA_MODEL` est facultatif et peut être omis pour utiliser le modèle par défaut.

### 3. Construire et démarrer les conteneurs

```powershell
docker compose up --build -d
docker compose ps
```

Cette commande démarre PostgreSQL, l’application web et l’API IA. Le service web et l’API attendent que PostgreSQL soit prêt. Au premier lancement, Docker télécharge également les images et installe les dépendances.

### 4. Créer les tables Django

```powershell
docker compose exec web python manage.py migrate
```

Les migrations doivent être exécutées avant l’installation des rôles SQL : le script attribue des droits sur les tables métier, dont celles des tickets.

### 5. Créer les rôles de lecture du service IA

Copiez le script SQL dans le conteneur PostgreSQL, puis exécutez-le :

```powershell
docker compose cp .\db\roles.sql postgres:/tmp/roles.sql
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/roles.sql'
```

Le script crée les rôles de profil et le compte `ai_login`, applique un délai maximal aux requêtes et configure l’accès en lecture seule. Exécutez-le une seule fois sur une base vierge. Si vous avez modifié le mot de passe de `ai_login` dans ce script, reportez exactement la même valeur dans `AI_DB_PASSWORD` du fichier `.env` avant de démarrer le service IA.

### 6. Charger les données Olist

```powershell
docker compose exec web python manage.py import_olist
```

La commande importe les fichiers CSV présents dans `data/`. **Attention : elle supprime d’abord les données Olist déjà chargées** pour les clients, vendeurs, produits, commandes, articles, paiements et avis. Ne la relancez pas si vous souhaitez conserver les données existantes.

### 7. Créer un compte administrateur et se connecter

```powershell
docker compose exec web python manage.py createsuperuser
```

Ouvrez ensuite :

- Application : <http://localhost:8000/>
- Chatbot : <http://localhost:8000/chat/>
- Tableau de bord : <http://localhost:8000/dashboard/>
- Administration Django : <http://localhost:8000/admin/>
- Santé de l’API IA : <http://localhost:8001/health>
- Documentation interactive de l’API IA : <http://localhost:8001/docs>

Connectez-vous avec le compte créé. Le superutilisateur reçoit le rôle administrateur. Pour tester les accès directeur, SAV ou vendeur, créez les comptes et attribuez-leur leur rôle depuis l’administration Django. Un compte vendeur doit également être associé à un vendeur.

## Utilisation de l’assistant

1. Connectez-vous à l’application.
2. Ouvrez la page **Chatbot**.
3. Posez une question en français, par exemple : « Quelles sont les cinq catégories les plus vendues ? »
4. Vous pouvez aussi cliquer sur le microphone, dicter une question, relire la transcription, puis l’envoyer.
5. Consultez la réponse, les résultats et, si nécessaire, la requête SQL produite. Utilisez 👍 ou 👎 pour évaluer la réponse.

Les données fournies couvrent le jeu Olist, dont les commandes s’étendent de 2016 à 2018. Les montants sont exprimés en réals brésiliens (R$).

## Commandes utiles

Afficher l’état des services et leurs journaux :

```powershell
docker compose ps
docker compose logs -f web
docker compose logs -f ai
docker compose logs -f postgres
```

Arrêter les conteneurs sans supprimer la base de données :

```powershell
docker compose down
```

Redémarrer le projet :

```powershell
docker compose up -d
```

Pour repartir de zéro, `docker compose down -v` supprime aussi le volume PostgreSQL et toutes les données persistées. À la prochaine mise en route, il faudra refaire les étapes de migration, création des rôles, import des données et création du compte administrateur.

## Dépannage

- **Le service IA renvoie une erreur d’authentification** : vérifiez que `NVIDIA_API_KEY` est valide, que le modèle configuré est accessible et que les conteneurs ont été redémarrés après toute modification de `.env` (`docker compose up -d`).
- **L’API IA ne se connecte pas à PostgreSQL** : vérifiez que les migrations et le script `db/roles.sql` ont été appliqués et que `AI_DB_PASSWORD` correspond au mot de passe du rôle `ai_login`.
- **Les données ne s’affichent pas** : vérifiez que l’import Olist s’est terminé sans erreur. Les CSV doivent être présents dans `data/`.
- **La dictée vocale n’est pas proposée** : utilisez Chrome ou Edge, autorisez l’accès au microphone et vérifiez la connexion Internet.
- **Un port est déjà utilisé** : libérez le port concerné ou adaptez le mappage de ports dans `docker-compose.yml`.

## Tests

Des fichiers de test et d’évaluation sont disponibles dans `web/core/tests.py` et `ai_service/`. Le script `ai_service/run_eval.py` appelle le modèle NVIDIA et la base de données : il nécessite donc des identifiants configurés, une base initialisée avec les rôles et données, ainsi qu’un accès réseau au service de modèle.

# Sales_AI
