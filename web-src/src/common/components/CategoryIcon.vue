<template>
  <!-- conf/categories.json icons: a Material Icons ligature name renders with the bundled icon
       font; any other value ("£", an emoji) renders as text in the same fixed 24x24 box, so both
       kinds line up identically. The fixed, clipped box also stops a mistyped ligature name from
       blowing out the row width (see CLAUDE.md's invalid-icon-name note). -->
  <i v-if="ligature" :title="title" class="material-icons category-icon">{{ icon }}</i>
  <span v-else :title="title" class="category-icon category-icon-text">{{ icon }}</span>
</template>

<script>
import {isLigatureIcon} from '@/main-app/utils/categories';

export default {
  name: 'CategoryIcon',
  props: {
    icon: {
      type: String,
      required: true
    },
    title: {
      type: String,
      default: null
    }
  },
  computed: {
    ligature() {
      return isLigatureIcon(this.icon);
    }
  }
}
</script>

<style scoped>
.category-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  overflow: hidden;
  white-space: nowrap;

  font-size: 24px;
  line-height: 24px;
}

.category-icon-text {
  font-family: "Roboto", sans-serif;
  font-size: 20px;
  font-weight: 500;
}
</style>
