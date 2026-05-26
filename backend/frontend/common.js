/* common.js — 所有页面共享的工具函数 */

// ── 认证管理 ──────────────────────────────────────────────────
const AUTH = {
  getToken   : () => localStorage.getItem('token'),
  getUsername: () => localStorage.getItem('username'),
  getRole    : () => localStorage.getItem('role'),
  save(token, username, role) {
    localStorage.setItem('token',    token);
    localStorage.setItem('username', username);
    localStorage.setItem('role',     role);
  },
  clear() {
    ['token', 'username', 'role'].forEach(k => localStorage.removeItem(k));
  },
  /** 未登录则跳转登录页，返回 false */
  guard() {
    if (!this.getToken()) {
      window.location.href = '/frontend/login.html';
      return false;
    }
    return true;
  },
};

// ── API 请求封装 ───────────────────────────────────────────────
async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  const token = AUTH.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res;
  try {
    res = await fetch('/api' + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    toast('网络错误，请检查服务是否启动', 'danger');
    throw err;
  }

  if (res.status === 401) {
    AUTH.clear();
    window.location.href = '/frontend/login.html';
    return null;
  }

  const data = await res.json();
  return { status: res.status, data };
}

// 语法糖
const GET    = (path)       => api('GET',    path);
const POST   = (path, body) => api('POST',   path, body);
const DELETE = (path)       => api('DELETE', path);

// ── Toast 通知 ─────────────────────────────────────────────────
function toast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
  }
  const id  = 'toast-' + Date.now();
  const bg  = type === 'success' ? 'text-bg-success' : 'text-bg-danger';
  const dtid = type === 'success' ? 'toast-success' : 'toast-error';
  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center ${bg} border-0"
         role="alert" data-testid="${dtid}" data-bs-autohide="true" data-bs-delay="3500">
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast" aria-label="关闭"></button>
      </div>
    </div>`);
  const el = document.getElementById(id);
  bootstrap.Toast.getOrCreateInstance(el).show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

// ── 导航栏渲染 ─────────────────────────────────────────────────
function renderNav(activePage) {
  const username = AUTH.getUsername() || '—';
  const role     = AUTH.getRole()     || '—';
  const pages    = [
    { href: '/frontend/dashboard.html', label: '📊 总览',   key: 'dashboard' },
    { href: '/frontend/fund.html',      label: '💳 资金管理', key: 'fund'      },
    { href: '/frontend/bill.html',      label: '📄 票据管理', key: 'bill'      },
    { href: '/frontend/pool.html',      label: '🏦 资金集中', key: 'pool'      },
  ];

  const links = pages.map(p => {
    const active = p.key === activePage ? 'active fw-bold' : '';
    return `<a class="nav-link ${active}" href="${p.href}"
               data-testid="nav-${p.key}">${p.label}</a>`;
  }).join('');

  const nav = document.getElementById('main-nav');
  if (!nav) return;
  nav.innerHTML = `
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm">
      <div class="container-fluid">
        <a class="navbar-brand fw-bold" href="/frontend/dashboard.html"
           data-testid="nav-brand">🏛 司库资金管理系统</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
                data-bs-target="#navContent">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navContent">
          <div class="navbar-nav me-auto">${links}</div>
          <div class="navbar-nav align-items-center gap-2">
            <span class="nav-link text-white-50 small" data-testid="nav-user-info">
              ${username}（${role}）
            </span>
            <button id="logout-btn" class="btn btn-outline-light btn-sm"
                    data-testid="logout-btn">退出登录</button>
          </div>
        </div>
      </div>
    </nav>`;

  document.getElementById('logout-btn').addEventListener('click', async () => {
    await POST('/auth/logout');
    AUTH.clear();
    window.location.href = '/frontend/login.html';
  });
}

// ── 通用工具 ───────────────────────────────────────────────────
/** 格式化金额，加千分位 */
function fmtAmount(n) {
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2 });
}

/** 状态 → 徽章 */
function statusBadge(status) {
  const map = {
    active:     ['success', '正常'],
    frozen:     ['secondary','已冻结'],
    pending:    ['warning',  '审批中'],
    executed:   ['success',  '已执行'],
    rejected:   ['danger',   '已拒绝'],
    holding:    ['info',     '持有中'],
    endorsed:   ['primary',  '已背书'],
    discounted: ['secondary','已贴现'],
    overdue:    ['danger',   '已逾期'],
    completed:  ['success',  '已完成'],
  };
  const [color, label] = map[status] || ['light', status];
  return `<span class="badge text-bg-${color}" data-testid="status-badge">${label}</span>`;
}

/** 将表格行变成 "空数据" 提示 */
function emptyRow(colspan, msg = '暂无数据') {
  return `<tr><td colspan="${colspan}" class="text-center text-muted py-4"
               data-testid="empty-row">${msg}</td></tr>`;
}

/** 简单的加载遮罩 */
function setLoading(btnEl, loading) {
  if (loading) {
    btnEl.disabled = true;
    btnEl._orig = btnEl.innerHTML;
    btnEl.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 处理中…`;
  } else {
    btnEl.disabled  = false;
    btnEl.innerHTML = btnEl._orig || btnEl.innerHTML;
  }
}
