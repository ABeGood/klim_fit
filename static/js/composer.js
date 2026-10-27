// Workout Composer: build/edit a workout template, or edit a client's assigned workout, as
// groups of sets (drag exercises from the library), with background live sync + Save/Cancel.
// Data contract: window.COMPOSER_DATA = { exercises, target, groups }
//   target = null for a new template, else the template/workout row plus kind: 'templates' | 'workouts'
//   groups = [{ id, name, note, sets: [{ id, exercise_id, exercise_name, has_*, target_*, rest_seconds, note }] }]
(function () {
    'use strict';

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
        workoutColumn: document.getElementById('workoutColumn'),
        chips: document.getElementById('libraryChips'),
        search: document.getElementById('librarySearch'),
        status: document.getElementById('saveStatus'),
        statusText: document.getElementById('saveStatusText')
    };

    let allowUnload = false;

    function notify(message, type) {
        if (window.FitCoachUtils) { FitCoachUtils.showNotification(message, type); }
    }

    // ---------- State ----------
    let lidCounter = 0;
    const lid = () => ++lidCounter;

    const PARAMS = ['reps', 'weight_kg', 'duration_s', 'distance_m'];

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
        // autoName is the fallback used while the admin hasn't typed a name
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

    // ---------- API + background sync queue ----------
    async function api(url, opts) {
        const options = opts || {};
        let resp;
        try {
            resp = await fetch(url, {
                method: options.method || 'GET',
                headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
                body: options.body ? JSON.stringify(options.body) : undefined
            });
        } catch (err) {
            throw new Error('network unreachable');
        }
        if (!resp.ok) {
            let detail = '';
            try { detail = (await resp.json()).detail || ''; } catch (_) { /* ignore */ }
            throw new Error(detail || ('HTTP ' + resp.status));
        }
        return resp.json();
    }

    // Ops run strictly in order; a failed op stays at the head of the queue and the
    // whole tail is retried on the next save event (or by clicking the status chip).
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
        el.status.className = 'wc-status ' + mode;
        if (mode === 'idle') el.statusText.textContent = 'Not started';
        if (mode === 'saving') el.statusText.textContent = 'Saving…';
        if (mode === 'saved') el.statusText.textContent = 'All changes saved';
        if (mode === 'error') {
            el.statusText.textContent = pendingLabels.length + ' change' +
                (pendingLabels.length > 1 ? 's' : '') + ' not saved';
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
            const resp = await api('/api/templates', {
                method: 'POST',
                body: { name: effectiveName(), description: t.description, duration_minutes: t.duration, note: t.note }
            });
            t.id = resp.id;
            if (!t.name.trim()) {
                t.autoName = 'Unnamed workout ' + resp.id;
                el.name.placeholder = t.autoName;
                await api(targetUrl(), { method: 'PUT', body: { name: t.autoName } });
            }
        });
    }

    let detailsTimer = null;
    function onDetailsChanged() {
        const t = state.target;
        t.name = el.name.value;
        t.description = el.description.value;
        t.duration = el.duration.value ? parseInt(el.duration.value, 10) : null;
        t.note = el.note.value;
        if (el.date) t.date = el.date.value;
        if (!t.createEnqueued) { maybeCreateTarget(); return; }

        clearTimeout(detailsTimer);
        detailsTimer = setTimeout(() => {
            sync.push('Update workout details', async () => {
                const body = { name: effectiveName(), description: t.description,
                               duration_minutes: t.duration, note: t.note };
                if (KIND === 'workouts') body.scheduled_date = t.date || null;
                await api(targetUrl(), { method: 'PUT', body: body });
            });
        }, 600);
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
            const resp = await api(targetUrl() + '/groups', { method: 'POST' });
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
            const resp = await api('/api/' + KIND + '/groups/' + group.id + '/sets', {
                method: 'POST', body: { exercise_id: exerciseId }
            });
            set.id = resp.id;
        });
    }

    function addExerciseAsNewGroup(exerciseId) {
        const group = addGroup();
        addSetToGroup(exerciseId, group);
    }

    function duplicateGroup(group, index) {
        const copy = {
            lid: lid(), id: null, name: group.name, note: group.note,
            sets: group.sets.map((s) => Object.assign({}, s, { lid: lid(), id: null }))
        };
        state.groups.splice(index + 1, 0, copy);
        render();
        sync.push('Duplicate group ' + (index + 1), async () => {
            const resp = await api('/api/' + KIND + '/groups/' + group.id + '/duplicate', { method: 'POST' });
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
            await api('/api/' + KIND + '/groups/' + group.id, { method: 'DELETE' });
        });
    }

    function duplicateSet(group, set, setIndex) {
        const ex = exerciseOf(set);
        const copy = Object.assign({}, set, { lid: lid(), id: null });
        group.sets.splice(setIndex + 1, 0, copy);
        render();
        sync.push('Duplicate ' + ex.name, async () => {
            const resp = await api('/api/' + KIND + '/sets/' + set.id + '/duplicate', { method: 'POST' });
            copy.id = resp.id;
        });
    }

    function removeSet(group, set, setIndex) {
        const ex = exerciseOf(set);
        group.sets.splice(setIndex, 1);
        render();
        sync.push('Remove ' + ex.name, async () => {
            await api('/api/' + KIND + '/sets/' + set.id, { method: 'DELETE' });
        });
    }

    // ---------- Debounced field sync ----------
    const fieldTimers = {};
    function debouncedPush(key, label, run) {
        clearTimeout(fieldTimers[key]);
        fieldTimers[key] = setTimeout(() => sync.push(label, run), 600);
    }

    // Empty input clears the value (sent as null); otherwise it must be positive (DB CHECKs)
    function onSetFieldChanged(set, field, label, rawValue, allowZero) {
        let value = null;
        if (rawValue !== '') {
            value = parseFloat(rawValue);
            if (isNaN(value) || value < 0 || (!allowZero && value === 0)) return;
        }
        set[field] = value;
        const ex = exerciseOf(set);
        debouncedPush(set.lid + ':' + field, ex.name + ': ' + label + ' = ' + (value === null ? '—' : value),
            async () => {
                const body = {};
                body[field] = value;
                await api('/api/' + KIND + '/sets/' + set.id, { method: 'PUT', body: body });
            });
    }

    function onSetNoteChanged(set, rawValue) {
        set.note = rawValue;
        const ex = exerciseOf(set);
        debouncedPush(set.lid + ':note', 'Note on ' + ex.name, async () => {
            await api('/api/' + KIND + '/sets/' + set.id, { method: 'PUT', body: { note: set.note } });
        });
    }

    function onGroupFieldChanged(group, index, field, rawValue) {
        group[field] = rawValue;
        debouncedPush(group.lid + ':' + field, (field === 'name' ? 'Name of' : 'Note on') + ' group ' + (index + 1),
            async () => {
                const body = {};
                body[field] = group[field];
                await api('/api/' + KIND + '/groups/' + group.id, { method: 'PUT', body: body });
            });
    }

    // ---------- Rendering ----------
    const PARAM_FIELDS = [
        { field: 'target_reps', label: 'Reps', flag: 'has_reps', step: '1' },
        { field: 'target_weight_kg', label: 'Weight, kg', flag: 'has_weight_kg', step: '0.5' },
        { field: 'target_duration_s', label: 'Duration, s', flag: 'has_duration_s', step: '5' },
        { field: 'target_distance_m', label: 'Distance, m', flag: 'has_distance_m', step: '10' }
    ];

    function iconButton(iconClass, title, danger, onClick) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'wc-icon-btn no-loading' + (danger ? ' danger' : '');
        btn.title = title;
        btn.innerHTML = '<i class="fas ' + iconClass + '"></i>';
        btn.addEventListener('click', onClick);
        return btn;
    }

    function noteInput(labelText, placeholder, value, onInput) {
        const wrap = document.createElement('div');
        wrap.className = 'wc-note';
        const label = document.createElement('label');
        label.textContent = labelText;
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = placeholder;
        input.maxLength = 500;
        input.value = value || '';
        input.addEventListener('input', () => onInput(input.value));
        wrap.appendChild(label);
        wrap.appendChild(input);
        return wrap;
    }

    function numberInput(labelText, step, min, value, dataset, onInput) {
        const wrap = document.createElement('div');
        wrap.className = 'wc-param';
        const label = document.createElement('label');
        label.textContent = labelText;
        const input = document.createElement('input');
        input.type = 'number';
        input.inputMode = 'decimal';
        input.step = step;
        input.min = min;
        input.placeholder = '—';
        Object.assign(input.dataset, dataset || {});
        if (value !== null && value !== undefined) input.value = value;
        input.addEventListener('input', () => {
            input.classList.remove('wc-invalid');
            onInput(input.value);
        });
        wrap.appendChild(label);
        wrap.appendChild(input);
        return wrap;
    }

    function renderSet(group, set, setIndex) {
        const ex = exerciseOf(set);

        const card = document.createElement('div');
        card.className = 'wc-entry';

        const head = document.createElement('div');
        head.className = 'wc-entry-head';
        const title = document.createElement('span');
        title.className = 'wc-entry-name';
        title.textContent = (setIndex + 1) + '. ' + ex.name;
        const actions = document.createElement('div');
        actions.className = 'wc-entry-actions';
        actions.appendChild(iconButton('fa-clone', 'Duplicate set', false,
            () => duplicateSet(group, set, setIndex)));
        actions.appendChild(iconButton('fa-times', 'Remove set', true,
            () => removeSet(group, set, setIndex)));
        head.appendChild(title);
        head.appendChild(actions);
        card.appendChild(head);

        const params = document.createElement('div');
        params.className = 'wc-entry-params';
        PARAM_FIELDS.forEach((p) => {
            if (!ex[p.flag]) return;
            params.appendChild(numberInput(p.label + ' *', p.step, p.step, set[p.field],
                { set: set.lid, field: p.field },
                (v) => onSetFieldChanged(set, p.field, p.label, v, false)));
        });
        params.appendChild(numberInput('Rest after, s', '5', '0', set.rest_seconds, null,
            (v) => onSetFieldChanged(set, 'rest_seconds', 'rest', v, true)));
        card.appendChild(params);

        card.appendChild(noteInput('Note to client', 'Optional note…', set.note,
            (v) => onSetNoteChanged(set, v)));
        return card;
    }

    function renderGroup(group, index) {
        const card = document.createElement('div');
        card.className = 'wc-set';
        card.dataset.groupLid = group.lid;

        const head = document.createElement('div');
        head.className = 'wc-set-head';
        const title = document.createElement('input');
        title.type = 'text';
        title.className = 'wc-group-name';
        title.placeholder = 'Group ' + (index + 1);
        title.maxLength = 200;
        title.value = group.name;
        title.title = 'Group name (optional)';
        title.addEventListener('input', () => onGroupFieldChanged(group, index, 'name', title.value));
        const actions = document.createElement('div');
        actions.className = 'wc-set-actions';
        actions.appendChild(iconButton('fa-clone', 'Duplicate group', false, () => duplicateGroup(group, index)));
        actions.appendChild(iconButton('fa-times', 'Remove group', true, () => removeGroup(group, index)));
        head.appendChild(title);
        head.appendChild(actions);
        card.appendChild(head);

        const body = document.createElement('div');
        body.className = 'wc-set-body';
        if (!group.sets.length) {
            const empty = document.createElement('div');
            empty.className = 'wc-set-empty';
            empty.textContent = 'Empty group — drop an exercise here';
            body.appendChild(empty);
        } else {
            group.sets.forEach((set, i) => body.appendChild(renderSet(group, set, i)));
        }
        card.appendChild(body);

        const meta = document.createElement('div');
        meta.className = 'wc-set-meta';
        meta.appendChild(noteInput('Note to client', 'Optional note for this group…', group.note,
            (v) => onGroupFieldChanged(group, index, 'note', v)));
        card.appendChild(meta);
        return card;
    }

    function render() {
        el.groups.innerHTML = '';
        state.groups.forEach((group, i) => el.groups.appendChild(renderGroup(group, i)));
    }

    // ---------- Save / Cancel ----------
    function validateAll() {
        const problems = [];
        let firstInvalid = null;

        if (!state.groups.length) problems.push('the workout has no groups');

        state.groups.forEach((group, gi) => {
            if (!group.sets.length) {
                problems.push('group ' + (gi + 1) + ' is empty');
                return;
            }
            group.sets.forEach((set) => {
                const ex = exerciseOf(set);
                PARAM_FIELDS.forEach((p) => {
                    if (!ex[p.flag]) return;
                    const v = set[p.field];
                    if (v === null || v === undefined || v <= 0) {
                        problems.push(ex.name + ' in group ' + (gi + 1) + ': ' + p.label.toLowerCase() + ' missing');
                        const input = el.groups.querySelector(
                            'input[data-set="' + set.lid + '"][data-field="' + p.field + '"]');
                        if (input) {
                            input.classList.add('wc-invalid');
                            firstInvalid = firstInvalid || input;
                        }
                    }
                });
            });
        });

        if (firstInvalid) firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return problems;
    }

    function doneUrl() {
        return KIND === 'workouts' ? '/workouts/' + state.target.id : '/admin/templates';
    }

    async function onSave() {
        if (!state.target.createEnqueued) {
            notify('Nothing to save yet — add exercises first.', 'warning');
            return;
        }
        const problems = validateAll();
        if (problems.length) {
            const extra = problems.length > 3 ? ' (+' + (problems.length - 3) + ' more)' : '';
            notify('Cannot save: ' + problems.slice(0, 3).join('; ') + extra, 'error');
            return;
        }
        if (!state.target.name.trim() &&
            !window.confirm('You haven\'t named this workout — save it as "' +
                            state.target.autoName + '"?')) {
            el.name.focus();
            return;
        }

        el.saveBtn.disabled = true;
        // Saving a template marks it ready (assignable); the server re-validates.
        if (KIND === 'templates') {
            sync.push('Mark template ready', async () => {
                await api(targetUrl(), { method: 'PUT', body: { status: 'ready' } });
            });
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

    // Cancel discards a template created in this session; for an existing template/workout
    // ("Back") changes are already saved live, so it just flushes and leaves.
    async function onCancel() {
        if (!IS_NEW) {
            el.cancelBtn.disabled = true;
            sync.retry();
            await sync.waitIdle();
            el.cancelBtn.disabled = false;
            if (sync.queue.length &&
                !window.confirm('Some changes are not saved yet. Leave anyway?')) return;
            allowUnload = true;
            window.location.href = doneUrl();
            return;
        }

        if (state.target.createEnqueued &&
            !window.confirm('Discard this workout and everything in it?')) return;

        el.cancelBtn.disabled = true;
        // Resolve the template id if the create op is still queued, then delete everything.
        sync.retry();
        await sync.waitIdle();
        sync.queue.length = 0;

        if (state.target.id) {
            try {
                await api(targetUrl(), { method: 'DELETE' });
            } catch (err) {
                el.cancelBtn.disabled = false;
                notify('Could not discard the workout: ' + err.message, 'error');
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
        if (ex.has_duration_s) parts.push('sec');
        if (ex.has_distance_m) parts.push('m');
        return parts.join(' · ');
    }

    function renderLibrary() {
        el.chips.innerHTML = '';
        DATA.exercises.forEach((ex) => {
            const chip = document.createElement('div');
            chip.className = 'wc-chip';
            chip.dataset.name = ex.name.toLowerCase();
            const strong = document.createElement('strong');
            strong.textContent = ex.name;
            const small = document.createElement('small');
            small.textContent = paramSummary(ex);
            chip.appendChild(strong);
            chip.appendChild(small);
            chip.title = ex.description || ex.name;
            initChipDrag(chip, ex);
            el.chips.appendChild(chip);
        });
    }

    el.search.addEventListener('input', () => {
        const term = el.search.value.trim().toLowerCase();
        el.chips.querySelectorAll('.wc-chip').forEach((chip) => {
            chip.classList.toggle('wc-hidden', term !== '' && chip.dataset.name.indexOf(term) === -1);
        });
    });

    // ---------- Drag & drop (pointer events: works for mouse AND touch) ----------
    const TOUCH_HOLD_MS = 250;    // long-press lifts the chip on touch (short swipe = scroll)
    const MOUSE_THRESHOLD = 5;    // px before a mouse press becomes a drag
    const TOUCH_CANCEL_DIST = 12; // px of early movement that means "scrolling, not dragging"

    let dropTarget = null; // {kind: 'group', group} | {kind: 'new'}

    function clearDropHighlight() {
        document.querySelectorAll('.wc-drop-target').forEach((n) => n.classList.remove('wc-drop-target'));
    }

    function updateDropTarget(x, y) {
        clearDropHighlight();
        dropTarget = null;
        const under = document.elementFromPoint(x, y);
        if (!under) return;
        const groupEl = under.closest('.wc-set');
        if (groupEl) {
            const group = state.groups.find((g) => String(g.lid) === groupEl.dataset.groupLid);
            if (group) {
                dropTarget = { kind: 'group', group: group };
                groupEl.classList.add('wc-drop-target');
            }
            return;
        }
        if (under.closest('#newGroupZone') || under.closest('.wc-main')) {
            dropTarget = { kind: 'new' };
            el.newGroupZone.classList.add('wc-drop-target');
        }
    }

    function autoScroll(y) {
        // The workout column scrolls itself on desktop; the window scrolls on mobile.
        const col = el.workoutColumn;
        const scrollable = col.scrollHeight > col.clientHeight + 4;
        const target = scrollable ? col : window;
        const top = scrollable ? col.getBoundingClientRect().top : 0;
        const bottom = scrollable ? col.getBoundingClientRect().bottom : window.innerHeight;
        if (y < top + 70) target.scrollBy(0, -14);
        else if (y > bottom - 90) target.scrollBy(0, 14);
    }

    function initChipDrag(chip, exercise) {
        chip.addEventListener('pointerdown', (down) => {
            if (down.button !== 0) return;
            const isTouch = down.pointerType !== 'mouse';
            const startX = down.clientX, startY = down.clientY;
            let ghost = null;
            let dragging = false;
            let holdTimer = null;

            function beginDrag(x, y) {
                dragging = true;
                try { chip.setPointerCapture(down.pointerId); } catch (_) { /* ignore */ }
                ghost = chip.cloneNode(true);
                ghost.classList.add('wc-ghost');
                ghost.style.width = chip.offsetWidth + 'px';
                document.body.appendChild(ghost);
                document.body.classList.add('wc-dragging');
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
                document.body.classList.remove('wc-dragging');
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
            if (document.body.classList.contains('wc-dragging')) e.preventDefault();
        });
    }

    // ---------- Wiring ----------
    el.name.value = state.target.name;
    el.description.value = state.target.description;
    el.duration.value = state.target.duration || '';
    el.note.value = state.target.note;
    if (el.date) el.date.value = state.target.date;
    if (!IS_NEW) {
        el.cancelBtn.innerHTML = '<i class="fas fa-arrow-left"></i> Back';
        setStatus('saved');
    }

    el.name.addEventListener('input', () => {
        el.name.classList.remove('wc-invalid');
        onDetailsChanged();
    });
    el.description.addEventListener('input', onDetailsChanged);
    el.duration.addEventListener('input', onDetailsChanged);
    el.note.addEventListener('input', onDetailsChanged);
    if (el.date) el.date.addEventListener('input', onDetailsChanged);

    el.addGroupBtn.addEventListener('click', addGroup);
    el.saveBtn.addEventListener('click', onSave);
    el.cancelBtn.addEventListener('click', onCancel);
    el.status.addEventListener('click', () => sync.retry());

    window.addEventListener('beforeunload', (e) => {
        if (!allowUnload && sync.queue.length) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    renderLibrary();
    render();
})();
