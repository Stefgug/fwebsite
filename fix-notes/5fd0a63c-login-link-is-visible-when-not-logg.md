# Auto-fix suggestion — login link is visible when not logged in

        **Test en échec :** `navigation.spec.ts` > `login link is visible when not logged in`
        **Commit déclencheur :** `5fd0a63c`

        ## Analyse

        Le test cherche un lien avec le texte exact "Login" (via la regex `/^Login$/i`), mais l'élément correspondant est introuvable dans le DOM après 5 secondes. Cela indique que le composant de navigation affiche un libellé différent (par exemple "Sign In", "Se connecter", ou "Account") ou que le lien de connexion n'est tout simplement pas rendu dans la navbar pour un utilisateur non authentifié. Le commentaire dans le test lui-même précise d'ailleurs "Navbar shows 'Login' (not 'Sign In')", ce qui suggère fortement que le texte réel dans le composant est "Sign In" et non "Login".

        ## Impact utilisateur

        Un utilisateur non connecté ne voit pas de lien d'accès à la page de connexion dans la barre de navigation, ce qui l'empêche de s'authentifier facilement depuis n'importe quelle page.

        ## Correction proposée

        Deux approches possibles selon la cause racine :

1. **Correction côté composant (recommandée)** : Si le texte affiché dans la navbar est "Sign In" alors qu'il devrait être "Login" (comme attendu par le test et la spec produit), modifier le composant Navbar pour remplacer "Sign In" par "Login".

2. **Correction côté test** : Si "Sign In" est le libellé voulu, mettre à jour la regex du test pour correspondre au texte réel : `{ name: /^Sign In$/i }`.

Dans tous les cas, s'assurer également que le lien est bien rendu conditionnellement lorsque l'utilisateur n'est **pas** authentifié (vérifier la logique de condition `isLoggedIn` / `session` dans le composant).

        ### Code suggéré
```

// OPTION 1 — Correction dans le composant Navbar
// Remplacer "Sign In" par "Login" pour correspondre à la spec

// Avant :
<Link href="/login">Sign In</Link>

// Après :
<Link href="/login">Login</Link>


// OPTION 2 — Correction dans le test si "Sign In" est le label voulu
// Avant :
const loginLink = page.getByRole('link', { name: /^Login$/i });

// Après :
const loginLink = page.getByRole('link', { name: /^Sign In$/i });

```
        **Fichier à modifier :** `frontend/components/Navbar.tsx`

        ---
        *Généré automatiquement par Claude Sonnet — vérifier avant de merger.*