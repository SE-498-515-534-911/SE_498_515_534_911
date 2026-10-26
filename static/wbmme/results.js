/* Results screen (US-22, MLE-F-010, MLE-F-011).
 *
 * Polls GET /api/evaluate/<run_id> every 2 seconds (SAD 4.2.3) until the run
 * is COMPLETED or FAILED, then draws the metric tiles, the bar chart and the
 * confusion matrix.
 *
 * Class names come from the user's own CSV, so they are NEVER put into the
 * page as HTML: everything is written with textContent.
 */
(function () {
  'use strict';

  var root = document.getElementById('results');
  if (!root) { return; }
  var apiUrl = root.dataset.apiUrl;
  var pollMs = Number(root.dataset.pollMs) || 2000;

  var METRIC_LABELS = {
    accuracy: 'Accuracy', precision: 'Precision', recall: 'Recall',
    f1: 'F1', roc_auc: 'ROC-AUC'
  };
  var METRIC_ORDER = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc'];

  function byId(id) { return document.getElementById(id); }

  function el(tag, text, className) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) { node.textContent = text; }
    if (className) { node.className = className; }
    return node;
  }

  function formatScore(value) {
    return typeof value === 'number' ? value.toFixed(3) : 'Not available';
  }

  function setStatus(status) {
    var badge = byId('run-status');
    badge.dataset.state = status;
    var words = {
      QUEUED: 'Queued…', RUNNING: 'Training…', TRAINED: 'Calculating results…',
      COMPLETED: 'Completed', FAILED: 'Failed'
    };
    badge.textContent = words[status] || status;
  }

  function showError(message) {
    var box = byId('results-error');
    box.textContent = message;
    box.hidden = false;
  }

  function renderTiles(test, averaging) {
    var tiles = byId('metric-tiles');
    tiles.textContent = '';
    METRIC_ORDER.forEach(function (name) {
      var tile = el('div', null, 'metric-tile');
      tile.appendChild(el('span', METRIC_LABELS[name]));
      tile.appendChild(el('strong', formatScore(test[name])));
      tiles.appendChild(tile);
    });
    byId('averaging-note').textContent =
      averaging === 'macro' ? '(macro-averaged over all classes)' : '(positive class)';
  }

  function renderTable(metrics) {
    var body = byId('metric-table').querySelector('tbody');
    body.textContent = '';
    METRIC_ORDER.forEach(function (name) {
      var row = el('tr');
      var head = el('th', METRIC_LABELS[name]);
      head.setAttribute('scope', 'row');
      row.appendChild(head);
      row.appendChild(el('td', formatScore(metrics.test[name])));
      row.appendChild(el('td', formatScore(metrics.train[name])));
      body.appendChild(row);
    });
  }

  function renderChart(metrics) {
    if (typeof window.Chart === 'undefined') { byId('chart-missing').hidden = false; return; }
    function series(split) {
      // null leaves a gap, so a metric that is not defined is not drawn as zero
      return METRIC_ORDER.map(function (name) {
        return typeof metrics[split][name] === 'number' ? metrics[split][name] : null;
      });
    }
    new window.Chart(byId('metric-chart'), {
      type: 'bar',
      data: {
        labels: METRIC_ORDER.map(function (name) { return METRIC_LABELS[name]; }),
        datasets: [
          { label: 'Test', data: series('test'), backgroundColor: '#42694a' },
          { label: 'Train', data: series('train'), backgroundColor: '#d8bda4' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 1 } }
      }
    });
  }

  function renderConfusionMatrix(confusion) {
    var table = byId('confusion-matrix');
    var caption = table.querySelector('caption');
    table.textContent = '';
    table.appendChild(caption);

    var head = el('tr');
    head.appendChild(el('th', 'Actual \\ Predicted'));
    confusion.labels.forEach(function (label) {
      var cell = el('th', label);
      cell.setAttribute('scope', 'col');
      head.appendChild(cell);
    });
    var thead = el('thead');
    thead.appendChild(head);
    table.appendChild(thead);

    var total = 0;
    var tbody = el('tbody');
    confusion.matrix.forEach(function (counts, i) {
      var rowTotal = counts.reduce(function (a, b) { return a + b; }, 0);
      total += rowTotal;
      var row = el('tr');
      var rowHead = el('th', confusion.labels[i]);
      rowHead.setAttribute('scope', 'row');
      row.appendChild(rowHead);
      counts.forEach(function (count, j) {
        var cell = el('td', count, i === j ? 'diagonal' : '');
        // Darker green = larger share of that actual class.
        var share = rowTotal ? count / rowTotal : 0;
        cell.style.backgroundColor = 'rgba(66, 105, 74, ' + (share * 0.75).toFixed(2) + ')';
        cell.style.color = share > 0.5 ? '#fff' : '';
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    byId('matrix-total').textContent = String(total);
  }

  function renderResults(data) {
    renderTiles(data.metrics.test, data.averaging);
    renderTable(data.metrics);
    renderChart(data.metrics);
    renderConfusionMatrix(data.confusion_matrix);
    byId('results-notes').textContent = (data.notes || []).join(' ');
    byId('results-body').hidden = false;
  }

  function handle(response) {
    var data = response.body;
    if (!response.ok) {
      setStatus('FAILED');
      showError(data && data.error ? data.error.message : 'The results could not be loaded.');
      return;
    }
    setStatus(data.status);
    if (data.status === 'FAILED') {
      showError(data.error ? data.error.message : 'The run failed.');
    } else if (data.status === 'COMPLETED' && data.metrics) {
      renderResults(data);
    } else {
      window.setTimeout(poll, pollMs);   // QUEUED, RUNNING or TRAINED: ask again
    }
  }

  function poll() {
    fetch(apiUrl, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(handle)
      .catch(function () {
        setStatus('FAILED');
        showError('The results could not be loaded. Check your connection and reload the page.');
      });
  }

  poll();
}());
