<template>
  <footer v-if="$nav.currentPage > 1" class="brand-footer">
    <img
      v-if="logoSrc"
      :src="logoSrc"
      alt="Logo"
      class="brand-logo"
    />
    <span class="brand-name">{{ brandName }}</span>
  </footer>
</template>

<script setup lang="ts">
/**
 * Brand footer — rendered on every slide except the cover.
 *
 * logoSrc and brandName are populated from _brand.yml during
 * project scaffolding. Update them when the brand changes.
 */
const logoSrc = ''   // e.g. '/logo.png' (place file in public/)
const brandName = '' // e.g. 'Acme Corp'
</script>

<style scoped>
.brand-footer {
  position: fixed;
  bottom: 1rem;
  left: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  opacity: 0.5;
  pointer-events: none;
  z-index: 100;
}

.brand-logo {
  height: 24px;
  width: auto;
}

.brand-name {
  font-size: 0.7rem;
  color: var(--ok-foreground, #111827);
}
</style>
