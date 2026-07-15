<template>
  <header class="app-header">
    <div class="app-header-inner">
      <svg class="logo" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path
          d="M14 6 L6 12 L10 20 L14 17 L14 42 H34 L34 17 L38 20 L42 12 L34 6
             C34 9.5 29.6 12 24 12 C18.4 12 14 9.5 14 6 Z"
          stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"
        />
        <path
          d="M24 12 C21 12 18.4 11.3 16.7 10.1"
          stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity="0.55"
        />
      </svg>
      <div class="header-text">
        <span class="eyebrow">Velmo — support</span>
        <h1>Assistant de commande</h1>
      </div>
    </div>
  </header>
</template>

<style lang="scss" scoped>
.app-header {
  background: var(--bg);
}

.app-header-inner {
  max-width: 480px;
  margin: 0 auto;
  padding: 28px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  color: var(--accent);
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

h1 {
  font-size: 19px;
  font-weight: 650;
  margin: 0;
  text-wrap: balance;
}
</style>
