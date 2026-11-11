/*
 * A second, self-contained Vuex store that lets admin.html RUN scripts - the Settings tabs for
 * placement=settings runners (Import from Gitea, Install Package, Secrets Manager...).
 *
 * The script form, preload banner, live output, execution tabs and scheduling all come straight
 * from the main app's components (MainAppContent/ScriptView/ScriptHeader), which talk to the store
 * through fixed module names: scripts, scriptConfig, scriptSetup, executions, auth, page... The
 * admin app's own store already uses 'scripts' and 'scriptConfig' for the config editor with a
 * different shape, so instead of renaming either side the settings page gets this store via the
 * component-level `store:` option (see SettingsScriptPage.vue) - Vuex injects it for that subtree
 * only, everything else in admin.html keeps the admin store.
 *
 * Everything below is reused unchanged from src/main-app/store, except 'scripts': the main app's
 * version is driven by the main app's router (#/<script name>), so this one is a small stand-in
 * fed by admin.html's own /settings/:scriptName route and GET scripts?mode=settings.
 */
import historyModule from '@/common/store/executions-module';
import authModule from '@/common/store/auth';
import {axiosInstance} from '@/common/utils/axios_utils';
import {isNull, logError} from '@/common/utils/common';
import pageModule from '@/main-app/store/page';
import scheduleModule from '@/main-app/store/scriptSchedule';
import scriptConfigModule from '@/main-app/store/scriptConfig';
import scriptExecutionManagerModule from '@/main-app/store/scriptExecutionManager';
import scriptSetupModule from '@/main-app/store/scriptSetup';
import serverConfigModule from '@/main-app/store/serverConfig';
import cloneDeep from 'lodash/cloneDeep';
import get from 'lodash/get';
import Vue from 'vue';
import Vuex from 'vuex';

Vue.use(Vuex);

// Modules declared with a plain `state: {...}` object share that object with every store that
// registers them. admin.html has two stores (this one and AdminApp's), both with 'auth' - give
// each module registered here its own copy.
function isolated(module) {
    const state = module.state;
    if (isNull(state) || (typeof state === 'function')) {
        return module;
    }
    const initialState = cloneDeep(state);
    return {...module, state: () => cloneDeep(initialState)};
}

const settingsScriptsModule = {
    namespaced: true,

    state: {
        scripts: [],
        loaded: false,
        loadError: null,
        selectedScript: null,
        predefinedParameters: null
    },

    actions: {
        init({commit}) {
            return axiosInstance.get('scripts', {params: {mode: 'settings'}})
                .then(({data}) => {
                    const scripts = data.scripts || [];
                    scripts.sort((s1, s2) => s1.name.toLowerCase().localeCompare(s2.name.toLowerCase()));
                    commit('SET_SCRIPTS', scripts);
                })
                .catch(e => {
                    logError(e);
                    commit('SET_LOAD_ERROR', get(e, 'message', String(e)));
                });
        },

        selectScript({state, commit}, scriptName) {
            if (state.selectedScript !== scriptName) {
                commit('SELECT_SCRIPT', scriptName);
            }
        }
    },

    mutations: {
        SET_SCRIPTS(state, scripts) {
            state.scripts = scripts;
            state.loaded = true;
            state.loadError = null;
        },

        SET_LOAD_ERROR(state, error) {
            state.loaded = true;
            state.loadError = error;
        },

        SELECT_SCRIPT(state, scriptName) {
            state.selectedScript = scriptName;
            state.predefinedParameters = null;
        }
    }
};

const store = new Vuex.Store({
    modules: {
        scripts: settingsScriptsModule,
        serverConfig: isolated(serverConfigModule),
        scriptConfig: scriptConfigModule(),
        scriptSetup: isolated(scriptSetupModule),
        executions: isolated(scriptExecutionManagerModule),
        auth: isolated(authModule),
        history: historyModule(),
        page: isolated(pageModule),
        scriptSchedule: isolated(scheduleModule)
    },

    actions: {
        init({dispatch}) {
            dispatch('auth/init');
            dispatch('serverConfig/init');
            dispatch('executions/init');
            return dispatch('scripts/init');
        },

        // Same as the main app's root action - ExecutionInstanceTabs dispatches it
        resetScript({dispatch, state}) {
            const selectedScript = state.scripts.selectedScript;

            dispatch('scriptSetup/reset');
            dispatch('scriptConfig/reloadScript', {selectedScript});
        }
    }
});

// The same wiring the main app's store/index.js sets up between its modules
store.watch((state) => state.scripts.selectedScript, (selectedScript) => {
    store.dispatch('resetScript');
    store.dispatch('executions/selectScript', {selectedScript});
});

store.watch((state) => state.scriptConfig.parameters, (parameters) => {
    const scriptConfig = store.state.scriptConfig.scriptConfig;
    const scriptName = scriptConfig ? scriptConfig.name : null;
    store.dispatch('scriptSetup/initFromParameters', {scriptName, parameters, scriptConfig});
});

axiosInstance.interceptors.response.use((response) => response, (error) => {
    if (get(error, 'response.status') === 401) {
        store.dispatch('auth/setAuthenticated', false);
    }
    throw error;
});

window.addEventListener('beforeunload', function (e) {
    if (store.getters['executions/hasActiveExecutors']) {
        // in modern browsers the message will be replaced with default one (security reasons)
        const message = 'Closing the page will stop all running scripts. Are you sure?';
        (e || window.event).returnValue = message;
        return message;
    }
});

export default store;
