export function createMobileController(ctx, deps) {
  let mobileNotifOverlay = null;
  let mobileNotifClose = null;
  let currentSection = 'containers';
  let notifPanelHome = null;
  let notifPanelHomeNextSibling = null;
  const mobileBreakpoint = window.matchMedia('(max-width: 767.98px)');
  const boundModalElements = new WeakSet();

  function isMobileLayout() {
    return mobileBreakpoint.matches;
  }

  function getViewportHeight() {
    return Math.round(window.visualViewport?.height || window.innerHeight || document.documentElement.clientHeight || 0);
  }

  function syncViewportHeight() {
    document.documentElement.style.setProperty('--ds-viewport-height', `${Math.max(getViewportHeight(), 320)}px`);
  }

  function updateVisibleModals() {
    document.querySelectorAll('.modal.show').forEach((modalElement) => {
      bootstrap.Modal.getInstance(modalElement)?.handleUpdate?.();
    });
  }

  function handleViewportChange() {
    syncViewportHeight();
    requestAnimationFrame(() => updateVisibleModals());
  }

  function bindModalViewportSync() {
    document.querySelectorAll('.modal').forEach((modalElement) => {
      if (boundModalElements.has(modalElement)) {
        return;
      }

      modalElement.addEventListener('show.bs.modal', handleViewportChange);
      modalElement.addEventListener('shown.bs.modal', handleViewportChange);
      boundModalElements.add(modalElement);
    });
  }

  function updateSectionTabs(section) {
    ctx.elements.mobileSectionTabs.forEach((tab) => {
      const active = tab.dataset.mobileSection === section;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
    });
  }

  function syncDesktopDashboardTab(section) {
    if (section === 'containers' && ctx.elements.dashboardContainersTab) {
      bootstrap.Tab.getOrCreateInstance(ctx.elements.dashboardContainersTab).show();
    }

    if (section === 'stacks' && ctx.elements.dashboardComposeTab) {
      bootstrap.Tab.getOrCreateInstance(ctx.elements.dashboardComposeTab).show();
    }
  }

  function setMobileSection(section, { syncDashboardTab = true } = {}) {
    const normalizedSection = ['info', 'workspace', 'containers', 'stacks'].includes(section)
      ? section
      : 'containers';

    currentSection = normalizedSection;
    updateSectionTabs(normalizedSection);

    if (isMobileLayout()) {
      document.body.dataset.mobileSection = normalizedSection;
    } else {
      document.body.removeAttribute('data-mobile-section');
    }

    if (syncDashboardTab) {
      syncDesktopDashboardTab(normalizedSection);
    }
  }

  function handleSectionTabClick(event) {
    event.preventDefault();
    setMobileSection(event.currentTarget.dataset.mobileSection);
  }

  function handleBreakpointChange() {
    const nowMobileLayout = isMobileLayout();

    if (nowMobileLayout) {
      setMobileSection(currentSection || 'containers', { syncDashboardTab: currentSection === 'containers' || currentSection === 'stacks' });
    } else {
      document.body.removeAttribute('data-mobile-section');
    }

    handleViewportChange();
  }

  function closeSidebarMenu() {
    ctx.elements.sidebarMenu.classList.remove('active');
    ctx.elements.sidebarOverlay.style.display = 'none';
    document.body.style.overflow = '';
  }

  function openSidebarMenu() {
    ctx.elements.sidebarMenu.classList.add('active');
    ctx.elements.sidebarOverlay.style.display = 'block';
    document.body.style.overflow = 'hidden';
  }

  function ensureMobileNotifChrome() {
    if (!notifPanelHome && ctx.elements.notifPanel) {
      notifPanelHome = ctx.elements.notifPanel.parentElement;
      notifPanelHomeNextSibling = ctx.elements.notifPanel.nextSibling;
    }

    if (!mobileNotifOverlay) {
      mobileNotifOverlay = document.createElement('div');
      mobileNotifOverlay.id = 'mobileNotifOverlay';
      Object.assign(mobileNotifOverlay.style, {
        display: 'none',
        position: 'fixed',
        inset: '0',
        background: 'rgba(0,0,0,0.45)',
        zIndex: '1999',
      });
      mobileNotifOverlay.addEventListener('click', closeMobileNotifications);
      document.body.appendChild(mobileNotifOverlay);
    }

    if (!mobileNotifClose) {
      mobileNotifClose = document.createElement('button');
      mobileNotifClose.type = 'button';
      mobileNotifClose.textContent = 'Close';
      mobileNotifClose.className = 'btn btn-sm btn-outline-secondary mb-2';
      mobileNotifClose.addEventListener('click', closeMobileNotifications);
      if (ctx.elements.notifPanelActions) {
        ctx.elements.notifPanelActions.appendChild(mobileNotifClose);
        mobileNotifClose.classList.remove('mb-2');
      } else {
        ctx.elements.notifPanel.prepend(mobileNotifClose);
      }
    }
  }

  function openMobileNotifications() {
    ensureMobileNotifChrome();
    deps.renderNotifications();
    deps.updateNotificationBadge();

    if (ctx.elements.notifPanel && ctx.elements.notifPanel.parentElement !== document.body) {
      document.body.appendChild(ctx.elements.notifPanel);
    }

    Object.assign(ctx.elements.notifPanel.style, {
      display: 'block',
      position: 'fixed',
      top: 'max(1rem, env(safe-area-inset-top))',
      left: '50%',
      right: 'auto',
      marginTop: '0',
      transform: 'translateX(-50%)',
      width: '92%',
      maxWidth: '420px',
      maxHeight: 'calc(var(--ds-viewport-height) - 2rem)',
      overflowY: 'auto',
      zIndex: '2000',
    });
    ctx.elements.notifPanel.classList.add('mobile-notif-visible');
    mobileNotifOverlay.style.display = 'block';
  }

  function closeMobileNotifications() {
    ctx.elements.notifPanel.classList.remove('mobile-notif-visible');
    ctx.elements.notifPanel.style.display = 'none';
    ctx.elements.notifPanel.style.position = '';
    ctx.elements.notifPanel.style.top = '';
    ctx.elements.notifPanel.style.left = '';
    ctx.elements.notifPanel.style.right = '';
    ctx.elements.notifPanel.style.transform = '';
    ctx.elements.notifPanel.style.width = '';
    ctx.elements.notifPanel.style.maxWidth = '';
    ctx.elements.notifPanel.style.maxHeight = '';
    ctx.elements.notifPanel.style.overflowY = '';
    ctx.elements.notifPanel.style.zIndex = '';

    if (notifPanelHome && ctx.elements.notifPanel.parentElement === document.body) {
      if (notifPanelHomeNextSibling && notifPanelHomeNextSibling.parentNode === notifPanelHome) {
        notifPanelHome.insertBefore(ctx.elements.notifPanel, notifPanelHomeNextSibling);
      } else {
        notifPanelHome.appendChild(ctx.elements.notifPanel);
      }
    }

    if (mobileNotifOverlay) {
      mobileNotifOverlay.style.display = 'none';
    }
  }

  function init() {
    syncViewportHeight();
    bindModalViewportSync();
    window.addEventListener('resize', handleViewportChange);
    window.visualViewport?.addEventListener('resize', handleViewportChange);
    window.visualViewport?.addEventListener('scroll', handleViewportChange);

    ctx.elements.mobileSectionTabs.forEach((tab) => {
      tab.addEventListener('click', handleSectionTabClick);
    });

    mobileBreakpoint.addEventListener('change', handleBreakpointChange);
    setMobileSection('containers');

    ctx.elements.mobileMenuToggle?.addEventListener('click', openSidebarMenu);
    ctx.elements.sidebarClose?.addEventListener('click', closeSidebarMenu);
    ctx.elements.sidebarOverlay?.addEventListener('click', closeSidebarMenu);

    ctx.elements.sidebarNotifToggle?.addEventListener('click', (event) => {
      event.stopPropagation();
      closeSidebarMenu();
      openMobileNotifications();
    });
    ctx.elements.sidebarThemeToggle?.addEventListener('click', () => {
      closeSidebarMenu();
      deps.toggleTheme();
    });
    ctx.elements.sidebarSettingsBtn?.addEventListener('click', () => {
      closeSidebarMenu();
      deps.openSettings();
    });
    ctx.elements.sidebarLogoutBtn?.addEventListener('click', () => {
      closeSidebarMenu();
      deps.logout();
    });
    ctx.elements.sidebarUserInfoBtn?.addEventListener('click', () => {
      closeSidebarMenu();
      deps.refreshUserInfo();
    });
  }

  return {
    init,
    closeSidebarMenu,
    openMobileNotifications,
    closeMobileNotifications,
  };
}
