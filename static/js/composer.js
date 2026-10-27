// Workout Composer: build/edit a workout template, or edit a client's assigned workout, as
// groups of sets (drag or tap exercises from the library), with background live sync + Save.
// Data contract: window.COMPOSER_DATA = { exercises, target, groups }
//   target = null for a new template, else the template/workout row plus kind: 'templates' | 'workouts'
//   groups = [{ id, name, note, sets: [{ id, exercise_id, exercise_name, has_*, target_*, rest_seconds, note }] }]
(function () {
    'use strict';

    const { api, h, ICONS, notify } = window.FitCoach;
    const DATA = window.COMPOSER_DATA || { exercises: [], target: null, groups: [] };
    const TARGET = DATA.target;
    const KIND = TARGET ? TARGET.kind : 'templates';
    const IS_NEW = !TARGET;

    const el = {
        name: document.getElementById('wcName'),
        duration: document.getElementById('wcDuration'),
        description: document.getElementById('wcDescription'),
        note: document.getElementById('wcNote'),
        date: document.getElementById('wcDate'),
        groups: document.getElementById('groupsContainer'),
        newGroupZone: document.getElementById('newGroupZone'),
        addGroupBtn: document.getElementById('addGroupBtn'),
        saveBtn: document.getElementById('saveBtn'),
        cancelBtn: document.getElementById('cancelBtn'),
        backLink: document.getElementById('backLink'),
        workoutColumn: document.getElementById('workoutColumn'),
        chips: document.getElementById('libraryChips'),
        search: document.getElementById('librarySearch'),
        status: document.getElementById('saveStatus'),
        statusText: document.getElementById('saveStatusText'),
        badge: document.getElementById('statusBadge')
    };

    let allowUnload = false;

    // ---------- State ----------
    let lidCounter = 0;
    const lid = () => ++lidCounter;

    const PARAMS = ['reps', 'weight_kg', 'duration_s', 'distance_m'];
    const PARAM_FIELDS = [
        { key: 'weight_kg', label: 'Kg', step: '0.5' },
        { key: 'reps', label: 'Reps', step: '1' },
        { key: 'duration_s', label: 'Seconds', step: '5' },
        { key: 'distance_m', label: 'Metres', step: '10' }
    ];

    // Exercise info for a set: the library entry, or the info that came with the set
    // (covers exercises archived from the library after they were used).
    const exerciseById = (id) => DATA.exercises.find((e) => e.id === id);
    function exerciseOf(set) {
        return exerciseById(set.exercise_id) || {
            id: set.exercise_id, name: set.exercise_name || 'Unknown exercise',
            has_reps: set.has_reps, has_weight_kg: set.has_weight_kg,
            has_duration_s: set.has_duration_s, has_distance_m: set.has_distance_m
        };
    }

    function setFromServer(s) {
        const set = { lid: lid(), id: s.id, exercise_id: s.exercise_id, rest_seconds: s.rest_seconds,
                      note: s.note || '', exercise_name: s.exercise_name };
        PARAMS.forEach((p) => {
            set['target_' + p] = s['target_' + p];
            set['has_' + p] = s['has_' + p];
        });
        return set;
    }

    const state = {
        // autoName is the fallback used while the coach hasn't typed a name
        target: {
            id: TARGET ? TARGET.id : null,
            createEnqueued: !IS_NEW,
            name: TARGET ? TARGET.name : '',
            autoName: 'Unnamed workout',
            description: TARGET ? (TARGET.description || '') : '',
            duration: TARGET ? TARGET.duration_minutes : null,
            note: TARGET ? (TARGET.note || '') : '',
            date: TARGET && TARGET.scheduled_date ? TARGET.scheduled_date : ''
        },
        groups: (DATA.groups || []).map((g) => ({
            lid: lid(), id: g.id, name: g.name || '', note: g.note || '', sets: g.sets.map(setFromServer)
        }))
    };

    const effectiveName = () => state.target.name.trim() || state.target.autoName;
    const targetUrl = () => '/api/' + KIND + '/' + state.target.id;

    // ---------- Background sync queue ----------
    // Ops run strictly in order; a failed op stays at the head of the queue and the
    // whole tail is retried on the next change (or by clicking the save-status text).
    const sync = {
        queue: [],
        running: false,
        hadFailure: false,

        push(label, run) {
            this.queue.push({ label, run });
            this.process();
        },

        retry() { this.process(); },

        waitIdle() {
            return new Promise((resolve) => {
                const timer = setInterval(() => {
                    if (!this.running) { clearInterval(timer); resolve(); }
                }, 120);
            });
        },

        async process() {
            if (this.running) return;
            this.running = true;
            setStatus('saving');
            let failed = null;

            while (this.queue.length) {
                const op = this.queue[0];
                try {
                    await op.run();
                    this.queue.shift();
                } catch (err) {
                    failed = err;
                    break;
                }
            }
            this.running = false;

            if (failed) {
                this.hadFailure = true;
                const labels = this.queue.map((op) => op.label);
                setStatus('error', labels);
                const extra = labels.length > 1 ? ' (+' + (labels.length - 1) + ' more pending)' : '';
                notify('Not saved: ' + labels[0] + extra + ' — ' + failed.message +
                       '. Will retry on your next change.', 'error');
            } else {
                if (this.hadFailure) {
                    this.hadFailure = false;
                    notify('All pending changes saved.', 'success');
                }
                setStatus(state.target.createEnqueued ? 'saved' : 'idle');
            }
        }
    };

    function setStatus(mode, pendingLabels) {
        el.status.className = 'save-state' + (mode === 'error' ? ' error' : '');
        if (mode === 'idle') el.statusText.textContent = 'Not started';
        if (mode === 'saving') el.statusText.textContent = 'Saving…';
        if (mode === 'saved') el.statusText.textContent = 'All changes saved';
        if (mode === 'error') {
            el.statusText.textContent = pendingLabels.length + ' change' +
                (pendingLabels.length > 1 ? 's' : '') + ' not saved — retry';
            el.status.title = 'Not saved:\n' + pendingLabels.join('\n') + '\n\nClick to retry now.';
        } else {
            el.status.title = 'Save status';
        }
    }

    // ---------- Template/workout lifecycle ----------
    // Only a NEW template is created here; force=true (structural actions) creates it even without
    // a name, falling back to the "Unnamed workout N" placeholder.
    function maybeCreateTarget(force) {
        const t = state.target;
        if (t.createEnqueued) return;
        if (!force && !t.name.trim()) return;
        t.createEnqueued = true;
        sync.push('Create template "' + effectiveName() + '"', async () => {
            const resp = await api('/api/templates', 'POST',
                { name: effectiveName(), description: t.description, duration_minutes: t.duration, note: t.note });
            t.id = resp.id;
            if (!t.name.trim()) {
                t.autoName = 'Unnamed workout ' + resp.id;
                el.name.placeholder = t.autoName;
                await api(targetUrl(), 'PUT', { name: t.autoName });
            }
        });
    }

    function onDetailsChanged() {
        const t = state.target;
        t.name = el.name.value;
        t.description = el.description.value;
        t.duration = el.duration.value ? parseInt(el.duration.value, 10) : null;
        t.note = el.note.value;
        if (el.date) t.date = el.date.value;
        if (!t.createEnqueued) { maybeCreateTarget(); return; }

        debouncedPush('details', 'Update workout details', async () => {
            const body = { name: effectiveName(), description: t.description,
                           duration_minutes: t.duration, note: t.note };
            if (KIND === 'workouts') body.scheduled_date = t.date || null;
            await api(targetUrl(), 'PUT', body);
        });
    }

    // ---------- Structural actions ----------
    function newSet(exerciseId) {
        const set = { lid: lid(), id: null, exercise_id: exerciseId, rest_seconds: null, note: '' };
        PARAMS.forEach((p) => { set['target_' + p] = null; });
        return set;
    }

    function addGroup() {
        maybeCreateTarget(true);
        const group = { lid: lid(), id: null, name: '', note: '', sets: [] };
        state.groups.push(group);
        render();
        sync.push('Add group ' + state.groups.length, async () => {
            const resp = await api(targetUrl() + '/groups', 'POST');
            group.id = resp.id;
        });
        return group;
    }

    function addSetToGroup(exerciseId, group) {
        maybeCreateTarget(true);
        const ex = exerciseById(exerciseId);
        const set = newSet(exerciseId);
        group.sets.push(set);
        render();
        sync.push('Add ' + ex.name, async () => {
            const resp = await api('/api/' + KIND + '/groups/' + group.id + '/sets', 'POST', { exercise_id: exerciseId });
            set.id = resp.id;
        });
        focusFirstInput(set);
    }

    function addExerciseAsNewGroup(exerciseId) {
        const group = addGroup();
        addSetToGroup(exerciseId, group);
    }

    function focusFirstInput(set) {
        const input = el.groups.querySelector('input[data-set="' + set.lid + '"]');
        if (input) input.focus({ preventScroll: false });
    }

    function duplicateGroup(group, index) {
        const copy = {
            lid: lid(), id: null, name: group.name, note: group.note,
            sets: group.sets.map((s) => Object.assign({}, s, { lid: lid(), id: null }))
        };
        state.groups.splice(index + 1, 0, copy);
        render();
        sync.push('Duplicate group ' + (index + 1), async () => {
            const resp = await api('/api/' + KIND + '/groups/' + group.id + '/duplicate', 'POST');
            copy.id = resp.id;
            resp.sets.forEach((serverSet, i) => {
                if (copy.sets[i]) copy.sets[i].id = serverSet.id;
            });
        });
    }

    function removeGroup(group, index) {
        if (group.sets.length &&
            !window.confirm('Remove group ' + (index + 1) + ' with ' + group.sets.length + ' set(s)?')) return;
        state.groups.splice(index, 1);
        render();
        sync.push('Remove group ' + (index + 1), async () => {
            await api('/api/' + KIND + '/groups/' + group.id, 'DELETE');
        });
    }

    function moveGroup(index, delta) {
        const to = index + delta;
        if (to < 0 || to >= state.groups.length) return;
        const moved = state.groups.splice(index, 1)[0];
        state.groups.splice(to, 0, moved);
        render();
        sync.push('Move group ' + (index + 1) + (delta < 0 ? ' up' : ' down'), async () => {
            // the order as it stands when this op runs (earlier ops have resolved every id by then)
            await api(targetUrl() + '/groups/order', 'PUT', { ids: state.groups.map((g) => g.id) });
        });
    }

    function duplicateSet(group, set) {
        const ex = exerciseOf(set);
        const copy = Object.assign({}, set, { lid: lid(), id: null });
        group.sets.splice(group.sets.indexOf(set) + 1, 0, copy);
        render();
        sync.push('Duplicate ' + ex.name, async () => {
            const resp = await api('/api/' + KIND + '/sets/' + set.id + '/duplicate', 'POST');
            copy.id = resp.id;
        });
    }

    function removeSet(group, set) {
        const ex = exerciseOf(set);
        group.sets.splice(group.sets.indexOf(set), 1);
        render();
        sync.push('Remove ' + ex.name, async () => {
            await api('/api/' + KIND + '/sets/' + set.id, 'DELETE');
        });
    }

    // ---------- Debounced field sync ----------
    // Typing waits 600 ms before its op is queued; Save queues whatever is still waiting right away.
    const pendingEdits = {}; // key -> { timer, label, run }
    function debouncedPush(key, label, run) {
        if (pendingEdits[key]) clearTimeout(pendingEdits[key].timer);
        pendingEdits[key] = { label: label, run: run, timer: setTimeout(() => flushEdit(key), 600) };
    }
    function flushEdit(key) {
        const edit = pendingEdits[key];
        if (!edit) return;
        clearTimeout(edit.timer);
        delete pendingEdits[key];
        sync.push(edit.label, edit.run);
    }
    function flushAllEdits() {
        Object.keys(pendingEdits).forEach(flushEdit);
    }

    // Empty input clears the value (sent as null); otherwise it must be positive (DB CHECKs)
    function onSetFieldChanged(set, field, label, rawValue, allowZero) {
        let value = null;
        if (rawValue !== '') {
            value = parseFloat(rawValue);
            if (isNaN(value) || value < 0 || (!allowZero && value === 0)) return;
        }
        set[field] = value;
        refreshValidity();
        const ex = exerciseOf(set);
        debouncedPush(set.lid + ':' + field, ex.name + ': ' + label + ' = ' + (value === null ? '—' : value),
            async () => {
                const body = {};
                body[field] = value;
                await api('/api/' + KIND + '/sets/' + set.id, 'PUT', body);
            });
    }

    function onSetNoteChanged(set, rawValue) {
        set.note = rawValue;
        const ex = exerciseOf(set);
        debouncedPush(set.lid + ':note', 'Note on ' + ex.name, async () => {
            await api('/api/' + KIND + '/sets/' + set.id, 'PUT', { note: set.note });
        });
    }

    function onGroupFieldChanged(group, field, rawValue) {
        group[field] = rawValue;
        debouncedPush(group.lid + ':' + field, (field === 'name' ? 'Name of' : 'Note on') + ' a group',
            async () => {
                const body = {};
                body[field] = group[field];
                await api('/api/' + KIND + '/groups/' + group.id, 'PUT', body);
            });
    }

    // ---------- Validation (live) ----------
    function problems() {
        const list = [];
        if (!state.groups.length) list.push('add at least one group');
        state.groups.forEach((group, gi) => {
            if (!group.sets.length) list.push('group ' + (gi + 1) + ' is empty');
            group.sets.forEach((set) => {
                const ex = exerciseOf(set);
                PARAM_FIELDS.forEach((p) => {
                    if (ex['has_' + p.key] && !(set['target_' + p.key] > 0)) {
                        list.push(ex.name + ' in group ' + (gi + 1) + ': ' + p.label.toLowerCase() + ' missing');
                    }
                });
            });
        });
        return list;
    }

    function refreshValidity() {
        const list = problems();
        const missing = list.filter((p) => p.indexOf('missing') !== -1).length;
        el.groups.querySelectorAll('input[data-required]').forEach((input) => {
            input.classList.toggle('invalid', input.value === '');
            input.setAttribute('aria-invalid', input.value === '' ? 'true' : 'false');
        });
        el.groups.querySelectorAll('.c-missing').forEach((n) => {
            const set = findSet(n.dataset.set);
            n.hidden = !set || !setMissing(set).length;
            if (set) n.textContent = exerciseOf(set).name + ' needs ' + setMissing(set).join(' and ') + ' before this can be ' + (KIND === 'templates' ? 'assigned.' : 'saved.');
        });
        if (list.length) {
            el.badge.className = 'badge badge-red';
            el.badge.textContent = missing ? missing + (missing === 1 ? ' field missing' : ' fields missing') : 'Not ready';
        } else if (KIND === 'workouts') {
            el.badge.className = 'badge';
            el.badge.textContent = 'Client copy';
        } else {
            el.badge.className = 'badge badge-blue';
            el.badge.textContent = TARGET && TARGET.status === 'ready' ? 'Ready' : 'Ready to save';
        }
        el.saveBtn.disabled = list.length > 0;
        el.saveBtn.title = list.length ? 'To save: ' + list.slice(0, 4).join('; ') : '';
    }

    function findSet(setLid) {
        for (const g of state.groups) for (const s of g.sets) if (String(s.lid) === String(setLid)) return s;
        return null;
    }
    function setMissing(set) {
        const ex = exerciseOf(set);
        return PARAM_FIELDS.filter((p) => ex['has_' + p.key] && !(set['target_' + p.key] > 0)).map((p) => p.label.toLowerCase());
    }

    // ---------- Rendering ----------
    function numberField(label, value, step, min, attrs, onInput) {
        const id = 'f' + lid();
        const input = h('input', Object.assign({ id: id, class: 'input num', type: 'number', inputmode: 'decimal',
                                                 step: step, min: min, placeholder: '—' }, attrs || {}));
        if (value !== null && value !== undefined) input.value = value;
        input.addEventListener('input', () => onInput(input.value));
        return h('div', { class: 'field' }, h('label', { for: id }, label), input);
    }

    function renderSet(group, set) {
        const ex = exerciseOf(set);
        const params = PARAM_FIELDS.filter((p) => ex['has_' + p.key]);
        const row = h('div', { class: 'c-set', style: '--cols:' + params.length });
        row.appendChild(h('span', { class: 'c-set-name', title: ex.name }, ex.name));
        params.forEach((p) => {
            row.appendChild(numberField(p.label + ' *', set['target_' + p.key], p.step, p.step,
                { 'data-set': set.lid, 'data-required': '1', 'aria-label': ex.name + ' ' + p.label + ' (required)' },
                (v) => onSetFieldChanged(set, 'target_' + p.key, p.label, v, false)));
        });
        row.appendChild(numberField('Rest, s', set.rest_seconds, '5', '0', { 'aria-label': ex.name + ' rest after, seconds' },
            (v) => onSetFieldChanged(set, 'rest_seconds', 'rest', v, true)));
        row.appendChild(h('button', { type: 'button', class: 'icon-btn soft', html: ICONS.copy, 'aria-label': 'Duplicate ' + ex.name + ' set',
                                      title: 'Duplicate set', onclick: () => duplicateSet(group, set) }));
        row.appendChild(h('button', { type: 'button', class: 'icon-btn soft', html: ICONS.x, 'aria-label': 'Remove ' + ex.name + ' set',
                                      title: 'Remove set', onclick: () => removeSet(group, set) }));

        const note = h('input', { class: 'input', type: 'text', maxlength: '500', placeholder: 'Note to client (optional)',
                                  'aria-label': 'Note on ' + ex.name, style: 'height: 38px' });
        note.value = set.note || '';
        note.addEventListener('input', () => onSetNoteChanged(set, note.value));

        return h('div', { class: 'c-set-wrap' }, row,
            h('div', { class: 'c-set-note' }, note),
            h('span', { class: 'c-missing', 'data-set': set.lid, hidden: true }));
    }

    function renderGroup(group, index) {
        const card = h('section', { class: 'card c-group', 'data-group-lid': group.lid, 'aria-label': 'Group ' + (index + 1) });

        const name = h('input', { class: 'c-group-name', type: 'text', maxlength: '200', placeholder: 'Group ' + (index + 1),
                                  'aria-label': 'Group ' + (index + 1) + ' name (optional)' });
        name.value = group.name;
        name.addEventListener('input', () => onGroupFieldChanged(group, 'name', name.value));
        card.appendChild(h('div', { class: 'c-group-head' },
            h('span', { class: 'c-group-num' }, String(index + 1)),
            name,
            h('button', { type: 'button', class: 'icon-btn', html: ICONS.up, 'aria-label': 'Move group ' + (index + 1) + ' up',
                          disabled: index === 0, onclick: () => moveGroup(index, -1) }),
            h('button', { type: 'button', class: 'icon-btn', html: ICONS.down, 'aria-label': 'Move group ' + (index + 1) + ' down',
                          disabled: index === state.groups.length - 1, onclick: () => moveGroup(index, 1) }),
            h('button', { type: 'button', class: 'icon-btn', html: ICONS.copy, 'aria-label': 'Duplicate group ' + (index + 1),
                          title: 'Duplicate group', onclick: () => duplicateGroup(group, index) }),
            h('button', { type: 'button', class: 'icon-btn', html: ICONS.x, 'aria-label': 'Remove group ' + (index + 1),
                          title: 'Remove group', onclick: () => removeGroup(group, index) })));

        const body = h('div', { class: 'c-group-body' });
        if (!group.sets.length) body.appendChild(h('div', { class: 'c-empty' }, 'Empty group — drop an exercise here'));
        group.sets.forEach((set) => body.appendChild(renderSet(group, set)));

        const last = group.sets[group.sets.length - 1];
        const note = h('input', { class: 'input', type: 'text', maxlength: '500', placeholder: 'e.g. Alternate, no rest between',
                                  'aria-label': 'Group ' + (index + 1) + ' note', style: 'height: 38px' });
        note.value = group.note;
        note.addEventListener('input', () => onGroupFieldChanged(group, 'note', note.value));
        body.appendChild(h('div', { style: 'display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding-top: 4px' },
            last ? h('button', { type: 'button', class: 'ui-btn ui-btn-outline ui-btn-sm', style: 'border-style: dashed',
                                 onclick: () => duplicateSet(group, last) }, '+ Another ' + exerciseOf(last).name + ' set') : null,
            h('div', { style: 'flex: 1 1 220px' }, note)));
        card.appendChild(body);
        return card;
    }

    function render() {
        el.groups.innerHTML = '';
        state.groups.forEach((group, i) => el.groups.appendChild(renderGroup(group, i)));
        refreshValidity();
    }

    // ---------- Save / Discard ----------
    function doneUrl() {
        return KIND === 'workouts' ? '/workouts/' + state.target.id : '/admin/templates';
    }

    async function onSave() {
        if (!state.target.createEnqueued) {
            notify('Nothing to save yet — add exercises first.', 'warning');
            return;
        }
        const list = problems();
        if (list.length) {
            notify('Cannot save: ' + list.slice(0, 3).join('; ') + (list.length > 3 ? ' (+' + (list.length - 3) + ' more)' : ''), 'error');
            return;
        }
        if (!state.target.name.trim() &&
            !window.confirm('You haven\'t named this workout — save it as "' + state.target.autoName + '"?')) {
            el.name.focus();
            return;
        }

        el.saveBtn.disabled = true;
        flushAllEdits(); // edits typed in the last 600 ms
        // Saving a template marks it ready (assignable); the server re-validates.
        if (KIND === 'templates') {
            sync.push('Mark template ready', async () => { await api(targetUrl(), 'PUT', { status: 'ready' }); });
        } else {
            sync.retry();
        }
        await sync.waitIdle();
        el.saveBtn.disabled = false;

        if (sync.queue.length) return; // failure toast already shown by the queue
        allowUnload = true;
        notify(KIND === 'templates' ? 'Template saved — ready to assign!' : 'Workout saved!', 'success');
        setTimeout(() => { window.location.href = doneUrl(); }, 400);
    }

    // Discard deletes a template created in this session (only shown for new templates)
    async function onDiscard() {
        if (state.target.createEnqueued && !window.confirm('Discard this template and everything in it?')) return;
        el.cancelBtn.disabled = true;
        Object.keys(pendingEdits).forEach((k) => { clearTimeout(pendingEdits[k].timer); delete pendingEdits[k]; });
        sync.retry();
        await sync.waitIdle();
        sync.queue.length = 0;
        if (state.target.id) {
            try {
                await api(targetUrl(), 'DELETE');
            } catch (err) {
                el.cancelBtn.disabled = false;
                notify('Could not discard: ' + err.message, 'error');
                return;
            }
        }
        allowUnload = true;
        window.location.href = '/admin/templates';
    }

    // ---------- Exercise library ----------
    function paramSummary(ex) {
        const parts = [];
        if (ex.has_reps) parts.push('reps');
        if (ex.has_weight_kg) parts.push('kg');
        if (ex.has_duration_s) parts.push('seconds');
        if (ex.has_distance_m) parts.push('metres');
        return parts.join(' · ');
    }

    function addToLastGroup(exerciseId) {
        const last = state.groups[state.groups.length - 1];
        if (last) addSetToGroup(exerciseId, last);
        else addExerciseAsNewGroup(exerciseId);
    }

    function renderLibrary() {
        el.chips.innerHTML = '';
        if (!DATA.exercises.length) {
            el.chips.appendChild(h('p', { class: 'muted' }, 'No exercises yet. ', h('a', { href: '/admin/exercises' }, 'Add some')));
        }
        DATA.exercises.forEach((ex) => {
            const chip = h('div', { class: 'chip', 'data-name': ex.name.toLowerCase(), title: ex.description || ex.name },
                h('span', { html: ICONS.grip }),
                h('span', { style: 'min-width: 0' }, h('strong', {}, ex.name), h('small', {}, paramSummary(ex))),
                h('button', { type: 'button', class: 'icon-btn soft chip-add', html: ICONS.plus,
                              'aria-label': 'Add ' + ex.name + ' to the last group',
                              onclick: (e) => { e.stopPropagation(); addToLastGroup(ex.id); } }));
            initChipDrag(chip, ex);
            el.chips.appendChild(chip);
        });
    }

    el.search.addEventListener('input', () => {
        const term = el.search.value.trim().toLowerCase();
        el.chips.querySelectorAll('.chip').forEach((chip) => {
            chip.hidden = term !== '' && chip.dataset.name.indexOf(term) === -1;
        });
    });

    // ---------- Drag & drop (pointer events: works for mouse AND touch) ----------
    const TOUCH_HOLD_MS = 250;    // long-press lifts the chip on touch (short swipe = scroll)
    const MOUSE_THRESHOLD = 5;    // px before a mouse press becomes a drag
    const TOUCH_CANCEL_DIST = 12; // px of early movement that means "scrolling, not dragging"

    let dropTarget = null; // {kind: 'group', group} | {kind: 'new'}

    function clearDropHighlight() {
        document.querySelectorAll('.drop-target').forEach((n) => n.classList.remove('drop-target'));
    }

    function updateDropTarget(x, y) {
        clearDropHighlight();
        dropTarget = null;
        const under = document.elementFromPoint(x, y);
        if (!under) return;
        const groupEl = under.closest('.c-group');
        if (groupEl) {
            const group = state.groups.find((g) => String(g.lid) === groupEl.dataset.groupLid);
            if (group) {
                dropTarget = { kind: 'group', group: group };
                groupEl.classList.add('drop-target');
            }
            return;
        }
        if (under.closest('#newGroupZone') || under.closest('#workoutColumn')) {
            dropTarget = { kind: 'new' };
            el.newGroupZone.classList.add('drop-target');
        }
    }

    function autoScroll(y) {
        if (y < 80) window.scrollBy(0, -14);
        else if (y > window.innerHeight - 90) window.scrollBy(0, 14);
    }

    function initChipDrag(chip, exercise) {
        chip.addEventListener('pointerdown', (down) => {
            if (down.button !== 0 || down.target.closest('button')) return;
            const isTouch = down.pointerType !== 'mouse';
            const startX = down.clientX, startY = down.clientY;
            let ghost = null;
            let dragging = false;
            let holdTimer = null;

            function beginDrag(x, y) {
                dragging = true;
                try { chip.setPointerCapture(down.pointerId); } catch (_) { /* ignore */ }
                ghost = chip.cloneNode(true);
                ghost.classList.add('ghost');
                ghost.style.width = chip.offsetWidth + 'px';
                document.body.appendChild(ghost);
                document.body.classList.add('dragging');
                moveGhost(x, y);
            }

            function moveGhost(x, y) {
                ghost.style.left = x + 'px';
                ghost.style.top = y + 'px';
            }

            function onMove(move) {
                const dx = move.clientX - startX, dy = move.clientY - startY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (!dragging) {
                    if (!isTouch && dist > MOUSE_THRESHOLD) beginDrag(move.clientX, move.clientY);
                    else if (isTouch && dist > TOUCH_CANCEL_DIST) cleanup(); // user is scrolling
                    return;
                }
                move.preventDefault();
                moveGhost(move.clientX, move.clientY);
                updateDropTarget(move.clientX, move.clientY);
                autoScroll(move.clientY);
            }

            function onUp() {
                const finalTarget = dragging ? dropTarget : null;
                cleanup();
                if (!finalTarget) return;
                if (finalTarget.kind === 'group') addSetToGroup(exercise.id, finalTarget.group);
                else addExerciseAsNewGroup(exercise.id);
            }

            function cleanup() {
                clearTimeout(holdTimer);
                chip.removeEventListener('pointermove', onMove);
                chip.removeEventListener('pointerup', onUp);
                chip.removeEventListener('pointercancel', cleanup);
                if (ghost) ghost.remove();
                document.body.classList.remove('dragging');
                clearDropHighlight();
                dropTarget = null;
                dragging = false;
            }

            if (isTouch) {
                holdTimer = setTimeout(() => beginDrag(startX, startY), TOUCH_HOLD_MS);
            }
            chip.addEventListener('pointermove', onMove);
            chip.addEventListener('pointerup', onUp);
            chip.addEventListener('pointercancel', cleanup);
        });
        chip.addEventListener('contextmenu', (e) => {
            if (document.body.classList.contains('dragging')) e.preventDefault();
        });
    }

    // ---------- Wiring ----------
    el.name.value = state.target.name;
    el.description.value = state.target.description;
    el.duration.value = state.target.duration || '';
    el.note.value = state.target.note;
    if (el.date) el.date.value = state.target.date;
    if (!IS_NEW) setStatus('saved');

    el.name.addEventListener('input', onDetailsChanged);
    el.description.addEventListener('input', onDetailsChanged);
    el.duration.addEventListener('input', onDetailsChanged);
    el.note.addEventListener('input', onDetailsChanged);
    if (el.date) el.date.addEventListener('input', onDetailsChanged);

    el.addGroupBtn.addEventListener('click', addGroup);
    el.saveBtn.addEventListener('click', onSave);
    if (el.cancelBtn) el.cancelBtn.addEventListener('click', onDiscard);
    el.status.addEventListener('click', () => sync.retry());
    el.backLink.addEventListener('click', async (e) => {
        // edits are live-saved; just make sure nothing is still waiting before leaving
        flushAllEdits();
        if (!sync.queue.length && !sync.running) return;
        e.preventDefault();
        sync.retry();
        await sync.waitIdle();
        if (sync.queue.length && !window.confirm('Some changes are not saved yet. Leave anyway?')) return;
        allowUnload = true;
        window.location.href = el.backLink.href;
    });

    window.addEventListener('beforeunload', (e) => {
        if (!allowUnload && (sync.queue.length || Object.keys(pendingEdits).length)) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    renderLibrary();
    render();
})();
