<script setup>
import { ref, computed, onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import AppNav from './components/AppNav.vue'
import AppFooter from './components/AppFooter.vue'

// Libellés humains — mêmes catégories que _CATEGORY_LABELS côté backend
// (src/velmo/guardrails/__init__.py), dupliqués ici car le front n'a pas
// accès au code Python.
const GUARDRAIL_LABELS = {
  hate: 'propos à caractère haineux',
  violence: 'menace ou contenu violent',
  sexual: 'contenu à caractère sexuel',
  self_harm: 'contenu lié à l’automutilation',
  out_of_scope: 'hors périmètre',
  prompt_injection: 'tentative de contournement des instructions',
  pii: 'donnée sensible',
  secret_leak: 'donnée sensible',
}

const users = ref([])
const selectedUserId = ref('')
const message = ref('')
const reply = ref('')
const latencyMs = ref(null)
const guardrailCategory = ref(null)
const isLoading = ref(false)
const isError = ref(false)

const selectedUserName = computed(() => {
  const user = users.value.find((u) => u.id === selectedUserId.value)
  return user ? user.full_name : ''
})

async function loadUsers() {
  const response = await fetch('/api/users')
  users.value = await response.json()
  if (users.value.length > 0) {
    selectedUserId.value = users.value[0].id
  }
}

async function submitMessage() {
  if (!message.value.trim() || !selectedUserId.value) return

  isLoading.value = true
  isError.value = false
  reply.value = ''
  latencyMs.value = null
  guardrailCategory.value = null

  try {
    const response = await fetch('/api/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: selectedUserId.value, message: message.value }),
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const data = await response.json()
    reply.value = data.reply
    latencyMs.value = data.latency_ms
    guardrailCategory.value = data.guardrail_category
  } catch (err) {
    isError.value = true
    reply.value = "Une erreur est survenue en contactant l'assistant. Réessayez dans un instant."
  } finally {
    isLoading.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <AppHeader />
  <AppNav :users="users" v-model:selected-user-id="selectedUserId" />

  <div class="page">
    <p class="active-client">
      Client actif : <strong>{{ selectedUserName }}</strong>
      <span class="active-client-hint">(changer via l'icône profil, en haut à droite)</span>
    </p>

    <form class="composer" @submit.prevent="submitMessage">
      <div class="field-group">
        <label for="message">Message</label>
        <textarea
          id="message"
          v-model="message"
          placeholder="Où en est ma commande O-2024-0101 ?"
        ></textarea>
      </div>
      <button class="submit" type="submit" :disabled="isLoading">
        <span v-if="isLoading" class="spinner"></span>
        <span>{{ isLoading ? 'Envoi…' : 'Envoyer' }}</span>
      </button>
    </form>

    <div class="result">
      <label>Réponse</label>
      <span v-if="latencyMs !== null" class="latency">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15 14" />
        </svg>
        <span>{{ (latencyMs / 1000).toFixed(1) }} s</span>
        <span v-if="guardrailCategory" class="guardrail-tag">
          garde-fou : {{ GUARDRAIL_LABELS[guardrailCategory] || guardrailCategory }}
        </span>
      </span>
      <div
        class="response-box"
        :class="{ 'is-empty': !reply, 'is-error': isError }"
        role="status"
        aria-live="polite"
      >
        {{ reply || "La réponse s'affichera ici après l'envoi du message." }}
      </div>
    </div>

   
    <div class="ai-notice" role="note">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" /><line x1="12" y1="11" x2="12" y2="16.5" /><circle cx="12" cy="7.8" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      <span>
        <strong>Vous échangez avec une IA.</strong> Système à risque limité
        (Règlement européen sur l'IA).
        <a href="https://www.cnil.fr/fr/entree-en-vigueur-du-reglement-europeen-sur-lia-les-premieres-questions-reponses-de-la-cnil" target="_blank" rel="noopener noreferrer">En savoir plus</a>.
        L'assistant peut faire des erreurs. Vérifiez les informations importantes
        (numéros de commande, montants) avant d'agir.
      </span>
    </div>
  </div>

  <AppFooter />
</template>

<style lang="scss" scoped>
.page {
  max-width: 480px;
  margin: 0 auto;
  padding: 40px 20px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  width: 100%;
}

.active-client {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);

  strong {
    color: var(--text);
  }
}

.active-client-hint {
  font-size: 11.5px;
  opacity: 0.8;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-muted);
}

textarea {
  width: 100%;
  font-family: inherit;
  font-size: 14.5px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
  resize: vertical;
  min-height: 84px;
}

textarea:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.composer {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

button.submit {
  align-self: flex-end;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--accent);
  color: var(--accent-contrast);
  border: none;
  border-radius: var(--radius);
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.spinner {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid color-mix(in srgb, var(--accent-contrast) 35%, transparent);
  border-top-color: var(--accent-contrast);
  animation: spin 0.7s linear infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.latency {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  width: fit-content;

  svg {
    width: 12px;
    height: 12px;
    opacity: 0.75;
  }
}

.guardrail-tag {
  font-family: inherit;
  font-size: 11.5px;
  color: var(--warning);
  &::before {
    content: '·';
    margin-right: 5px;
  }
}

.response-box {
  background: color-mix(in srgb, var(--accent) 5%, var(--bg));
  border: none;
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 14px 16px;
  min-height: 72px;
  font-size: 14.5px;
  white-space: pre-wrap;
  cursor: default;
  user-select: text;

  &.is-empty {
    background: transparent;
    border-left-color: var(--border);
    color: var(--text-muted);
    font-style: italic;
  }

  &.is-error {
    background: var(--danger-bg);
    border-left-color: var(--danger);
    color: var(--danger);
    font-style: normal;
  }
}

.meta {
  margin: 0;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  font-size: 11.5px;
  color: var(--text-muted);
}

.ai-notice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: color-mix(in srgb, var(--warning) 12%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--warning) 35%, var(--border));
  border-radius: var(--radius);
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--text-muted);
  // Marge haute propre (au-delà du gap normal de .page), pour ne pas se
  // confondre avec la zone réponse juste au-dessus.
  margin-top: 28px;

  svg {
    flex-shrink: 0;
    width: 15px;
    height: 15px;
    margin-top: 1px;
    color: var(--warning);
  }

  strong {
    color: var(--text);
    font-weight: 600;
  }

  a {
    color: var(--warning);
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
}
</style>
