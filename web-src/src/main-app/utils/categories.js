import {isBlankString, isNull} from '@/common/utils/common';

// Mirrors CategoryService's fallbacks (src/config/category_service.py), used only if the server
// response somehow lacks them (e.g. an older backend).
export const DEFAULT_CATEGORY_ICON = 'label';
export const DEFAULT_UNCATEGORISED = {name: 'Uncategorised', icon: 'label_outline'};

function byName(o1, o2) {
    return o1.name.toLowerCase().localeCompare(o2.name.toLowerCase());
}

/**
 * Builds the user view's Category > Group > Script hierarchy.
 *
 * - Categories keep the order of conf/categories.json; ones with no visible scripts are dropped.
 * - The Uncategorised bucket always comes last and holds every script with no category.
 * - Inside a category: groups first (alphabetical), then scripts with no group (alphabetical) -
 *   so a script with neither category nor group ends up at the very bottom of Uncategorised.
 *
 * Returns [{key, name, icon, uncategorised, groups: [{key, name, scripts}], scripts, allScripts}]
 */
export function buildCategoryTree(scripts, categories, uncategorised) {
    const uncategorisedInfo = isNull(uncategorised) ? DEFAULT_UNCATEGORISED : uncategorised;

    const nodes = [];
    const nodesByName = {};

    const createNode = (name, icon, isUncategorised) => {
        const node = {
            key: (isUncategorised ? '\u0000' : '') + name,
            name,
            icon: isBlankString(icon) ? DEFAULT_CATEGORY_ICON : icon,
            uncategorised: isUncategorised,
            groupsByName: {},
            scripts: [],
            allScripts: []
        };
        if (!isUncategorised) {
            nodesByName[name] = node;
        }
        nodes.push(node);
        return node;
    };

    for (const category of (categories || [])) {
        if (!(category.name in nodesByName)) {
            createNode(category.name, category.icon, false);
        }
    }
    const uncategorisedNode = createNode(uncategorisedInfo.name, uncategorisedInfo.icon, true);

    for (const script of (scripts || [])) {
        let node;
        if (isBlankString(script.category)) {
            node = uncategorisedNode;
        } else {
            node = nodesByName[script.category];
            if (!node) {
                // Not expected (the server registers every used category), but never lose a script
                node = createNode(script.category, DEFAULT_CATEGORY_ICON, false);
            }
        }

        node.allScripts.push(script);

        if (isBlankString(script.group)) {
            node.scripts.push(script);
        } else {
            let group = node.groupsByName[script.group];
            if (!group) {
                group = {key: node.key + '\u0001' + script.group, name: script.group, scripts: []};
                node.groupsByName[script.group] = group;
            }
            group.scripts.push(script);
        }
    }

    // Uncategorised was created before any ad hoc categories - keep it last regardless
    const ordered = nodes.filter(n => !n.uncategorised).concat([uncategorisedNode]);

    return ordered
        .filter(node => node.allScripts.length > 0)
        .map(node => {
            const groups = Object.values(node.groupsByName);
            groups.forEach(group => group.scripts.sort(byName));
            groups.sort(byName);
            node.scripts.sort(byName);

            const {groupsByName, ...rest} = node;
            return {...rest, groups};
        });
}

export function findScriptLocation(tree, scriptName) {
    for (const category of tree) {
        for (const group of category.groups) {
            if (group.scripts.some(s => s.name === scriptName)) {
                return {category, group};
            }
        }
        if (category.scripts.some(s => s.name === scriptName)) {
            return {category, group: null};
        }
    }
    return null;
}

// A Material Icons ligature name (lowercase_with_underscores) is rendered with the icon font;
// anything else ("£", an emoji) is rendered as plain text.
export function isLigatureIcon(icon) {
    return !isBlankString(icon) && /^[a-z0-9_]+$/.test(icon);
}
