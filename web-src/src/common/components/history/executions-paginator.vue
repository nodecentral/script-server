<template>
  <div class="executions-paginator">
    <div class="page-size-panel">
      <label class="page-size-label" for="executions-page-size">Rows</label>
      <select id="executions-page-size" class="browser-default page-size-select"
              :value="pageSize"
              :disabled="loading"
              @change="pageSizeChanged">
        <option v-for="option in pageSizeOptions" :key="option" :value="option">{{ option }}</option>
      </select>
    </div>
    <span class="range-label">{{ rangeLabel }}</span>
    <div class="buttons-panel">
      <button class="btn-flat prev-button"
              :disabled="prevDisabled"
              @click="prevPage">Previous
      </button>
      <button class="btn-flat next-button"
              :disabled="nextDisabled"
              @click="nextPage">Next
      </button>
    </div>
  </div>
</template>

<script>
import {mapActions, mapState} from 'vuex';
import {PAGE_SIZE_OPTIONS} from '@/common/store/executions-module';

export default {
  name: 'executions-paginator',

  data() {
    return {
      pageSizeOptions: PAGE_SIZE_OPTIONS
    }
  },

  methods: {
    ...mapActions('history', ['nextPage', 'prevPage', 'setPageSize']),

    pageSizeChanged(event) {
      this.setPageSize(parseInt(event.target.value));
    }
  },

  computed: {
    ...mapState('history', ['executions', 'pageSize', 'total', 'hasNext', 'hasPrev', 'loading', 'cursorStack']),

    rangeStart() {
      if (this.executions.length === 0) {
        return 0;
      }
      return this.cursorStack.length * this.pageSize + 1;
    },

    rangeEnd() {
      if (this.executions.length === 0) {
        return 0;
      }
      return this.rangeStart + this.executions.length - 1;
    },

    rangeLabel() {
      if (this.executions.length === 0) {
        return '0 of ' + this.total;
      }
      return this.rangeStart + '-' + this.rangeEnd + ' of ' + this.total;
    },

    prevDisabled() {
      return !this.hasPrev || this.loading;
    },

    nextDisabled() {
      return !this.hasNext || this.loading;
    }
  }
}
</script>

<style scoped>
.executions-paginator {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 16px;
  padding: 8px 0;
  color: var(--font-color-medium);
  font-size: 0.9em;
}

.executions-paginator .page-size-panel {
  display: flex;
  align-items: center;
  gap: 8px;
}

.executions-paginator .page-size-label {
  color: var(--font-color-medium);
}

.executions-paginator .page-size-select {
  width: auto;
  height: 2rem;
  padding: 0 1.5rem 0 0.5rem;
  color: var(--font-color-main);
  background-color: var(--background-color);
  border: 1px solid var(--outline-color);
  border-radius: 2px;
}

.executions-paginator .buttons-panel {
  display: flex;
  gap: 4px;
}

.executions-paginator button {
  color: var(--primary-color);
}

.executions-paginator button:disabled {
  color: var(--font-color-disabled);
  cursor: default;
}
</style>
