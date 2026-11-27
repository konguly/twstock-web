/* 存股雷達・美股：資料來自 us/index.json（每年 4 月底依 SEC 年報篩選一次；股價每個交易日更新）
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
  function chg(s) { return isNum(s.p) && isNum(s.p0) && s.p0 > 0 ? (s.p / s.p0 - 1) * 100 : null; }
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
      ret: function (a, b) { return n(chg(b), -999) - n(chg(a), -999); },
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
    var chips = [["ROE5年最低", fmt(s.rm, 1, "%")], ["股東回報率", fmt(s.shy, 1, "%")], ["營收成長", fmt(s.rg, 1, "%")]]
      .map(function (x) { return '<span class="chip">' + x[0] + " " + x[1] + "</span>"; }).join("");
    var tag = s.ipo ? '<span class="chip warn">新上市</span>' : s.ok ? '<span class="chip good">三項通過</span>' : '<span class="chip">' + (s.k || 0) + "/3</span>";
    var sub = s.ipo ? "<span>" + esc(s.ipo.replace(/-/g, "/")) + " 上市</span>" : "<span>4/30 起 " + pct(chg(s)) + "</span>";
    return '<a class="card" href="#/s/' + esc(s.c) + '"><div class="row"><div><span class="name">' + esc(title(s)) + '</span><span class="code">' + esc(s.c) + "</span></div>" +
      '<div class="price">$' + fmt(s.p, 2) + "</div></div>" +
      '<div class="meta">' + flagsHtml(s.f) + tag + "<span>" + esc(s.i || "") + "</span>" + sub + "</div>" +
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
    var sorts = (state.tab === "pick" ? [["group", "依產業分組"]] : []).concat([["roe", "ROE 高→低"], ["shy", "股東回報率高→低"], ["rev", "營收成長高→低"], ["ret", "4/30 起股價漲跌"], ["mcap", "市值大→小"], ["pass", "通過項目多→少"], ["code", "代號"]])
      .map(function (x) { return '<option value="' + x[0] + '"' + (x[0] === state.sort ? " selected" : "") + ">" + x[1] + "</option>"; }).join("");
    app.innerHTML = '<div class="tabs" role="tablist"><button class="tab" data-tab="pick" aria-selected="' + (state.tab === "pick") + '">美股優等生</button>' +
      '<button class="tab" data-tab="all" aria-selected="' + (state.tab === "all") + '">全部股票</button></div>' +
      '<div class="controls"><input id="q" type="search" placeholder="搜尋代號或名稱" value="' + esc(state.q) + '"><select id="ind">' + indOpts + '</select><select id="sort">' + sorts + "</select></div>" +
      '<p class="hint">' + (state.tab === "pick" ? D.meta.screen_date.replace(/-/g, "/") + " 換股名單，三項全過才入選：" + esc(cond()) + "。方塊依序為 ROE／股東回報／營收，綠＝通過、紅＝未過。"
        : "美股市值前 1,500 大中的非金融股（以 " + D.meta.screen_date.replace(/-/g, "/") + " 資料篩選），另加 " + (D.meta.n_new || 0) + " 檔近年新上市、市值 30 億美元以上的公司（標示「新上市」，未滿 5 年財報，暫不評估）。") + "</p><div id=\"results\"></div>";
    fillResults();
    Array.prototype.forEach.call(app.querySelectorAll(".tab"), function (b) { b.onclick = function () { state.tab = b.getAttribute("data-tab"); state.shown = PAGE; state.ind = ""; if (state.tab === "all" && state.sort === "group") state.sort = "roe"; if (state.tab === "pick") state.sort = "group"; renderList(); }; });
    var q = document.getElementById("q"), comp = false;
    q.addEventListener("compositionstart", function () { comp = true; });
    q.addEventListener("compositionend", function () { comp = false; state.q = q.value; state.shown = PAGE; fillResults(); });
    q.addEventListener("input", function () { if (comp) return; state.q = q.value; state.shown = PAGE; fillResults(); });
    document.getElementById("ind").onchange = function () { state.ind = this.value; state.shown = PAGE; fillResults(); };
    document.getElementById("sort").onchange = function () { state.sort = this.value; fillResults(); };
  }
  function niceStep(span, n) {
    var raw = span / n, p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }
  function axis(vals, n) {
    var v = vals.filter(isNum), lo = Math.min(0, Math.min.apply(null, v)), hi = Math.max(0, Math.max.apply(null, v));
    if (hi === lo) hi = lo + 1;
    var st = niceStep(hi - lo, n);
    return { lo: Math.floor(lo / st) * st, hi: Math.ceil(hi / st) * st, st: st };
  }
  function growthSvg(g0) {
    // 和季營收、ROE 表一致：最新的期間放最左邊
    var g = {};
    Object.keys(g0).forEach(function (k) { g[k] = Array.isArray(g0[k]) ? g0[k].slice().reverse() : g0[k]; });
    var W = 640, H = 380, L = 62, R = 46, T = 64, B = 316, n = g.labels.length;
    var bars = [["gp", "營業毛利", "#4f81bd"], ["opex", "營業費用", "#c0504d"], ["opinc", "營業利益", "#9bbb59"]];
    var lines = [["gm", "毛利率", "#8064a2"], ["exr", "營業費用率", "#4bacc6"], ["om", "營業利益率", "#f79646"]];
    var has = function (k) { return g[k].some(isNum); };
    bars = bars.filter(function (d) { return has(d[0]); }); lines = lines.filter(function (d) { return has(d[0]); });
    var la = axis([].concat(g.gp, g.opex, g.opinc), 5), ra = axis([].concat(g.gm, g.exr, g.om), 5);
    var yl = function (v) { return B - (v - la.lo) / (la.hi - la.lo) * (B - T); };
    var yr = function (v) { return B - (v - ra.lo) / (ra.hi - ra.lo) * (B - T); };
    var gw = (W - L - R) / n, bw = gw * 0.22;
    var cx = function (i) { return L + gw * (i + 0.5); };
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" class="gchart" role="img" aria-label="成長力道圖">';
    // 圖例
    bars.concat(lines).forEach(function (d, i) {
      var x = 70 + (i % 3) * 190, y = 16 + Math.floor(i / 3) * 22, isBar = i < bars.length;
      s += isBar ? '<rect x="' + x + '" y="' + (y - 9) + '" width="16" height="11" fill="' + d[2] + '"/>'
        : '<line x1="' + x + '" y1="' + (y - 4) + '" x2="' + (x + 18) + '" y2="' + (y - 4) + '" stroke="' + d[2] + '" stroke-width="3"/><circle cx="' + (x + 9) + '" cy="' + (y - 4) + '" r="3.5" fill="' + d[2] + '"/>';
      s += '<text x="' + (x + 24) + '" y="' + y + '" font-size="13" fill="currentColor">' + d[1] + (isBar ? "（百萬美元）" : "（%）") + "</text>";
    });
    // 格線與座標
    for (var v = la.lo; v <= la.hi + la.st / 2; v += la.st) {
      var y = yl(v);
      s += '<line x1="' + L + '" y1="' + y + '" x2="' + (W - R) + '" y2="' + y + '" stroke="currentColor" stroke-opacity="' + (v === 0 ? 0.5 : 0.12) + '"/>';
      s += '<text x="' + (L - 6) + '" y="' + (y + 4) + '" font-size="11" text-anchor="end" fill="currentColor" fill-opacity=".75">' + Math.round(v).toLocaleString("zh-TW") + "</text>";
    }
    for (v = ra.lo; v <= ra.hi + ra.st / 2; v += ra.st) {
      s += '<text x="' + (W - R + 6) + '" y="' + (yr(v) + 4) + '" font-size="11" fill="currentColor" fill-opacity=".75">' + (+v.toFixed(1)) + "</text>";
    }
    // 長條
    g.labels.forEach(function (lab, i) {
      bars.forEach(function (d, k) {
        var val = g[d[0]][i];
        if (!isNum(val)) return;
        var x = cx(i) + (k - bars.length / 2) * bw, y0 = yl(0), y1 = yl(val);
        s += '<rect x="' + x.toFixed(1) + '" y="' + Math.min(y0, y1).toFixed(1) + '" width="' + (bw - 1).toFixed(1) + '" height="' + Math.max(1, Math.abs(y1 - y0)).toFixed(1) + '" fill="' + d[2] + '"><title>' + lab + " " + d[1] + " " + fmt(val, 0) + " 百萬美元</title></rect>";
      });
      s += '<text x="' + cx(i) + '" y="' + (B + 18) + '" font-size="12" text-anchor="middle" fill="currentColor">' + esc(lab) + "</text>";
    });
    // 折線與數值
    lines.forEach(function (d, k) {
      var pts = [];
      g[d[0]].forEach(function (val, i) { if (isNum(val)) pts.push([cx(i), yr(val), val]); });
      if (!pts.length) return;
      s += '<polyline fill="none" stroke="' + d[2] + '" stroke-width="2.5" points="' + pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '"/>';
      pts.forEach(function (p) {
        s += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="3.5" fill="' + d[2] + '"/>' +
          '<text x="' + p[0].toFixed(1) + '" y="' + (p[1] - 8).toFixed(1) + '" font-size="11" text-anchor="middle" fill="' + d[2] + '" font-weight="600" class="v">' + p[2].toFixed(1) + "</text>";
      });
    });
    s += '<text x="' + (W / 2) + '" y="' + (H - 10) + '" font-size="11" text-anchor="middle" fill="currentColor" fill-opacity=".6">左軸：金額（百萬美元）　右軸：比率（%）</text>';
    return s + "</svg>";
  }

  var FIN = null;
  function loadFin() { if (!FIN) FIN = fetch("us/fin.json", { cache: "no-cache" }).then(function (r) { return r.json(); }); return FIN; }
  function renderStock(code) {
    var a = null; D.stocks.forEach(function (s) { if (s.c === code) a = s; });
    if (!a) { app.innerHTML = '<a class="back" href="#/">‹ 回清單</a><div class="empty">找不到這檔股票。</div>'; return; }
    var cls = a.ok ? "good" : a.ipo ? "warn" : "bad";
    var verdict = a.ok ? "三項全過，列入 " + D.meta.screen_date.slice(0, 4) + " 年名單" : a.ipo ? "新上市（" + a.ipo.replace(/-/g, "/") + "），還沒有 5 年財報，暫不評估" : "未入選（" + a.k + "/3）";
    var c0 = chg(a);
    var html = '<a class="back" href="#/">‹ 回清單</a><section class="sec"><div class="row"><div><span class="name">' + esc(title(a)) + '</span><span class="code">' + esc(a.c) + " · " + esc(a.i) + "</span></div>" +
      '<div class="price">$' + fmt(a.p, 2) + "</div></div><div class=\"note\">" + esc(a.n) + " · 市值約 " + fmt(a.mcap * 10, 0) + " 億美元</div>" +
      '<div class="big ' + cls + '" style="margin-top:8px">' + verdict + "</div>" +
      (a.hl ? '<p class="note">' + esc(a.hl) + "</p>" : "") + (a.p0 ? '<p class="note">4/30 收盤 $' + fmt(a.p0, 2) + "，至 " + esc(D.meta.price_date) + " 股價漲跌 " + pct(c0) + "（不含股利）</p>" : "") + "</section>";
    var chk = [
      [a.f.charAt(0), "獲利能力", "近 5 年 ROE 最低值", fmt(a.rm, 1, "%"), "≥ " + C.roe_min + "%", "每年淨利 ÷ 平均股東權益，取 5 年中最低的一年"],
      [a.f.charAt(1), "回饋股東", "股東回報率", fmt(a.shy, 1, "%"), "≥ " + C.shy_min + "%", (isNum(a.div) ? "（現金股利 " + fmt(a.div, 0) + " + 買回庫藏股 " + fmt(a.bb, 0) + " 百萬美元）÷ 市值" : "（現金股利＋買回庫藏股）÷ 市值")],
      [a.f.charAt(2), "成長", "近一年營收成長", fmt(a.rg, 1, "%"), "≥ " + C.rev_min + "%", (isNum(a.rev) ? "營收 " + fmt(a.rev, 0) + " vs 前一年 " + fmt(a.rev0, 0) + " 百萬美元" : "最近一個會計年度 vs 前一年")]];
    html += '<section class="sec"><h2>三項選股條件</h2>';
    chk.forEach(function (c) {
      html += '<div class="ind"><div class="mk">' + (c[0] === "1" ? '<span class="ok-mk">✔</span>' : c[0] === "0" ? '<span class="no-mk">✘</span>' : '<span class="na-mk">—</span>') + '</div><div class="t">' + c[1] + '</div><div class="v">' + c[3] + '</div><div class="s">' + c[2] + "：" + esc(c[5]) + '</div><div class="std">標準 ' + c[4] + "</div></div>";
    });
    html += (a.fy_end ? '<p class="note">最近一個會計年度結束於 ' + esc(a.fy_end) + (a.ipo ? "。新上市公司上市未滿 5 年，ROE 條件先記為未通過" : "") + "。</p>" : "") + "</section>";
    if (a.rh) {
      var y0 = +D.meta.screen_date.slice(0, 4) - 5;
      html += '<section class="sec"><h2>年度 ROE（%）</h2><div class="scroll"><table><tr><th>會計年度</th>' + a.rh.map(function (v, i) { return "<th>" + (y0 + i) + "</th>"; }).reverse().join("") +
        "</tr><tr><td>ROE</td>" + a.rh.map(function (v) { return '<td class="' + (!isNum(v) ? "" : v >= C.roe_min ? "good" : "bad") + '">' + fmt(v, 1) + "</td>"; }).reverse().join("") + "</tr></table></div></section>";
    }
    html += '<section class="sec"><h2>成長力道</h2><div id="growth"><div class="empty">載入中…</div></div></section>';
    html += '<section class="sec"><h2>相關連結</h2><div class="links"><a href="https://finance.yahoo.com/quote/' + encodeURIComponent(a.c) + '" target="_blank" rel="noopener">Yahoo Finance</a>' +
      (a.cik ? '<a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&amp;CIK=' + encodeURIComponent(a.cik) + '&amp;type=10-K&amp;owner=include&amp;count=40" target="_blank" rel="noopener">SEC 年報（10-K）</a>' : "") + "</div></section>";
    app.innerHTML = html; window.scrollTo(0, 0);
    loadFin().then(function (F) {
      var box = document.getElementById("growth"); if (!box) return;
      var L = F[a.c];
      if (!L || !L.length) { box.innerHTML = '<p class="note">SEC 還沒有這家公司的年度財報資料（新上市公司要等第一份年報）。</p>'; return; }
      var g = { labels: [], gp: [], opex: [], opinc: [], gm: [], exr: [], om: [] };
      L.forEach(function (r) {
        var rev = r[1], gp = r[2], op = r[3], m = +r[0].slice(5, 7);
        g.labels.push(r[0].slice(0, 4) + (m === 12 ? "年" : "/" + m));
        g.gp.push(gp); g.opinc.push(op); g.opex.push(isNum(gp) && isNum(op) ? gp - op : null);
        g.gm.push(isNum(gp) && rev > 0 ? gp / rev * 100 : null); g.om.push(isNum(op) && rev > 0 ? op / rev * 100 : null);
        g.exr.push(isNum(gp) && isNum(op) && rev > 0 ? (gp - op) / rev * 100 : null);
      });
      box.innerHTML = '<div class="scroll">' + growthSvg(g) + "</div>" +
        '<p class="note">依會計年度（標示年度結束的年／月），金額單位百萬美元。毛利率＝營業毛利÷營收、營業費用率＝營業費用÷營收、營業利益率＝營業利益÷營收。' +
        (g.gp.every(function (v) { return !isNum(v); }) ? "這家公司的財報沒有「營業毛利」（服務業常見），只畫營業利益。" : "") + "資料來源：SEC 年報。</p>";
    }).catch(function () { var box = document.getElementById("growth"); if (box) box.innerHTML = '<p class="note">成長力道資料載入失敗。</p>'; });
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
      "<ul><li>2015～2025 年化 17.2%，S&amp;P 500 13.8%；最差一年 −6.2%；選中的股票約 70% 賺錢（全部股票平均 58%）。</li>" +
      "<li>* 2026 為 4/30 至 " + esc(D.meta.price_date) + " 的報酬。</li></ul>" +
      "<h3>使用方式（一年只動一次）</h3><ol><li>每年 4 月底看一次名單（美國公司年報多在 3 月底前公布）。</li><li>名單上有、手上沒有的，買進。</li><li>手上有、名單上已經沒有的，賣掉。</li><li>其他時間只看，不買也不賣。名單不到 10 檔時，沒買滿的部分留現金。</li></ol>" +
      "<h3>限制（請務必看）</h3><ul>" +
      "<li><b>結果可能高估</b>：已下市或被併購的公司查不到股價，只能排除，等於只看存活下來的公司；估計每年高估約 2～3 個百分點。</li>" +
      "<li><b>不是乾淨的樣本外驗證</b>：只用 2015～2019 年選出的最佳組合，2020～2025 年是 16.0%，輸給 S&amp;P 500 的 17.9%。本頁條件是看過全期資料後挑出的穩定組合。</li>" +
      "<li>S&amp;P 500 在這段期間沒有任何一年（4月→4月）虧損，這方法的優勢是「選中的股票多數賺錢」，不保證每年贏大盤。</li>" +
      "<li><b>不含外國公司</b>：台積電、ASML、Novo 等申報 20-F 的外國公司，SEC 沒有它們的美國會計資料，不在名單內（S&amp;P 1500 也不收）。</li>" +
      "<li><b>新上市公司</b>：近年上市、市值 30 億美元以上的公司（例如 Anthropic、SpaceX）列在「全部股票」，標示「新上市」；要等滿 5 年財報才會評估。</li>" +
      "<li>名單每年 4 月底更新一次；股價每個交易日收盤後更新（台灣時間平日晚上），目前為 " + esc(D.meta.price_date) + " 收盤。僅供自我檢視，非投資建議。</li></ul>" +
      "<h3>成長力道圖</h3><p>個股頁的「成長力道」和台股版相同：長條是營業毛利、營業費用、營業利益（百萬美元），折線是毛利率、營業費用率、營業利益率。美股依各公司的會計年度，資料來自 SEC 年報。</p></section>";
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
