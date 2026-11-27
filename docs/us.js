/* 存股雷達・美股：資料來自 us/index.json（每年 4 月底依 SEC 年報篩選一次）
   選股法：近5年ROE每年≥12%、股東回報率(股利+庫藏股)/市值≥4%、近一年營收成長≥5%，三項全過才入選；排除金融業。 */
(function () {
  "use strict";
  var app = document.getElementById("app"), updatedEl = document.getElementById("updated");
  var D = null, C = {}, PAGE = 60;
  var state = { tab: "pick", q: "", ind: "", sort: "group", shown: PAGE };
  var NAMES = ["ROE", "股東回報", "營收"];
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function fmt(v, d, s) { return isNum(v) ? v.toLocaleString("zh-TW", { minimumFractionDigits: d, maximumFractionDigits: d }) + (s || "") : "—"; }
  function pct(v) { return isNum(v) ? '<span class="' + (v >= 0 ? "pos" : "neg") + '">' + (v >= 0 ? "+" : "") + fmt(v, 1, "%") + "</span>" : "—"; }
  function flagsHtml(f) {
    var h = '<span class="sq" title="ROE / 股東回報率 / 營收成長">';
    for (var i = 0; i < 3; i++) { var c = (f || "---").charAt(i); h += '<i class="' + (c === "1" ? "good" : c === "0" ? "bad" : "") + '">' + NAMES[i].charAt(0) + "</i>"; }
    return h + "</span>";
  }
  function title(s) { return s.zh && s.zh !== s.c ? s.zh : s.n; }
  function cond() { return "近" + C.roe_years + "年 ROE 每年 ≥ " + C.roe_min + "%、股東回報率 ≥ " + C.shy_min + "%、近一年營收成長 ≥ " + C.rev_min + "%"; }

  function filtered() {
    var q = state.q.trim().toLowerCase();
    var L = D.stocks.filter(function (s) {
      if (state.tab === "pick" && !s.ok) return false;
      if (state.ind && s.i !== state.ind) return false;
      if (q && s.c.toLowerCase().indexOf(q) < 0 && (s.n || "").toLowerCase().indexOf(q) < 0 && (s.zh || "").toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    function n(v, d) { return isNum(v) ? v : d; }
    var cmp = {
      roe: function (a, b) { return n(b.rm, -999) - n(a.rm, -999); },
      shy: function (a, b) { return n(b.shy, -1) - n(a.shy, -1); },
      rev: function (a, b) { return n(b.rg, -999) - n(a.rg, -999); },
      ret: function (a, b) { return n(b.ret, -999) - n(a.ret, -999); },
      mcap: function (a, b) { return n(b.mcap, 0) - n(a.mcap, 0); },
      pass: function (a, b) { return (b.k || 0) - (a.k || 0) || n(b.mcap, 0) - n(a.mcap, 0); },
      code: function (a, b) { return a.c < b.c ? -1 : 1; }
    };
    var by = cmp[state.sort] || cmp.roe;
    if (state.tab === "pick" && state.sort === "group") L.sort(function (a, b) { return (a.i || "").localeCompare(b.i || "", "zh-TW") || cmp.roe(a, b); });
    else L.sort(by);
    return L;
  }
  function card(s) {
    var chips = [["ROE5年最低", fmt(s.rm, 1, "%")], ["股東回報率", fmt(s.shy, 1, "%")], ["殖利率", fmt(s.y, 1, "%")],
      ["營收成長", fmt(s.rg, 1, "%")], ["負債比", fmt(s.db, 0, "%")], ["PB", fmt(s.pb, 1)]]
      .map(function (x) { return '<span class="chip">' + x[0] + " " + x[1] + "</span>"; }).join("");
    var tag = s.ok ? '<span class="chip good">三項通過</span>' : '<span class="chip">' + (s.k || 0) + "/3</span>";
    return '<a class="card" href="#/s/' + esc(s.c) + '"><div class="row"><div><span class="name">' + esc(title(s)) + '</span><span class="code">' + esc(s.c) + "</span></div>" +
      '<div class="price">$' + fmt(s.p, 2) + "</div></div>" +
      '<div class="meta">' + flagsHtml(s.f) + tag + "<span>" + esc(s.i || "") + "</span><span>4/30 起 " + pct(s.ret) + "</span></div>" +
      (s.hl ? '<div class="hl">' + esc(s.hl) + "</div>" : "") + '<div class="chips">' + chips + "</div></a>";
  }
  function fillResults() {
    var box = document.getElementById("results"); if (!box) return;
    var L = filtered(), html = "";
    if (!L.length) html = '<div class="empty">找不到符合的股票。</div>';
    else if (state.tab === "pick" && state.sort === "group") {
      var cur = null, cnt = {};
      L.forEach(function (s) { cnt[s.i] = (cnt[s.i] || 0) + 1; });
      L.forEach(function (s) { if (s.i !== cur) { cur = s.i; html += '<div class="group-h"><span>' + esc(cur) + "</span><span>" + cnt[cur] + " 檔</span></div>"; } html += card(s); });
    } else {
      L.slice(0, state.shown).forEach(function (s) { html += card(s); });
      if (L.length > state.shown) html += '<button class="more" id="more">再顯示 ' + Math.min(PAGE, L.length - state.shown) + " 檔（共 " + L.length + "）</button>";
    }
    box.innerHTML = html;
    var m = document.getElementById("more"); if (m) m.onclick = function () { state.shown += PAGE; fillResults(); };
  }
  function renderList() {
    var inds = {}; D.stocks.forEach(function (s) { if (s.i && (state.tab === "all" || s.ok)) inds[s.i] = 1; });
    var indOpts = '<option value="">全部產業</option>' + Object.keys(inds).sort(function (a, b) { return a.localeCompare(b, "zh-TW"); })
      .map(function (i) { return "<option" + (i === state.ind ? " selected" : "") + ">" + esc(i) + "</option>"; }).join("");
    var sorts = (state.tab === "pick" ? [["group", "依產業分組"]] : []).concat([["roe", "ROE 高→低"], ["shy", "股東回報率高→低"], ["rev", "營收成長高→低"], ["ret", "4/30 起漲幅"], ["mcap", "市值大→小"], ["pass", "通過項目多→少"], ["code", "代號"]])
      .map(function (x) { return '<option value="' + x[0] + '"' + (x[0] === state.sort ? " selected" : "") + ">" + x[1] + "</option>"; }).join("");
    app.innerHTML = '<div class="tabs" role="tablist"><button class="tab" data-tab="pick" aria-selected="' + (state.tab === "pick") + '">美股優等生</button>' +
      '<button class="tab" data-tab="all" aria-selected="' + (state.tab === "all") + '">全部股票</button></div>' +
      '<div class="controls"><input id="q" type="search" placeholder="搜尋代號或名稱" value="' + esc(state.q) + '"><select id="ind">' + indOpts + '</select><select id="sort">' + sorts + "</select></div>" +
      '<p class="hint">' + (state.tab === "pick" ? D.meta.screen_date.replace(/-/g, "/") + " 換股名單，三項全過才入選：" + esc(cond()) + "。方塊依序為 ROE／股東回報／營收，綠＝通過、紅＝未過。"
        : "美股市值前 1,500 大中的非金融股（以 " + D.meta.screen_date.replace(/-/g, "/") + " 資料篩選）。") + "</p><div id=\"results\"></div>";
    fillResults();
    Array.prototype.forEach.call(app.querySelectorAll(".tab"), function (b) { b.onclick = function () { state.tab = b.getAttribute("data-tab"); state.shown = PAGE; state.ind = ""; if (state.tab === "all" && state.sort === "group") state.sort = "roe"; if (state.tab === "pick") state.sort = "group"; renderList(); }; });
    var q = document.getElementById("q"), comp = false;
    q.addEventListener("compositionstart", function () { comp = true; });
    q.addEventListener("compositionend", function () { comp = false; state.q = q.value; state.shown = PAGE; fillResults(); });
    q.addEventListener("input", function () { if (comp) return; state.q = q.value; state.shown = PAGE; fillResults(); });
    document.getElementById("ind").onchange = function () { state.ind = this.value; state.shown = PAGE; fillResults(); };
    document.getElementById("sort").onchange = function () { state.sort = this.value; fillResults(); };
  }
  function renderStock(code) {
    var a = null; D.stocks.forEach(function (s) { if (s.c === code) a = s; });
    if (!a) { app.innerHTML = '<a class="back" href="#/">‹ 回清單</a><div class="empty">找不到這檔股票。</div>'; return; }
    var cls = a.ok ? "good" : "bad";
    var html = '<a class="back" href="#/">‹ 回清單</a><section class="sec"><div class="row"><div><span class="name">' + esc(title(a)) + '</span><span class="code">' + esc(a.c) + " · " + esc(a.i) + "</span></div>" +
      '<div class="price">$' + fmt(a.p, 2) + "</div></div><div class=\"note\">" + esc(a.n) + " · 市值約 " + fmt(a.mcap * 10, 0) + " 億美元</div>" +
      '<div class="big ' + cls + '" style="margin-top:8px">' + (a.ok ? "三項全過，列入 " + D.meta.screen_date.slice(0, 4) + " 年名單" : "未入選（" + a.k + "/3）") + "</div>" +
      (a.hl ? '<p class="note">' + esc(a.hl) + "</p>" : "") + '<p class="note">' + (a.p0 ? "4/30 收盤 $" + fmt(a.p0, 2) + "，" : "") + "4/30 至 " + esc(D.meta.price_date) + " 含息報酬 " + pct(a.ret) + "</p></section>";
    var chk = [
      [a.f.charAt(0) === "1", "獲利能力", "近 5 年 ROE 最低值", fmt(a.rm, 1, "%"), "≥ " + C.roe_min + "%", "每年淨利 ÷ 平均股東權益，取 5 年中最低的一年"],
      [a.f.charAt(1) === "1", "回饋股東", "股東回報率", fmt(a.shy, 1, "%"), "≥ " + C.shy_min + "%", (isNum(a.div) ? "（現金股利 " + fmt(a.div, 0) + " + 買回庫藏股 " + fmt(a.bb, 0) + " 百萬美元）÷ 市值" : "（現金股利＋買回庫藏股）÷ 市值")],
      [a.f.charAt(2) === "1", "成長", "近一年營收成長", fmt(a.rg, 1, "%"), "≥ " + C.rev_min + "%", (isNum(a.rev) ? "營收 " + fmt(a.rev, 0) + " vs 前一年 " + fmt(a.rev0, 0) + " 百萬美元" : "最近一個會計年度 vs 前一年")]];
    html += '<section class="sec"><h2>三項選股條件</h2>';
    chk.forEach(function (c) {
      html += '<div class="ind"><div class="mk">' + (c[0] ? '<span class="ok-mk">✔</span>' : '<span class="no-mk">✘</span>') + '</div><div class="t">' + c[1] + '</div><div class="v">' + c[3] + '</div><div class="s">' + c[2] + "：" + esc(c[5]) + '</div><div class="std">標準 ' + c[4] + "</div></div>";
    });
    html += '<p class="note">參考（不列入條件）：現金殖利率 ' + fmt(a.y, 1, "%") + "、負債比 " + fmt(a.db, 1, "%") + "、股價淨值比 " + fmt(a.pb, 1) + (a.fy_end ? "。會計年度結束於 " + esc(a.fy_end) : "") + "。</p></section>";
    if (a.rh) {
      var y0 = +D.meta.screen_date.slice(0, 4) - 5;
      html += '<section class="sec"><h2>年度 ROE（%）</h2><div class="scroll"><table><tr><th>會計年度</th>' + a.rh.map(function (v, i) { return "<th>" + (y0 + i) + "</th>"; }).reverse().join("") +
        "</tr><tr><td>ROE</td>" + a.rh.map(function (v) { return '<td class="' + (!isNum(v) ? "" : v >= C.roe_min ? "good" : "bad") + '">' + fmt(v, 1) + "</td>"; }).reverse().join("") + "</tr></table></div></section>";
    }
    html += '<section class="sec"><h2>相關連結</h2><div class="links"><a href="https://finance.yahoo.com/quote/' + encodeURIComponent(a.c) + '" target="_blank" rel="noopener">Yahoo Finance</a>' +
      '<a href="https://www.sec.gov/edgar/browse/?CIK=' + encodeURIComponent(a.c) + '" target="_blank" rel="noopener">SEC 財報</a></div></section>';
    app.innerHTML = html; window.scrollTo(0, 0);
  }
  function renderAbout() {
    var Y = D.meta.backtest.years, rows = "";
    Object.keys(Y).forEach(function (y) { var v = Y[y]; rows += "<tr><td>" + y + (y === "2026" ? "*" : "") + "</td><td>" + v[2] + "</td><td>" + pct(v[0]) + "</td><td>" + pct(v[1]) + "</td></tr>"; });
    app.innerHTML = '<a class="back" href="#/">‹ 回清單</a><section class="sec about"><h2>選股方法（美股）</h2>' +
      "<p>從美國市值前 1,500 大公司（約等於 S&P 1500）中排除金融業，三項條件全部通過才入選：</p><ol>" +
      "<li><b>近 5 年 ROE 每年都 ≥ 12%</b>：長期高獲利，沒有爛掉的年度。</li>" +
      "<li><b>股東回報率 ≥ 4%</b>：（現金股利＋買回庫藏股）÷ 市值。美國公司常用庫藏股代替發股利，所以把兩者合計。</li>" +
      "<li><b>近一年營收成長 ≥ 5%</b>。</li></ol>" +
      "<h3>為什麼和台股條件不一樣</h3><ul><li>台股的「PB ≤ 1.5、殖利率 ≥ 4%」在美股大型股每年只選得到 0～1 檔。</li>" +
      "<li>在美股回測中，要求「便宜」（低 PB、高殖利率）反而讓報酬變差；長期高 ROE＋營收成長＋回饋股東比較有效。</li></ul>" +
      "<h3>回測結果（每年 4 月底換股，等權重，已扣交易成本）</h3><div class=\"scroll\"><table><tr><th>年度（4月→隔年4月）</th><th>檔數</th><th>本方法</th><th>S&amp;P 500</th></tr>" + rows + "</table></div>" +
      "<ul><li>2015～2025 年化 17.2%，S&amp;P 500 13.8%；最差一年 −6.3%；選中的股票約 70% 賺錢（全部股票平均 58%）。</li>" +
      "<li>* 2026 為 4/30 至 " + esc(D.meta.price_date) + " 的報酬。</li></ul>" +
      "<h3>使用方式（一年只動一次）</h3><ol><li>每年 4 月底看一次名單（美國公司年報多在 3 月底前公布）。</li><li>名單上有、手上沒有的，買進。</li><li>手上有、名單上已經沒有的，賣掉。</li><li>其他時間只看，不買也不賣。名單不到 10 檔時，沒買滿的部分留現金。</li></ol>" +
      "<h3>限制（請務必看）</h3><ul>" +
      "<li><b>結果可能高估</b>：已下市或被併購的公司查不到股價，只能排除，等於只看存活下來的公司；估計每年高估約 2～3 個百分點。</li>" +
      "<li><b>不是乾淨的樣本外驗證</b>：只用 2015～2019 年選出的最佳組合，2020～2025 年是 15.8%，輸給 S&amp;P 500 的 17.9%。本頁條件是看過全期資料後挑出的穩定組合。</li>" +
      "<li>S&amp;P 500 在這段期間沒有任何一年（4月→4月）虧損，這方法的優勢是「選中的股票多數賺錢」，不保證每年贏大盤。</li>" +
      "<li>名單每年 4 月底更新一次；股價為 " + esc(D.meta.price_date) + " 的月資料。僅供自我檢視，非投資建議。</li></ul></section>";
  }
  function route() {
    var h = location.hash || "#/", m = h.match(/^#\/s\/([\w.\-]+)/);
    if (m) return renderStock(m[1]);
    if (h === "#/about") return renderAbout();
    renderList();
  }
  fetch("us/index.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (j) {
    D = { meta: j.meta, stocks: j.rows.map(function (r) { var o = {}; j.cols.forEach(function (k, i) { if (r[i] != null) o[k] = r[i]; }); o.ok = o.f === "111"; o.k = (o.f || "").split("1").length - 1; return o; }) }; C = j.meta.config;
    updatedEl.textContent = j.meta.screen_date.replace(/-/g, "/") + " 換股名單 · 入選 " + j.meta.n_ok + " / " + j.meta.n + " 檔 · 股價 " + j.meta.price_date;
    window.addEventListener("hashchange", route); route();
  }).catch(function (e) { app.innerHTML = '<div class="empty">資料載入失敗：' + esc(e.message) + "</div>"; });
})();
