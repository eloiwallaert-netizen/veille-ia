# veille-ia

Site de veille IA et de formations, catégorisé par métier (Sales & Business Development, Customer Success & Account Management, Management & Leadership, Product & Design, Tech/Data & AI, Marketing/Growth & Brand, Operations/Finance/HR & Legal), pensé pour des nouveaux arrivants dans le monde de l'IA.

**Site en ligne : [veille-ia.eloi-wallaert.workers.dev](https://veille-ia.eloi-wallaert.workers.dev)** (hébergé sur Cloudflare)

## Structure

- `index.html` : page du site, autonome (pas de build requis)
- `support.js` : runtime nécessaire au rendu de la page
- `data/articles.json` : contenu des actualités, chargé au runtime par `index.html`. Contient les articles curated (analyse écrite, ressources de formation) et les articles ajoutés automatiquement chaque jour (`"auto": true`)
- `scripts/fetch_news.py` : script d'ingestion RSS quotidien (voir ci-dessous)
- `.github/workflows/daily-update.yml` : automatisation GitHub Actions

## Mise à jour automatique quotidienne

Un workflow GitHub Actions (`daily-update.yml`) tourne chaque jour à 6h UTC :
1. Récupère les derniers articles de 7 flux RSS IA publics (OpenAI, Google AI Blog, Hugging Face, VentureBeat, TechCrunch, MIT Technology Review, The Verge)
2. Pour chaque nouvel article, va chercher la page source complète et en tire un résumé par extraction (les phrases les plus représentatives, sans reformulation). Si la page n'est pas récupérable (paywall, protection anti-bot), retombe sur le teaser fourni par le flux RSS
3. Catégorise chaque article par thématique via des mots-clés (sur le texte complet si disponible, sinon sur le teaser), puis déduit les métiers concernés à partir de la matrice `RELEVANCE` (même logique que dans `index.html`)
4. Ajoute les nouveaux articles à `data/articles.json` (max 30 articles auto conservés, les articles curated ne sont jamais supprimés) et pousse le commit

Ce commit déclenche automatiquement un redéploiement Cloudflare (déjà connecté au repo, branche `main`).

Pas d'appel LLM dans cette automatisation (choix assumé) : le résumé est extractif (des phrases piquées telles quelles dans l'article, pas une synthèse rédigée), les articles auto n'ont pas de ressources de formation associées, et la catégorisation par mots-clés reste approximative. Un filtre écarte les paragraphes/phrases qui ressemblent à du bruit promotionnel ou UI (bannières d'évènement, newsletters, cookies...) avant le scoring du résumé. Tous les articles (curated et auto) s'ouvrent sur une page interne du site avec leur résumé ; les articles auto affichent en plus un lien direct vers la source complète.

Déclenchement manuel possible depuis l'onglet Actions du repo GitHub, ou via `gh workflow run daily-update.yml`.

## Déploiement

Site statique. Aucune commande de build : servir `index.html` tel quel. Le fichier `data/articles.json` doit être servi au même niveau que `index.html`.

Déployé actuellement sur **Cloudflare** (connecté en Git à la branche `main`, build command vide, output directory `/`), bande passante illimitée en gratuit — contrairement à Netlify (plan gratuit limité à 100 Go/mois), qui n'est plus utilisé pour ce projet.
