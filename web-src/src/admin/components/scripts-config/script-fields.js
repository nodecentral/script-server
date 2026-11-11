export const nameField = {
    name: 'Script name',
    required: true
};
export const groupField = {
    name: 'Group',
    description: 'Aggregates scripts from the same group under one expandable heading, inside their category'
};
export const categoryField = {
    name: 'Category',
    description: 'Top level of the sidebar (Category > Group > Script), e.g. Finance, Music. '
        + 'Icons come from conf/categories.json - a new name is added there automatically with the default icon. '
        + 'Leave empty for Uncategorised'
};
export const settingsPlacementField = {
    name: 'Settings tab (admin only)',
    description: 'Moves this script out of the sidebar into a tab of the admin Settings page. '
        + 'Only admins can see or run it'
};
export const scriptPathField = {
    name: 'Script path',
    required: true
};
export const descriptionField = {
    name: 'Description'
};
export const workDirField = {
    name: 'Working directory'
};
export const allowAllField = {
    name: 'Allow all'
};
export const allowAllAdminsField = {
    name: 'Any admin'
};
export const outputFormatField = {
    name: 'Output format',
    description: 'Specifies in which format the script outputs data ' +
        '(terminal, plain text, html tags, or an extended html page (iframe)',
    values: ['terminal', 'text', 'html', 'html_iframe']
};
export const requiresTerminalField = {
    name: 'Enable pseudo-terminal',
    description: 'Enables pseudo-terminal. ' +
        'This is need for some utilities which behave differently, when executed from terminal'
};
export const includeScriptField = {
    name: 'Include config',
    description: 'Allows to include another shared config'
};
export const globalInstancesField = {
    name: 'Shared Script Instances',
    description: 'Allows script instances to be shared by all users'
};

export const schedulingEnabledField = {
    name: 'Enabled',
    description: 'Enables possibility to schedule scripts'
};

export const schedulingAutoCleanupField = {
    name: 'Auto cleanup',
    description: 'Mark finished scripts as seen by user, i.e. remove from active tabs. '
        + 'Always disabled when output_files are specified'
};