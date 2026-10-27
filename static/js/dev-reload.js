// Dev-only live reload, loaded when DEV_RELOAD=1 (see /__dev/version in app.py).
// CSS edits swap the stylesheets without losing page state; template/JS edits reload the page;
// a server restart (Python edit) reloads once the server answers again.
(function () {
    let last = null;
    let down = false;

    function swapCss() {
        document.querySelectorAll('link[rel="stylesheet"][href^="/static/"]').forEach((link) => {
            const url = new URL(link.href);
            url.searchParams.set('v', Date.now());
            link.href = url.toString();
        });
    }

    async function check() {
        try {
            const res = await fetch('/__dev/version', { cache: 'no-store' });
            const v = await res.json();
            if (down) return location.reload();
            if (last && v.page !== last.page) return location.reload();
            if (last && v.css !== last.css) swapCss();
            last = v;
        } catch (e) {
            down = true;
        }
    }

    setInterval(check, 700);
    check();
})();
