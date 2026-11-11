'use strict';
import historyModule from '@/common/store/executions-module';
import {axiosInstance} from '@/common/utils/axios_utils';
import MockAdapter from 'axios-mock-adapter';
import Vuex from 'vuex';
import {createScriptServerTestVue, flushPromises} from '../test_utils';

const localVue = createScriptServerTestVue();
localVue.use(Vuex);

let axiosMock;
let requestParams;

function record(id, user = 'user' + id, script = 'script' + id) {
    return {id, startTime: null, user, script, status: 'finished', exitCode: 0};
}

function page(records, total, nextCursor) {
    return {records, total, nextCursor};
}

function mockPages(pagesByCursor) {
    axiosMock.onGet('history/execution_log/short').reply(config => {
        requestParams.push(config.params);
        const cursor = config.params.after;
        return [200, pagesByCursor[cursor === undefined ? 'FIRST' : cursor]];
    });
}

function mockDeferredPages() {
    const pendingResponses = [];

    axiosMock.onGet('history/execution_log/short').reply(config => {
        requestParams.push(config.params);
        return new Promise(resolve => pendingResponses.push(data => resolve([200, data])));
    });

    return pendingResponses;
}

function lastParams() {
    return requestParams[requestParams.length - 1];
}

describe('Test executions module', function () {
    let store;

    beforeEach(function () {
        store = new Vuex.Store({
            modules: {
                history: historyModule()
            }
        });

        axiosMock = new MockAdapter(axiosInstance);
        requestParams = [];
    });

    afterEach(function () {
        axiosMock.restore();
    });

    describe('Test first page', function () {

        it('test load first page', async function () {
            mockPages({FIRST: page([record('1'), record('2')], 5, 'cursor1')});

            await store.dispatch('history/init');
            await flushPromises();

            expect(lastParams()).toEqual({limit: 25, sort: 'startTime', order: 'desc'});
            expect(store.state.history.executions.map(e => e.id)).toEqual(['1', '2']);
            expect(store.state.history.total).toEqual(5);
            expect(store.state.history.hasNext).toBeTrue();
            expect(store.state.history.hasPrev).toBeFalse();
            expect(store.state.history.loading).toBeFalse();
        });

        it('test translate records', async function () {
            mockPages({FIRST: page([{id: '1', startTime: null, user: 'me', script: 's', status: 'error', exitCode: 3}], 1, null)});

            await store.dispatch('history/init');
            await flushPromises();

            expect(store.state.history.executions[0].fullStatus).toEqual('error (3)');
            expect(store.state.history.executions[0].startTimeString).toEqual('');
        });

        it('test no next page when cursor is null', async function () {
            mockPages({FIRST: page([record('1')], 1, null)});

            await store.dispatch('history/init');
            await flushPromises();

            expect(store.state.history.hasNext).toBeFalse();
        });

        it('test loading reset on failure', async function () {
            axiosMock.onGet('history/execution_log/short').reply(500);

            await store.dispatch('history/init');
            await flushPromises();

            expect(store.state.history.loading).toBeFalse();
            expect(store.state.history.executions).toEqual([]);
        });
    });

    describe('Test traversal', function () {

        beforeEach(async function () {
            mockPages({
                FIRST: page([record('1')], 3, 'cursor1'),
                cursor1: page([record('2')], 3, 'cursor2'),
                cursor2: page([record('3')], 3, null)
            });

            await store.dispatch('history/init');
            await flushPromises();
        });

        it('test next page sends cursor', async function () {
            await store.dispatch('history/nextPage');
            await flushPromises();

            expect(lastParams().after).toEqual('cursor1');
            expect(store.state.history.executions.map(e => e.id)).toEqual(['2']);
            expect(store.state.history.hasPrev).toBeTrue();
            expect(store.state.history.hasNext).toBeTrue();
        });

        it('test last page has no next', async function () {
            await store.dispatch('history/nextPage');
            await flushPromises();
            await store.dispatch('history/nextPage');
            await flushPromises();

            expect(store.state.history.executions.map(e => e.id)).toEqual(['3']);
            expect(store.state.history.hasNext).toBeFalse();
            expect(store.state.history.hasPrev).toBeTrue();
        });

        it('test prev page returns to first page', async function () {
            await store.dispatch('history/nextPage');
            await flushPromises();
            await store.dispatch('history/nextPage');
            await flushPromises();
            await store.dispatch('history/prevPage');
            await flushPromises();

            expect(lastParams().after).toEqual('cursor1');
            expect(store.state.history.executions.map(e => e.id)).toEqual(['2']);
            expect(store.state.history.hasPrev).toBeTrue();

            await store.dispatch('history/prevPage');
            await flushPromises();

            expect(lastParams().after).toBeUndefined();
            expect(store.state.history.executions.map(e => e.id)).toEqual(['1']);
            expect(store.state.history.hasPrev).toBeFalse();
        });

        it('test next page ignored on last page', async function () {
            await store.dispatch('history/nextPage');
            await flushPromises();
            await store.dispatch('history/nextPage');
            await flushPromises();

            const requestCount = requestParams.length;
            await store.dispatch('history/nextPage');
            await flushPromises();

            expect(requestParams.length).toEqual(requestCount);
        });

        it('test prev page ignored on first page', async function () {
            const requestCount = requestParams.length;

            await store.dispatch('history/prevPage');
            await flushPromises();

            expect(requestParams.length).toEqual(requestCount);
        });
    });

    describe('Test reset to first page', function () {

        beforeEach(async function () {
            mockPages({
                FIRST: page([record('1')], 3, 'cursor1'),
                cursor1: page([record('2')], 3, 'cursor2')
            });

            await store.dispatch('history/init');
            await flushPromises();
            await store.dispatch('history/nextPage');
            await flushPromises();
        });

        it('test search resets to first page', async function () {
            await store.dispatch('history/setSearch', 'abc');
            await flushPromises();

            expect(lastParams()).toEqual({limit: 25, sort: 'startTime', order: 'desc', search: 'abc'});
            expect(store.state.history.searchText).toEqual('abc');
            expect(store.state.history.hasPrev).toBeFalse();
        });

        it('test blank search is not sent', async function () {
            await store.dispatch('history/setSearch', '   ');
            await flushPromises();

            expect(lastParams().search).toBeUndefined();
        });

        it('test sort resets to first page', async function () {
            await store.dispatch('history/setSort', {column: 'user', order: 'asc'});
            await flushPromises();

            expect(lastParams()).toEqual({limit: 25, sort: 'user', order: 'asc'});
            expect(store.state.history.hasPrev).toBeFalse();
        });

        it('test page size resets to first page', async function () {
            await store.dispatch('history/setPageSize', 100);
            await flushPromises();

            expect(lastParams()).toEqual({limit: 100, sort: 'startTime', order: 'desc'});
            expect(store.state.history.pageSize).toEqual(100);
            expect(store.state.history.hasPrev).toBeFalse();
        });
    });

    describe('Test out of order responses', function () {

        it('test stale response does not overwrite newer state', async function () {
            const pendingResponses = mockDeferredPages();

            store.dispatch('history/init');
            await flushPromises();
            store.dispatch('history/setSearch', 'newer');
            await flushPromises();

            expect(pendingResponses.length).toEqual(2);

            pendingResponses[1](page([record('newer')], 1, null));
            await flushPromises();
            pendingResponses[0](page([record('stale')], 99, 'staleCursor'));
            await flushPromises();

            expect(store.state.history.executions.map(e => e.id)).toEqual(['newer']);
            expect(store.state.history.total).toEqual(1);
            expect(store.state.history.hasNext).toBeFalse();
            expect(store.state.history.loading).toBeFalse();
        });
    });
});
