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


/* ── 2. SIDEBAR TOGGLE & SCROLL PERSISTENCE ─────────────────────── */
const SIDEBAR_SCROLL_KEY = 'vvit_sidebar_scroll';

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (!sidebar) return;
  const open = sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open', open);
  document.body.style.overflow = open ? 'hidden' : '';
}

function initSidebarScrollPersistence() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;

  // Record scroll position continuously as user scrolls
  sidebar.addEventListener('scroll', () => {
    sessionStorage.setItem(SIDEBAR_SCROLL_KEY, sidebar.scrollTop);
  }, { passive: true });

  // Save scroll position when clicking any navigation link
  sidebar.querySelectorAll('a.nav-link').forEach(link => {
    link.addEventListener('click', () => {
      sessionStorage.setItem(SIDEBAR_SCROLL_KEY, sidebar.scrollTop);
    });
  });

  // Restore saved scroll position if available
  const savedScroll = sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
  if (savedScroll !== null) {
    sidebar.scrollTop = parseInt(savedScroll, 10);
  }

  // Ensure active navigation item is scrolled into view
  const activeLink = sidebar.querySelector('a.nav-link.active');
  if (activeLink) {
    setTimeout(() => {
      activeLink.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    }, 50);
  }
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
    document.querySelectorAll(`input[name="${name}"]:not([type="hidden"])`).forEach(el => {
      _pickers.push(flatpickr(el, { ...base, maxDate:'today', defaultDate: el.value||undefined }));
    });
  });

  /* Admin / HOD attendance filter date */
  document.querySelectorAll('input[name="date"]:not([type="hidden"])').forEach(el => {
    if (el.id === 'dateInput' || el._flatpickr) return;
    const fp = flatpickr(el, {
      ...base,
      defaultDate: el.value || undefined,
      onChange(dates, dateStr) {
        if (el.form && el.form.method && el.form.method.toUpperCase() === 'GET') {
          el.form.submit();
        }
      }
    });
    _pickers.push(fp);
  });

  /* Any other visible date inputs */
  document.querySelectorAll('input[type="date"]:not([id="dateInput"]):not([type="hidden"])').forEach(el => {
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


/* ── 10. BUTTON RIPPLE EFFECT ───────────────────────────────────── */
function initButtonRipples() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('.btn-vvit-primary, .btn-vvit-secondary, .btn-vvit-outline, .btn-vvit-success, .btn-vvit-danger, .btn-sm-accent, .btn-sm-danger, .btn-sm-edit, .btn-download, .btn-vvit-tab, .vvit-btn, .vvit-btn-primary, .vvit-btn-secondary, .vvit-btn-danger, .vvit-btn-success, .btn-leave-approve, .btn-leave-reject, .btn-leave-remarks, .btn-leave-apply, .theme-toggle-btn, .notif-bell-btn, .page-btn, .btn-login');
    if (!btn) return;
    
    const rect = btn.getBoundingClientRect();
    const wave = document.createElement('span');
    wave.className = 'vvit-ripple-wave';
    const size = Math.max(rect.width, rect.height);
    wave.style.width = wave.style.height = `${size}px`;
    wave.style.left = `${e.clientX - rect.left - size / 2}px`;
    wave.style.top = `${e.clientY - rect.top - size / 2}px`;
    
    btn.appendChild(wave);
    setTimeout(() => wave.remove(), 650);
  });
}


/* ── 10b. DATE INPUT PICKER TRIGGER ─────────────────────────────── */
function initDateInputPickerTrigger() {
  document.addEventListener('click', e => {
    const wrapper = e.target.closest('.date-input-wrapper');
    if (!wrapper) return;
    
    const inputs = Array.from(wrapper.querySelectorAll('input'));
    for (const inp of inputs) {
      if (inp._flatpickr) {
        inp._flatpickr.open();
        return;
      }
    }
    const visibleInp = wrapper.querySelector('input:not([type="hidden"])') || inputs[0];
    if (visibleInp) {
      if (typeof visibleInp.showPicker === 'function') {
        try { visibleInp.showPicker(); } catch (err) {}
      } else {
        visibleInp.focus();
      }
    }
  });
}


/* ── 11. DOM READY ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Re-apply theme so icon updates correctly
  applyTheme(localStorage.getItem(THEME_KEY) || 'dark');

  initToasts();
  animatePctBars();
  animateGauge();
  initButtonRipples();
  initSidebarScrollPersistence();
  initDateInputPickerTrigger();
  document.body.classList.add('js-loaded');
  triggerStaggeredEntrance();

  if (typeof flatpickr !== 'undefined') {
    initDatePickers();
  } else {
    window.addEventListener('load', initDatePickers);
  }
});
