<template>
  <div class="main-app-content">
    <ScriptView ref="scriptView" :class="{collapsed: showError}"
                :hideExecutionControls="showError"/>
    <div v-if="showError" class="error-panel">
      <p v-if="!authenticated">
        Credentials expired, please <a href="javascript:void(0)" onclick="location.reload()">relogin</a>
      </p>
      <p v-else-if="scriptLoadError && notFound">
        Failed to load script info: script '{{ selectedScript }}' not found
      </p>
      <template v-else-if="scriptLoadError && cannotParse">
        <p>Cannot parse script config file, please contact the administrator</p>
        <pre v-if="parseErrorDetail" class="error-detail">{{ parseErrorDetail }}</pre>
      </template>
      <template v-else-if="scriptLoadError">
        <p>Failed to load script info. Error message:</p>
        <pre class="error-detail">{{ scriptLoadError }}</pre>
        <p v-if="isGenericError" class="error-hint">Try to reload the page.</p>
        <p v-else class="error-hint">The server log has the full traceback.</p>
      </template>
    </div>
  </div>
</template>

<script>
import {isEmptyString} from '@/common/utils/common';
import {mapActions, mapState} from 'vuex';
import {CANNOT_PARSE_ERROR_PREFIX, GENERIC_LOAD_ERRORS, NOT_FOUND_ERROR_PREFIX} from '../../store/scriptConfig';
import ScriptView from './script-view';

export default {
  name: 'MainAppContent',
  components: {ScriptView},

  computed: {
    showError() {
      return !!(this.scriptLoadError || !this.authenticated);
    },
    notFound() {
      return !isEmptyString(this.scriptLoadError) && this.scriptLoadError.startsWith(NOT_FOUND_ERROR_PREFIX);
    },
    cannotParse() {
      return !isEmptyString(this.scriptLoadError) && this.scriptLoadError.startsWith(CANNOT_PARSE_ERROR_PREFIX); 
    },
    parseErrorDetail() {
      // admins get "file.json: <JSON error>" after the prefix
      const rest = this.scriptLoadError.substring(CANNOT_PARSE_ERROR_PREFIX.length).replace(/^[:\s]+/, '');
      return rest.startsWith('"') ? '' : rest;
    },
    isGenericError() {
      return GENERIC_LOAD_ERRORS.includes(this.scriptLoadError);
    },
    ...mapState('auth', ['authenticated']),
    ...mapState('scriptConfig', {scriptLoadError: 'loadError', loading: 'loading'}),
    ...mapState('scripts', ['selectedScript'])
  },
  methods: {
    ...mapActions('page', ['setLoading'])
  },
  watch: {
    loading: {
      immediate: true,
      handler(newValue) {
        this.setLoading(newValue);
      }
    }
  }
}
</script>

<style scoped>
.main-app-content {
  height: 100%;

  background: var(--background-color);
  padding: 16px 24px 12px;

  display: flex;
  flex-direction: column;
}

.main-app-content >>> .input-field label {
  top: 0;

  text-overflow: ellipsis;
  white-space: nowrap;
  overflow: hidden;
}

.collapsed {
  flex: 0 1 auto;
}

.error-panel {
  color: #F44336;
  margin-top: 17px;
}

.error-panel p {
  margin: 0;
}

.error-panel .error-detail {
  margin: 6px 0;
  padding: 8px 10px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  color: var(--font-color-main);
  background: var(--surface-color);
  border-left: 3px solid #F44336;
}

.error-panel .error-hint {
  color: var(--font-color-medium);
  font-size: 13px;
}

</style>