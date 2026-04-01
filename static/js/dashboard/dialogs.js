export function createDialogController(ctx) {
  let currentResolver = null;
  let hiddenHandlerBound = false;

  function ensureModal() {
    if (!ctx.state.appDialogModal && ctx.elements.appDialogModalEl) {
      ctx.state.appDialogModal = bootstrap.Modal.getOrCreateInstance(ctx.elements.appDialogModalEl);
    }

    if (!hiddenHandlerBound && ctx.elements.appDialogModalEl) {
      ctx.elements.appDialogModalEl.addEventListener('hidden.bs.modal', () => {
        if (currentResolver) {
          currentResolver(false);
          currentResolver = null;
        }
      });
      hiddenHandlerBound = true;
    }
  }

  function setTone(tone = 'primary') {
    const confirmButton = ctx.elements.appDialogConfirm;
    if (!confirmButton) return;
    confirmButton.className = 'btn';
    confirmButton.classList.add(
      tone === 'danger' ? 'btn-danger'
        : tone === 'warning' ? 'btn-warning'
          : 'btn-primary',
    );
  }

  function configureDialog({
    title,
    message,
    confirmLabel,
    cancelLabel,
    tone = 'primary',
    hideCancel = false,
  }) {
    ensureModal();
    ctx.elements.appDialogTitle.textContent = title || 'Confirm action';
    ctx.elements.appDialogMessage.textContent = message || '';
    ctx.elements.appDialogConfirm.textContent = confirmLabel || 'Confirm';
    ctx.elements.appDialogCancel.textContent = cancelLabel || 'Cancel';
    ctx.elements.appDialogCancel.hidden = hideCancel === true;
    setTone(tone);
  }

  function confirm(options = {}) {
    configureDialog(options);
    return new Promise((resolve) => {
      currentResolver = resolve;

      const confirmHandler = () => {
        ctx.state.appDialogModal.hide();
        if (currentResolver) {
          const resolver = currentResolver;
          currentResolver = null;
          resolver(true);
        }
      };

      ctx.elements.appDialogConfirm.onclick = confirmHandler;
      ctx.state.appDialogModal.show();
    });
  }

  function alert(options = {}) {
    return confirm({
      title: options.title || 'Notice',
      message: options.message || '',
      confirmLabel: options.confirmLabel || 'Close',
      tone: options.tone || 'primary',
      hideCancel: true,
    });
  }

  return {
    confirm,
    alert,
  };
}
