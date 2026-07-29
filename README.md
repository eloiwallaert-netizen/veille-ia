# veille-ia

Site de veille IA et de formations, catégorisé par métier (Sales & Business Development, Customer Success & Account Management, Management & Leadership, Product & Design, Tech/Data & AI, Marketing/Growth & Brand, Operations/Finance/HR & Legal), pensé pour des nouveaux arrivants dans le monde de l'IA.

## Structure

- `index.html` : page du site, autonome (pas de build requis)
- `support.js` : runtime nécessaire au rendu de la page
- `data/articles.json` : contenu des actualités, chargé au runtime par `index.html`. Contient les articles curated (analyse écrite, ressources de formation) et les articles ajoutés automatiquement chaque jour (`"auto": true`)
- `scripts/fetch_news.py` : script d'ingestion RSS quotidien (voir ci-dessous)
- `.github/workflows/daily-update.yml` : automatisation GitHub Actions

## Mise à jour automatique quotidienne

Un workflow GitHub Actions (`daily-update.yml`) tourne chaque jour à 6h UTC :
1. Récupère les derniers articles de 7 flux RSS IA publics (OpenAI, Google AI Blog, Hugging Face, VentureBeat, TechCrunch, MIT Technology Review, The Verge)
2. Catégorise chaque article par thématique via des mots-clés, puis déduit les métiers concernés à partir de la matrice `RELEVANCE` (même logique que dans `index.html`)
3. Ajoute les nouveaux articles à `data/articles.json` (max 30 articles auto conservés, les articles curated ne sont jamais supprimés) et pousse le commit

Ce commit déclenche automatiquement un redéploiement Netlify (déjà connecté au repo).

Pas d'appel LLM dans cette automatisation (choix assumé) : les articles auto n'ont pas d'analyse rédigée ni de ressources de formation associées, et la catégorisation par mots-clés est approximative. Ils s'affichent comme un simple lien vers l'article source plutôt qu'une page interne détaillée.

Déclenchement manuel possible depuis l'onglet Actions du repo GitHub, ou via `gh workflow run daily-update.yml`.

## Déploiement

Site statique. Aucune commande de build : servir `index.html` tel quel (Netlify, Vercel, GitHub Pages...). Le fichier `data/articles.json` doit être servi au même niveau que `index.html`.
