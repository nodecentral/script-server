<template>
  <!-- One Settings tab: a placement=settings runner, rendered with the main app's own script
       components so the preload banner, form, live output, execution tabs and scheduling behave
       exactly as they do in the user view - just below admin.html's horizontal tab bar instead
       of beside the sidebar. -->
  <div class="settings-script-page">
    <div class="settings-script-header shadow-8dp">
      <ScriptHeader/>
      <div v-if="pageLoading" class="progress">
        <div class="indeterminate"></div>
      </div>
    </div>

    <div v-if="notListed" class="settings-script-message">
      <p>
        <b>{{ scriptName }}</b> is not a Settings script - its runner has no
        <code>"placement": "settings"</code>, or it no longer exists.
      </p>
    </div>
    <MainAppContent v-else class="settings-script-content"/>
  </div>
</template>

<script>
import MainAppContent from '@/main-app/components/scripts/MainAppContent';
import ScriptHeader from '@/main-app/components/scripts/ScriptHeader';
import {mapState} from 'vuex';
import settingsRunnerStore from '../../store/settings-runner-store';

export default {
  name: 'SettingsScriptPage',
  components: {MainAppContent, ScriptHeader},

  // Injects the runner store for this subtree only - see settings-runner-store.js
  store: settingsRunnerStore,

  props: {
    scriptName: {
      type: String,
      required: true
    }
  },

  computed: {
    ...mapState('page', ['pageLoading']),
    ...mapState('scripts', {
      scriptsLoaded: 'loaded',
      settingsScripts: 'scripts'
    }),

    notListed() {
      return this.scriptsLoaded && !this.settingsScripts.some(script => script.name === this.scriptName);
    }
  },

  watch: {
    scriptName: {
      immediate: true,
      handler(scriptName) {
        this.$store.dispatch('scripts/selectScript', scriptName);
      }
    }
  }
}
</script>

<style scoped>
.settings-script-page {
  height: 100%;
  display: flex;
  flex-direction: column;

  background: var(--background-color);
}

/* Matches the user view's content header (AppLayout .content-header): same height, padding and
   elevation, so a script looks the same in both places. */
.settings-script-header {
  position: relative;
  flex: 0 0 auto;

  padding-left: 24px;
  border-bottom: 1px solid var(--separator-color);
  background: var(--script-header-background);
  z-index: 1;
}

.settings-script-header .progress {
  position: absolute;
  left: 0;
  bottom: -1px;
  margin: 0;
}

.settings-script-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.settings-script-message {
  padding: 16px 24px;
  color: var(--font-color-main);
}
</style>
