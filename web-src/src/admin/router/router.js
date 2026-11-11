import {routerChildren as executionRouterChildren} from '@/common/components/history/executions-log-page';
import Vue from 'vue';
import VueRouter from 'vue-router';
import AdminExecutionsLogPage from '../components/history/AdminExecutionsLogPage';
import ScriptConfig from '../components/scripts-config/ScriptConfig';
import ScriptConfigListPage from '../components/scripts-config/ScriptConfigListPage';
import ScriptsList from '../components/scripts-config/ScriptsList';
import SettingsScriptPage from '../components/settings/SettingsScriptPage';

Vue.use(VueRouter);

const router = new VueRouter({
    mode: 'hash',
    routes: [
        {
            path: '/logs',
            component: AdminExecutionsLogPage,
            children: executionRouterChildren
        },
        {
            path: '/scripts',
            component: ScriptConfigListPage,
            children: [
                {path: '', component: ScriptsList},
                {path: ':scriptName', component: ScriptConfig, props: true}
            ]
        },
        {
            // placement=settings runners (Import from Gitea, Install Package, Secrets Manager...)
            path: '/settings/:scriptName',
            component: SettingsScriptPage,
            props: true
        },
        {path: '*', redirect: '/logs'}
    ],
    linkActiveClass: 'active'
});

export default router