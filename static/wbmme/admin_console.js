/* Admin panel (US-37, MLE-F-016; SAD 4.5.3).
 *
 * Talks to /api/admin/users, /api/admin/datasets and /api/admin/audit. Every
 * destructive action (a role change, deactivating an account, deleting a
 * dataset) asks for confirmation first (SAD 4.5.5).
 *
 * Names of users and datasets, and the targets in the audit log, come from
 * other people, so nothing is ever written into the page as HTML: only with
 * textContent.
 */
(function () {
  'use strict';

  var root = document.getElementById('admin-console');
  if (!root) { return; }
  var currentUserId = Number(root.dataset.currentUserId);

  var ROLES = [
    ['STUDENT', 'Student'], ['DATA_SCIENTIST', 'Data Scientist'], ['ADMIN', 'Admin']
  ];
  var ROLE_LABELS = {};
  ROLES.forEach(function (pair) { ROLE_LABELS[pair[0]] = pair[1]; });

  var state = {
    users: { page: 1, loaded: false },
    datasets: { page: 1, loaded: false },
    audit: { page: 1, loaded: false }
  };

  function byId(id) { return document.getElementById(id); }

  function el(tag, text, className) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) { node.textContent = text; }
    if (className) { node.className = className; }
    return node;
  }

  // ---- talking to the API ---------------------------------------------------------

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function api(method, url, body) {
    var options = {
      method: method,
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json', 'X-CSRFToken': csrfToken() }
    };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (response) {
      if (response.status === 204) { return { ok: true, status: 204, body: null }; }
      return response.json().then(
        function (data) { return { ok: response.ok, status: response.status, body: data }; },
        function () { return { ok: false, status: response.status, body: null }; }
      );
    }).catch(function () {
      return { ok: false, status: 0, body: null };
    });
  }

  function errorText(result) {
    if (result.body && result.body.error) { return result.body.error.message; }
    return 'Something went wrong. Check your connection and try again.';
  }

  // ---- messages -------------------------------------------------------------------

  function showMessage(text, isError) {
    var box = byId('console-message');
    box.textContent = text;
    box.classList.toggle('is-error', Boolean(isError));
    box.hidden = false;
  }

  function clearMessage() { byId('console-message').hidden = true; }

  // ---- small helpers --------------------------------------------------------------

  function formatDate(iso) {
    return iso ? new Date(iso).toLocaleString() : '—';
  }

  function formatSize(bytes) {
    if (bytes < 1024) { return bytes + ' B'; }
    if (bytes < 1024 * 1024) { return (bytes / 1024).toFixed(1) + ' KB'; }
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function fillRows(tableId, rows, columns) {
    var body = byId(tableId).querySelector('tbody');
    body.textContent = '';
    if (!rows.length) {
      var row = el('tr', null, 'empty-row');
      var cell = el('td', 'Nothing to show.');
      cell.colSpan = columns;
      row.appendChild(cell);
      body.appendChild(row);
    }
    return body;
  }

  function renderPager(containerId, meta, goTo) {
    var box = byId(containerId);
    box.textContent = '';
    box.appendChild(el('span', 'Page ' + meta.page + ' of ' + meta.pages + ' (' + meta.total + ' in total)'));
    var prev = el('button', 'Previous');
    prev.type = 'button';
    prev.disabled = meta.page <= 1;
    prev.addEventListener('click', function () { goTo(meta.page - 1); });
    var next = el('button', 'Next');
    next.type = 'button';
    next.disabled = meta.page >= meta.pages;
    next.addEventListener('click', function () { goTo(meta.page + 1); });
    box.appendChild(prev);
    box.appendChild(next);
  }

  // ---- users ----------------------------------------------------------------------

  function changeUser(user, change, undo) {
    return api('PATCH', '/api/admin/users/' + user.id, change).then(function (result) {
      if (result.ok) {
        showMessage('Saved: ' + user.username + '.', false);
      } else {
        showMessage(errorText(result), true);
        if (undo) { undo(); }
      }
      loadUsers();
    });
  }

  function roleCell(user, isSelf) {
    var cell = el('td');
    var select = el('select');
    select.setAttribute('aria-label', 'Role of ' + user.username);
    if (!user.role) {
      var none = el('option', 'No role');
      none.value = '';
      select.appendChild(none);
    }
    ROLES.forEach(function (pair) {
      var option = el('option', pair[1]);
      option.value = pair[0];
      select.appendChild(option);
    });
    select.value = user.role || '';
    select.disabled = isSelf;            // an Admin cannot change their own role (the server refuses too)
    select.addEventListener('change', function () {
      var chosen = select.value;
      var question = 'Change the role of ' + user.username + ' to ' + ROLE_LABELS[chosen] + '?';
      if (!window.confirm(question)) { select.value = user.role || ''; return; }
      changeUser(user, { role: chosen }, function () { select.value = user.role || ''; });
    });
    cell.appendChild(select);
    return cell;
  }

  function statusCell(user) {
    var cell = el('td');
    cell.appendChild(el('span', user.is_active ? 'Active' : 'Deactivated',
      'status-pill' + (user.is_active ? '' : ' status-off')));
    return cell;
  }

  function actionCell(user, isSelf) {
    var cell = el('td');
    var button = el('button', user.is_active ? 'Deactivate' : 'Reactivate',
      user.is_active ? 'is-danger' : '');
    button.type = 'button';
    button.disabled = isSelf;
    button.addEventListener('click', function () {
      var question = user.is_active
        ? 'Deactivate ' + user.username + '? They will be logged out and will not be able to log in.'
        : 'Reactivate ' + user.username + '? They will be able to log in again.';
      if (window.confirm(question)) { changeUser(user, { is_active: !user.is_active }); }
    });
    cell.appendChild(button);
    return cell;
  }

  function renderUsers(data) {
    var body = fillRows('users-table', data.users, 6);
    data.users.forEach(function (user) {
      var isSelf = user.id === currentUserId;
      var row = el('tr');
      var nameCell = el('td');
      nameCell.appendChild(el('strong', user.username));
      if (isSelf) { nameCell.appendChild(el('span', '(you)', 'you-tag')); }
      row.appendChild(nameCell);
      row.appendChild(roleCell(user, isSelf));
      row.appendChild(statusCell(user));
      row.appendChild(el('td', formatDate(user.date_joined)));
      row.appendChild(el('td', formatDate(user.last_login)));
      row.appendChild(actionCell(user, isSelf));
      body.appendChild(row);
    });
    renderPager('users-pager', data.pagination, function (page) { state.users.page = page; loadUsers(); });
  }

  function loadUsers() {
    return api('GET', '/api/admin/users?page=' + state.users.page).then(function (result) {
      if (result.ok) { renderUsers(result.body); } else { showMessage(errorText(result), true); }
    });
  }

  // ---- datasets -------------------------------------------------------------------

  function deleteDataset(dataset, visibleCount) {
    var question = 'Delete "' + dataset.name + '" owned by ' + dataset.owner.username + '? ' +
      'Its training runs and trained models are deleted too. This cannot be undone.';
    if (!window.confirm(question)) { return; }
    api('DELETE', '/api/admin/datasets/' + dataset.id).then(function (result) {
      if (result.ok) {
        showMessage('Dataset deleted.', false);
        if (visibleCount === 1 && state.datasets.page > 1) { state.datasets.page -= 1; }
      } else {
        showMessage(errorText(result), true);
      }
      loadDatasets();
    });
  }

  function renderDatasets(data) {
    var body = fillRows('datasets-table', data.datasets, 5);
    data.datasets.forEach(function (dataset) {
      var row = el('tr');
      var nameCell = el('td');
      nameCell.appendChild(el('strong', dataset.name));
      row.appendChild(nameCell);
      row.appendChild(el('td', dataset.owner.username));
      row.appendChild(el('td', formatSize(dataset.size_bytes)));
      row.appendChild(el('td', formatDate(dataset.uploaded_at)));
      var actions = el('td');
      var button = el('button', 'Delete', 'is-danger');
      button.type = 'button';
      button.addEventListener('click', function () { deleteDataset(dataset, data.datasets.length); });
      actions.appendChild(button);
      row.appendChild(actions);
      body.appendChild(row);
    });
    renderPager('datasets-pager', data.pagination, function (page) { state.datasets.page = page; loadDatasets(); });
  }

  function loadDatasets() {
    return api('GET', '/api/admin/datasets?page=' + state.datasets.page).then(function (result) {
      if (result.ok) { renderDatasets(result.body); } else { showMessage(errorText(result), true); }
    });
  }

  // ---- audit log ------------------------------------------------------------------

  function renderAudit(data) {
    var body = fillRows('audit-table', data.entries, 5);
    data.entries.forEach(function (entry) {
      var row = el('tr');
      row.appendChild(el('td', formatDate(entry.timestamp)));
      row.appendChild(el('td', entry.user ? entry.user.username : '—'));
      row.appendChild(el('td', entry.action));
      row.appendChild(el('td', entry.target || '—'));
      row.appendChild(el('td', entry.ip_address || '—'));
      body.appendChild(row);
    });
    renderPager('audit-pager', data.pagination, function (page) { state.audit.page = page; loadAudit(); });
  }

  function loadAudit() {
    var url = '/api/admin/audit?page=' + state.audit.page;
    var action = byId('audit-action').value;
    if (action) { url += '&action=' + encodeURIComponent(action); }
    return api('GET', url).then(function (result) {
      if (result.ok) { renderAudit(result.body); } else { showMessage(errorText(result), true); }
    });
  }

  byId('audit-action').addEventListener('change', function () {
    state.audit.page = 1;
    loadAudit();
  });

  // ---- tabs -----------------------------------------------------------------------

  var loaders = { users: loadUsers, datasets: loadDatasets, audit: loadAudit };

  function showTab(name) {
    clearMessage();
    Object.keys(loaders).forEach(function (key) {
      var selected = key === name;
      byId('tab-' + key).setAttribute('aria-selected', selected ? 'true' : 'false');
      byId('panel-' + key).hidden = !selected;
    });
    loaders[name]();                    // always refresh, so the Admin sees current data
  }

  Object.keys(loaders).forEach(function (key) {
    byId('tab-' + key).addEventListener('click', function () { showTab(key); });
  });

  showTab('users');
}());
