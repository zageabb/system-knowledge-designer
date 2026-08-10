(function () {
  "use strict";

  function cellValue(cell) {
    const control = cell.querySelector("input:not([type=hidden]), select, textarea");
    const text = control ? (control.type === "checkbox" ? (control.checked ? "Yes" : "No") : control.value) : cell.textContent.trim();
    return {html: cell.innerHTML, text};
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, character => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[character]);
  }

  function setRows(table, rows) {
    const columnCount = table._skdColumnCount || 0;
    table._skdTabulator?.replaceData(rows.map((values, rowIndex) => {
      const row = {_row: rowIndex};
      for (let index = 0; index < columnCount; index += 1) {
        const value = values[index] ?? "";
        row[`column_${index}`] = {html: escapeHtml(value), text: String(value)};
      }
      return row;
    }));
  }

  function enhance(table) {
    if (table.dataset.tabulator === "off" || table._skdTabulator || !window.Tabulator) return;
    const headings = Array.from(table.querySelectorAll("thead th"));
    if (!headings.length) return;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const placeholderRow = bodyRows.find(row => row.cells.length === 1 && row.cells[0].colSpan > 1);
    const dataRows = bodyRows.filter(row => row !== placeholderRow);
    const data = dataRows.map((row, rowIndex) => {
      const record = {_row: rowIndex};
      Array.from(row.cells).forEach((cell, index) => { record[`column_${index}`] = cellValue(cell); });
      return record;
    });
    const columns = headings.map((heading, index) => {
      const title = heading.textContent.trim();
      const values = new Set(data.map(row => row[`column_${index}`]?.text).filter(Boolean));
      const nonFilter = /action|marker/i.test(title) || !data.length;
      const definition = {
        title,
        field: `column_${index}`,
        formatter: cell => cell.getValue()?.html || "",
        sorter: (a, b) => String(a?.text || "").localeCompare(String(b?.text || ""), undefined, {numeric: true}),
        headerSort: !/action/i.test(title),
        minWidth: /action|detail|statement|value/i.test(title) ? 190 : 110,
      };
      if (!nonFilter) {
        if (values.size > 0 && values.size <= 8) {
          definition.headerFilter = "list";
          definition.headerFilterParams = {values: {"": "All", ...Object.fromEntries(Array.from(values).sort().map(value => [value, value]))}, clearable: true};
          definition.headerFilterFunc = (needle, value) => !needle || value?.text === needle;
        } else {
          definition.headerFilter = "input";
          definition.headerFilterPlaceholder = "Filter…";
          definition.headerFilterFunc = (needle, value) => String(value?.text || "").toLocaleLowerCase().includes(String(needle).toLocaleLowerCase());
        }
      }
      return definition;
    });
    table._skdColumnCount = columns.length;
    table._skdSetRows = rows => setRows(table, rows);
    table._skdTabulator = new Tabulator(table, {
      data,
      columns,
      layout: "fitDataStretch",
      responsiveLayout: "collapse",
      placeholder: placeholderRow?.textContent.trim() || "No rows",
      pagination: data.length > 20 ? "local" : false,
      paginationSize: 20,
      paginationSizeSelector: [20, 50, 100],
      movableColumns: true,
      columnDefaults: {resizable: true, tooltip: true},
    });
  }

  function enhanceAll() { document.querySelectorAll("table").forEach(enhance); }
  window.SystemKnowledgeTables = {enhance, enhanceAll, setRows};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhanceAll);
  else enhanceAll();
}());
