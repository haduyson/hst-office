/*
 * Hộp hỏi đồng ý cookie cho Google Analytics (Consent Mode v2).
 *
 * - Thẻ <head> của mỗi trang đặt mặc định 'denied' cho analytics_storage, ad_storage, ad_user_data,
 *   ad_personalization rồi mới gọi gtag('config'). Tệp này KHÔNG tải gtag.js khi người xem chưa bấm
 *   "Đồng ý", nên trước lúc đó trang không gửi gì tới Google và không có cookie nào.
 * - "Đồng ý" chỉ bật analytics_storage; ba mục quảng cáo luôn giữ 'denied' (trang không chạy quảng cáo).
 * - Lựa chọn lưu ở localStorage "hst-consent" (không phải cookie), hỏi lại sau 12 tháng.
 * - "Từ chối" (kể cả khi đổi ý sau này) xóa cookie _ga, _ga_LRLQZ0R9QJ của trang này.
 * - Nút "Cài đặt cookie" được thêm vào .footer-nav để mở lại hộp hỏi bất cứ lúc nào.
 */
(function () {
  'use strict';
  var KEY = 'hst-consent';
  var MAX_AGE = 365 * 24 * 3600 * 1000;
  var GA_ID = 'G-LRLQZ0R9QJ';
  var box = null;

  function gtag() { (window.dataLayer = window.dataLayer || []).push(arguments); }

  function readChoice() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (v && (v.c === 'granted' || v.c === 'denied') && Date.now() - v.t < MAX_AGE) return v.c;
    } catch (e) { /* bộ nhớ bị chặn: coi như chưa chọn */ }
    return null;
  }

  function saveChoice(c) {
    try { localStorage.setItem(KEY, JSON.stringify({ c: c, t: Date.now() })); } catch (e) { /* bỏ qua */ }
  }

  // Tải gtag.js sau thao tác đầu tiên hoặc 4 giây sau khi trang tải xong để không làm chậm trang.
  var loaded = false;
  function loadGa(now) {
    var events = ['scroll', 'pointerdown', 'keydown', 'touchstart'];
    function load() {
      if (loaded) return; loaded = true;
      events.forEach(function (e) { removeEventListener(e, load); });
      var s = document.createElement('script'); s.async = true;
      s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
      document.head.appendChild(s);
    }
    if (now) return load();
    events.forEach(function (e) { addEventListener(e, load, { once: true, passive: true }); });
    if (document.readyState === 'complete') setTimeout(load, 4000);
    else addEventListener('load', function () { setTimeout(load, 4000); });
  }

  function clearGaCookies() {
    var host = location.hostname, parts = host.split('.');
    var domains = ['', host, '.' + host];
    if (parts.length > 2) domains.push('.' + parts.slice(-2).join('.'));
    document.cookie.split(';').forEach(function (c) {
      var name = c.split('=')[0].trim();
      if (name !== '_ga' && name !== '_ga_' + GA_ID.slice(2)) return;
      domains.forEach(function (d) {
        document.cookie = name + '=; Max-Age=0; path=/' + (d ? '; domain=' + d : '');
      });
    });
  }

  function apply(c, fromClick) {
    if (c === 'granted') {
      gtag('consent', 'update', { analytics_storage: 'granted' });
      loadGa(fromClick);
    } else {
      gtag('consent', 'update', { analytics_storage: 'denied' });
      clearGaCookies();
    }
  }

  function injectStyle() {
    var css =
      '.hst-consent{position:fixed;left:16px;right:16px;bottom:16px;z-index:1000;max-width:560px;margin:0 auto;' +
      'background:#fff;color:var(--body,#322e2e);border:1px solid var(--line,#dce6f0);border-radius:14px;' +
      'box-shadow:0 10px 30px rgba(6,27,54,.16);padding:18px 18px 16px;font-size:14px;line-height:1.55}' +
      '.hst-consent h2{margin:0 0 6px;font-size:16px;color:var(--ink,#172d47)}' +
      '.hst-consent p{margin:0}' +
      '.hst-consent a{color:var(--blue-dark,#07569a);font-weight:700}' +
      '.hst-consent-actions{display:flex;gap:10px;margin-top:14px}' +
      '.hst-consent-actions button{flex:1 1 0;min-height:44px;border-radius:10px;font:inherit;font-weight:700;' +
      'cursor:pointer;border:1px solid var(--blue,#0b6fc1);background:#fff;color:var(--blue-dark,#07569a)}' +
      '.hst-consent-actions button:hover,.hst-consent-actions button:focus-visible{background:var(--blue,#0b6fc1);color:#fff}' +
      '.footer-nav .cookie-settings{display:inline-flex;align-items:center;min-height:44px;padding:0;border:0;' +
      'background:none;font:inherit;font-size:12px;font-weight:700;color:var(--blue-dark,#07569a);cursor:pointer}' +
      '.footer-nav .cookie-settings:hover{text-decoration:underline}';
    var s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
  }

  function hide() { if (box) { box.remove(); box = null; } }

  function show() {
    if (box) return box.querySelector('button').focus();
    box = document.createElement('section');
    box.className = 'hst-consent';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-labelledby', 'hst-consent-title');
    box.innerHTML =
      '<h2 id="hst-consent-title">Cookie đo lượt xem</h2>' +
      '<p>Trang này dùng Google Analytics để đếm lượt xem và biết trang nào hữu ích. Google Analytics chỉ chạy ' +
      'và đặt cookie khi bạn bấm “Đồng ý”. Bạn có thể đổi lựa chọn bất cứ lúc nào ở mục “Cài đặt cookie” cuối ' +
      'trang. <a href="/quyen-rieng-tu/#cookie">Tìm hiểu thêm</a></p>' +
      '<div class="hst-consent-actions">' +
      '<button type="button" data-c="denied">Từ chối</button>' +
      '<button type="button" data-c="granted">Đồng ý</button></div>';
    box.addEventListener('click', function (e) {
      var c = e.target.getAttribute && e.target.getAttribute('data-c');
      if (!c) return;
      saveChoice(c); apply(c, true); hide();
    });
    box.addEventListener('keydown', function (e) { if (e.key === 'Escape') hide(); });
    document.body.appendChild(box);
  }

  function addFooterLink() {
    var nav = document.querySelector('.footer-nav');
    if (!nav || nav.querySelector('.cookie-settings')) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'cookie-settings'; b.textContent = 'Cài đặt cookie';
    b.addEventListener('click', function () { show(); box.querySelector('button').focus(); });
    nav.appendChild(b);
  }

  var choice = readChoice();
  if (choice) apply(choice, false);
  function init() {
    injectStyle();
    addFooterLink();
    if (!choice) show();
    if (location.hash === '#cai-dat-cookie') show();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
