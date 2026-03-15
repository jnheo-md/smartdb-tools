document.addEventListener('DOMContentLoaded', () => {

  // ── 1. Copy-to-clipboard ──────────────────────────────────────────────

  const clipboardIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  const checkIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';

  document.querySelectorAll('.copy-btn').forEach((btn) => {
    btn.innerHTML = clipboardIcon;

    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-code');
      navigator.clipboard.writeText(code).then(() => {
        btn.innerHTML = checkIcon;
        btn.classList.add('copied');

        setTimeout(() => {
          btn.innerHTML = clipboardIcon;
          btn.classList.remove('copied');
        }, 2000);
      });
    });
  });

  // ── 2. Smooth scroll for anchor links ─────────────────────────────────

  const NAV_OFFSET = 64;

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId === '#') return;

      const target = document.querySelector(targetId);
      if (!target) return;

      e.preventDefault();

      const top = target.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
      window.scrollTo({ top, behavior: 'smooth' });

      // Close mobile menu if open
      closeMobileMenu();
    });
  });

  // ── 3. Mobile hamburger menu toggle ───────────────────────────────────

  const hamburger = document.querySelector('.hamburger');
  const navLinks = document.querySelector('.nav-links');

  const closeMobileMenu = () => {
    if (navLinks && navLinks.classList.contains('active')) {
      navLinks.classList.remove('active');
      if (hamburger) {
        hamburger.classList.remove('active');
        hamburger.setAttribute('aria-expanded', 'false');
      }
    }
  };

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      const isOpen = navLinks.classList.toggle('active');
      hamburger.classList.toggle('active');
      hamburger.setAttribute('aria-expanded', String(isOpen));
    });

    navLinks.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', closeMobileMenu);
    });

    document.addEventListener('click', (e) => {
      if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
        closeMobileMenu();
      }
    });
  }

  // ── 4. Active nav highlighting with IntersectionObserver ──────────────

  const sections = document.querySelectorAll('section[id]');
  const navItems = document.querySelectorAll('.nav-links a[href^="#"]');

  if (sections.length > 0 && navItems.length > 0) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            navItems.forEach((item) => {
              item.classList.toggle('active', item.getAttribute('href') === `#${id}`);
            });
          }
        });
      },
      { threshold: 0.3, rootMargin: `-${NAV_OFFSET}px 0px 0px 0px` }
    );

    sections.forEach((section) => navObserver.observe(section));
  }

  // ── 5. Nav background on scroll ───────────────────────────────────────

  const nav = document.querySelector('.nav');

  if (nav) {
    const onScroll = () => {
      nav.classList.toggle('scrolled', window.scrollY > 20);
    };

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

});
