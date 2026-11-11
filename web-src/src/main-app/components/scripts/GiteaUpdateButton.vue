<template>
  <!-- One-tap "update from Gitea" (admins only, only for scripts whose runner came from a Gitea
       import - see src/features/gitea_origin.py). Re-runs Import from Gitea for that repo in the
       background with apply on (no dry run), then reloads this script so the new version shows. -->
  <button v-if="origin"
          :class="{updating}"
          :disabled="updating"
          :title="tooltip"
          class="button-gitea-update btn btn-flat"
          @click="update">
    <i class="material-icons">{{ updating ? 'sync' : 'cloud_download' }}</i>
  </button>
</template>

<script>
import '@/common/materializecss/imports/toast';
import {axiosInstance} from '@/common/utils/axios_utils';
import {isNull} from '@/common/utils/common';
import {parametersToFormData} from '@/main-app/store/mainStoreHelper';
import get from 'lodash/get';
import {mapState} from 'vuex';

const POLL_INTERVAL_MS = 1000;
const MAX_WAIT_MS = 10 * 60 * 1000;

function escapeHtml(text) {
  return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
}

function formatTime(iso) {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  return isNaN(date.getTime()) ? null : date.toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export default {
  name: 'GiteaUpdateButton',

  data() {
    return {
      origin: null,
      updating: false
    }
  },

  computed: {
    ...mapState('scripts', ['selectedScript']),
    ...mapState('auth', {isAdmin: 'admin'}),

    tooltip() {
      const origin = this.origin;
      if (!origin) {
        return '';
      }
      const lines = [`Update from Gitea: ${origin.owner}/${origin.repo} @ ${origin.branch}`];
      if (origin.commit) {
        const committed = formatTime(origin.commitTime);
        lines.push(`Installed: commit ${origin.commit}` + (committed ? ` (${committed})` : ''));
      }
      const imported = formatTime(origin.importedAt);
      if (imported) {
        lines.push(`Imported ${imported}`);
      }
      lines.push('Re-imports the whole repo straight away (no dry run).');
      return lines.join('\n');
    }
  },

  watch: {
    selectedScript: {immediate: true, handler: 'loadOrigin'},
    isAdmin: 'loadOrigin'
  },

  methods: {
    loadOrigin() {
      const scriptName = this.selectedScript;
      this.origin = null;

      if (!this.isAdmin || isNull(scriptName)) {
        return;
      }

      axiosInstance.get('admin/scripts/' + encodeURIComponent(scriptName) + '/origin')
          .then(({data}) => {
            if (this.selectedScript === scriptName) {
              this.origin = data.origin || null;
            }
          })
          .catch(() => {
            // not an admin after all, script gone, older server - just no button
          });
    },

    async update() {
      const origin = this.origin;
      if (!origin || this.updating) {
        return;
      }

      this.updating = true;
      let executionId = null;

      try {
        const formData = parametersToFormData(origin.updateParameters || {});
        formData.append('__script_name', origin.updater);

        const {data} = await axiosInstance.post('executions/start', formData);
        executionId = data;

        const startedAt = Date.now();
        for (; ;) {
          await sleep(POLL_INTERVAL_MS);
          const {data: status} = await axiosInstance.get('executions/status/' + executionId);
          if (status === 'finished') {
            break;
          }
          if (Date.now() - startedAt > MAX_WAIT_MS) {
            throw new Error('still running after 10 minutes - check Settings › Logs');
          }
        }

        const {data: execution} = await axiosInstance.get('history/execution_log/long/' + executionId);
        const log = execution.log || '';
        const summaryLine = log.split('\n').reverse().find(line => line.startsWith('SUMMARY:'));

        if (execution.exitCode === 0) {
          const summary = summaryLine ? summaryLine.substring('SUMMARY:'.length).trim()
              : `${origin.owner}/${origin.repo} imported`;
          M.toast({html: 'Updated from Gitea: ' + escapeHtml(summary), displayLength: 8000});
        } else {
          const lastLines = log.trim().split('\n').slice(-3).join(' / ');
          this.showFailure(executionId, lastLines);
        }
      } catch (e) {
        const message = get(e, 'response.data') || get(e, 'message') || String(e);
        this.showFailure(executionId, typeof message === 'string' ? message : JSON.stringify(message));
      } finally {
        if (!isNull(executionId)) {
          axiosInstance.post('executions/cleanup/' + executionId).catch(() => null);
        }
        this.updating = false;
      }

      // Pick up the re-imported runner (and its scripts) straight away, and the new commit
      this.$store.dispatch('resetScript');
      this.loadOrigin();
    },

    showFailure(executionId, details) {
      const logLink = isNull(executionId) ? ''
          : ` <a href="admin.html#/logs/${encodeURIComponent(executionId)}" target="_blank" ` +
          'style="margin-left: 12px; color: inherit; text-decoration: underline">Open log</a>';
      M.toast({
        html: 'Update from Gitea failed: ' + escapeHtml(details || 'unknown error') + logLink,
        displayLength: 12000
      });
    }
  }
}
</script>

<style scoped>
/* Same metrics as ScriptHeader's Parameter History button, which it sits beside */
.button-gitea-update {
  margin-right: 4px;
  width: 40px;
  height: 40px;
  line-height: 40px;
  padding: 0;
  min-width: 40px;
  color: var(--font-color-medium);
}

.button-gitea-update i {
  font-size: 24px;
}

.button-gitea-update.updating i {
  animation: gitea-update-spin 1s linear infinite;
}

@keyframes gitea-update-spin {
  from {
    transform: rotate(360deg);
  }
  to {
    transform: rotate(0deg);
  }
}
</style>
