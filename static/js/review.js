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
    DATA.groups.forEach((g, gi) => {
        groupById[g.id] = { label: groupLabel(g, gi) };
        g.sets.forEach((s, si) => { setById[s.id] = { label: s.exercise_name + ' · set ' + (si + 1) }; });
    });

    // ---------- Status ----------
    const allSets = DATA.groups.reduce((acc, g) => acc.concat(g.sets), []);
    const doneCount = allSets.filter((s) => s.completed_at).length;
    const badge = document.getElementById('statusBadge');
    if (workout.completed) { badge.className = 'badge badge-blue'; badge.textContent = 'Completed · ' + doneCount + '/' + allSets.length + ' sets'; }
    else if (doneCount) { badge.className = 'badge badge-orange'; badge.textContent = 'In progress · ' + doneCount + '/' + allSets.length + ' sets'; }
    else { badge.className = 'badge'; badge.textContent = 'Not started · 0/' + allSets.length + ' sets'; }
    badge.style.fontSize = '13px'; badge.style.padding = '5px 10px';

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
    function renderGroups() {
        const container = document.getElementById('groups');
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
            group.sets.forEach((s, si) => {
                const tr = h('tr', { 'data-key': 's' + s.id },
                    h('td', { style: 'font-weight: 800; color: var(--muted); width: 40px' }, String(si + 1)),
                    h('td', { style: 'font-weight: 600' }, s.exercise_name, s.note ? h('span', { class: 'sub' }, s.note) : null),
                    h('td', {}, targetText(s), s.rest_seconds ? h('span', { class: 'sub' }, 'rest ' + s.rest_seconds + ' s') : null),
                    h('td', {}, s.completed_at
                        ? h('span', { class: 'done-mark', html: ICONS.check.replace(/22/g, '16') }, ' ' + targetText(s, 'actual_'))
                        : h('span', { style: 'color: var(--faint); font-weight: 600' }, 'Not yet')),
                    h('td', { style: 'text-align: right' }, threadButton('s' + s.id)));
                tbody.appendChild(tr);
            });
            card.appendChild(h('div', { class: 'table-wrap' },
                h('table', { class: 'table', style: 'min-width: 520px' },
                    h('thead', {}, h('tr', {},
                        h('th', { scope: 'col' }, 'Set'), h('th', { scope: 'col' }, 'Exercise'),
                        h('th', { scope: 'col' }, 'Target'), h('th', { scope: 'col' }, 'Done'),
                        h('th', { scope: 'col', style: 'text-align: right' }, 'Chat'))),
                    tbody)));
            container.appendChild(card);
        });
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

    renderGroups();
    renderChat();
})();
