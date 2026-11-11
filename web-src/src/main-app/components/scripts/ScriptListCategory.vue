<template>
  <div :class="{expanded, 'has-selected': containsSelected}" class="script-list-category">
    <a :title="category.name" class="collection-item waves-effect category-header"
       @click="$emit('category-clicked', category.key)">
      <CategoryIcon :icon="category.icon" class="category-header-icon"/>
      <span class="category-name">{{ category.name }}</span>
      <span class="category-count">{{ category.allScripts.length }}</span>
      <i class="material-icons expand-icon">{{ expanded ? 'expand_less' : 'expand_more' }}</i>
    </a>

    <div v-if="expanded" class="category-children">
      <ScriptListGroup v-for="group in groups" :key="group.key" :group="group"
                       @group-clicked="$emit('group-clicked', group.key)"/>
      <ScriptListItem v-for="script in category.scripts" :key="script.name" :script="script"/>
    </div>
  </div>
</template>

<script>
import CategoryIcon from '@/common/components/CategoryIcon';
import {mapState} from 'vuex';
import ScriptListGroup from './ScriptListGroup';
import ScriptListItem from './ScriptListItem';

export default {
  name: 'ScriptListCategory',
  components: {CategoryIcon, ScriptListGroup, ScriptListItem},
  props: {
    category: {
      type: Object,
      required: true
    },
    expanded: {
      type: Boolean,
      default: false
    },
    activeGroup: {
      type: String,
      default: null
    }
  },
  computed: {
    ...mapState('scripts', ['selectedScript']),

    // ScriptListGroup's existing contract: {name, isActive, scripts}
    groups() {
      return this.category.groups.map(group => ({...group, isActive: group.key === this.activeGroup}));
    },

    containsSelected() {
      return this.category.allScripts.some(script => script.name === this.selectedScript);
    }
  }
}
</script>

<style scoped>
/* Indentation: children line up with the category NAME (20px gutter + 24px icon + 16px gap),
   and scripts inside a group step in one more level, matching upstream's group nesting. */
.script-list-category .collection-item.category-header {
  border: none;
  display: flex;
  flex-direction: row;
  align-items: center;
  padding-right: 16px;

  font-weight: 500;
  color: var(--font-color-main);
}

.category-header-icon {
  margin-right: 16px;
  color: var(--font-color-medium);
}

.script-list-category.has-selected .category-header-icon {
  color: var(--primary-color);
}

.category-name {
  flex: 1 1 auto;
  min-width: 0;

  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.category-count {
  flex: 0 0 auto;
  margin-left: 8px;

  font-size: 0.85em;
  font-weight: 400;
  color: var(--font-color-medium);
}

.expand-icon {
  flex: 0 0 auto;
  margin-left: 4px;
  line-height: 16px;
  color: var(--font-color-medium);
}

.script-list-category.expanded {
  border-bottom: 1px solid var(--separator-color);
}

.category-children >>> .script-list-group .collection-item.script-group {
  padding-left: 60px;
}

.category-children >>> .script-list-group .collection-item.script-list-item {
  padding-left: 76px;
}

.category-children > .collection-item.script-list-item {
  padding-left: 60px;
}
</style>
