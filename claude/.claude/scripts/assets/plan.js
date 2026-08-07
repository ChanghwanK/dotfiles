/* Plan preview interactions — inlined into the output by plan-to-html.py.
 *
 * Everything here is progressive enhancement. The decision form is a plain
 * POST and must keep working if this file throws, so nothing below is allowed
 * to be load-bearing for approving a plan.
 *
 * Selector contract: ~/.claude/docs/plan-html-template.md
 */
(function () {
  'use strict';

  var body = document.body;
  var SERVER = body.dataset.mode === 'server';
  var KEY = 'plan:' + (body.dataset.planKey || 'unknown');

  /* localStorage throws on an opaque origin (file:// in some browsers) and
     when the quota is gone. Losing checkbox state is acceptable; losing the
     page is not. */
  function load(name, fallback) {
    try {
      var raw = localStorage.getItem(KEY + ':' + name);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) { return fallback; }
  }
  function save(name, value) {
    try { localStorage.setItem(KEY + ':' + name, JSON.stringify(value)); }
    catch (e) { /* ignore */ }
  }

  /* ---- theme ---------------------------------------------------------- */
  var THEMES = ['auto', 'light', 'dark'];
  var LABEL = { auto: '테마: 자동', light: '테마: 라이트', dark: '테마: 다크' };

  function currentTheme() {
    var t = null;
    try { t = localStorage.getItem('planTheme'); } catch (e) { }
    return THEMES.indexOf(t) > 0 ? t : 'auto';
  }
  function applyTheme(t) {
    if (t === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
    try {
      if (t === 'auto') localStorage.removeItem('planTheme');
      else localStorage.setItem('planTheme', t);
    } catch (e) { }
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = LABEL[t];
  }
  function cycleTheme() {
    var next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    applyTheme(next);
  }
  applyTheme(currentTheme());
  var themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', cycleTheme);

  /* ---- checkboxes + progress ------------------------------------------ */
  var boxes = Array.prototype.slice.call(document.querySelectorAll('input.chk'));
  var stepBoxes = boxes.filter(function (b) {
    return (b.dataset.key || '').indexOf('step:') === 0;
  });
  var tracked = stepBoxes.length ? stepBoxes : boxes;

  var stored = load('chk', {});
  boxes.forEach(function (b) {
    var k = b.dataset.key;
    if (!k) return;
    /* Frontmatter wins over localStorage: `/plan:check` on the shell side is
       the source of truth, and a browser that silently disagreed with the
       plan file would be worse than one that forgets a click. */
    if (b.dataset.seed === 'done') { b.checked = true; stored[k] = true; }
    else if (Object.prototype.hasOwnProperty.call(stored, k)) b.checked = !!stored[k];
    markDone(b);
  });
  save('chk', stored);

  function markDone(b) {
    var li = b.closest('li');
    if (li) li.classList.toggle('done', b.checked);
  }

  var bar = document.getElementById('progress-bar');
  var label = document.getElementById('progress-label');
  var wrap = document.getElementById('progress');

  function refreshProgress() {
    if (!tracked.length || !wrap) return;
    wrap.hidden = false;
    var done = tracked.filter(function (b) { return b.checked; }).length;
    if (bar) bar.style.width = (done / tracked.length * 100) + '%';
    if (label) label.textContent = done + ' / ' + tracked.length;
  }
  refreshProgress();

  boxes.forEach(function (b) {
    b.addEventListener('change', function () {
      if (b.dataset.key) { stored[b.dataset.key] = b.checked; save('chk', stored); }
      markDone(b);
      refreshProgress();
    });
  });

  /* ---- scroll spy ------------------------------------------------------ */
  var links = {};
  Array.prototype.forEach.call(document.querySelectorAll('#plan-toc a'), function (a) {
    links[a.dataset.target] = a;
  });
  var sections = Array.prototype.slice.call(document.querySelectorAll('section.sec'));

  if (sections.length && window.IntersectionObserver) {
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      var active = null;
      for (var i = 0; i < sections.length; i++) {
        if (visible[sections[i].id]) { active = sections[i].id; break; }
      }
      Object.keys(links).forEach(function (id) {
        links[id].classList.toggle('active', id === active);
      });
    }, { rootMargin: '0px 0px -70% 0px' });
    sections.forEach(function (s) { obs.observe(s); });
  }

  /* ---- step detail accordions ----------------------------------------- */
  var details = Array.prototype.slice.call(document.querySelectorAll('details.step-detail'));
  var openState = load('open', null);
  if (openState) {
    details.forEach(function (d) {
      var k = d.dataset.step;
      if (Object.prototype.hasOwnProperty.call(openState, k)) d.open = !!openState[k];
    });
  }
  function persistOpen() {
    var m = {};
    details.forEach(function (d) { m[d.dataset.step] = d.open; });
    save('open', m);
  }
  details.forEach(function (d) { d.addEventListener('toggle', persistOpen); });

  /* Jumping to a collapsed detail must open it, or the link looks broken. */
  function revealHash() {
    var id = location.hash.slice(1);
    if (!id) return;
    var el = document.getElementById(id);
    if (el && el.tagName === 'DETAILS') el.open = true;
    var host = el && el.closest ? el.closest('details') : null;
    if (host) host.open = true;
  }
  window.addEventListener('hashchange', revealHash);
  revealHash();

  var collapseBtn = document.getElementById('collapse-all');
  if (collapseBtn && details.length) {
    collapseBtn.addEventListener('click', function () {
      var anyOpen = details.some(function (d) { return d.open; });
      details.forEach(function (d) { d.open = !anyOpen; });
      collapseBtn.textContent = anyOpen ? '전체 펼치기' : '전체 접기';
      persistOpen();
    });
  } else if (collapseBtn) {
    collapseBtn.hidden = true;
  }

  /* ---- copy buttons ---------------------------------------------------- */
  Array.prototype.forEach.call(document.querySelectorAll('pre'), function (pre) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy-btn';
    btn.textContent = '복사';
    btn.addEventListener('click', function () {
      var text = (pre.querySelector('code') || pre).textContent;
      var done = function () {
        btn.textContent = '복사됨';
        setTimeout(function () { btn.textContent = '복사'; }, 1200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, fallbackCopy);
      } else { fallbackCopy(); }
      function fallbackCopy() {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); done(); } catch (e) { }
        document.body.removeChild(ta);
      }
    });
    pre.appendChild(btn);
  });

  /* ---- decision form --------------------------------------------------- */
  var form = document.getElementById('plan-form');
  function submitAction(value, confirmText) {
    if (!form) return;
    var btn = form.querySelector('button[value="' + value + '"]');
    if (!btn) return;
    if (confirmText && !window.confirm(confirmText)) return;
    if (form.requestSubmit) form.requestSubmit(btn);
    else { btn.click(); }
  }
  if (SERVER && form) {
    var submitted = false;
    form.addEventListener('submit', function (e) {
      var s = e.submitter;
      if (s && s.value === 'reject' &&
          !window.confirm('이 플랜을 폐기합니다. 계속할까요?')) {
        e.preventDefault();
        return;
      }
      submitted = true;
    });

    /* Closing the tab without deciding would otherwise block the agent until
       the server timeout. The server waits out a grace period before acting,
       because a reload fires pagehide too. */
    window.addEventListener('pagehide', function () {
      if (submitted || !navigator.sendBeacon) return;
      try { navigator.sendBeacon('/abandon', ''); } catch (e) { }
    });
  }

  /* ---- draft autosave --------------------------------------------------
     The hook has a wall-clock timeout; if it fires mid-sentence the typed
     discussion would otherwise be gone. This makes a timeout non-destructive. */
  var draftFields = Array.prototype.slice.call(
    document.querySelectorAll('#discuss, .quiz-answer'));
  if (draftFields.length) {
    var draft = load('draft', {});
    draftFields.forEach(function (f) {
      var k = f.name || f.id;
      if (k && draft[k] && !f.value) f.value = draft[k];
    });
    var timer = null;
    draftFields.forEach(function (f) {
      markAnswered(f);
      f.addEventListener('input', function () {
        markAnswered(f);
        clearTimeout(timer);
        timer = setTimeout(function () {
          draftFields.forEach(function (g) {
            var k = g.name || g.id;
            if (k) draft[k] = g.value;
          });
          save('draft', draft);
        }, 400);
      });
    });
  }
  function markAnswered(f) {
    var item = f.closest ? f.closest('.quiz-item') : null;
    if (item) item.classList.toggle('answered', f.value.trim().length > 0);
  }

  /* ---- keyboard -------------------------------------------------------- */
  var SHORTCUTS = [
    ['j / k', '다음 / 이전 섹션'],
    ['t', '테마 전환'],
    ['c', '스텝 상세 전체 접기'],
    ['?', '이 도움말']
  ];
  if (SERVER) {
    SHORTCUTS.push(['d', '논의 입력창으로']);
    SHORTCUTS.push(['a', '승인 (확인 후)']);
    SHORTCUTS.push(['r', '거부 (확인 후)']);
  }
  var help = document.getElementById('help-panel');
  if (help) {
    help.innerHTML = '<dl>' + SHORTCUTS.map(function (s) {
      return '<dt>' + s[0] + '</dt><dd>' + s[1] + '</dd>';
    }).join('') + '</dl>';
  }
  function toggleHelp(force) {
    if (!help) return;
    help.hidden = force === undefined ? !help.hidden : !force;
  }
  var helpBtn = document.getElementById('help-toggle');
  if (helpBtn) helpBtn.addEventListener('click', function () { toggleHelp(); });

  var cursor = -1;
  function gotoSection(delta) {
    if (!sections.length) return;
    cursor = Math.max(0, Math.min(sections.length - 1, cursor + delta));
    sections[cursor].scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  document.addEventListener('keydown', function (e) {
    /* Without this guard, typing "advance" in the discussion box would hit the
       `a` shortcut and approve the plan. */
    var t = e.target;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) {
      if (e.key === 'Escape') t.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    switch (e.key) {
      case 'j': gotoSection(1); break;
      case 'k': gotoSection(-1); break;
      case 't': cycleTheme(); break;
      case 'c': if (collapseBtn && !collapseBtn.hidden) collapseBtn.click(); break;
      case '?': toggleHelp(); break;
      case 'Escape': toggleHelp(false); break;
      case 'd':
        if (SERVER) {
          var d = document.getElementById('discuss');
          if (d) { e.preventDefault(); d.focus(); }
        }
        break;
      case 'a':
        if (SERVER) submitAction('approve', '이 플랜을 승인합니다. 계속할까요?');
        break;
      case 'r':
        if (SERVER) submitAction('reject', '이 플랜을 폐기합니다. 계속할까요?');
        break;
      default: return;
    }
  });

  /* ---- narrow-screen TOC toggle ---------------------------------------- */
  var head = document.getElementById('sidebar-head');
  var sidebar = document.getElementById('sidebar');
  if (head && sidebar) {
    head.addEventListener('click', function () { sidebar.classList.toggle('open'); });
    head.style.cursor = 'pointer';
  }
})();
