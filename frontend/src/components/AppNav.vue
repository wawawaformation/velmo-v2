<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  users: { type: Array, required: true },
  selectedUserId: { type: String, required: true },
})

const emit = defineEmits(['update:selectedUserId'])

const isOpen = ref(false)
const rootEl = ref(null)

function toggleMenu() {
  isOpen.value = !isOpen.value
}

function closeMenu() {
  isOpen.value = false
}

function selectUser(userId) {
  emit('update:selectedUserId', userId)
  closeMenu()
}

function onDocumentClick(event) {
  if (isOpen.value && rootEl.value && !rootEl.value.contains(event.target)) {
    closeMenu()
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') closeMenu()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <nav class="site-nav" aria-label="Navigation principale">
    <div class="site-nav-inner">
      <div class="site-nav-links">
        <a href="#" class="current">Accueil</a>
        <a href="#">À propos</a>
        <a href="#">Nos maillots</a>
        <a href="#">Contact</a>
      </div>

      <div class="user-menu" ref="rootEl">
        <button
          class="user-menu-trigger"
          type="button"
          aria-haspopup="true"
          :aria-expanded="isOpen"
          aria-label="Changer de client"
          @click="toggleMenu"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4.4 3.6-7 8-7s8 2.6 8 7" />
          </svg>
        </button>
        <div class="user-menu-dropdown" role="menu" v-show="isOpen">
          <span class="user-menu-label">Client actif</span>
          <button
            v-for="user in props.users"
            :key="user.id"
            class="user-menu-option"
            :class="{ 'is-selected': user.id === props.selectedUserId }"
            role="menuitemradio"
            :aria-checked="user.id === props.selectedUserId"
            @click="selectUser(user.id)"
          >
            {{ user.full_name }}
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<style lang="scss" scoped>
nav.site-nav {
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.site-nav-inner {
  max-width: 480px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 48px;
}

.site-nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  min-width: 0;
}

.site-nav a {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-decoration: none;
  padding: 6px 10px;
  border-radius: var(--radius);

  &:hover {
    color: var(--text);
    background: var(--bg);
  }

  &.current {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }
}

.user-menu {
  position: relative;
  flex-shrink: 0;
}

.user-menu-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;

  &:hover,
  &[aria-expanded='true'] {
    border-color: var(--accent);
    color: var(--accent);
  }

  svg {
    width: 17px;
    height: 17px;
  }
}

.user-menu-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 10;
  min-width: 220px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 8px 24px color-mix(in srgb, var(--text) 12%, transparent);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-menu-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 6px 10px 4px;
}

.user-menu-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  text-align: left;
  font-family: inherit;
  font-size: 13.5px;
  color: var(--text);
  background: none;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  padding: 8px 10px;
  cursor: pointer;

  &:hover {
    background: var(--bg);
  }

  &.is-selected {
    color: var(--accent);
    font-weight: 600;

    &::after {
      content: '✓';
    }
  }
}
</style>
