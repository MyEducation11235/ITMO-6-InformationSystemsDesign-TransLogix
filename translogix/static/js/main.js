/**
 * TransLogix — общие утилиты для всех страниц
 */

// ── Fetch helper ────────────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const merged = { ...defaults, ...options };
  if (options.headers) merged.headers = { ...defaults.headers, ...options.headers };

  try {
    const resp = await fetch(url, merged);
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || `Ошибка ${resp.status}`, 'danger');
      return null;
    }
    return data;
  } catch (err) {
    showToast('Ошибка соединения с сервером', 'danger');
    return null;
  }
}

// ── Toast notifications ──────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons = {
    success: 'bi-check-circle-fill text-success',
    warning: 'bi-exclamation-triangle-fill text-warning',
    danger: 'bi-x-circle-fill text-danger',
    info: 'bi-info-circle-fill text-primary',
  };
  const icon = icons[type] || icons.info;

  const id = 'toast-' + Date.now();
  const html = `
    <div id="${id}" class="toast align-items-center border-0 bg-white shadow" role="alert" aria-live="assertive">
      <div class="d-flex align-items-center p-3 gap-2">
        <i class="bi ${icon} fs-5"></i>
        <span class="flex-grow-1">${message}</span>
        <button type="button" class="btn-close btn-sm ms-2" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML('beforeend', html);

  const el = document.getElementById(id);
  const toast = new bootstrap.Toast(el, { delay: 3500 });
  toast.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

// ── Status helpers ───────────────────────────────────────────────────────────
function statusLabel(status) {
  const labels = { new: 'Новый', in_route: 'В маршруте', completed: 'Выполнен' };
  return labels[status] || status;
}

function statusBadge(status) {
  const badges = {
    new: 'bg-primary',
    in_route: 'bg-warning text-dark',
    completed: 'bg-success',
  };
  return badges[status] || 'bg-secondary';
}

// ── Date formatter ───────────────────────────────────────────────────────────
function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
}
