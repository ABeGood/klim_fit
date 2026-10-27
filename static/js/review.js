// Coach's review of a client workout: targets vs what the client did, per group, plus the chat.
// Clicking a set's/group's chat button filters the chat to that thread; replies go to the shown thread.
// Data contract: window.WORKOUT_DATA = { workout, groups, comments, viewer: { id, is_admin } }
(function () {
    'use strict';

    const { api, h, ICONS, notify, targetText, timeLabel } = window.FitCoach;
    const DATA = window.WORKOUT_DATA;
    const workout = DATA.workout;
    const viewer = DATA.viewer;
    const firstName = (workout.client_name || 'client').split(' ')[0];

    const groupLabel = (g, i) => g.name || 'Group ' + (i + 1);
    const setById = {}, groupById = {};
    // Labels used by the chat ("Bench Press · set 2"); rebuilt whenever sets are added/removed
    function rebuildLabels() {
        DATA.groups.forEach((g, gi) => {
            groupById[g.id] = { label: groupLabel(g, gi) };
            g.sets.forEach((s, si) => { setById[s.id] = { label: s.exercise_name + ' · set ' + (si + 1) }; });
        });
    }
    rebuildLabels();

    // ---------- Status ----------
    const badge = document.getElementById('statusBadge');
    function refreshStatus() {
        const allSets = DATA.groups.reduce((acc, g) => acc.concat(g.sets), []);
        const doneCount = allSets.filter((s) => s.completed_at).length;
        if (workout.completed) { badge.className = 'badge badge-blue'; badge.textContent = 'Completed · ' + doneCount + '/' + allSets.length + ' sets'; }
        else if (doneCount) { badge.className = 'badge badge-orange'; badge.textContent = 'In progress · ' + doneCount + '/' + allSets.length + ' sets'; }
        else { badge.className = 'badge'; badge.textContent = 'Not started · 0/' + allSets.length + ' sets'; }
        badge.style.fontSize = '13px'; badge.style.padding = '5px 10px';
    }
    refreshStatus();

    // ---------- Chat store ----------
    const keyOf = (c) => c.set_id ? 's' + c.set_id : c.group_id ? 'g' + c.group_id : 'w';
    const contextOf = (key) => key[0] === 's' ? setById[key.slice(1)].label
        : key[0] === 'g' ? groupById[key.slice(1)].label : 'the workout';
    const comments = DATA.comments.slice();
    const countOf = (key) => comments.filter((c) => keyOf(c) === key).length;
    let filter = null; // null = all messages, else a thread key

    const threadButtons = {};
    function threadButton(key, attach) {
        const btn = h('button', { type: 'button', class: 'thread-btn' });
        const refresh = () => {
            const n = countOf(key);
            btn.className = 'thread-btn' + (n ? ' has' : '');
            btn.textContent = n ? n + (n === 1 ? ' message' : ' messages') : 'Comment';
            btn.setAttribute('aria-label', 'Chat about ' + contextOf(key) + (n ? ', ' + n + ' messages' : ''));
        };
        btn.addEventListener('click', () => { filter = key; renderChat(); document.getElementById('chatInput').focus(); });
        threadButtons[key] = refresh;
        refresh();
        return btn;
    }

    // ---------- Groups ----------
    // Not completed: targets, rest and note are editable in place (each change saves on its own), and a set
    // can be duplicated or removed. Completed workouts are frozen (the API refuses edits), so they're read-only.
    const EDITABLE = !workout.completed;
    const PARAMS = [
        { key: 'weight_kg', label: 'kg', step: '0.5' },
        { key: 'reps', label: 'reps', step: '1' },
        { key: 'duration_s', label: 's', step: '5' },
        { key: 'distance_m', label: 'm', step: '10' }
    ];

    async function saveSetField(set, field, input, raw, allowZero) {
        let value = null;
        if (raw !== '') {
            value = parseFloat(raw);
            if (isNaN(value) || value < 0 || (!allowZero && value === 0)) {
                notify('Enter a number greater than 0' + (allowZero ? ' (or 0)' : '') + ', or leave it empty.', 'warning');
                input.value = set[field] == null ? '' : set[field];
                return;
            }
        }
        if (value === set[field] || (value === null && set[field] == null)) return;
        const body = {};
        body[field] = value;
        input.classList.remove('saved');
        try {
            const updated = await api('/api/workouts/sets/' + set.id, 'PUT', body);
            set[field] = updated[field];
            input.classList.add('saved');
            setTimeout(() => input.classList.remove('saved'), 1200);
        } catch (err) {
            notify('Not saved: ' + err.message, 'error');
            input.value = set[field] == null ? '' : set[field];
        }
    }

    function targetEditor(set) {
        const wrap = h('div', { class: 'inline-fields' });
        PARAMS.forEach((p) => {
            if (!set['has_' + p.key]) return;
            const input = h('input', { type: 'number', class: 'inline-num', step: p.step, min: '0', inputmode: 'decimal',
                                       placeholder: '—', 'aria-label': set.exercise_name + ' target ' + p.label });
            if (set['target_' + p.key] != null) input.value = set['target_' + p.key];
            input.addEventListener('change', () => saveSetField(set, 'target_' + p.key, input, input.value, false));
            wrap.appendChild(h('label', { class: 'inline-field' }, input, h('span', {}, p.label)));
        });
        return wrap;
    }

    function restEditor(set) {
        const input = h('input', { type: 'number', class: 'inline-num', step: '5', min: '0', inputmode: 'numeric',
                                   placeholder: '—', 'aria-label': set.exercise_name + ' rest after, seconds' });
        if (set.rest_seconds != null) input.value = set.rest_seconds;
        input.addEventListener('change', () => saveSetField(set, 'rest_seconds', input, input.value, true));
        return h('label', { class: 'inline-field' }, input, h('span', {}, 's'));
    }

    function noteEditor(set) {
        const input = h('input', { type: 'text', class: 'inline-text', maxlength: '500', placeholder: 'Add a note…',
                                   'aria-label': 'Note on ' + set.exercise_name });
        input.value = set.note || '';
        input.addEventListener('change', async () => {
            const text = input.value.trim();
            if (text === (set.note || '')) return;
            try {
                const updated = await api('/api/workouts/sets/' + set.id, 'PUT', { note: text });
                set.note = updated.note;
                input.classList.add('saved');
                setTimeout(() => input.classList.remove('saved'), 1200);
            } catch (err) {
                notify('Not saved: ' + err.message, 'error');
            }
        });
        return input;
    }

    async function duplicateSet(group, set) {
        try {
            const copy = await api('/api/workouts/sets/' + set.id + '/duplicate', 'POST');
            group.sets.splice(group.sets.indexOf(set) + 1, 0, copy);
            rerender();
        } catch (err) {
            notify('Could not duplicate: ' + err.message, 'error');
        }
    }

    async function removeSet(group, set) {
        const logged = set.completed_at || PARAMS.some((p) => set['actual_' + p.key] != null);
        const msgs = countOf('s' + set.id);
        const warn = [logged ? 'the client\'s logged results' : '', msgs ? msgs + ' chat message(s)' : ''].filter(Boolean);
        if (!confirm('Remove ' + set.exercise_name + ' set ' + (group.sets.indexOf(set) + 1) + '?' +
                     (warn.length ? ' This also deletes ' + warn.join(' and ') + '.' : ''))) return;
        try {
            await api('/api/workouts/sets/' + set.id, 'DELETE');
            group.sets.splice(group.sets.indexOf(set), 1);
            for (let i = comments.length - 1; i >= 0; i--) if (comments[i].set_id === set.id) comments.splice(i, 1);
            if (filter === 's' + set.id) filter = null;
            rerender();
        } catch (err) {
            notify('Could not remove: ' + err.message, 'error');
        }
    }

    function renderGroups() {
        const container = document.getElementById('groups');
        container.innerHTML = '';
        if (!DATA.groups.length) {
            container.appendChild(h('div', { class: 'card empty' }, 'This workout has no exercises.'));
            return;
        }
        DATA.groups.forEach((group, gi) => {
            const card = h('section', { class: 'card', style: 'overflow: hidden', 'aria-label': groupLabel(group, gi) });
            card.appendChild(h('div', { style: 'display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 18px 6px; flex-wrap: wrap' },
                h('div', {},
                    h('h2', { style: 'font-size: 17px; font-weight: 800' }, groupLabel(group, gi)),
                    group.note ? h('div', { class: 'muted', style: 'font-size: 13px; font-style: italic' }, '“' + group.note + '”') : null),
                threadButton('g' + group.id)));
            const tbody = h('tbody');
            if (!group.sets.length) tbody.appendChild(h('tr', {}, h('td', { colspan: '7', class: 'empty' }, 'No sets in this group.')));
            group.sets.forEach((s, si) => {
                const done = s.completed_at
                    ? h('span', { class: 'done-mark', html: ICONS.check.replace(/22/g, '16') }, ' ' + targetText(s, 'actual_'))
                    : h('span', { style: 'color: var(--faint); font-weight: 600' }, 'Not yet');
                const tr = EDITABLE
                    ? h('tr', { 'data-key': 's' + s.id },
                        h('td', { class: 'set-no', style: 'font-weight: 800; color: var(--muted); width: 36px' }, String(si + 1)),
                        h('td', { class: 'set-title', style: 'min-width: 170px' }, h('div', { style: 'font-weight: 600' }, h('span', { class: 'set-no-inline' }, (si + 1) + '. '), s.exercise_name), noteEditor(s)),
                        h('td', { 'data-label': 'Target' }, targetEditor(s)),
                        h('td', { 'data-label': 'Rest' }, restEditor(s)),
                        h('td', { 'data-label': 'Done' }, done),
                        h('td', { class: 'actions', style: 'text-align: right' }, threadButton('s' + s.id)),
                        h('td', { class: 'actions', style: 'white-space: nowrap; text-align: right' },
                            h('button', { type: 'button', class: 'icon-btn soft', html: ICONS.copy, title: 'Duplicate set',
                                          'aria-label': 'Duplicate ' + s.exercise_name + ' set ' + (si + 1), onclick: () => duplicateSet(group, s) }),
                            ' ',
                            h('button', { type: 'button', class: 'icon-btn soft', html: ICONS.x, title: 'Remove set',
                                          'aria-label': 'Remove ' + s.exercise_name + ' set ' + (si + 1), onclick: () => removeSet(group, s) })))
                    : h('tr', { 'data-key': 's' + s.id },
                        h('td', { class: 'set-no', style: 'font-weight: 800; color: var(--muted); width: 36px' }, String(si + 1)),
                        h('td', { class: 'set-title', style: 'font-weight: 600' }, h('span', { class: 'set-no-inline' }, (si + 1) + '. '), s.exercise_name, s.note ? h('span', { class: 'sub' }, s.note) : null),
                        h('td', { 'data-label': 'Target' }, targetText(s)),
                        h('td', { 'data-label': 'Rest' }, s.rest_seconds != null ? s.rest_seconds + ' s' : '—'),
                        h('td', { 'data-label': 'Done' }, done),
                        h('td', { class: 'actions', style: 'text-align: right' }, threadButton('s' + s.id)));
                tbody.appendChild(tr);
            });
            const heads = ['Set', 'Exercise', 'Target', 'Rest', 'Done'].map((t) => h('th', { scope: 'col' }, t));
            heads.push(h('th', { scope: 'col', style: 'text-align: right' }, 'Chat'));
            if (EDITABLE) heads.push(h('th', { scope: 'col' }, h('span', { class: 'sr-only' }, 'Actions')));
            card.appendChild(h('div', { class: 'table-wrap' },
                h('table', { class: 'table review-table table-stack', style: 'min-width: ' + (EDITABLE ? 760 : 560) + 'px' },
                    h('thead', {}, h('tr', {}, ...heads)), tbody)));
            container.appendChild(card);
        });
    }

    function rerender() {
        rebuildLabels();
        renderGroups();
        renderChat();
        refreshStatus();
    }

    // ---------- Chat panel ----------
    const list = document.getElementById('chatMessages');
    const input = document.getElementById('chatInput');

    function renderChat() {
        const pills = document.getElementById('threadPills');
        pills.innerHTML = '';
        pills.appendChild(h('button', { type: 'button', class: 'pill', 'aria-pressed': filter === null ? 'true' : 'false',
            onclick: () => { filter = null; renderChat(); } }, 'All messages'));
        if (filter) pills.appendChild(h('button', { type: 'button', class: 'pill', 'aria-pressed': 'true' }, contextOf(filter)));

        document.querySelectorAll('tr.selected').forEach((tr) => tr.classList.remove('selected'));
        if (filter) { const tr = document.querySelector('tr[data-key="' + filter + '"]'); if (tr) tr.classList.add('selected'); }

        list.innerHTML = '';
        const shown = comments.filter((c) => filter === null || keyOf(c) === filter);
        if (!shown.length) list.appendChild(h('p', { class: 'empty' }, filter ? 'No messages about ' + contextOf(filter) + ' yet.' : 'No messages yet.'));
        shown.forEach((c) => {
            const mine = c.author_id === viewer.id;
            list.appendChild(h('div', { class: 'msg' + (mine ? ' mine' : '') },
                h('span', { class: 'msg-meta' }, (mine ? 'You' : c.author_name.split(' ')[0]) + ' · on ' + contextOf(keyOf(c)) + ' · ' + timeLabel(c.created_at)),
                h('div', { class: 'bubble' }, c.body)));
        });
        list.scrollTop = list.scrollHeight;
        input.placeholder = filter ? 'Reply about ' + contextOf(filter) + '…' : 'Message ' + firstName + ' about this workout…';
    }

    document.getElementById('chatForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        const attach = !filter ? {} : filter[0] === 's' ? { set_id: +filter.slice(1) } : { group_id: +filter.slice(1) };
        const send = e.target.querySelector('button');
        send.disabled = true;
        try {
            const comment = await api('/api/workouts/' + workout.id + '/comments', 'POST', Object.assign({ body: text }, attach));
            comments.push(comment);
            input.value = '';
            renderChat();
            if (threadButtons[keyOf(comment)]) threadButtons[keyOf(comment)]();
        } catch (err) {
            notify('Message not sent: ' + err.message, 'error');
        }
        send.disabled = false;
    });

    // Delete the whole workout (also its logged results and chat), then back to Clients
    document.getElementById('deleteWorkoutBtn').addEventListener('click', async () => {
        if (!confirm('Delete "' + workout.name + '" for ' + workout.client_name + '? ' +
                     'Their logged results and chat for it are deleted too. This can\'t be undone.')) return;
        try {
            await api('/api/workouts/' + workout.id, 'DELETE');
            window.location.href = '/admin/users';
        } catch (err) {
            notify('Could not delete: ' + err.message, 'error');
        }
    });

    renderGroups();
    renderChat();
})();
