'use strict';

import {buildCategoryTree, findScriptLocation, isLigatureIcon} from '@/main-app/utils/categories';

const UNCATEGORISED = {name: 'Uncategorised', icon: 'label_outline'};

function names(tree) {
    return tree.map(c => c.name);
}

describe('Test category tree', function () {
    it('Test everything uncategorised', function () {
        const tree = buildCategoryTree([{name: 'b'}, {name: 'a'}], [], UNCATEGORISED);

        expect(names(tree)).toEqual(['Uncategorised']);
        expect(tree[0].uncategorised).toBeTrue();
        expect(tree[0].scripts.map(s => s.name)).toEqual(['a', 'b']);
        expect(tree[0].groups).toEqual([]);
    });

    it('Test categories keep file order, Uncategorised last, empty ones hidden', function () {
        const categories = [
            {name: 'Music', icon: 'music_note'},
            {name: 'Empty', icon: 'label'},
            {name: 'Finance', icon: '£'}];
        const scripts = [
            {name: 'loose'},
            {name: 'budget', category: 'Finance'},
            {name: 'tags', category: 'Music'}];

        const tree = buildCategoryTree(scripts, categories, UNCATEGORISED);

        expect(names(tree)).toEqual(['Music', 'Finance', 'Uncategorised']);
        expect(tree[1].icon).toBe('£');
    });

    it('Test groups first then ungrouped scripts, both alphabetical', function () {
        const scripts = [
            {name: 'zeta'},
            {name: 'beta', group: 'G2'},
            {name: 'alpha'},
            {name: 'gamma', group: 'g1'},
            {name: 'delta', group: 'G2'}];

        const [category] = buildCategoryTree(scripts, [], UNCATEGORISED);

        expect(category.groups.map(g => g.name)).toEqual(['g1', 'G2']);
        expect(category.groups[1].scripts.map(s => s.name)).toEqual(['beta', 'delta']);
        expect(category.scripts.map(s => s.name)).toEqual(['alpha', 'zeta']);
        expect(category.allScripts.length).toBe(5);
    });

    it('Test blank category and group count as missing', function () {
        const tree = buildCategoryTree(
            [{name: 'a', category: ' ', group: ''}, {name: 'b', category: null, group: ' \n'}],
            [], UNCATEGORISED);

        expect(names(tree)).toEqual(['Uncategorised']);
        expect(tree[0].groups).toEqual([]);
        expect(tree[0].scripts.map(s => s.name)).toEqual(['a', 'b']);
    });

    it('Test unknown category still shown, with default icon', function () {
        const tree = buildCategoryTree([{name: 'a', category: 'Garden'}], [], UNCATEGORISED);

        expect(names(tree)).toEqual(['Garden']);
        expect(tree[0].icon).toBe('label');
    });

    it('Test same group name in different categories stays separate', function () {
        const tree = buildCategoryTree([
            {name: 'a', category: 'Music', group: 'Library'},
            {name: 'b', category: 'Movies', group: 'Library'}
        ], [{name: 'Music'}, {name: 'Movies'}], UNCATEGORISED);

        expect(tree[0].groups[0].key).not.toEqual(tree[1].groups[0].key);
    });

    it('Test default Uncategorised when server sends none', function () {
        const tree = buildCategoryTree([{name: 'a'}], [], null);

        expect(tree[0].name).toBe('Uncategorised');
        expect(tree[0].icon).toBe('label_outline');
    });

    it('Test find script location', function () {
        const tree = buildCategoryTree([
            {name: 'a', category: 'Music', group: 'Library'},
            {name: 'b', category: 'Music'}
        ], [{name: 'Music'}], UNCATEGORISED);

        expect(findScriptLocation(tree, 'a').group.name).toBe('Library');
        expect(findScriptLocation(tree, 'b').group).toBeNull();
        expect(findScriptLocation(tree, 'b').category.name).toBe('Music');
        expect(findScriptLocation(tree, 'missing')).toBeNull();
    });

    it('Test ligature icon detection', function () {
        expect(isLigatureIcon('music_note')).toBeTrue();
        expect(isLigatureIcon('£')).toBeFalse();
        expect(isLigatureIcon('Music')).toBeFalse();
        expect(isLigatureIcon('')).toBeFalse();
        expect(isLigatureIcon(null)).toBeFalse();
    });
});
