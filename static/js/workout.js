// Workout page: the client logs actual values and ticks sets; coach and client chat on the
// workout, each group and each set.
// Data contract: window.WORKOUT_DATA = { workout, groups, comments, viewer: { id, is_admin } }
(function () {
    'use strict';

    const DATA = window.WORKOUT_DATA;
    const workout = DATA.workout;
    const viewer = DATA.viewer;
    const canLog = !viewer.is_admin; // results are the client's to enter; the coach reviews them

    const PARAMS = [
        { key: 'reps', label: 'Reps', unit: '', step: '1' },
        { key: 'weight_kg', label: 'Kg', unit: ' kg', step: '0.5' },
        { key: 'duration_s', label: 'Sec', unit: ' s', step: '5' },
        { key: 'distance_m', label: 'Metres', unit: ' m', step: '10' }
    ];

    function notify(message, type) {
        if (window.FitCoachUtils) { FitCoachUtils.showNotification(message, type); }
    }

    async function api(url, method, body) {
        const resp = await fetch(url, {
            method: method || 'GET',
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined
        });
        if (!resp.ok) {
            let detail = '';
            try { detail = (await resp.json()).detail || ''; } catch (_) { /* ignore */ }
            throw new Error(detail || ('HTTP ' + resp.status));
        }
        return resp.json();
    }

    function node(tag, className, text) {
        const n = document.createElement(tag);
        if (className) n.className = className;
        if (text !== undefined) n.textContent = text;
        return n;
    }

    // ---------- Chat ----------
    // A thread is identified by what it's attached to: { workout_id } | { group_id } | { set_id }
    const threadKey = (c) => c.set_id ? 's' + c.set_id : c.group_id ? 'g' + c.group_id : 'w';
    const threads = {}; // key -> [comment]
    DATA.comments.forEach((c) => { (threads[threadKey(c)] = threads[threadKey(c)] || []).push(c); });
    const threadViews = {}; // key -> function that re-renders that thread

    function renderThread(container, key, attach) {
        container.innerHTML = '';
        const list = node('div', 'wv-thread');
        (threads[key] || []).forEach((c) => {
            const msg = node('div', 'wv-msg' + (c.author_id === viewer.id ? ' mine' : ''));
            const when = new Date(c.created_at).toLocaleString();
            msg.appendChild(node('small', '', (c.author_role === 'admin' ? 'Coach ' : '') + c.author_name + ' · ' + when));
            msg.appendChild(document.createTextNode(c.body));
            list.appendChild(msg);
        });
        const form = node('form', 'wv-compose');
        const input = node('input');
        input.type = 'text';
        input.maxLength = 2000;
        input.placeholder = viewer.is_admin ? 'Reply to your client…' : 'Message your coach…';
        const send = node('button', 'btn btn-primary btn-sm no-loading');
        send.type = 'submit';
        send.innerHTML = '<i class="fas fa-paper-plane"></i>';
        form.appendChild(input);
        form.appendChild(send);
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            send.disabled = true;
            try {
                const comment = await api('/api/workouts/' + workout.id + '/comments', 'POST',
                    Object.assign({ body: text }, attach));
                (threads[key] = threads[key] || []).push(comment);
                threadViews[key]();
            } catch (err) {
                notify('Message not sent: ' + err.message, 'error');
                send.disabled = false;
            }
        });
        list.appendChild(form);
        container.appendChild(list);
    }

    // Collapsible thread for a group or set: "Comments (n)" toggles it open
    function chatToggle(key, attach) {
        const wrap = node('div');
        const toggle = node('button', 'wv-chat-toggle');
        toggle.type = 'button';
        const body = node('div');
        body.hidden = true;
        const label = () => {
            const n = (threads[key] || []).length;
            toggle.innerHTML = '<i class="fas fa-comment"></i> ' + (n ? 'Comments (' + n + ')' : 'Comment');
        };
        threadViews[key] = () => { renderThread(body, key, attach); label(); };
        toggle.addEventListener('click', () => {
            body.hidden = !body.hidden;
            if (!body.hidden) threadViews[key]();
        });
        label();
        wrap.appendChild(toggle);
        wrap.appendChild(body);
        return wrap;
    }

    // ---------- Sets ----------
    function targetText(set) {
        const parts = [];
        PARAMS.forEach((p) => {
            const v = set['target_' + p.key];
            if (set['has_' + p.key] && v !== null) parts.push(p.key === 'reps' ? '× ' + v : v + p.unit);
        });
        if (set.rest_seconds) parts.push('rest ' + set.rest_seconds + ' s');
        return parts.join(' · ');
    }

    async function saveResult(set, row, body) {
        try {
            const updated = await api('/api/workout-sets/' + set.id + '/result', 'PUT', body);
            Object.assign(set, updated);
            row.classList.toggle('done', !!set.completed_at);
            refreshStatus();
        } catch (err) {
            notify('Not saved: ' + err.message, 'error');
        }
    }

    function renderSet(set, index) {
        const row = node('div', 'wv-set' + (set.completed_at ? ' done' : ''));
        const head = node('div', 'wv-set-head');
        const title = node('div');
        title.appendChild(node('div', 'wv-set-name', (index + 1) + '. ' + set.exercise_name));
        title.appendChild(node('div', 'wv-target', targetText(set)));
        head.appendChild(title);
        row.appendChild(head);
        if (set.note) row.appendChild(node('div', 'wv-note', set.note));

        const results = node('div', 'wv-results');
        const inputs = {}; // param key -> its input
        PARAMS.forEach((p) => {
            if (!set['has_' + p.key]) return;
            const wrap = node('div');
            wrap.appendChild(node('label', '', p.label));
            const input = node('input');
            input.type = 'number';
            input.inputMode = 'decimal';
            input.step = p.step;
            input.min = '0';
            input.placeholder = set['target_' + p.key] !== null ? set['target_' + p.key] : '—';
            if (set['actual_' + p.key] !== null) input.value = set['actual_' + p.key];
            input.disabled = !canLog;
            inputs[p.key] = input;
            input.addEventListener('change', () => {
                const value = input.value === '' ? null : parseFloat(input.value);
                if (value !== null && !(value > 0)) { notify('Values must be greater than 0', 'warning'); return; }
                const body = {};
                body['actual_' + p.key] = value;
                saveResult(set, row, body);
            });
            wrap.appendChild(input);
            results.appendChild(wrap);
        });

        const done = node('label', 'wv-done');
        const check = node('input');
        check.type = 'checkbox';
        check.checked = !!set.completed_at;
        check.disabled = !canLog;
        check.addEventListener('change', () => {
            // Ticking a set with empty values logs the targets as done ("did it as planned")
            const body = { completed: check.checked };
            if (check.checked) {
                PARAMS.forEach((p) => {
                    if (set['has_' + p.key] && set['actual_' + p.key] === null && set['target_' + p.key] !== null) {
                        body['actual_' + p.key] = set['target_' + p.key];
                    }
                });
            }
            saveResult(set, row, body).then(() => {
                // reflect auto-filled actuals
                Object.keys(inputs).forEach((key) => {
                    if (set['actual_' + key] !== null) inputs[key].value = set['actual_' + key];
                });
            });
        });
        done.appendChild(check);
        done.appendChild(document.createTextNode(' Done'));
        results.appendChild(done);
        row.appendChild(results);

        row.appendChild(chatToggle('s' + set.id, { set_id: set.id }));
        return row;
    }

    function renderGroups() {
        const container = document.getElementById('wvGroups');
        if (!DATA.groups.length) {
            container.appendChild(node('p', 'empty-state', 'This workout has no exercises yet.'));
            return;
        }
        DATA.groups.forEach((group, gi) => {
            const card = node('div', 'wv-card');
            card.appendChild(node('div', 'wv-group-title', group.name || 'Group ' + (gi + 1)));
            if (group.note) card.appendChild(node('div', 'wv-note', group.note));
            group.sets.forEach((set, si) => card.appendChild(renderSet(set, si)));
            card.appendChild(chatToggle('g' + group.id, { group_id: group.id }));
            container.appendChild(card);
        });
    }

    // ---------- Workout status ----------
    async function refreshStatus() {
        try {
            const fresh = await api('/api/workouts/' + workout.id);
            const badge = document.getElementById('wvStatus');
            badge.className = 'status-badge ' + (fresh.completed ? 'completed' : 'pending');
            badge.textContent = fresh.completed ? 'Completed' : 'In progress';
            if (fresh.completed && !workout.completed) notify('Workout complete — great job!', 'success');
            workout.completed = fresh.completed;
        } catch (_) { /* status badge is cosmetic */ }
    }

    renderGroups();
    const workoutChat = document.getElementById('wvWorkoutChat');
    threadViews.w = () => renderThread(workoutChat, 'w', {});
    threadViews.w();
})();
