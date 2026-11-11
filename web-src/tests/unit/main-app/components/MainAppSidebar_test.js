'use strict';
import {mount} from '@vue/test-utils';
import Vuex from 'vuex';
import VueRouter from 'vue-router';
import MainAppSidebar from '@/main-app/components/MainAppSidebar';
import {attachToDocument, createScriptServerTestVue, vueTicks} from '../../test_utils';
import router from '@/main-app/router/router';
import {buildCategoryTree} from '@/main-app/utils/categories';

const localVue = createScriptServerTestVue();
localVue.use(Vuex);
localVue.use(VueRouter);

describe('Test MainAppSidebar', function () {
    let sidebar;
    let store;

    beforeEach(async function () {
        store = new Vuex.Store({
            modules: {
                serverConfig: {
                    namespaced: true,
                    state: {
                        serverName: 'Custom name',
                        version: null
                    }
                },
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

        sidebar = mount(MainAppSidebar, {
            attachTo: attachToDocument(),
            store,
            localVue,
            router
        });

        sidebar.vm.$parent.$forceUpdate();
        await sidebar.vm.$nextTick();
    });

    afterEach(function () {
        sidebar.destroy();
    });

    describe('Test title', function () {

        it('test title from config', async function () {
            const header = sidebar.find('.server-header');

            expect(header.text()).toBe('Custom name');
        });

        it('test change title in config', async function () {
            store.state.serverConfig.serverName = 'Another name';
            await vueTicks();

            const header = sidebar.find('.server-header');

            expect(header.text()).toBe('Another name');
        });

        it('test default title when missing', async function () {
            store.state.serverConfig.serverName = null;
            await vueTicks();

            const header = sidebar.find('.server-header');

            expect(header.text()).toBe('Script server');
        });

        it('test long title', async function () {
            store.state.serverConfig.serverName = 'Some very very long title';
            await vueTicks();

            const header = sidebar.find('.server-header');

            expect(header.classes()).toContain('header-gt-21-chars');
        });
    });


    // v2.0.0: which category/group is open lives here (it survives collapsing to the rail)
    describe('Test category tree state', function () {
        const SCRIPTS = [
            {name: 'abc', category: 'Music', group: 'g3'},
            {name: 'def', category: 'Music', group: 'g2'},
            {name: 'xyz', category: 'Music', group: 'g2'},
            {name: 'loose'}];

        async function setScripts() {
            store.state.scripts.categories = [{name: 'Music', icon: 'music_note'}];
            store.state.scripts.scripts = SCRIPTS;
            await vueTicks();
        }

        function openCategoryNames() {
            return sidebar.findAll('.script-list-category.expanded .category-name').wrappers.map(w => w.text());
        }

        function openGroupScripts() {
            return sidebar.findAll('.script-list-group.active .script-list-item .script-name').wrappers.map(w => w.text());
        }

        async function clickCategory(name) {
            const header = sidebar.findAll('.category-header').wrappers.find(w => w.find('.category-name').text() === name);
            await header.trigger('click');
            await vueTicks();
        }

        async function clickGroup(name) {
            const header = sidebar.findAll('.script-group').wrappers.find(w => w.find('span').text() === name);
            await header.trigger('click');
            await vueTicks();
        }

        it('Test nothing open by default', async function () {
            await setScripts();

            expect(openCategoryNames()).toEqual([]);
        });

        it('Test open by default when selected', async function () {
            await setScripts();
            store.state.scripts.selectedScript = 'abc';
            await vueTicks();

            expect(openCategoryNames()).toEqual(['Music']);
            expect(openGroupScripts()).toEqual(['abc']);
        });

        it('Test single category opens automatically', async function () {
            store.state.scripts.scripts = [{name: 'a'}, {name: 'b'}];
            await vueTicks();

            expect(openCategoryNames()).toEqual(['Uncategorised']);
        });

        it('Test open on click', async function () {
            await setScripts();
            await clickCategory('Music');
            await clickGroup('g2');

            expect(openCategoryNames()).toEqual(['Music']);
            expect(openGroupScripts()).toEqual(['def', 'xyz']);
        });

        it('Test open another group on click', async function () {
            await setScripts();
            await clickCategory('Music');
            await clickGroup('g2');
            await clickGroup('g3');

            expect(openGroupScripts()).toEqual(['abc']);
        });

        it('Test close group on second click', async function () {
            await setScripts();
            await clickCategory('Music');
            await clickGroup('g2');
            await clickGroup('g2');

            expect(openGroupScripts()).toEqual([]);
        });

        it('Test open another category closes the first', async function () {
            await setScripts();
            await clickCategory('Music');
            await clickCategory('Uncategorised');

            expect(openCategoryNames()).toEqual(['Uncategorised']);
        });

        it('Test rail shows one icon per category and opens it', async function () {
            await setScripts();
            await sidebar.setProps({railCollapsed: true});
            await vueTicks();

            const icons = sidebar.findAll('.rail-category-button');
            expect(icons.wrappers.map(w => w.attributes('title'))).toEqual(['Music', 'Uncategorised']);

            await icons.at(1).trigger('click');
            expect(sidebar.emitted('toggle-expand')).toBeArrayOfSize(1);

            await sidebar.setProps({railCollapsed: false});
            await vueTicks();
            expect(openCategoryNames()).toEqual(['Uncategorised']);
        });
    });

    describe('Test version', function () {
        it('Test version and whats new link', async function () {
            store.state.serverConfig.version = '2.0.0';
            await vueTicks();

            const panel = sidebar.find('.version-panel');
            expect(panel.find('.version-number').text()).toBe('v2.0.0');
            expect(panel.find('.whats-new').text()).toBe("What's new");
            expect(panel.attributes('href')).toContain('changelog');
        });
    });
});
