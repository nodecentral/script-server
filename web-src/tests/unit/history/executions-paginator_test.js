'use strict';
import ExecutionsPaginator from '@/common/components/history/executions-paginator'
import historyModule from '@/common/store/executions-module';
import {mount} from '@vue/test-utils';
import Vuex from 'vuex';
import {attachToDocument, createScriptServerTestVue, vueTicks} from '../test_utils';

const localVue = createScriptServerTestVue();
localVue.use(Vuex);

function records(count) {
    const result = [];
    for (let i = 0; i < count; i++) {
        result.push({id: String(i)});
    }
    return result;
}

describe('Test executions paginator', function () {
    let paginator;
    let store;

    beforeEach(async function () {
        store = new Vuex.Store({
            modules: {
                history: historyModule()
            }
        });

        paginator = mount(ExecutionsPaginator, {
            attachTo: attachToDocument(),
            store,
            localVue
        });

        await vueTicks();
    });

    afterEach(function () {
        paginator.destroy();
    });

    async function setPageState({executions = [], total = 0, pageSize = 25, cursorStack = [], hasNext = false, hasPrev = false, loading = false}) {
        const state = store.state.history;
        state.executions = executions;
        state.total = total;
        state.pageSize = pageSize;
        state.cursorStack = cursorStack;
        state.hasNext = hasNext;
        state.hasPrev = hasPrev;
        state.loading = loading;

        await vueTicks();
    }

    function rangeLabel() {
        return paginator.find('.range-label').text();
    }

    function prevButton() {
        return paginator.find('.prev-button').element;
    }

    function nextButton() {
        return paginator.find('.next-button').element;
    }

    describe('Test range label', function () {

        it('test first page range', async function () {
            await setPageState({executions: records(25), total: 348});

            expect(rangeLabel()).toEqual('1-25 of 348');
        });

        it('test second page range', async function () {
            await setPageState({executions: records(25), total: 348, cursorStack: ['cursor1']});

            expect(rangeLabel()).toEqual('26-50 of 348');
        });

        it('test partial last page range', async function () {
            await setPageState({executions: records(23), total: 348, cursorStack: ['cursor1', 'cursor2']});

            expect(rangeLabel()).toEqual('51-73 of 348');
        });

        it('test custom page size range', async function () {
            await setPageState({executions: records(10), total: 348, pageSize: 10, cursorStack: ['cursor1']});

            expect(rangeLabel()).toEqual('11-20 of 348');
        });

        it('test empty range', async function () {
            await setPageState({executions: [], total: 0});

            expect(rangeLabel()).toEqual('0 of 0');
        });
    });

    describe('Test button states', function () {

        it('test both disabled on single page', async function () {
            await setPageState({executions: records(3), total: 3});

            expect(prevButton().disabled).toBeTrue();
            expect(nextButton().disabled).toBeTrue();
        });

        it('test next enabled when more pages', async function () {
            await setPageState({executions: records(25), total: 100, hasNext: true});

            expect(prevButton().disabled).toBeTrue();
            expect(nextButton().disabled).toBeFalse();
        });

        it('test prev enabled on later page', async function () {
            await setPageState({executions: records(25), total: 100, cursorStack: ['cursor1'], hasPrev: true, hasNext: true});

            expect(prevButton().disabled).toBeFalse();
            expect(nextButton().disabled).toBeFalse();
        });

        it('test both disabled while loading', async function () {
            await setPageState({
                executions: records(25), total: 100, cursorStack: ['cursor1'],
                hasPrev: true, hasNext: true, loading: true
            });

            expect(prevButton().disabled).toBeTrue();
            expect(nextButton().disabled).toBeTrue();
        });
    });

    describe('Test page size select', function () {

        it('test options', async function () {
            const options = paginator.findAll('.page-size-select option').wrappers.map(w => w.text());

            expect(options).toEqual(['10', '25', '50', '100', '250', '500']);
        });

        it('test select disabled while loading', async function () {
            await setPageState({loading: true});

            expect(paginator.find('.page-size-select').element.disabled).toBeTrue();
        });
    });
});
