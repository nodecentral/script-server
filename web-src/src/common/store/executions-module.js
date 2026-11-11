import {isBlankString, isEmptyString, isNull, logError} from '@/common/utils/common';
import {axiosInstance} from '@/common/utils/axios_utils';

export const DEFAULT_PAGE_SIZE = 25;
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250, 500];
export const DEFAULT_SORT_COLUMN = 'startTime';
export const DEFAULT_ORDER = 'desc';

const store = () => ({
    state: {
        executions: [],
        selectedExecution: null,
        selectedExecutionId: null,
        loading: false,
        detailsLoading: false,
        pageSize: DEFAULT_PAGE_SIZE,
        total: 0,
        searchText: '',
        sortColumn: DEFAULT_SORT_COLUMN,
        order: DEFAULT_ORDER,
        hasNext: false,
        hasPrev: false,
        // cursors of the pages visited before the current one; its length is also the current page index
        cursorStack: [],
        currentCursor: null,
        nextCursor: null,
        // incremented per request, so that a late response of an outdated request is dropped
        requestToken: 0
    },
    namespaced: true,
    actions: {
        init({commit, dispatch}) {
            commit('SET_EXECUTION_DETAILS', {execution: null, id: null});

            return dispatch('loadFirstPage');
        },

        loadFirstPage({dispatch}) {
            return dispatch('loadPage', {cursor: null, cursorStack: []});
        },

        reload({dispatch}) {
            return dispatch('loadFirstPage');
        },

        nextPage({dispatch, state}) {
            if (!state.hasNext) {
                return Promise.resolve();
            }

            return dispatch('loadPage', {
                cursor: state.nextCursor,
                cursorStack: [...state.cursorStack, state.currentCursor]
            });
        },

        prevPage({dispatch, state}) {
            if (!state.hasPrev) {
                return Promise.resolve();
            }

            const cursorStack = [...state.cursorStack];
            const cursor = cursorStack.pop();

            return dispatch('loadPage', {cursor, cursorStack});
        },

        setPageSize({commit, dispatch}, pageSize) {
            commit('SET_PAGE_SIZE', pageSize);

            return dispatch('loadFirstPage');
        },

        setSearch({commit, dispatch}, searchText) {
            commit('SET_SEARCH_TEXT', isNull(searchText) ? '' : searchText);

            return dispatch('loadFirstPage');
        },

        setSort({commit, dispatch}, {column, order}) {
            commit('SET_SORT', {column, order});

            return dispatch('loadFirstPage');
        },

        loadPage({commit, state}, {cursor, cursorStack}) {
            const requestToken = state.requestToken + 1;
            commit('SET_REQUEST_TOKEN', requestToken);
            commit('SET_LOADING', true);

            const params = {
                limit: state.pageSize,
                sort: state.sortColumn,
                order: state.order
            };
            if (!isBlankString(state.searchText)) {
                params.search = state.searchText;
            }
            if (!isEmptyString(cursor)) {
                params.after = cursor;
            }

            return axiosInstance.get('history/execution_log/short', {params}).then(({data}) => {
                if (requestToken !== state.requestToken) {
                    return;
                }

                commit('SET_PAGE', {data, cursor, cursorStack});
                commit('SET_LOADING', false);
            }).catch((error) => {
                if (requestToken === state.requestToken) {
                    commit('SET_LOADING', false);
                }
                logError(error);
            });
        },

        selectExecution({commit, state}, executionId) {
            if (isEmptyString(executionId)) {
                commit('SET_EXECUTION_DETAILS', {id: executionId, execution: null});
                commit('SET_DETAILS_LOADING', false);
                return;
            }

            let execution = findById(state.executions, executionId);
            if (isNull(execution)) {
                execution = {
                    id: executionId,
                    user: 'Unknown',
                    script: 'Unknown'
                };
            }
            commit('SET_EXECUTION_DETAILS', {id: executionId, execution});
            commit('SET_DETAILS_LOADING', true);

            axiosInstance.get('history/execution_log/long/' + executionId).then(({data: incomingLog}) => {
                if (executionId !== state.selectedExecutionId) {
                    return;
                }

                const executionLog = translateExecutionLog(incomingLog);

                commit('SET_EXECUTION_DETAILS', {id: executionId, execution: executionLog});
                commit('SET_DETAILS_LOADING', false);
            }).catch((error) => {
                logError(error);
            });
        }
    },
    mutations: {
        SET_LOADING(state, loading) {
            state.loading = loading;
        },

        SET_EXECUTIONS(state, executions) {
            state.executions = executions;
        },

        SET_EXECUTION_DETAILS(state, {execution, id}) {
            state.selectedExecution = execution;
            state.selectedExecutionId = id;
        },

        SET_DETAILS_LOADING(state, loading) {
            state.detailsLoading = loading;
        },

        SET_REQUEST_TOKEN(state, requestToken) {
            state.requestToken = requestToken;
        },

        SET_PAGE_SIZE(state, pageSize) {
            state.pageSize = pageSize;
        },

        SET_SEARCH_TEXT(state, searchText) {
            state.searchText = searchText;
        },

        SET_SORT(state, {column, order}) {
            state.sortColumn = column;
            state.order = order;
        },

        SET_PAGE(state, {data, cursor, cursorStack}) {
            const records = isNull(data) || isNull(data.records) ? [] : data.records;

            state.executions = records.map(log => translateExecutionLog(log));
            state.total = isNull(data) || isNull(data.total) ? 0 : data.total;
            state.nextCursor = isNull(data) || isNull(data.nextCursor) ? null : data.nextCursor;
            state.hasNext = !isNull(state.nextCursor);
            state.currentCursor = isNull(cursor) ? null : cursor;
            state.cursorStack = cursorStack;
            state.hasPrev = cursorStack.length > 0;
        }
    }
});

export default store

export function translateExecutionLog(log) {
    log.startTimeString = getStartTimeString(log);
    log.fullStatus = getFullStatus(log);

    return log;
}

function getStartTimeString(log) {
    if (!isNull(log.startTime)) {
        const startTime = new Date(log.startTime);
        return startTime.toLocaleDateString() + ' ' + startTime.toLocaleTimeString();
    } else {
        return '';
    }
}

function getFullStatus(log) {
    if (!isNull(log.exitCode) && !isNull(log.status)) {
        return log.status + ' (' + log.exitCode + ')'
    } else if (!isNull(log.status)) {
        return log.status;
    }
}

function findById(executions, id) {
    return executions.find(execution => execution.id === id)
}
