/* ═══════════════════════════════════════════════════════════════════
   VVIT Portal — Main JavaScript
   Handles: theme toggle, sidebar, Flatpickr, animations, CSRF
   ═══════════════════════════════════════════════════════════════════ */
'use strict';

/* ── 1. DARK / LIGHT THEME ───────────────────────────────────────── */
const THEME_KEY = 'vvit-theme';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) icon.className = theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
}

function toggleTheme() {
  const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
  setTimeout(initDatePickers, 60);  // refresh calendar colours
}

// Apply saved theme immediately (before paint)
(function () { applyTheme(localStorage.getItem(THEME_KEY) || 'dark'); })();


/* ── 2. SIDEBAR TOGGLE ───────────────────────────────────────────── */
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (!sidebar) return;
  const open = sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open', open);
  document.body.style.overflow = open ? 'hidden' : '';
}

window.addEventListener('resize', () => {
  if (window.innerWidth >= 992) {
    const s = document.getElementById('sidebar');
    const o = document.getElementById('sidebarOverlay');
    if (s) s.classList.remove('open');
    if (o) o.classList.remove('open');
    document.body.style.overflow = '';
  }
});


/* ── 3. CSRF ─────────────────────────────────────────────────────── */
function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  if (el) return el.value;
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}


/* ── 4. DAY NAME FROM DATE STRING ────────────────────────────────── */
function getDayName(dateStr) {
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const p    = String(dateStr).split('-');
  const d    = p.length === 3 ? new Date(+p[0],+p[1]-1,+p[2]) : new Date(dateStr);
  return days[d.getDay()];
}


/* ── 5. FLATPICKR DATE PICKERS ───────────────────────────────────── */
let _pickers = [];

function initDatePickers() {
  if (typeof flatpickr === 'undefined') return;

  // Destroy old instances first
  _pickers.forEach(p => { try { p.destroy(); } catch(e){} });
  _pickers = [];

  const base = {
    dateFormat: 'Y-m-d',
    altInput:   true,
    altFormat:  'D, d M Y',   // e.g. Mon, 28 Mar 2025
    allowInput: true,
  };

  /* Mark Attendance date */
  const att = document.getElementById('dateInput');
  if (att) {
    const fp = flatpickr(att, {
      ...base,
      maxDate:     att.getAttribute('max') || 'today',
      minDate:     att.getAttribute('min') || undefined,
      defaultDate: att.value || 'today',
      onChange(dates) {
        if (!dates[0]) return;
        const d    = dates[0];
        const iso  = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
        // fire custom event so mark_attendance.js can reload slots
        att.dispatchEvent(new CustomEvent('fp-datechange', { detail: iso }));
      },
    });
    _pickers.push(fp);
  }

  /* Report date_from / date_to */
  ['date_from','date_to'].forEach(name => {
    document.querySelectorAll(`input[name="${name}"]`).forEach(el => {
      _pickers.push(flatpickr(el, { ...base, maxDate:'today', defaultDate: el.value||undefined }));
    });
  });

  /* Admin attendance filter date */
  document.querySelectorAll('input[name="date"]').forEach(el => {
    if (el.id === 'dateInput') return;
    _pickers.push(flatpickr(el, { ...base, defaultDate: el.value||undefined }));
  });

  /* Any other date inputs */
  document.querySelectorAll('input[type="date"]:not([id="dateInput"])').forEach(el => {
    if (el._flatpickr) return;
    _pickers.push(flatpickr(el, { ...base, defaultDate: el.value||undefined }));
  });
}


/* ── 6. ANIMATIONS ───────────────────────────────────────────────── */
function animatePctBars() {
  document.querySelectorAll('.pct-bar-fill').forEach(el => {
    const w = el.style.width; el.style.width='0';
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      el.style.transition='width 0.8s cubic-bezier(0.4,0,0.2,1)';
      el.style.width=w;
    }));
  });
}

function animateGauge() {
  document.querySelectorAll('.ai-gauge-fill').forEach(el => {
    const w = el.style.width; el.style.width='0';
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      el.style.transition='width 1s cubic-bezier(0.4,0,0.2,1)';
      el.style.width=w;
    }));
  });
}


/* ── 7. TOAST INIT ───────────────────────────────────────────────── */
function initToasts() {
  if (typeof bootstrap === 'undefined') return;
  document.querySelectorAll('.toast').forEach(el => {
    bootstrap.Toast.getOrCreateInstance(el, {delay:4500}).show();
  });
}


/* ── 8. KEYBOARD SHORTCUTS ───────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (e.altKey && e.key === 't') toggleTheme();
  if (e.altKey && e.key === 'm') {
    const a = document.querySelector('a[href*="mark-attendance"]');
    if (a) a.click();
  }
});


/* ── 9. STAGGERED ENTRANCE ANIMATION ─────────────────────────────── */
function triggerStaggeredEntrance() {
  const elements = document.querySelectorAll('.glass-card, .kpi-card, .vvit-table, .timetable-grid');
  elements.forEach((el, index) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(15px)';
    el.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1), border-color var(--t-med), box-shadow var(--t-med)';
    setTimeout(() => {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    }, index * 60);
  });
}


/* ── 10. DOM READY ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Re-apply theme so icon updates correctly
  applyTheme(localStorage.getItem(THEME_KEY) || 'dark');

  initToasts();
  animatePctBars();
  animateGauge();
  document.body.classList.add('js-loaded');
  triggerStaggeredEntrance();

  if (typeof flatpickr !== 'undefined') {
    initDatePickers();
  } else {
    window.addEventListener('load', initDatePickers);
  }
});
