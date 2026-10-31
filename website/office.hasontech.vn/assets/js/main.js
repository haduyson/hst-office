(() => {
  'use strict';

  const menuButton = document.querySelector('.menu-toggle');
  const navigation = document.querySelector('#main-nav');
  if (menuButton && navigation) {
    const closeMenu = () => {
      menuButton.setAttribute('aria-expanded', 'false');
      navigation.classList.remove('is-open');
    };
    menuButton.hidden = false;
    document.documentElement.classList.add('nav-enhanced');
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') !== 'true';
      menuButton.setAttribute('aria-expanded', String(open));
      navigation.classList.toggle('is-open', open);
    });
    navigation.addEventListener('click', (event) => {
      if (event.target.closest('a')) closeMenu();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
        closeMenu();
        menuButton.focus();
      }
    });
    document.addEventListener('click', (event) => {
      if (!event.target.closest('.header-inner')) closeMenu();
    });
    window.matchMedia('(min-width: 761px)').addEventListener('change', closeMenu);
  }

  // Keep all content visible if IntersectionObserver or motion is unavailable.
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if ('IntersectionObserver' in window && !reducedMotion.matches) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll('[data-reveal]').forEach((element) => observer.observe(element));
  }

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.hidden = false;
    button.addEventListener('click', async () => {
      const code = document.getElementById(button.dataset.copy);
      const status = document.getElementById('copy-status');
      if (!code || !status) return;
      try {
        await navigator.clipboard.writeText(code.textContent.trim());
        status.textContent = 'Đã sao chép lệnh giải nén.';
      } catch {
        const range = document.createRange();
        range.selectNodeContents(code);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        status.textContent = 'Đã chọn lệnh. Nhấn Ctrl+C (hoặc Command+C trên Mac) để sao chép.';
      }
    });
  });

  // Opening the Linux guide from a card also expands the native details element.
  const openLinkedDetails = () => {
    if (window.location.hash === '#cai-dat-linux') {
      const details = document.getElementById('cai-dat-linux');
      if (details) details.open = true;
    }
  };
  window.addEventListener('hashchange', openLinkedDetails);
  document.querySelectorAll('a[href="#cai-dat-linux"]').forEach((link) => {
    link.addEventListener('click', openLinkedDetails);
  });
  openLinkedDetails();

  // Điểm mới: bản cũ thu gọn trong <details>; link tới #v<phiên bản> thì tự mở bản đó.
  const openVersion = () => {
    const target = window.location.hash && document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
    const details = target && (target.querySelector('details.release-details') || target.closest('details'));
    if (details && !details.open) details.open = true;
  };
  openVersion();
  window.addEventListener('hashchange', openVersion);

  // GA4 does not recognise /tai/* as file downloads (no file extension), so report them explicitly.
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href^="/tai/"]');
    if (!link || typeof window.gtag !== 'function') return;
    const platform = link.getAttribute('href').replace(/^\/tai\//, '').replace(/\/$/, '');
    window.gtag('event', 'file_download', {
      file_name: platform,
      link_url: new URL(link.getAttribute('href'), window.location.origin).href,
      page_path: window.location.pathname,
      transport_type: 'beacon'
    });
  });

  // Missing/invalid configuration leaves the current static HTML intact.
  const config = window.HST_OFFICE_CONFIG;
  if (!config || !config.platforms) return;
  const usable = (entry) => Boolean(entry && entry.available === true &&
    typeof entry.path === 'string' && /^\/tai\/[a-z0-9-]+$/.test(entry.path));

  document.querySelectorAll('[data-release-label]').forEach((element) => {
    if (typeof config.releaseLabel === 'string') element.textContent = config.releaseLabel;
  });
  document.querySelectorAll('[data-release-tag]').forEach((element) => {
    if (typeof config.tag === 'string') element.textContent = config.tag;
  });
  const schema = document.querySelector('script[type="application/ld+json"]');
  if (schema && typeof config.tag === 'string') {
    try {
      const data = JSON.parse(schema.textContent);
      // Structured data may be a single node or an @graph; only the SoftwareApplication carries the version.
      const nodes = Array.isArray(data['@graph']) ? data['@graph'] : [data];
      const app = nodes.find((node) => node['@type'] === 'SoftwareApplication');
      if (app) {
        app.softwareVersion = config.tag.replace(/^v/, '');
        schema.textContent = JSON.stringify(data);
      }
    } catch { /* The static structured data remains available. */ }
  }

  const setAvailability = (link, entry) => {
    const available = usable(entry);
    link.classList.toggle('is-unavailable', !available);
    if (available) {
      link.href = entry.path;
      link.removeAttribute('aria-disabled');
      link.removeAttribute('tabindex');
      link.removeAttribute('role');
    } else {
      link.removeAttribute('href');
      link.setAttribute('role', 'link');
      link.setAttribute('aria-disabled', 'true');
      link.setAttribute('tabindex', '-1');
    }
    return available;
  };
  document.querySelectorAll('[data-download]').forEach((link) => {
    const available = setAvailability(link, config.platforms[link.dataset.download]);
    link.querySelector('[data-button-label]').textContent = available
      ? link.dataset.availableLabel : link.dataset.unavailableLabel;
  });
  document.querySelectorAll('[data-checksum]').forEach((link) => {
    if (!setAvailability(link, config.checksum)) link.textContent = 'SHA256SUMS · Sắp có';
  });
  document.querySelectorAll('[data-platform-card]').forEach((card) => {
    const key = card.dataset.platformCard;
    const available = key === 'macos'
      ? usable(config.platforms['macos-arm']) || usable(config.platforms['macos-intel'])
      : usable(config.platforms[key]);
    const status = card.querySelector('.platform-status');
    status.textContent = available ? 'Sẵn sàng tải' : 'Đang chuẩn bị';
    status.classList.toggle('status-soon', !available);
  });
  const command = document.getElementById('linux-command');
  if (command && typeof config.linuxArchive === 'string' && /^[A-Za-z0-9_.-]+\.tar\.gz$/.test(config.linuxArchive)) {
    command.textContent = `tar xzf ${config.linuxArchive}`;
  }

  const hero = document.getElementById('hero-download');
  if (!hero) return;
  const showRecommendation = (key, family) => {
    const entry = config.platforms[key];
    hero.href = usable(entry) ? entry.path : '#tai-ve';
    hero.querySelector('span').textContent = usable(entry)
      ? `Tải miễn phí cho ${entry.label}`
      : family ? `${family} sắp có · Xem các bản tải` : 'Chọn phiên bản tải miễn phí';
    document.querySelectorAll('[data-platform-card]').forEach((card) => {
      card.classList.toggle('is-recommended', card.dataset.platformCard === (family === 'macOS' ? 'macos' : key));
    });
  };

  const clientHints = navigator.userAgentData;
  const userAgent = navigator.userAgent || '';
  const platform = clientHints?.platform || navigator.platform || '';
  const mobile = clientHints?.mobile || /Android|iPhone|iPad|iPod/i.test(userAgent) ||
    (/Mac/i.test(platform) && navigator.maxTouchPoints > 1);
  if (mobile) {
    showRecommendation(null, null);
  } else if (/Win/i.test(platform)) {
    showRecommendation('windows', 'Windows');
  } else if (/Mac/i.test(platform)) {
    const defaultMac = usable(config.platforms['macos-arm']) ? 'macos-arm' : 'macos-intel';
    showRecommendation(defaultMac, 'macOS');
    // Client Hints can identify Apple Silicon; Safari often provides no architecture.
    if (typeof clientHints?.getHighEntropyValues === 'function') {
      clientHints.getHighEntropyValues(['architecture']).then(({ architecture }) => {
        if (/arm/i.test(architecture)) showRecommendation('macos-arm', 'macOS');
        else if (/x86|x64/i.test(architecture)) showRecommendation('macos-intel', 'macOS');
      }).catch(() => { /* Keep the available Mac choice or the coming-soon link. */ });
    }
  } else if (/Linux/i.test(platform)) {
    showRecommendation('linux', 'Linux');
  } else {
    showRecommendation(null, null);
  }
})();
