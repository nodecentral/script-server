<template>
  <div class="main-app-sidebar">
    <div v-if="railCollapsed" class="rail-strip">
      <a class="btn-flat rail-toggle-button" title="Expand sidebar" @click="$emit('toggle-expand')">
        <i class="material-icons">menu</i>
      </a>
      <!-- One icon per category: opens the sidebar with that category already expanded -->
      <div class="rail-categories">
        <a v-for="category in categoryTree" :key="category.key"
           :class="{'has-selected': category.key === selectedCategoryKey}"
           :title="category.name"
           class="btn-flat rail-category-button"
           @click="openCategoryFromRail(category.key)">
          <CategoryIcon :icon="category.icon"/>
        </a>
      </div>
    </div>

    <template v-else>
      <div class="list-header">
        <router-link :class="{
                      'header-gt-15-chars' : serverName && serverName.length >= 15,
                     'header-gt-18-chars' : serverName && serverName.length >= 18,
                     'header-gt-21-chars' : serverName && serverName.length >= 21
        }" :title="versionString"
                     class="header server-header"
                     to="/">
          {{ serverName || 'Script server' }}
        </router-link>

        <SearchPanel v-model="searchText"/>

        <div class="header-link">
          <a v-if="railMode" class="pin-toggle-button" title="Pin sidebar open"
             @click="$emit('toggle-rail-mode')">
            <i class="material-icons">lock_open</i>
          </a>
          <a v-else class="pin-toggle-button" title="Auto-hide sidebar" @click="$emit('toggle-rail-mode')">
            <i class="material-icons">lock</i>
          </a>
          <a v-if="adminUser" class="primary-color-text" href="admin.html">
            <i class="material-icons">settings</i>
          </a>
          <a v-else href="https://github.com/bugy/script-server" target="_blank">
            <svg aria-hidden="true" class="svg-icon github-icon" height="20px" viewBox="0 0 16 16" width="20px">
              <path
                  d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
          </a>
        </div>
      </div>

      <ScriptsList :active-category="activeCategory"
                   :active-group="activeGroup"
                   :search-text="searchText"
                   @category-clicked="toggleCategory"
                   @group-clicked="toggleGroup"/>

      <router-link
          class="waves-effect btn-flat bottom-panel primary-color-text history-button"
          to='/history'>
        History
      </router-link>

      <router-link class="version-panel" title="What's new in this version" to="/changelog">
        <span v-if="versionString" class="version-number">{{ versionString }}</span>
        <span class="whats-new">What's new</span>
      </router-link>

      <div v-if="authEnabled" class="logout-panel bottom-panel">
        <span>{{ username }}</span>
        <a class="btn-icon-flat waves-effect logout-button waves-circle" @click="logout">
          <i class="material-icons primary-color-text">power_settings_new</i>
        </a>
      </div>
    </template>
  </div>
</template>

<script>
import CategoryIcon from '@/common/components/CategoryIcon';
import {isNull} from '@/common/utils/common';
import {mapActions, mapGetters, mapState} from 'vuex';
import {findScriptLocation} from '../utils/categories';
import ScriptsList from './scripts/ScriptsList'
import SearchPanel from './SearchPanel';

export default {
  name: 'MainAppSidebar',
  components: {
    CategoryIcon,
    SearchPanel,
    ScriptsList
  },
  props: {
    // Desktop-only "slim rail" state, passed down from AppLayout's scoped sidebar slot. When
    // true, render just the toggle button - not a squeezed copy of the full list.
    railCollapsed: {
      type: Boolean,
      default: false
    },
    // Whether rail mode is the user's current preference at all (independent of whether it's
    // collapsed or temporarily expanded right now) - drives which pin-toggle icon/tooltip shows.
    railMode: {
      type: Boolean,
      default: false
    }
  },

  data() {
    return {
      searchText: '',
      // Keys from the category tree (utils/categories.js). Kept here rather than in ScriptsList
      // because ScriptsList isn't rendered while the sidebar is collapsed to the rail.
      activeCategory: null,
      activeGroup: null
    }
  },

  computed: {
    ...mapGetters('scripts', ['categoryTree']),
    ...mapState('scripts', ['selectedScript']),

    selectedLocation() {
      if (isNull(this.selectedScript)) {
        return null;
      }
      return findScriptLocation(this.categoryTree, this.selectedScript);
    },

    selectedCategoryKey() {
      return this.selectedLocation ? this.selectedLocation.category.key : null;
    },

    ...mapState('serverConfig', {
      versionString: state => state.version ? 'v' + state.version : null,
      serverName: 'serverName'
    }),
    ...mapState('auth', {
      adminUser: 'admin',
      username: 'username',
      authEnabled: 'enabled'
    })
  },

  methods: {
    ...mapActions(['logout']),

    toggleCategory(categoryKey) {
      this.activeCategory = (this.activeCategory === categoryKey) ? null : categoryKey;
      this.activeGroup = null;
    },

    toggleGroup(groupKey) {
      this.activeGroup = (this.activeGroup === groupKey) ? null : groupKey;
    },

    openCategoryFromRail(categoryKey) {
      if (this.activeCategory !== categoryKey) {
        this.activeCategory = categoryKey;
        this.activeGroup = null;
      }
      this.searchText = '';
      this.$emit('toggle-expand');
    },

    revealSelectedScript() {
      const location = this.selectedLocation;
      if (isNull(location)) {
        return;
      }
      this.activeCategory = location.category.key;
      this.activeGroup = location.group ? location.group.key : null;
    }
  },

  watch: {
    // Follow the selected script (deep link, back/forward, a search pick) so the tree opens on it
    selectedLocation: {
      immediate: true,
      handler(newLocation, oldLocation) {
        const sameCategory = newLocation && oldLocation && (newLocation.category.key === oldLocation.category.key);
        const sameGroup = sameCategory && ((newLocation.group && newLocation.group.key)
            === (oldLocation.group && oldLocation.group.key));
        if (!sameGroup) {
          this.revealSelectedScript();
        }
      }
    },

    // Only one category in total (e.g. nothing categorised yet): no point making people click it open
    categoryTree: {
      immediate: true,
      handler(tree) {
        if ((tree.length === 1) && isNull(this.activeCategory)) {
          this.activeCategory = tree[0].key;
        }
      }
    }
  }
}
</script>

<style scoped>
.list-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;

  border-bottom: 5px solid transparent; /* This is to make the header on the same level as the script header */

  flex-shrink: 0;

  position: relative;
}

.server-header {
  flex-grow: 1;
  margin-left: 0.4rem;

  font-size: 1.64rem;
  padding: 0.8rem;
  font-weight: 300;
  line-height: 110%;
  color: var(--font-color-main);
  min-width: 0;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.server-header.header-gt-15-chars {
  font-size: 1.45rem;
}

.server-header.header-gt-18-chars {
  font-size: 1.25rem;
}

.server-header.header-gt-21-chars {
  font-size: 1.2rem;
}

.main-app-sidebar {
  height: 100%;

  background: var(--background-color);

  display: flex;
  flex-direction: column;
}

.header-link {
  margin: 0 1rem;
  display: flex;
  line-height: 0;
}

.header-link .svg-icon {
  width: 24px;
  height: 24px;
}

.header-link .svg-icon path {
  fill: var(--primary-color)
}

.pin-toggle-button {
  color: var(--font-color-medium);
  flex-shrink: 0;

  /* Defensive sizing: an unrecognised material-icons ligature name renders as raw fallback text
     instead of a glyph and can otherwise blow out this whole header row's width (this exact bug
     shipped once already - keyboard_double_arrow_left/push_pin aren't in this project's bundled
     icon font version). Clip and fix the size so a bad icon name degrades to a small blank box
     instead of pushing the server name out of view. */
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  overflow: hidden;
  white-space: nowrap;
}

.pin-toggle-button:hover {
  color: var(--font-color-main);
}

.rail-strip {
  height: 100%;
  width: 56px;

  display: flex;
  flex-direction: column;
  align-items: center;
}

.rail-toggle-button {
  margin-top: 12px;
  width: 40px;
  height: 40px;

  display: flex;
  align-items: center;
  justify-content: center;

  flex-shrink: 0;
  border-radius: 50%;
  color: var(--font-color-main);
}

.rail-categories {
  width: 100%;
  margin-top: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--separator-color);

  display: flex;
  flex-direction: column;
  align-items: center;

  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.rail-category-button {
  width: 40px;
  height: 40px;
  margin: 2px 0;
  padding: 0;

  display: flex;
  align-items: center;
  justify-content: center;

  flex-shrink: 0;
  border-radius: 50%;
  color: var(--font-color-medium);
}

.rail-category-button:hover {
  color: var(--font-color-main);
}

/* The category holding the open script - same primary/focus pairing as an active list item */
.rail-category-button.has-selected {
  color: var(--primary-color);
  background-color: var(--focus-color);
}

.history-button {
  line-height: 3em;
  text-align: center;
}

/* Version + "What's new" link, under History */
.version-panel {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: baseline;
  gap: 8px;

  padding: 4px 0 8px;
  font-size: 0.85em;
  color: var(--font-color-medium);
}

.version-panel:hover .whats-new {
  text-decoration: underline;
}

.version-panel .version-number {
  font-weight: 500;
  color: var(--font-color-main);
}

.version-panel .whats-new {
  color: var(--primary-color);
}

.bottom-panel {
  height: 3em;
  width: 100%;
  border-top: 1px solid var(--separator-color);

  flex-shrink: 0;
}

.logout-panel {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
}

.logout-button {
  margin-left: 4px;
}

</style>