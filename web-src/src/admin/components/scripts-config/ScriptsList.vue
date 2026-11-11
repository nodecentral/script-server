<template>
  <div class="container scripts-list">
    <PageProgress v-if="loading"/>
    <div v-else>
      <router-link :to="newScriptPath" append class="waves-effect waves-light btn add-script-btn">
        <i class="material-icons left">add</i>
        Add
      </router-link>
      <div class="collection">

        <template v-for="script in scripts">
          <router-link :key="script.name"
                       :class="{'parsing-failed': script.parsingFailed}"
                       :to="script.path"
                       append
                       class="collection-item">
            <span class="script-name">{{ script.name }}</span>
            <span v-if="script.location" class="script-location">{{ script.location }}</span>
          </router-link>
        </template>

      </div>
    </div>
  </div>
</template>

<script>
import PageProgress from '@/common/components/PageProgress';
import {mapActions, mapState} from 'vuex';
import {NEW_SCRIPT} from '../../store/script-config-module';

// Where the script shows up: a Settings tab, or its place in the sidebar's Category > Group tree
function describeLocation(script) {
  if (script.placement === 'settings') {
    return 'Settings tab';
  }
  return [script.category, script.group].filter(part => part).join(' › ');
}

export default {
  name: 'ScriptsList',

  mounted: function () {
    this.init();
  },

  data() {
    return {
      newScriptPath: NEW_SCRIPT
    }
  },

  computed: {
    ...mapState('scripts', {
      scripts: state => {
        return state.scripts
            ? state.scripts.map(s => ({
              name: s.name,
              path: encodeURIComponent(s.name),
              parsingFailed: s.parsingFailed,
              location: describeLocation(s)
            }))
            : []
      },
      loading: 'loading'
    })
  },

  components: {
    PageProgress
  },

  methods: {
    ...mapActions('scripts', ['init'])
  }
}
</script>

<style scoped>
.scripts-list {
  margin-top: 1.5em;
  margin-bottom: 1em;
}

.add-script-btn {
  margin-bottom: 1em;
}

.scripts-list .collection-item {
  display: flex;
  align-items: baseline;
}

.scripts-list .collection-item .script-name {
  flex: 1 1 auto;
  min-width: 0;
}

.scripts-list .collection-item .script-location {
  flex: 0 1 auto;
  margin-left: 16px;

  font-size: 0.85em;
  color: var(--font-color-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scripts-list .collection-item.parsing-failed {
  color: var(--error-color);
  pointer-events: none;
}

.scripts-list .collection-item.parsing-failed::after {
  content: '(failed to parse config file)';
}

</style>