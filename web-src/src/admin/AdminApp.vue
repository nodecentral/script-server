<template>
  <div class="admin-page">
    <div class="page-title primary-color-dark">
      <div class="main-header">
        <a class="btn-flat left home-button" href="index.html">
          <i class="material-icons">home</i>
        </a>
        <!-- Horizontal Settings menu: the two built-in admin pages, then one tab per
             placement=settings runner (scrolls sideways when they don't fit, e.g. on an iPad) -->
        <ul ref="tabs" class="tabs settings-tabs">
          <li class="tab">
            <router-link to="/logs">Logs</router-link>
          </li>
          <li class="tab">
            <router-link to="/scripts">Scripts</router-link>
          </li>
          <li v-if="settingsScripts.length" aria-hidden="true" class="tab-separator"></li>
          <li v-for="script in settingsScripts" :key="script.name" class="tab">
            <router-link :to="settingsScriptPath(script.name)" :title="script.name">{{ script.name }}</router-link>
          </li>
        </ul>
      </div>
      <div v-if="subheader" class="subheader">{{ subheader }}</div>
    </div>
    <router-view class="page-content"/>
  </div>
</template>

<script>
import executions from '@/common/store/executions-module';
import Vue from 'vue';
import Vuex, {mapActions, mapState} from 'vuex';
import scriptConfig from './store/script-config-module';
import scripts from './store/scripts-module';
import File_upload from '@/common/components/file_upload'
import authModule from '@/common/store/auth';
import settingsRunnerStore from './store/settings-runner-store';

Vue.use(Vuex);

const store = new Vuex.Store({
  state: {
    subheader: null
  },
  modules: {
    'history': executions(),
    scripts: scripts,
    scriptConfig: scriptConfig,
    auth: authModule
  },
  actions: {
    setSubheader({commit}, subheader) {
      commit('SET_SUBHEADER', subheader);
    }
  },
  mutations: {
    SET_SUBHEADER(state, subheader) {
      if (subheader) {
        state.subheader = subheader;
      } else {
        state.subheader = null;
      }
    }
  }
});

export default {
  name: 'AdminApp',
  components: {File_upload},
  store,

  mounted() {
    // No M.Tabs.init: Materialize's JS indicator only measures the tabs present at mount, and
    // the settings tabs arrive later from the server. Active state comes from router-link's
    // 'active' class instead (styled below).
    this.init();

    settingsRunnerStore.dispatch('init')
        .then(() => this.$nextTick(this.scrollActiveTabIntoView));
  },

  computed: {
    ...mapState(['subheader']),

    // Read straight from the runner store (it's reactive), the admin store doesn't hold them
    settingsScripts() {
      return settingsRunnerStore.state.scripts.scripts;
    }
  },

  methods: {
    ...mapActions(['setSubheader']),
    ...mapActions('auth', ['init']),

    settingsScriptPath(scriptName) {
      return '/settings/' + encodeURIComponent(scriptName);
    },

    scrollActiveTabIntoView() {
      const tabs = this.$refs.tabs;
      const active = tabs && tabs.querySelector('a.active');
      if (!active) {
        return;
      }
      const tabsRect = tabs.getBoundingClientRect();
      const activeRect = active.getBoundingClientRect();
      if ((activeRect.left < tabsRect.left) || (activeRect.right > tabsRect.right)) {
        tabs.scrollLeft += activeRect.left - tabsRect.left - (tabsRect.width - activeRect.width) / 2;
      }
    }
  },

  watch: {
    $route() {
      this.setSubheader(null);
      this.$nextTick(this.scrollActiveTabIntoView);
    }
  }
}
</script>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;

  background: var(--background-color);
  font-family: "Roboto", sans-serif;
  font-weight: normal;

  height: 100vh;
}

.page-title {
  flex: 0 0 0;
  width: 100%;

  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;

  box-shadow: var(--shadow-4dp);
}

.main-header {
  display: flex;
  align-items: stretch;
  min-width: 0;
}

.tabs.settings-tabs {
  flex: 1 1 auto;
  width: auto;
  min-width: 0;
  margin: 0;

  display: flex;
  background: none;

  /* Sideways scrolling with touch momentum, scrollbar hidden (the header is only 48px tall) */
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.tabs.settings-tabs::-webkit-scrollbar {
  display: none;
}

.tabs.settings-tabs .tab {
  flex: 0 0 auto;
}

.tabs.settings-tabs .tab a {
  max-width: 16em;
  font-size: 1em;
  font-weight: 500;
  letter-spacing: 1px;
}

/* Replaces Materialize's JS-positioned .indicator: same colour, drawn on the active link itself */
.tabs.settings-tabs .tab a.active {
  box-shadow: inset 0 -2px 0 var(--font-on-primary-color-dark-main);
}

/* Built-in admin pages | settings scripts */
.tab-separator {
  flex: 0 0 auto;
  width: 1px;
  margin: 12px 8px;
  background: var(--font-on-primary-color-dark-medium);
  opacity: 0.5;
}

.subheader {
  font-size: 1em;
  font-weight: 400;

  text-transform: uppercase;
  text-align: center;
  color: var(--font-on-primary-color-dark-main);

  margin-top: 0.8em;
  margin-bottom: 0.8em;
}

.page-content {
  flex: 1 1 0;
  overflow-y: auto;
}

.home-button {
  flex: 0 0 auto;
  height: 100%;
  padding-left: 20px;
  padding-right: 20px;
}

.home-button i {
  font-size: 1.8em;
  line-height: 1.8em;
}
</style>