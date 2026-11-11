<template>
  <!-- CHANGELOG.md from the server (GET /changelog), rendered as markdown -->
  <div class="changelog-panel">
    <p v-if="error" class="changelog-error">{{ error }}</p>
    <article v-else class="changelog-content" v-html="html"></article>
  </div>
</template>

<script>
import {axiosInstance} from '@/common/utils/axios_utils';
import DOMPurify from 'dompurify';
import get from 'lodash/get';
import {marked} from 'marked';

export default {
  name: 'ChangelogPanel',

  data() {
    return {
      html: '',
      error: null
    }
  },

  mounted() {
    axiosInstance.get('changelog', {responseType: 'text'})
        .then(({data}) => {
          const html = DOMPurify.sanitize(marked.parse(data, {gfm: true}));
          // Links in the changelog (e.g. upstream) open in a new tab, not inside the app
          const container = document.createElement('div');
          container.innerHTML = html;
          container.querySelectorAll('a[href^="http"]').forEach(link => {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener');
          });
          this.html = container.innerHTML;
        })
        .catch(e => {
          this.error = (get(e, 'response.status') === 404)
              ? 'No changelog is available on this server.'
              : 'Failed to load the changelog: ' + get(e, 'message', String(e));
        });
  }
}
</script>

<style scoped>
.changelog-panel {
  height: 100%;
  overflow-y: auto;
  padding: 16px 24px 32px;
  background: var(--background-color);
  color: var(--font-color-main);
}

.changelog-content {
  max-width: 50em;
  line-height: 1.5;
}

.changelog-content >>> h1 {
  display: none; /* the page header already says "What's new" */
}

.changelog-content >>> h2 {
  margin: 1.6em 0 0.4em;
  padding-bottom: 0.3em;
  border-bottom: 1px solid var(--separator-color);

  font-size: 1.5rem;
  font-weight: 400;
  color: var(--primary-color);
}

.changelog-content >>> h2:first-of-type {
  margin-top: 0.6em;
}

.changelog-content >>> h3 {
  margin: 1.2em 0 0.3em;
  font-size: 1.1rem;
  font-weight: 500;
}

.changelog-content >>> p {
  margin: 0.5em 0;
}

.changelog-content >>> ul {
  margin: 0.3em 0 0.8em;
  padding-left: 1.4em;
}

.changelog-content >>> ul li {
  list-style-type: disc;
  margin: 0.25em 0;
}

.changelog-content >>> code {
  padding: 0.1em 0.35em;
  border-radius: 3px;
  background: var(--background-color-high-emphasis);
  font-size: 0.9em;
}

.changelog-content >>> a {
  color: var(--primary-color);
}

.changelog-error {
  color: var(--font-color-medium);
}
</style>
