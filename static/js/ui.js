// Shared helpers for the coach/client app screens (the auth pages use main.js).
// Exposes window.FitCoachUtils.showNotification (used by composer.js / workout pages) and window.FitCoach.
(function () {
    'use strict';

    function stack() {
        let el = document.querySelector('.flash-messages');
        if (!el) {
            el = document.createElement('div');
            el.className = 'flash-messages';
            el.setAttribute('role', 'status');
            document.body.appendChild(el);
        }
        return el;
    }

    function dismiss(alert) {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        setTimeout(() => alert.remove(), 250);
    }

    function wire(alert) {
        const close = alert.querySelector('.close-btn');
        if (close) close.addEventListener('click', () => dismiss(alert));
        setTimeout(() => { if (alert.parentElement) dismiss(alert); }, 5000);
    }

    function showNotification(message, type) {
        const alert = document.createElement('div');
        alert.className = 'alert alert-' + (type || 'info');
        const text = document.createElement('span');
        text.textContent = message;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'close-btn';
        close.setAttribute('aria-label', 'Dismiss');
        close.textContent = '×';
        alert.appendChild(text);
        alert.appendChild(close);
        stack().appendChild(alert);
        wire(alert);
    }

    // JSON fetch; throws Error(detail) on non-2xx
    async function api(url, method, body) {
        let resp;
        try {
            resp = await fetch(url, {
                method: method || 'GET',
                headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
                body: body !== undefined ? JSON.stringify(body) : undefined
            });
        } catch (err) {
            throw new Error('network unreachable');
        }
        if (!resp.ok) {
            let detail = '';
            try { detail = (await resp.json()).detail || ''; } catch (_) { /* not JSON */ }
            if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join('; ');
            throw new Error(detail || ('HTTP ' + resp.status));
        }
        return resp.json();
    }

    // Tiny element builder: h('div', {class: 'x', onclick: fn}, child, 'text', ...)
    function h(tag, attrs) {
        const el = document.createElement(tag);
        Object.entries(attrs || {}).forEach(([k, v]) => {
            if (v === null || v === undefined || v === false) return;
            if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
            else if (k === 'class') el.className = v;
            else if (k === 'html') el.innerHTML = v; // only ever static icon markup
            else el.setAttribute(k, v === true ? '' : v);
        });
        for (let i = 2; i < arguments.length; i++) {
            const child = arguments[i];
            if (child === null || child === undefined || child === false) continue;
            el.appendChild(typeof child === 'string' || typeof child === 'number' ? document.createTextNode(child) : child);
        }
        return el;
    }

    const ICONS = {
        check: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="5 12 10 17 19 7"></polyline></svg>',
        chat: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z"></path></svg>',
        back: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 6 9 12 15 18"></polyline></svg>',
        send: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>',
        up: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 15 12 9 18 15"></polyline></svg>',
        down: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>',
        x: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><line x1="6" y1="6" x2="18" y2="18"></line><line x1="18" y1="6" x2="6" y2="18"></line></svg>',
        copy: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
        grip: '<svg class="grip" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="9" cy="6" r="1.6"></circle><circle cx="15" cy="6" r="1.6"></circle><circle cx="9" cy="12" r="1.6"></circle><circle cx="15" cy="12" r="1.6"></circle><circle cx="9" cy="18" r="1.6"></circle><circle cx="15" cy="18" r="1.6"></circle></svg>',
        plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>'
    };

    // "Bench Press · 60 kg × 10" style target text for a set (has_* + target_* fields)
    function targetText(set, prefix) {
        const p = prefix || 'target_';
        const parts = [];
        if (set.has_weight_kg && set[p + 'weight_kg'] != null) parts.push(set[p + 'weight_kg'] + ' kg');
        if (set.has_reps && p === 'target_' && set.target_reps_max) parts.push('× max');
        else if (set.has_reps && set[p + 'reps'] != null) parts.push('× ' + set[p + 'reps']);
        if (set.has_duration_s && set[p + 'duration_s'] != null) parts.push(set[p + 'duration_s'] + ' s');
        if (set.has_distance_m && set[p + 'distance_m'] != null) parts.push(set[p + 'distance_m'] + ' m');
        return parts.join(' ') || '—';
    }

    function timeLabel(iso) {
        const d = new Date(iso);
        const today = new Date();
        const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);
        const hm = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (d.toDateString() === today.toDateString()) return hm;
        if (d.toDateString() === yesterday.toDateString()) return 'Yesterday ' + hm;
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + hm;
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.flash-messages .alert').forEach(wire);
    });

    window.FitCoachUtils = { showNotification: showNotification };
    window.FitCoach = { api: api, h: h, ICONS: ICONS, notify: showNotification, targetText: targetText, timeLabel: timeLabel };
})();
