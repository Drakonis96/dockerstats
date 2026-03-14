export function createMobileController(ctx, deps) {
  let mobileNotifOverlay = null;
  let mobileNotifClose = null;

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
      ctx.elements.notifPanel.prepend(mobileNotifClose);
    }
  }

  function openMobileNotifications() {
    ensureMobileNotifChrome();
    deps.renderNotifications();
    deps.updateNotificationBadge();

    Object.assign(ctx.elements.notifPanel.style, {
      display: 'block',
      position: 'fixed',
      top: '50%',
      left: '50%',
      right: 'auto',
      marginTop: '0',
      transform: 'translate(-50%, -50%)',
      width: '92%',
      maxWidth: '420px',
      maxHeight: '85vh',
      overflowY: 'auto',
      zIndex: '2000',
    });
    mobileNotifOverlay.style.display = 'block';
  }

  function closeMobileNotifications() {
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
    if (mobileNotifOverlay) {
      mobileNotifOverlay.style.display = 'none';
    }
  }

  function init() {
    ctx.elements.mobileMenuToggle?.addEventListener('click', openSidebarMenu);
    ctx.elements.sidebarClose?.addEventListener('click', closeSidebarMenu);
    ctx.elements.sidebarOverlay?.addEventListener('click', closeSidebarMenu);

    ctx.elements.sidebarNotifToggle?.addEventListener('click', () => {
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
