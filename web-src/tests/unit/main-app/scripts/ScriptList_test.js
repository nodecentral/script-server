'use strict';

import ScriptsList from '@/main-app/components/scripts/ScriptsList';
import {buildCategoryTree} from '@/main-app/utils/categories';
import router from '@/main-app/router/router';
import {mount} from '@vue/test-utils';
import VueRouter from 'vue-router';
import Vuex from 'vuex';
import {attachToDocument, createScriptServerTestVue, triggerSingleClick, vueTicks} from '../../test_utils';

const localVue = createScriptServerTestVue();
localVue.use(Vuex);
localVue.use(VueRouter);

// v2.0.0: Category > Group > Script. Which category/group is open is owned by MainAppSidebar
// (see MainAppSidebar_test.js) and passed in as props, so here those are set directly.
describe('Test ScriptConfig', function () {
    let store;
    let listComponent;

    beforeEach(async function () {
        store = new Vuex.Store({
            modules: {
                scripts: {
                    namespaced: true,
                    state: {
                        scripts: [],
                        categories: [],
                        uncategorised: {name: 'Uncategorised', icon: 'label_outline'},
                        selectedScript: null
                    },
                    getters: {
                        categoryTree: state => buildCategoryTree(state.scripts, state.categories, state.uncategorised)
                    }
                },
                executions: {
                    executors: {}
                }
            }
        });

        listComponent = mount(ScriptsList, {
            store,
            localVue,
            router,
            attachTo: attachToDocument()
        });

        await vueTicks();
    });

    afterEach(async function () {
        await vueTicks();

        listComponent.destroy();
    });

    function categoryNames() {
        return $(listComponent.vm.$el).find('.category-header .category-name').toArray().map(e => e.textContent.trim());
    }

    function categoryKey(name) {
        return listComponent.vm.categoryTree.find(c => c.name === name).key;
    }

    function groupKey(categoryName, groupName) {
        return listComponent.vm.categoryTree.find(c => c.name === categoryName)
            .groups.find(g => g.name === groupName).key;
    }

    // Visible rows inside the open category, in order: "[group] name" for group headers, plain name for scripts
    function openRows() {
        return $(listComponent.vm.$el).find('.category-children .collection-item').toArray().map(item => {
            if ($(item).hasClass('script-group')) {
                return '[group] ' + $(item).find('span').first().text().trim();
            }
            return $(item).find('.script-name').text().trim();
        });
    }

    async function setScripts(scripts, categories = []) {
        store.state.scripts.categories = categories;
        store.state.scripts.scripts = scripts;
        await vueTicks();
    }

    async function open(category, group = null) {
        await listComponent.setProps({activeCategory: category, activeGroup: group});
        await vueTicks();
    }

    describe('Test show list', function () {
        it('Test show single item', async function () {
            await setScripts([{'name': 'abc'}]);

            expect(categoryNames()).toEqual(['Uncategorised']);
            expect(openRows()).toEqual([]);

            await open(categoryKey('Uncategorised'));
            expect(openRows()).toEqual(['abc']);
        });

        it('Test show multiple items', async function () {
            await setScripts([{'name': 'abc'}, {'name': 'xyz'}, {'name': 'def'}]);
            await open(categoryKey('Uncategorised'));

            expect(openRows()).toEqual(['abc', 'def', 'xyz']);
        });

        it('Test show categories in configured order, Uncategorised last', async function () {
            await setScripts([
                    {'name': 'loose'},
                    {'name': 'tags', 'category': 'Music'},
                    {'name': 'budget', 'category': 'Finance'}],
                [{name: 'Finance', icon: '£'}, {name: 'Photos', icon: 'photo_library'}, {name: 'Music', icon: 'music_note'}]);

            expect(categoryNames()).toEqual(['Finance', 'Music', 'Uncategorised']);
        });

        it('Test groups before ungrouped scripts', async function () {
            await setScripts([
                {'name': 'abc', 'group': 'g3'},
                {'name': 'ghi'},
                {'name': 'xyz', 'group': 'g2'},
                {'name': 'jkl', 'group': 'g2'},
                {'name': 'def'}]);
            await open(categoryKey('Uncategorised'));

            expect(openRows()).toEqual(['[group] g2', '[group] g3', 'def', 'ghi']);
        });

        it('Test show multiple items in different groups when empty', async function () {
            await setScripts([
                {'name': 'abc', 'group': null},
                {'name': 'xyz', 'group': ''},
                {'name': 'def', 'group': ' \n'}]);
            await open(categoryKey('Uncategorised'));

            expect(openRows()).toEqual(['abc', 'def', 'xyz']);
        });

        it('Test open group shows its scripts sorted', async function () {
            await setScripts([
                {'name': 'xyz', 'group': 'g2', 'category': 'Music'},
                {'name': 'def', 'group': 'g2', 'category': 'Music'},
                {'name': 'abc', 'group': 'g1', 'category': 'Music'}], [{name: 'Music'}]);
            await open(categoryKey('Music'), groupKey('Music', 'g2'));

            expect(openRows()).toEqual(['[group] g1', '[group] g2', 'def', 'xyz']);
        });

        it('Test category script count', async function () {
            await setScripts([{'name': 'a', 'category': 'Music'}, {'name': 'b', 'category': 'Music', 'group': 'x'}],
                [{name: 'Music'}]);

            expect($(listComponent.vm.$el).find('.category-count').text().trim()).toBe('2');
        });
    });

    describe('Test clicks', function () {
        it('Test click on category emits its key', async function () {
            await setScripts([{'name': 'a', 'category': 'Music'}], [{name: 'Music'}]);

            triggerSingleClick($(listComponent.vm.$el).find('.category-header').get(0));
            await vueTicks();

            expect(listComponent.emitted('category-clicked')[0]).toEqual([categoryKey('Music')]);
        });

        it('Test click on group emits its key', async function () {
            await setScripts([{'name': 'a', 'category': 'Music', 'group': 'Library'}], [{name: 'Music'}]);
            await open(categoryKey('Music'));

            triggerSingleClick($(listComponent.vm.$el).find('.script-group').get(0));
            await vueTicks();

            expect(listComponent.emitted('group-clicked')[0]).toEqual([groupKey('Music', 'Library')]);
        });
    });

    describe('Test search', function () {
        it('Test search spans categories with breadcrumbs', async function () {
            await setScripts([
                {'name': 'Portfolio Report', 'category': 'Finance', 'group': 'Portfolio'},
                {'name': 'Report Albums', 'category': 'Music'},
                {'name': 'Other'}], [{name: 'Finance'}, {name: 'Music'}]);

            await listComponent.setProps({searchText: 'report'});
            await vueTicks();

            const items = $(listComponent.vm.$el).find('.collection-item').toArray();
            expect(items.map(i => $(i).find('.script-name').text().trim())).toEqual(['Portfolio Report', 'Report Albums']);
            expect(items.map(i => $(i).find('.script-breadcrumb').text().trim())).toEqual(['Finance › Portfolio', 'Music']);
        });

        it('Test search with no match', async function () {
            await setScripts([{'name': 'abc'}]);

            await listComponent.setProps({searchText: 'zzz'});
            await vueTicks();

            expect($(listComponent.vm.$el).find('.no-search-results').text().trim()).toBe('No matching scripts');
        });
    });
});
