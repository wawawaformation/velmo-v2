<template>
  <footer class="site-footer">
    <div class="site-footer-inner">
      <nav class="site-footer-links" aria-label="Liens de pied de page">
        <a href="#">Confidentialité</a>
        <a href="#">CGU</a>
        <a href="#">Contact</a>
      </nav>
      <span class="site-footer-copy">© 2026 Velmo — maillots de football collector.</span>
    </div>
  </footer>
</template>

<style lang="scss" scoped>
.site-footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
  margin-top: auto;
}

.site-footer-inner {
  max-width: 480px;
  margin: 0 auto;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.site-footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;

  a {
    font-size: 12px;
    color: var(--text-muted);
    text-decoration: none;

    &:hover {
      color: var(--accent);
      text-decoration: underline;
      text-underline-offset: 2px;
    }
  }
}

.site-footer-copy {
  font-size: 11.5px;
  color: var(--text-muted);
  opacity: 0.85;
}
</style>
