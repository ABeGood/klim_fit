// Client workout log: log actual values per set, tick sets done (rest timer after each), and chat
// with the coach on the workout, a group or a set (full-screen chat; the phone's back button closes it).
// Data contract: window.WORKOUT_DATA = { workout, groups, comments, viewer: { id, is_admin } }
(function () {
    'use strict';

    const { api, h, ICONS, notify, targetText, timeLabel } = window.FitCoach;
    const DATA = window.WORKOUT_DATA;
    const workout = DATA.workout;
    const viewer = DATA.viewer;
    const PARAMS = [
        { key: 'weight_kg', label: 'Kg', step: '0.5', mode: 'decimal' },
        { key: 'reps', label: 'Reps', step: '1', mode: 'numeric' },
        { key: 'duration_s', label: 'Sec', step: '5', mode: 'numeric' },
        { key: 'distance_m', label: 'M', step: '10', mode: 'numeric' }
    ];

    const allSets = [];
    DATA.groups.forEach((g, gi) => g.sets.forEach((s, si) => {
        s._group = g; s._groupIndex = gi; s._index = si;
        s._done = !!s.completed_at; // what the screen shows; completed_at = what the server confirmed
        allSets.push(s);
    }));
    const groupLabel = (g) => g.name || 'Group ' + (g._i + 1);
    DATA.groups.forEach((g, i) => { g._i = i; });

    // ---------- Progress ----------
    function refreshProgress() {
        const done = allSets.filter((s) => s._done).length;
        const total = allSets.length;
        const pct = total ? Math.round((done / total) * 100) : 0;
        document.getElementById('progressText').textContent = done + ' of ' + total + ' sets';
        document.getElementById('progressPct').textContent = pct + '%';
        const bar = document.getElementById('progressBar');
        bar.firstElementChild.style.width = pct + '%';
        bar.setAttribute('aria-valuenow', done);
        bar.setAttribute('aria-valuemax', total);
        const nowComplete = total > 0 && done === total;
        if (nowComplete && !workout.completed) notify('Workout complete — great job!', 'success');
        workout.completed = nowComplete;
    }

    // ---------- Rest timer ----------
    const rest = { left: 0, timer: null, setId: null };
    const restBar = document.getElementById('restBar');
    function showRest() {
        const m = Math.floor(rest.left / 60), s = rest.left % 60;
        document.getElementById('restClock').textContent = m + ':' + String(s).padStart(2, '0');
        restBar.hidden = rest.left <= 0;
        if (rest.left <= 0) { clearInterval(rest.timer); rest.timer = null; }
    }
    function startRest(seconds, nextSet, setId) {
        rest.left = seconds;
        rest.setId = setId;
        document.getElementById('restNext').textContent = 'Rest · next: ' + (nextSet ? nextSet.exercise_name : 'finish');
        clearInterval(rest.timer);
        rest.timer = setInterval(() => { rest.left -= 1; showRest(); }, 1000);
        showRest();
    }
    document.getElementById('restAdd').addEventListener('click', () => { rest.left += 15; showRest(); });
    document.getElementById('restSkip').addEventListener('click', () => { rest.left = 0; showRest(); });

    // ---------- Results ----------
    async function saveResult(set, body) {
        try {
            const updated = await api('/api/workout-sets/' + set.id + '/result', 'PUT', body);
            Object.assign(set, {
                actual_reps: updated.actual_reps, actual_weight_kg: updated.actual_weight_kg,
                actual_duration_s: updated.actual_duration_s, actual_distance_m: updated.actual_distance_m
            });
            // Only a tick/untick decides done-ness: a value-only save racing a tick may answer last with a stale state
            if ('completed' in body) set.completed_at = updated.completed_at;
            return true;
        } catch (err) {
            notify('Not saved: ' + err.message, 'error');
            return false;
        }
    }

    // ---------- Chat store ----------
    const threadKey = (c) => c.set_id ? 's' + c.set_id : c.group_id ? 'g' + c.group_id : 'w';
    const threads = {};
    DATA.comments.forEach((c) => (threads[threadKey(c)] = threads[threadKey(c)] || []).push(c));
    const countOf = (key) => (threads[key] || []).length;

    // ---------- Render groups ----------
    const chatButtons = {}; // thread key -> function refreshing its label

    // Names are the chat buttons: tapping a set's exercise name or a group's name opens that thread.
    // A small count appears next to the name once the thread has messages.
    function nameButton(key, cls, text, ariaName, open) {
        const btn = h('button', { type: 'button', class: 'name-btn ' + cls, onclick: open });
        const refresh = () => {
            const n = countOf(key);
            btn.setAttribute('aria-label', ariaName + ': ' + (n ? n + (n === 1 ? ' message' : ' messages') : 'comments'));
            btn.innerHTML = '';
            btn.appendChild(h('span', { class: 'name-text' }, text));
            if (n) btn.appendChild(h('span', { class: 'count' }, String(n)));
        };
        chatButtons[key] = refresh;
        refresh();
        return btn;
    }

    function renderSet(set, group, cols) {
        const row = h('div', { class: 'set-row' + (set.completed_at ? ' done' : '') });
        const grid = h('div', { class: 'set-grid', style: '--cols:' + cols.length + '; grid-template-columns: 30px minmax(0, 1fr) repeat(' + cols.length + ', ' + (cols.length > 2 ? 54 : 64) + 'px) 48px' });
        grid.appendChild(h('span', { class: 'set-num' }, String(set._index + 1)));
        grid.appendChild(nameButton('s' + set.id, 'set-name', set.exercise_name,
            set.exercise_name + ', set ' + (set._index + 1), () => openChat({ set_id: set.id })));

        const inputs = {};
        cols.forEach((p) => {
            if (!set['has_' + p.key]) { grid.appendChild(h('span', { class: 'set-blank' }, '—')); return; }
            const input = h('input', {
                type: 'number', class: 'set-input', inputmode: p.mode, step: p.step, min: '0',
                'aria-label': 'Set ' + (set._index + 1) + ' ' + set.exercise_name + ' ' + p.label,
                placeholder: p.key === 'reps' && set.target_reps_max ? 'max'
                    : set['target_' + p.key] != null ? String(set['target_' + p.key]) : '—'
            });
            if (cols.length > 2) input.style.width = '54px';
            if (set['actual_' + p.key] != null) input.value = set['actual_' + p.key];
            input.addEventListener('change', async () => {
                const value = input.value === '' ? null : parseFloat(input.value);
                if (value !== null && !(value > 0)) { notify('Values must be greater than 0', 'warning'); return; }
                const body = {};
                body['actual_' + p.key] = value;
                await saveResult(set, body);
            });
            inputs[p.key] = input;
            grid.appendChild(input);
        });

        const tick = h('button', {
            type: 'button', class: 'tick', html: ICONS.check,
            'aria-pressed': set.completed_at ? 'true' : 'false',
            'aria-label': 'Set ' + (set._index + 1) + ' ' + set.exercise_name + ' done'
        });
        // Optimistic: the tap updates the screen at once and the save runs in the background, one request
        // at a time per set. If a save fails, the set goes back to its last server-confirmed state.
        let saving = Promise.resolve();
        const showDone = () => {
            tick.setAttribute('aria-pressed', set._done ? 'true' : 'false');
            row.classList.toggle('done', set._done);
            refreshProgress();
        };
        tick.addEventListener('click', () => {
            const markDone = !set._done;
            const body = { completed: markDone };
            const filled = []; // empty fields we filled with the logged value, cleared again on failure
            // Every Done click saves what's in the fields, ticking or unticking. When ticking, an empty
            // field = "did it as planned": log the saved value or the target.
            PARAMS.forEach((p) => {
                if (!set['has_' + p.key]) return;
                const typed = inputs[p.key] && inputs[p.key].value !== '' ? parseFloat(inputs[p.key].value) : null;
                const value = typed !== null ? typed
                    : markDone ? (set['actual_' + p.key] != null ? set['actual_' + p.key] : set['target_' + p.key]) : null;
                if (value != null && value > 0) {
                    body['actual_' + p.key] = value;
                    if (typed === null && inputs[p.key]) { inputs[p.key].value = value; filled.push(inputs[p.key]); }
                }
            });

            set._done = markDone;
            showDone();
            if (markDone && set.rest_seconds > 0) {
                startRest(set.rest_seconds, allSets.find((s) => !s._done && allSets.indexOf(s) > allSets.indexOf(set)), set.id);
            } else if (!markDone && rest.setId === set.id) {
                rest.left = 0; showRest();
            }

            saving = saving.then(async () => {
                const ok = await saveResult(set, body);
                if (ok) return;
                filled.forEach((input) => { input.value = ''; });
                set._done = !!set.completed_at;
                showDone();
                if (!set._done && rest.setId === set.id) { rest.left = 0; showRest(); }
            });
        });
        grid.appendChild(tick);
        row.appendChild(grid);

        // Keyboard: Enter → next value in this set; Enter on its last value ticks the set and jumps to the
        // next set's first value. Shift+Enter goes back. Values are selected on focus so typing replaces them.
        const order = Object.values(inputs);
        order.forEach((input, i) => {
            input.addEventListener('focus', () => { try { input.select(); } catch (_) { /* ignore */ } });
            input.addEventListener('keydown', async (e) => {
                if (e.key !== 'Enter' || e.isComposing) return;
                e.preventDefault();
                const all = Array.from(document.querySelectorAll('.set-input'));
                if (e.shiftKey) { const prev = all[all.indexOf(input) - 1]; if (prev) prev.focus(); return; }
                if (i < order.length - 1) { order[i + 1].focus(); return; }
                if (!set._done) tick.click();                        // the tick saves the typed values too
                const later = all.slice(all.indexOf(input) + 1)
                    .find((x) => !x.closest('.set-row').classList.contains('done'));
                if (later) later.focus(); else input.blur();
            });
        });
        if (!order.length) tick.setAttribute('aria-keyshortcuts', 'Enter');

        if (set.note) row.appendChild(h('div', { class: 'set-note' }, set.note));
        return row;
    }

    function renderGroups() {
        const container = document.getElementById('groups');
        if (!DATA.groups.length) {
            container.appendChild(h('div', { class: 'card empty' }, 'This workout has no exercises yet.'));
            return;
        }
        DATA.groups.forEach((group) => {
            const cols = PARAMS.filter((p) => group.sets.some((s) => s['has_' + p.key]));
            const card = h('section', { class: 'card group-card', 'aria-label': groupLabel(group) });
            card.appendChild(h('div', { class: 'group-head' },
                h('h2', {}, nameButton('g' + group.id, 'group-name', groupLabel(group), groupLabel(group),
                    () => openChat({ group_id: group.id }))),
                h('span', { class: 'muted', style: 'font-size: 13px; font-weight: 600' },
                    group.sets.length + (group.sets.length === 1 ? ' set' : ' sets'))));
            if (group.note) card.appendChild(h('p', { class: 'group-note' }, '“' + group.note + '”'));
            if (group.sets.length) {
                const head = h('div', { class: 'set-grid head', 'aria-hidden': 'true',
                    style: '--cols:' + cols.length + '; grid-template-columns: 30px minmax(0, 1fr) repeat(' + cols.length + ', ' + (cols.length > 2 ? 54 : 64) + 'px) 48px' },
                    h('span', {}, 'Set'), h('span', {}, 'Exercise'));
                cols.forEach((p) => head.appendChild(h('span', { style: 'text-align: center' }, p.label)));
                head.appendChild(h('span'));
                card.appendChild(head);
            }
            group.sets.forEach((set) => card.appendChild(renderSet(set, group, cols)));
            container.appendChild(card);
        });
    }

    // ---------- Chat screen ----------
    const screen = document.getElementById('chatScreen');
    const list = document.getElementById('chatMessages');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    let current = null; // { key, attach }

    function renderMessages() {
        list.innerHTML = '';
        const msgs = threads[current.key] || [];
        if (!msgs.length) list.appendChild(h('p', { class: 'empty' }, 'No messages yet — ask your coach anything about this.'));
        msgs.forEach((c) => {
            const mine = c.author_id === viewer.id;
            list.appendChild(h('div', { class: 'msg' + (mine ? ' mine' : '') },
                h('span', { class: 'msg-meta' }, (mine ? 'You' : (c.author_role === 'admin' ? 'Coach ' : '') + c.author_name) + ' · ' + timeLabel(c.created_at)),
                h('div', { class: 'bubble' }, c.body)));
        });
        list.scrollTop = list.scrollHeight;
    }

    function openChat(attach, fromHistory) {
        const key = attach.set_id ? 's' + attach.set_id : attach.group_id ? 'g' + attach.group_id : 'w';
        current = { key: key, attach: attach };
        const facts = document.getElementById('chatFacts');
        facts.innerHTML = '';
        if (attach.set_id) {
            const set = allSets.find((s) => s.id === attach.set_id);
            document.getElementById('chatTitle').textContent = set.exercise_name + ' · Set ' + (set._index + 1);
            document.getElementById('chatSub').textContent = groupLabel(set._group);
            facts.appendChild(h('div', { class: 'fact' }, h('small', {}, 'Target'), h('strong', {}, targetText(set))));
            facts.appendChild(h('div', { class: 'fact' + (set.completed_at ? ' done' : '') }, h('small', {}, 'Done'),
                h('strong', {}, set.completed_at ? targetText(set, 'actual_') : 'Not yet')));
        } else if (attach.group_id) {
            const group = DATA.groups.find((g) => g.id === attach.group_id);
            document.getElementById('chatTitle').textContent = groupLabel(group);
            document.getElementById('chatSub').textContent = 'Chat with your coach about this group';
        } else {
            document.getElementById('chatTitle').textContent = 'Workout chat';
            document.getElementById('chatSub').textContent = 'Chat with your coach about this workout';
        }
        screen.hidden = false;
        document.body.style.overflow = 'hidden';
        if (!fromHistory) history.pushState({ chat: attach }, '');
        renderMessages();
        input.focus();
    }

    function closeChat() {
        screen.hidden = true;
        document.body.style.overflow = '';
        current = null;
    }

    document.getElementById('chatBack').addEventListener('click', () => history.back());
    window.addEventListener('popstate', (e) => {
        if (e.state && e.state.chat) openChat(e.state.chat, true);
        else closeChat();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text || !current) return;
        const send = form.querySelector('button');
        send.disabled = true;
        try {
            const comment = await api('/api/workouts/' + workout.id + '/comments', 'POST', Object.assign({ body: text }, current.attach));
            (threads[current.key] = threads[current.key] || []).push(comment);
            input.value = '';
            renderMessages();
            if (chatButtons[current.key]) chatButtons[current.key]();
            refreshWorkoutPreview();
        } catch (err) {
            notify('Message not sent: ' + err.message, 'error');
        }
        send.disabled = false;
    });

    function refreshWorkoutPreview() {
        const msgs = threads.w || [];
        const last = msgs[msgs.length - 1];
        if (last) document.getElementById('workoutChatPreview').textContent =
            (last.author_id === viewer.id ? 'You' : 'Coach') + ': ' + last.body;
    }

    document.getElementById('workoutChatBtn').addEventListener('click', () => openChat({}));

    renderGroups();
    workout.completed = allSets.length > 0 && allSets.every((s) => s.completed_at);
    refreshProgress();
    refreshWorkoutPreview();
})();
