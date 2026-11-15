const queryForm = document.querySelector('#query-form');
const queryInput = document.querySelector('#query-input');

if (queryForm) {
  queryForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const query = queryInput.value.trim();
    if (!query) {
      queryInput.focus();
      return;
    }
    window.localStorage.setItem('economic-agent-query', query);
    window.location.href = '/answer.html';
  });

  document.querySelectorAll('[data-query]').forEach((button) => {
    button.addEventListener('click', () => {
      queryInput.value = button.dataset.query;
      queryInput.focus();
    });
  });
}

const questionText = document.querySelector('#question-text');
if (questionText) {
  const query = window.localStorage.getItem('economic-agent-query') || '';
  questionText.textContent = query || 'No question was entered';
  if (!query) {
    showError('Go back and enter a question about GDP or Core CPI.');
  } else {
    fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'The agent could not answer this question.');
        return payload;
      })
      .then(renderResult)
      .catch((error) => showError(error.message));
  }
}

function renderResult(result) {
  document.querySelector('#loading-state').hidden = true;
  document.querySelector('#result-content').hidden = false;
  document.querySelector('#answer-text').textContent = result.answer;
  renderMetrics(result.metrics || []);
  renderWarnings(result.warnings || []);
  renderSources(result.sources || []);
  if (result.chart) {
    document.querySelector('#chart-title').textContent = result.chart.title;
    renderChart(result.chart);
  } else {
    document.querySelector('.chart-card').hidden = true;
  }
}

function renderMetrics(metrics) {
  const container = document.querySelector('#metrics-list');
  container.innerHTML = metrics.map((metric) => `
    <div class="metric-row">
      <span class="metric-label">${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
      ${metric.detail ? `<small>${escapeHtml(metric.detail)}</small>` : ''}
    </div>
  `).join('');
}

function renderWarnings(warnings) {
  const container = document.querySelector('#warnings');
  if (!warnings.length) {
    container.hidden = true;
    return;
  }
  container.innerHTML = warnings.map((warning) => `<div class="warning">ⓘ ${escapeHtml(warning)}</div>`).join('');
}

function renderSources(sources) {
  document.querySelector('#sources-list').innerHTML = sources.map((source) => `
    <div class="source-row">
      <div><strong>${escapeHtml(source.series_id)} · ${escapeHtml(source.name)}</strong><small>${escapeHtml(source.local_grounding)}</small></div>
      <a href="${escapeAttribute(source.url)}" target="_blank" rel="noreferrer">Open FRED ↗</a>
    </div>
  `).join('');
}

function renderChart(chart) {
  const wrap = document.querySelector('#chart-wrap');
  const width = 900;
  const height = 390;
  const padding = { top: 22, right: 28, bottom: 52, left: 64 };
  const allValues = chart.series.flatMap((series) => series.values.map((point) => point.value));
  if (!allValues.length) {
    wrap.innerHTML = '<div class="empty-chart">Not enough observations to draw a chart.</div>';
    return;
  }
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const span = max - min || Math.abs(max) || 1;
  const yMin = min - span * 0.08;
  const yMax = max + span * 0.08;
  const dates = [...new Set(chart.series.flatMap((series) => series.values.map((point) => point.date)))].sort();
  const x = (index) => padding.left + (index / Math.max(dates.length - 1, 1)) * (width - padding.left - padding.right);
  const y = (value) => padding.top + (1 - (value - yMin) / (yMax - yMin)) * (height - padding.top - padding.bottom);
  const colors = ['#e86f51', '#1b6ca8', '#4e9f70'];
  const grid = Array.from({ length: 5 }, (_, index) => {
    const value = yMin + ((yMax - yMin) * index) / 4;
    const yy = y(value);
    return `<line x1="${padding.left}" y1="${yy}" x2="${width - padding.right}" y2="${yy}" class="chart-grid" />
      <text x="${padding.left - 12}" y="${yy + 4}" text-anchor="end" class="chart-axis-label">${formatChartValue(value)}</text>`;
  }).join('');
  const lines = chart.series.map((series, seriesIndex) => {
    const points = series.values.map((point) => `${x(dates.indexOf(point.date))},${y(point.value)}`).join(' ');
    const dots = series.values.map((point) => `<circle cx="${x(dates.indexOf(point.date))}" cy="${y(point.value)}" r="3.5" fill="${colors[seriesIndex % colors.length]}" />`).join('');
    return `<polyline points="${points}" fill="none" stroke="${colors[seriesIndex % colors.length]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />${dots}`;
  }).join('');
  const xLabels = dates.filter((_, index) => dates.length < 10 || index % Math.ceil(dates.length / 7) === 0).map((date) => `<text x="${x(dates.indexOf(date))}" y="${height - 18}" text-anchor="middle" class="chart-axis-label">${escapeHtml(date)}</text>`).join('');
  wrap.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttribute(chart.title)}">
    ${grid}<line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" class="chart-axis" />
    ${lines}${xLabels}<text x="18" y="${height / 2}" transform="rotate(-90 18 ${height / 2})" class="chart-y-label">${escapeHtml(chart.y_label || '')}</text>
  </svg>`;
  document.querySelector('#chart-legend').innerHTML = chart.series.map((series, index) => `<span><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(series.name)}</span>`).join('');
}

function showError(message) {
  const loading = document.querySelector('#loading-state');
  if (loading) loading.hidden = true;
  const error = document.querySelector('#error-state');
  if (error) {
    error.hidden = false;
    error.textContent = message;
  }
}

function formatChartValue(value) {
  return Math.abs(value) >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(1);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}
