'use strict';

import GiteaUpdateButton from '@/main-app/components/scripts/GiteaUpdateButton';
import {axiosInstance} from '@/common/utils/axios_utils';
import {mount} from '@vue/test-utils';
import MockAdapter from 'axios-mock-adapter';
import Vuex from 'vuex';
import {attachToDocument, createScriptServerTestVue, flushPromises, vueTicks} from '../../../test_utils';

const localVue = createScriptServerTestVue();
localVue.use(Vuex);

const ORIGIN = {
    type: 'gitea', url: 'http://gitea', owner: 'me', repo: 'demo', branch: 'main',
    commit: 'abc1234', commitTime: '2026-11-11T14:02:00+00:00', importedAt: '2026-11-11T14:05:00+00:00',
    updater: 'Import from Gitea',
    updateParameters: {manual_repo: 'me/demo', branch: 'main', token_key: 'auto', apply: true}
};

describe('Test GiteaUpdateButton', function () {
    let axiosMock;
    let store;
    let button;
    let resetScriptCalls;
    let toasts;
    let originalToast;

    beforeEach(function () {
        axiosMock = new MockAdapter(axiosInstance);
        resetScriptCalls = 0;
        toasts = [];
        originalToast = M.toast;
        M.toast = options => toasts.push(options.html);

        store = new Vuex.Store({
            modules: {
                scripts: {namespaced: true, state: {selectedScript: null}},
                auth: {namespaced: true, state: {admin: true}}
            },
            actions: {
                resetScript() {
                    resetScriptCalls++;
                }
            }
        });
    });

    afterEach(function () {
        M.toast = originalToast;
        axiosMock.restore();
        if (button) {
            button.destroy();
        }
    });

    async function mountFor(scriptName) {
        store.state.scripts.selectedScript = scriptName;
        button = mount(GiteaUpdateButton, {store, localVue, attachTo: attachToDocument()});
        await flushPromises();
        await vueTicks();
    }

    it('Test hidden when script has no origin', async function () {
        axiosMock.onGet('admin/scripts/Local%20Script/origin').reply(200, {origin: null});

        await mountFor('Local Script');

        expect(button.find('button').exists()).toBeFalse();
    });

    it('Test hidden for non-admins without asking the server', async function () {
        store.state.auth.admin = false;

        await mountFor('Demo Hello');

        expect(button.find('button').exists()).toBeFalse();
        expect(axiosMock.history.get).toBeArrayOfSize(0);
    });

    it('Test shown with origin details', async function () {
        axiosMock.onGet('admin/scripts/Demo%20Hello/origin').reply(200, {origin: ORIGIN});

        await mountFor('Demo Hello');

        const element = button.find('button');
        expect(element.exists()).toBeTrue();
        expect(element.attributes('title')).toContain('me/demo @ main');
        expect(element.attributes('title')).toContain('commit abc1234');
    });

    it('Test one-tap update runs the import with apply and reloads the script', async function () {
        axiosMock.onGet('admin/scripts/Demo%20Hello/origin').reply(200, {origin: ORIGIN});
        axiosMock.onPost('executions/start').reply(200, '42');
        axiosMock.onGet('executions/status/42').reply(200, 'finished');
        axiosMock.onGet('history/execution_log/long/42').reply(200, {
            exitCode: 0, log: 'cloning...\nSUMMARY: me/demo @ def5678 (11 Nov 2026 15:00): 2 updated\n'
        });
        axiosMock.onPost('executions/cleanup/42').reply(200);

        await mountFor('Demo Hello');
        await button.vm.update();

        const startRequest = axiosMock.history.post.find(r => r.url === 'executions/start');
        const sent = Object.fromEntries(startRequest.data.entries());
        expect(sent).toEqual({
            manual_repo: 'me/demo', branch: 'main', token_key: 'auto', apply: 'true',
            __script_name: 'Import from Gitea'
        });
        expect(axiosMock.history.post.map(r => r.url)).toContain('executions/cleanup/42');
        expect(toasts[0]).toContain('me/demo @ def5678');
        expect(toasts[0]).toContain('2 updated');
        expect(resetScriptCalls).toBe(1);
        expect(button.vm.updating).toBeFalse();
    });

    it('Test failed update shows the error and a log link', async function () {
        axiosMock.onGet('admin/scripts/Demo%20Hello/origin').reply(200, {origin: ORIGIN});
        axiosMock.onPost('executions/start').reply(200, '43');
        axiosMock.onGet('executions/status/43').reply(200, 'finished');
        axiosMock.onGet('history/execution_log/long/43').reply(200, {
            exitCode: 1, log: 'Cloning...\nfatal: repository not found\nClone failed <check>\n'
        });
        axiosMock.onPost('executions/cleanup/43').reply(200);

        await mountFor('Demo Hello');
        await button.vm.update();

        expect(toasts[0]).toContain('Update from Gitea failed');
        expect(toasts[0]).toContain('Clone failed &lt;check&gt;');
        expect(toasts[0]).toContain('admin.html#/logs/43');
    });
});
