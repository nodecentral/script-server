<template>
  <div ref="scriptList" class="scripts-list collection">
    <template v-if="searching">
      <ScriptListItem v-for="result in searchResults" :key="result.script.name"
                      :breadcrumb="result.breadcrumb" :script="result.script"/>
      <div v-if="searchResults.length === 0" class="no-search-results">No matching scripts</div>
    </template>

    <template v-else>
      <ScriptListCategory v-for="category in categoryTree" :key="category.key"
                          :active-group="activeGroup"
                          :category="category"
                          :expanded="category.key === activeCategory"
                          @category-clicked="$emit('category-clicked', $event)"
                          @group-clicked="$emit('group-clicked', $event)"/>
    </template>
  </div>
</template>

<script>
import {isBlankString} from '@/common/utils/common';
import {mapGetters} from 'vuex';
import ScriptListCategory from './ScriptListCategory';
import ScriptListItem from './ScriptListItem';

/*
 * Category > Group > Script tree (see utils/categories.js for the ordering rules). Which category
 * and group are expanded is owned by MainAppSidebar, not here: the sidebar stays alive while it's
 * collapsed to the slim rail (this list doesn't), and the rail's category icons need to open a
 * specific category when the sidebar expands.
 */
export default {
  name: 'ScriptsList',
  components: {ScriptListCategory, ScriptListItem},
  props: {
    searchText: {
      type: String,
      default: null
    },
    activeCategory: {
      type: String,
      default: null
    },
    activeGroup: {
      type: String,
      default: null
    }
  },

  computed: {
    ...mapGetters('scripts', ['categoryTree']),

    searching() {
      return !isBlankString(this.searchText);
    },

    // Search covers every category at once and shows where each match lives
    searchResults() {
      const search = this.searchText.trim().toLowerCase();
      const showCategory = this.categoryTree.length > 1;

      const results = [];
      for (const category of this.categoryTree) {
        const prefix = showCategory ? [category.name] : [];

        for (const group of category.groups) {
          for (const script of group.scripts) {
            results.push({script, breadcrumb: prefix.concat([group.name]).join(' › ')});
          }
        }
        for (const script of category.scripts) {
          results.push({script, breadcrumb: prefix.join(' › ')});
        }
      }

      return results.filter(result => result.script.name.toLowerCase().includes(search));
    }
  }
}
</script>

<style scoped>
.scripts-list {
  overflow: auto;
  overflow-wrap: normal;
  border: none;
  margin: 0;

  flex-grow: 1;
}

.no-search-results {
  padding: 10px 20px;
  color: var(--font-color-medium);
}
</style>
