<template>
  <div class="main-content-header">
    <h3 class="header">What's new</h3>
    <span v-if="version" class="current-version">you're on v{{ version }}</span>
  </div>
</template>

<script>
import {mapState} from 'vuex';

export default {
  name: 'ChangelogHeader',
  computed: {
    ...mapState('serverConfig', ['version'])
  }
}
</script>

<style scoped>
/* Same header metrics as the History page (AppHistoryHeader.vue) */
.main-content-header {
  padding: 0;
  height: 56px;
  display: flex;
  align-items: center;
}

.main-content-header h3 {
  padding: 0;
  display: inline;
  color: var(--font-color-main);
  line-height: 1.3em;
  font-size: 1.3em;
}

.current-version {
  margin-left: 16px;
  color: var(--font-color-medium);
}
</style>
