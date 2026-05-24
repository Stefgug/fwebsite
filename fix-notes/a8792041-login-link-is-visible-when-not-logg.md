# Auto-fix suggestion — login link is visible when not logged in

        **Test en échec :** `navigation.spec.ts` > `login link is visible when not logged in`
        **Commit déclencheur :** `a8792041`

        ## Analyse

        Le test recherche un lien avec le texte exact "Login" via `getByRole('link', { name: /^Login$/i })`, mais l'élément est introuvable après 5 secondes. Cela indique que le lien d'authentification dans la navbar utilise un texte différent (probablement "Sign In", "Se connecter", ou similaire), ou que le composant de connexion n'est pas rendu du tout dans le DOM côté navbar. Le commentaire dans le test lui-même mentionne `// Navbar shows "Login" (not "Sign In")`, ce qui suggère que le composant affiche actuellement "Sign In" au lieu de "Login".

        ## Impact utilisateur

        Les utilisateurs non connectés ne voient pas de lien de connexion clairement identifiable dans la barre de navigation, ce qui les empêche de trouver facilement la page de connexion.

        ## Correction proposée

        Modifier le composant Navbar pour que le lien d'authentification affiche le texte "Login" et non "Sign In" (ou tout autre libellé actuellement utilisé). Il faut localiser le composant de navigation (souvent `Navbar.tsx` ou `Header.tsx`) et remplacer le texte du lien par "Login".

        ### Code suggéré
```

// ❌ Avant — texte ne correspondant pas au test
<Link href="/login">Sign In</Link>

// ✅ Après — texte aligné avec le test Playwright
<Link href="/login">Login</Link>

```
        **Fichier à modifier :** `frontend/components/Navbar.tsx`

        ---
        *Généré automatiquement par Claude Sonnet — vérifier avant de merger.*