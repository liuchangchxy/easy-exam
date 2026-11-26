/* EasyExam 设计规范 · 图标符号表（语义对齐后）
   每个页面引入本脚本即可使用 <svg class="od-icon"><use href="#i-name"/></svg>
   命名按用户动作定义：import=拿进来 / export=拿出去 / archive=归档 / restore=撤销归档 / trash=删除 */
(function () {
  var P = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/>',
    library: '<path d="M4 4h5v16H4z"/><path d="M11 4h4v16h-4z"/><path d="M17 5l3 15"/><path d="M4 4h5"/>',
    review: '<path d="M3.5 12a8.5 8.5 0 1 1 2.6 6.1"/><path d="M3.5 20v-5h5"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    exam: '<rect x="4.5" y="3.5" width="15" height="17" rx="1.5"/><path d="M8.5 8.5h7M8.5 12h7M8.5 15.5h4"/>',
    note: '<rect x="4.5" y="3.5" width="15" height="17" rx="1.5"/><path d="M8 3.5v3M8 9.5v0M8 13v0M8 16.5v0"/><path d="M12 8.5h4M12 12h4M12 15.5h4"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v2.6M12 18.9v2.6M4.2 7.2l2.3 1.3M17.5 15.5l2.3 1.3M4.2 16.8l2.3-1.3M17.5 8.5l2.3-1.3"/>',
    more: '<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/>',
    plus: '<path d="M12 4.5v15M4.5 12h15"/>',
    x: '<path d="M5.5 5.5l13 13M18.5 5.5l-13 13"/>',
    check: '<path d="M4.5 12.5l5 5 10-11"/>',
    'alert-triangle': '<path d="M12 3.5 2.5 20h19L12 3.5z"/><path d="M12 9.5v4.5"/><path d="M12 17.2v.3"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><path d="M12 7.8v.3"/>',
    play: '<path d="M7 4.5v15l12-7.5-12-7.5z"/>',
    'arrow-left': '<path d="M20 12H4"/><path d="M10.5 5.5 4 12l6.5 6.5"/>',
    'arrow-right': '<path d="M4 12h16"/><path d="M13.5 5.5 20 12l-6.5 6.5"/>',
    'chevron-right': '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
    'chevron-down': '<path d="M5.5 9.5 12 16l6.5-6.5"/>',
    'chevron-up': '<path d="M5.5 14.5 12 8l6.5 6.5"/>',
    trash: '<path d="M4.5 6.5h15"/><path d="M9.5 6.5V4.5h5v2"/><path d="M6.5 6.5 7.5 20h9l1-13.5"/><path d="M10.5 10v6M13.5 10v6"/>',
    archive: '<rect x="3.5" y="4.5" width="17" height="4.5" rx="1"/><path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9"/><path d="M10 13h4"/>',
    restore: '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/><path d="M3.5 4v5h5"/>',
    /* import：托盘 + 箭头进入托盘（拿进来） */
    import: '<path d="M12 3.5v10"/><path d="M8.5 10 12 13.5 15.5 10"/><path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/>',
    /* export：托盘 + 箭头离开托盘（拿出去） */
    export: '<path d="M12 13.5v-10"/><path d="M8.5 7 12 3.5 15.5 7"/><path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/>',
    edit: '<path d="M4 20h4l11-11-4-4L4 16v4z"/><path d="M14.5 5.5 18.5 9.5"/>',
    copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="1.5"/><path d="M15.5 5.5A1.5 1.5 0 0 0 14 4H6a2 2 0 0 0-2 2v8a1.5 1.5 0 0 0 1.5 1.5"/>',
    users: '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6"/><path d="M17.5 14.4c2.3.7 4 2.6 4 5.6"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20c0-4.1 3.4-7 7.5-7s7.5 2.9 7.5 7"/>',
    lock: '<rect x="5" y="10.5" width="14" height="9.5" rx="1.5"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
    unlock: '<rect x="5" y="10.5" width="14" height="9.5" rx="1.5"/><path d="M8 10.5V7a4 4 0 0 1 7.5-2"/>',
    flag: '<path d="M5.5 3.5v17"/><path d="M5.5 4.5h11l-2.5 3.5 2.5 3.5h-11"/>',
    sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/>',
    moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.5 2.3 3.8 5.2 3.8 8.5s-1.3 6.2-3.8 8.5c-2.5-2.3-3.8-5.2-3.8-8.5S9.5 5.8 12 3.5z"/>',
    logout: '<path d="M14 3.5H7A2 2 0 0 0 5 5.5v13a2 2 0 0 0 2 2h7"/><path d="M17.5 8.5 21 12l-3.5 3.5"/><path d="M21 12h-9"/>',
    key: '<circle cx="8" cy="15.5" r="4.5"/><path d="M11 12.5 20 3.5"/><path d="M16.5 7l3 3"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.2l3.5 2"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="16" rx="1.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    chart: '<path d="M4 20h16"/><path d="M7 20v-7M12 20V6M17 20v-4"/>',
    target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    zap: '<path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12l1-8z"/>',
    draft: '<path d="M6 3.5h8L19 8.5V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M13.5 3.5v5H19"/><path d="M9 13l3.5 3.5L20 9"/>',
    cpu: '<rect x="6.5" y="6.5" width="11" height="11" rx="1.5"/><rect x="10" y="10" width="4" height="4" rx=".5"/><path d="M9 3.5v3M15 3.5v3M9 17.5v3M15 17.5v3M3.5 9h3M3.5 15h3M17.5 9h3M17.5 15h3"/>',
    link: '<path d="M9.5 14.5 14.5 9.5"/><path d="M11 5.5h3.5a4 4 0 0 1 0 8H13"/><path d="M13 18.5H9.5a4 4 0 0 1 0-8H11"/>',
    filter: '<path d="M3.5 5.5h17l-6.5 7.5v6l-4-2v-4L3.5 5.5z"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.4-5.7"/><path d="M20 3.5V8h-4.5"/>',
    save: '<path d="M5 3.5h11L20.5 8v12a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1v-16a1 1 0 0 1 1-1z"/><path d="M8.5 3.5v5h7"/><path d="M8.5 14.5h7v6h-7z"/>',
    download: '<path d="M12 3.5v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/><path d="M4.5 19.5h15"/>',
    external: '<path d="M14 4.5h5.5V10"/><path d="M19.5 4.5 11 13"/><path d="M18 14v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    folder: '<path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4l2 2.5h8A1.5 1.5 0 0 1 20.5 9v9a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 18V6.5z"/>',
    'file-text': '<path d="M6 3.5h8L19 8.5V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"/><path d="M13.5 3.5v5H19"/><path d="M9 13h6M9 16.5h4"/>',
    shield: '<path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6l-7-2.5z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    command: '<path d="M8 4.5H6.5A2.5 2.5 0 0 0 4 7v2.5h4V4.5z"/><path d="M16 4.5h-1.5A2.5 2.5 0 0 0 12 7v2.5h4V4.5z"/><path d="M8 14.5H4V17a2.5 2.5 0 0 0 2.5 2.5H8v-5z"/><path d="M16 14.5h-4v5H16a2.5 2.5 0 0 0 2.5-2.5v-2.5z"/>',
    inbox: '<path d="M3.5 12.5h4l1.5 2.5h6l1.5-2.5h4"/><path d="M5.5 4.5h13l3 8v6a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1v-6l3-8z"/>',
    list: '<path d="M8.5 6.5h12M8.5 12h12M8.5 17.5h12"/><path d="M4 6.5h.01M4 12h.01M4 17.5h.01"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
    columns: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><path d="M9.2 4.5v15M14.8 4.5v15"/>',
    book: '<path d="M4.5 4.5A1.5 1.5 0 0 1 6 3h6.5v18H6a1.5 1.5 0 0 1-1.5-1.5v-15z"/><path d="M12.5 3H18a1.5 1.5 0 0 1 1.5 1.5v15A1.5 1.5 0 0 1 18 21h-5.5"/>',
    sparkles: '<path d="M12 3.5 13.8 9 19 10.8 13.8 12.6 12 18l-1.8-5.4L5 10.8 10.2 9 12 3.5z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z"/>',
    activity: '<path d="M3.5 12.5h3.5l2.5-6 4 12 2.5-6h4.5"/>',
    award: '<circle cx="12" cy="9" r="5.5"/><path d="M8.8 13.5 7 21l5-2.5L17 21l-1.8-7.5"/>',
    minus: '<path d="M4.5 12h15"/>',
    menu: '<path d="M4 6.5h16M4 12h16M4 17.5h16"/>'
  };
  var NS = 'http://www.w3.org/2000/svg';
  function sprite() {
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'icon-sprite');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = '<defs>' + Object.keys(P).map(function (k) {
      return '<symbol id="i-' + k + '" viewBox="0 0 24 24">' + P[k] + '</symbol>';
    }).join('') + '</defs>';
    document.body.appendChild(svg);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sprite);
  else sprite();
  /* 便捷函数：返回图标 HTML 字符串 */
  window.eeIcon = function (name, size) {
    var s = size ? ' style="--od-icon-size:' + size + '"' : '';
    return '<svg class="od-icon" aria-hidden="true"' + s + '><use href="#i-' + name + '"/></svg>';
  };
})();
