// Workout Composer: build workout templates (assigned to clients later) from
// drag-and-drop sets of exercises, with background live sync + Save/Cancel.
// Data contract: window.COMPOSER_DATA = { exercises }
(function () {
    'use strict';

    const DATA = window.COMPOSER_DATA || { exercises: [] };

    const el = {
        name: document.getElementById('wcName'),
        duration: document.getElementById('wcDuration'),
        description: document.getElementById('wcDescription'),
        sets: document.getElementById('setsContainer'),
        newSetZone: document.getElementById('newSetZone'),
        addSetBtn: document.getElementById('addSetBtn'),
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

    const state = {
        // autoName is the fallback used while the admin hasn't typed a name
        workout: { id: null, createEnqueued: false, name: '', autoName: 'Unnamed workout',
                   description: '', duration: null },
        sets: [] // { lid, id, rest_seconds, comment,
                 //   exercises: [{ lid, id, exercise_id, reps, weight_kg, duration_s, distance_m, comment }] }
    };

    const effectiveName = () => state.workout.name.trim() || state.workout.autoName;

    const exerciseById = (id) => DATA.exercises.find((e) => e.id === id);

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
                setStatus(state.workout.createEnqueued ? 'saved' : 'idle');
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

    // ---------- Workout lifecycle ----------
    // force=true (structural actions) creates the workout even without a name,
    // falling back to the "Unnamed workout N" placeholder.
    function maybeCreateWorkout(force) {
        const w = state.workout;
        if (w.createEnqueued) return;
        if (!force && !w.name.trim()) return;
        w.createEnqueued = true;
        sync.push('Create workout "' + effectiveName() + '"', async () => {
            const resp = await api('/api/workouts', {
                method: 'POST',
                body: { name: effectiveName(), description: w.description, duration_minutes: w.duration }
            });
            w.id = resp.id;
            if (!w.name.trim()) {
                w.autoName = 'Unnamed workout ' + resp.id;
                el.name.placeholder = w.autoName;
                await api('/api/workouts/' + w.id, { method: 'PUT', body: { name: w.autoName } });
            }
        });
    }

    let detailsTimer = null;
    function onDetailsChanged() {
        const w = state.workout;
        w.name = el.name.value;
        w.description = el.description.value;
        w.duration = el.duration.value ? parseInt(el.duration.value, 10) : null;
        if (!w.createEnqueued) { maybeCreateWorkout(); return; }

        clearTimeout(detailsTimer);
        detailsTimer = setTimeout(() => {
            sync.push('Update workout details', async () => {
                await api('/api/workouts/' + w.id, {
                    method: 'PUT',
                    body: { name: effectiveName(), description: w.description, duration_minutes: w.duration }
                });
            });
        }, 600);
    }

    // ---------- Structural actions ----------
    function newEntry(exerciseId) {
        return { lid: lid(), id: null, exercise_id: exerciseId,
                 reps: null, weight_kg: null, duration_s: null, distance_m: null, comment: '' };
    }

    function addSet() {
        maybeCreateWorkout(true);
        const set = { lid: lid(), id: null, rest_seconds: null, comment: '', exercises: [] };
        state.sets.push(set);
        render();
        sync.push('Add set ' + state.sets.length, async () => {
            const resp = await api('/api/workouts/' + state.workout.id + '/sets', { method: 'POST' });
            set.id = resp.id;
        });
        return set;
    }

    function addExerciseToSet(exerciseId, set) {
        maybeCreateWorkout(true);
        const ex = exerciseById(exerciseId);
        const entry = newEntry(exerciseId);
        set.exercises.push(entry);
        render();
        sync.push('Add ' + ex.name, async () => {
            const resp = await api('/api/sets/' + set.id + '/exercises', {
                method: 'POST', body: { exercise_id: exerciseId }
            });
            entry.id = resp.id;
        });
    }

    function addExerciseAsNewSet(exerciseId) {
        const set = addSet();
        addExerciseToSet(exerciseId, set);
    }

    function duplicateSet(set, index) {
        const copy = {
            lid: lid(), id: null, rest_seconds: set.rest_seconds, comment: set.comment,
            exercises: set.exercises.map((entry) => Object.assign({}, entry, { lid: lid(), id: null }))
        };
        state.sets.splice(index + 1, 0, copy);
        render();
        sync.push('Duplicate set ' + (index + 1), async () => {
            const resp = await api('/api/sets/' + set.id + '/duplicate', { method: 'POST' });
            copy.id = resp.id;
            resp.exercises.forEach((serverEntry, i) => {
                if (copy.exercises[i]) copy.exercises[i].id = serverEntry.id;
            });
        });
    }

    function removeSet(set, index) {
        if (set.exercises.length &&
            !window.confirm('Remove set ' + (index + 1) + ' with ' + set.exercises.length + ' exercise(s)?')) return;
        state.sets.splice(index, 1);
        render();
        sync.push('Remove set ' + (index + 1), async () => {
            await api('/api/sets/' + set.id, { method: 'DELETE' });
        });
    }

    function duplicateEntry(set, entry, entryIndex) {
        const ex = exerciseById(entry.exercise_id);
        const copy = Object.assign({}, entry, { lid: lid(), id: null });
        set.exercises.splice(entryIndex + 1, 0, copy);
        render();
        sync.push('Duplicate ' + ex.name, async () => {
            const resp = await api('/api/exercise-sets/' + entry.id + '/duplicate', { method: 'POST' });
            copy.id = resp.id;
        });
    }

    function removeEntry(set, entry, entryIndex) {
        const ex = exerciseById(entry.exercise_id);
        set.exercises.splice(entryIndex, 1);
        render();
        sync.push('Remove ' + ex.name, async () => {
            await api('/api/exercise-sets/' + entry.id, { method: 'DELETE' });
        });
    }

    // ---------- Debounced field sync ----------
    const fieldTimers = {};
    function debouncedPush(key, label, run) {
        clearTimeout(fieldTimers[key]);
        fieldTimers[key] = setTimeout(() => sync.push(label, run), 600);
    }

    function onEntryParamChanged(entry, field, label, rawValue) {
        const value = rawValue === '' ? null : parseFloat(rawValue);
        if (value === null || isNaN(value) || value <= 0) return; // DB CHECKs require positive values
        entry[field] = value;
        const ex = exerciseById(entry.exercise_id);
        debouncedPush(entry.lid + ':' + field, ex.name + ': ' + label + ' = ' + value, async () => {
            const body = {};
            body[field] = value;
            await api('/api/exercise-sets/' + entry.id, { method: 'PUT', body: body });
        });
    }

    function onEntryCommentChanged(entry, rawValue) {
        entry.comment = rawValue;
        const ex = exerciseById(entry.exercise_id);
        debouncedPush(entry.lid + ':comment', 'Note on ' + ex.name, async () => {
            await api('/api/exercise-sets/' + entry.id, { method: 'PUT', body: { comment: entry.comment } });
        });
    }

    function pushSetFields(set, label) {
        debouncedPush(set.lid + ':meta', label, async () => {
            await api('/api/sets/' + set.id, {
                method: 'PUT',
                body: { rest_seconds: set.rest_seconds, comment: set.comment }
            });
        });
    }

    function onSetRestChanged(set, index, rawValue) {
        const value = rawValue === '' ? null : parseInt(rawValue, 10);
        if (value === null || isNaN(value) || value < 0) return;
        set.rest_seconds = value;
        pushSetFields(set, 'Set ' + (index + 1) + ': rest = ' + value + 's');
    }

    function onSetCommentChanged(set, index, rawValue) {
        set.comment = rawValue;
        pushSetFields(set, 'Note on set ' + (index + 1));
    }

    // ---------- Rendering ----------
    const PARAM_FIELDS = [
        { field: 'reps', label: 'Reps', flag: 'has_reps', step: '1' },
        { field: 'weight_kg', label: 'Weight, kg', flag: 'has_weight_kg', step: '0.5' },
        { field: 'duration_s', label: 'Duration, s', flag: 'has_duration_s', step: '5' },
        { field: 'distance_m', label: 'Distance, m', flag: 'has_distance_m', step: '10' }
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

    function renderEntry(set, entry, entryIndex) {
        const ex = exerciseById(entry.exercise_id) ||
            { name: 'Unknown exercise', has_reps: true, has_weight_kg: true, has_duration_s: true, has_distance_m: true };

        const card = document.createElement('div');
        card.className = 'wc-entry';

        const head = document.createElement('div');
        head.className = 'wc-entry-head';
        const title = document.createElement('span');
        title.className = 'wc-entry-name';
        title.textContent = ex.name;
        const actions = document.createElement('div');
        actions.className = 'wc-entry-actions';
        actions.appendChild(iconButton('fa-clone', 'Duplicate exercise', false,
            () => duplicateEntry(set, entry, entryIndex)));
        actions.appendChild(iconButton('fa-times', 'Remove exercise', true,
            () => removeEntry(set, entry, entryIndex)));
        head.appendChild(title);
        head.appendChild(actions);
        card.appendChild(head);

        const params = document.createElement('div');
        params.className = 'wc-entry-params';
        PARAM_FIELDS.forEach((p) => {
            if (!ex[p.flag]) return;
            const wrap = document.createElement('div');
            wrap.className = 'wc-param';
            const label = document.createElement('label');
            label.textContent = p.label + ' *';
            const input = document.createElement('input');
            input.type = 'number';
            input.inputMode = 'decimal';
            input.step = p.step;
            input.min = p.step;
            input.placeholder = '—';
            input.dataset.entry = entry.lid;
            input.dataset.field = p.field;
            if (entry[p.field] !== null && entry[p.field] !== undefined) input.value = entry[p.field];
            input.addEventListener('input', () => {
                input.classList.remove('wc-invalid');
                onEntryParamChanged(entry, p.field, p.label, input.value);
            });
            wrap.appendChild(label);
            wrap.appendChild(input);
            params.appendChild(wrap);
        });
        card.appendChild(params);

        card.appendChild(noteInput('Note to client', 'Optional note…', entry.comment,
            (v) => onEntryCommentChanged(entry, v)));
        return card;
    }

    function renderSet(set, index) {
        const card = document.createElement('div');
        card.className = 'wc-set';
        card.dataset.setLid = set.lid;

        const head = document.createElement('div');
        head.className = 'wc-set-head';
        const title = document.createElement('span');
        title.className = 'wc-set-title';
        title.textContent = 'Set ' + (index + 1);
        const actions = document.createElement('div');
        actions.className = 'wc-set-actions';
        actions.appendChild(iconButton('fa-clone', 'Duplicate set', false, () => duplicateSet(set, index)));
        actions.appendChild(iconButton('fa-times', 'Remove set', true, () => removeSet(set, index)));
        head.appendChild(title);
        head.appendChild(actions);
        card.appendChild(head);

        const body = document.createElement('div');
        body.className = 'wc-set-body';
        if (!set.exercises.length) {
            const empty = document.createElement('div');
            empty.className = 'wc-set-empty';
            empty.textContent = 'Empty set — drop an exercise here';
            body.appendChild(empty);
        } else {
            set.exercises.forEach((entry, i) => body.appendChild(renderEntry(set, entry, i)));
        }
        card.appendChild(body);

        const meta = document.createElement('div');
        meta.className = 'wc-set-meta';
        const restWrap = document.createElement('div');
        restWrap.className = 'wc-param';
        const restLabel = document.createElement('label');
        restLabel.textContent = 'Rest after set, s';
        const restInput = document.createElement('input');
        restInput.type = 'number';
        restInput.inputMode = 'numeric';
        restInput.min = '0';
        restInput.step = '5';
        restInput.placeholder = '—';
        if (set.rest_seconds !== null && set.rest_seconds !== undefined) restInput.value = set.rest_seconds;
        restInput.addEventListener('input', () => onSetRestChanged(set, index, restInput.value));
        restWrap.appendChild(restLabel);
        restWrap.appendChild(restInput);
        meta.appendChild(restWrap);
        meta.appendChild(noteInput('Note to client', 'Optional note for this set…', set.comment,
            (v) => onSetCommentChanged(set, index, v)));
        card.appendChild(meta);
        return card;
    }

    function render() {
        el.sets.innerHTML = '';
        state.sets.forEach((set, i) => el.sets.appendChild(renderSet(set, i)));
    }

    // ---------- Save / Cancel ----------
    function validateAll() {
        const problems = [];
        let firstInvalid = null;

        if (!state.sets.length) problems.push('the workout has no sets');

        state.sets.forEach((set, si) => {
            if (!set.exercises.length) {
                problems.push('set ' + (si + 1) + ' is empty');
                return;
            }
            set.exercises.forEach((entry) => {
                const ex = exerciseById(entry.exercise_id);
                if (!ex) return;
                PARAM_FIELDS.forEach((p) => {
                    if (!ex[p.flag]) return;
                    const v = entry[p.field];
                    if (v === null || v === undefined || v <= 0) {
                        problems.push(ex.name + ' in set ' + (si + 1) + ': ' + p.label.toLowerCase() + ' missing');
                        const input = el.sets.querySelector(
                            'input[data-entry="' + entry.lid + '"][data-field="' + p.field + '"]');
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

    async function onSave() {
        if (!state.workout.createEnqueued) {
            notify('Nothing to save yet — add exercises first.', 'warning');
            return;
        }
        const problems = validateAll();
        if (problems.length) {
            const extra = problems.length > 3 ? ' (+' + (problems.length - 3) + ' more)' : '';
            notify('Cannot save: ' + problems.slice(0, 3).join('; ') + extra, 'error');
            return;
        }
        if (!state.workout.name.trim() &&
            !window.confirm('You haven\'t named this workout — save it as "' +
                            state.workout.autoName + '"?')) {
            el.name.focus();
            return;
        }

        el.saveBtn.disabled = true;
        sync.retry();
        await sync.waitIdle();
        el.saveBtn.disabled = false;

        if (sync.queue.length) return; // failure toast already shown by the queue
        allowUnload = true;
        notify('Workout saved!', 'success');
        setTimeout(() => { window.location.href = '/admin/dashboard'; }, 400);
    }

    async function onCancel() {
        if (state.workout.createEnqueued &&
            !window.confirm('Discard this workout and everything in it?')) return;

        el.cancelBtn.disabled = true;
        // Resolve the workout id if the create op is still queued, then delete everything.
        sync.retry();
        await sync.waitIdle();
        sync.queue.length = 0;

        if (state.workout.id) {
            try {
                await api('/api/workouts/' + state.workout.id, { method: 'DELETE' });
            } catch (err) {
                el.cancelBtn.disabled = false;
                notify('Could not discard the workout: ' + err.message, 'error');
                return;
            }
        }
        allowUnload = true;
        window.location.href = '/admin/dashboard';
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

    let dropTarget = null; // {kind: 'set', set} | {kind: 'new'}

    function clearDropHighlight() {
        document.querySelectorAll('.wc-drop-target').forEach((n) => n.classList.remove('wc-drop-target'));
    }

    function updateDropTarget(x, y) {
        clearDropHighlight();
        dropTarget = null;
        const under = document.elementFromPoint(x, y);
        if (!under) return;
        const setEl = under.closest('.wc-set');
        if (setEl) {
            const set = state.sets.find((s) => String(s.lid) === setEl.dataset.setLid);
            if (set) {
                dropTarget = { kind: 'set', set: set };
                setEl.classList.add('wc-drop-target');
            }
            return;
        }
        if (under.closest('#newSetZone') || under.closest('.wc-main')) {
            dropTarget = { kind: 'new' };
            el.newSetZone.classList.add('wc-drop-target');
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
                if (finalTarget.kind === 'set') addExerciseToSet(exercise.id, finalTarget.set);
                else addExerciseAsNewSet(exercise.id);
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
    el.name.addEventListener('input', () => {
        el.name.classList.remove('wc-invalid');
        onDetailsChanged();
    });
    el.description.addEventListener('input', onDetailsChanged);
    el.duration.addEventListener('input', onDetailsChanged);

    el.addSetBtn.addEventListener('click', addSet);
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
