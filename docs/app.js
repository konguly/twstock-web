/* 存股雷達 V6：純靜態網頁(無外部套件)。資料來自 data/index.json 與 data/stocks/<代號>.json
   選股法：近5年ROE每年≥5%、PB≤1.5、殖利率≥4%、近四季營收沒衰退、負債比≤50%，五項全過才入選。 */
(function () {
  "use strict";
  var app = document.getElementById("app");
  var updatedEl = document.getElementById("updated");
  var INDEX = null, IS_DEMO = false, CFG = {};
  var state = { tab: "pick", q: "", ind: "", sort: "yield", shown: 60 };
  var PAGE = 60;
  var NAMES = ["ROE", "PB", "殖利率", "營收", "負債"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function fmt(v, d, suffix) {
    if (!isNum(v)) return "—";
    return v.toLocaleString("zh-TW", { minimumFractionDigits: d == null ? 1 : d, maximumFractionDigits: d == null ? 1 : d }) + (suffix || "");
  }
  function fetchJson(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }
  function tz(s) {
    if (!s) return "";
    var d = new Date(s);
    if (isNaN(d)) return s;
    return d.toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
  }
  function flagsHtml(f) {
    f = f || "-----";
    var h = '<span class="sq" title="ROE / PB / 殖利率 / 營收 / 負債">';
    for (var i = 0; i < 5; i++) {
      var c = f.charAt(i);
      h += '<i class="' + (c === "1" ? "good" : c === "0" ? "bad" : "") + '">' + NAMES[i].charAt(0) + "</i>";
    }
    return h + "</span>";
  }
  function cond() {
    return "ROE ≥ " + CFG.roe_min + "%（近" + CFG.roe_years + "年每年）、PB ≤ " + CFG.pb_max + "、殖利率 ≥ " + CFG.yield_min +
      "%、近四季營收成長 ≥ " + CFG.rev_growth_min + "%、負債比 ≤ " + CFG.debt_max + "%";
  }

  /* ---------- 載入 ---------- */
  function load() {
    return fetchJson("data/index.json").catch(function () {
      IS_DEMO = true;
      return fetchJson("demo/index.json");
    }).then(function (j) {
      INDEX = j;
      CFG = j.meta.config || { roe_min: 5, roe_years: 5, pb_max: 1.5, yield_min: 4, rev_growth_min: 0, debt_max: 50 };
      var m = j.meta;
      updatedEl.textContent = (IS_DEMO ? "示範資料 · " : "") + "更新於 " + tz(m.updated_at) + " · 入選 " +
        INDEX.stocks.filter(function (s) { return s.ok; }).length + " / " + m.n_stocks + " 檔";
    });
  }

  /* ---------- 清單頁 ---------- */
  function filtered() {
    var q = state.q.trim().toLowerCase();
    var list = INDEX.stocks.filter(function (s) {
      if (state.tab === "pick" && !s.ok) return false;
      if (state.ind && s.i !== state.ind) return false;
      if (q && (s.c.toLowerCase().indexOf(q) < 0 && (s.n || "").toLowerCase().indexOf(q) < 0)) return false;
      return true;
    });
    function n(v, dflt) { return isNum(v) ? v : dflt; }
    var cmp = {
      yield: function (a, b) { return n(b.y, -1) - n(a.y, -1); },
      pb: function (a, b) { return n(a.pb, 99) - n(b.pb, 99); },
      roe: function (a, b) { return n(b.rm, -99) - n(a.rm, -99); },
      rev: function (a, b) { return n(b.rg, -999) - n(a.rg, -999); },
      pass: function (a, b) { return (b.k || 0) - (a.k || 0) || n(b.y, -1) - n(a.y, -1); },
      code: function (a, b) { return a.c < b.c ? -1 : 1; }
    }[state.sort];
    if (state.tab === "pick") {
      list.sort(function (a, b) { return (a.i || "").localeCompare(b.i || "", "zh-TW") || cmp(a, b); });
    } else list.sort(cmp);
    return list;
  }

  function card(s) {
    var chips = [
      ["ROE5年最低", fmt(s.rm, 1, "%")], ["PB", fmt(s.pb, 2)], ["殖利率", fmt(s.y, 1, "%")],
      ["營收成長", fmt(s.rg, 1, "%")], ["負債比", fmt(s.db, 0, "%")]
    ].map(function (x) { return '<span class="chip">' + x[0] + " " + x[1] + "</span>"; }).join("");
    var tag = s.fin ? '<span class="chip">金融股不適用</span>' :
      s.ok ? '<span class="chip good">五項通過</span>' : '<span class="chip">' + (s.k || 0) + "/5</span>";
    return '<a class="card" href="#/s/' + esc(s.c) + '">' +
      '<div class="row"><div><span class="name">' + esc(s.n) + '</span><span class="code">' + esc(s.c) + "</span></div>" +
      '<div class="price">' + fmt(s.p, 2) + "</div></div>" +
      '<div class="meta">' + flagsHtml(s.f) + tag + '<span>' + esc(s.i || "") + "</span></div>" +
      '<div class="chips">' + chips + "</div></a>";
  }

  function fillResults() {
    var box = document.getElementById("results");
    if (!box) return;
    var list = filtered();
    var html = "";
    if (!list.length) {
      html = '<div class="empty">' + (state.tab === "pick" ? "目前沒有股票五項全部通過。" : "找不到符合的股票。") + "</div>";
    } else if (state.tab === "pick") {
      var cur = null, cnt = {};
      list.forEach(function (s) { cnt[s.i] = (cnt[s.i] || 0) + 1; });
      list.forEach(function (s) {
        if (s.i !== cur) { cur = s.i; html += '<div class="group-h"><span>' + esc(cur || "其他") + "</span><span>" + cnt[cur] + " 檔</span></div>"; }
        html += card(s);
      });
    } else {
      list.slice(0, state.shown).forEach(function (s) { html += card(s); });
      if (list.length > state.shown) html += '<button class="more" id="more">再顯示 ' + Math.min(PAGE, list.length - state.shown) + " 檔（共 " + list.length + "）</button>";
    }
    box.innerHTML = html;
    var more = document.getElementById("more");
    if (more) more.onclick = function () { state.shown += PAGE; fillResults(); };
  }

  function renderList() {
    var inds = {};
    INDEX.stocks.forEach(function (s) { if (s.i) inds[s.i] = 1; });
    var indOpts = '<option value="">全部產業</option>' + Object.keys(inds).sort(function (a, b) { return a.localeCompare(b, "zh-TW"); })
      .map(function (i) { return '<option' + (i === state.ind ? " selected" : "") + ">" + esc(i) + "</option>"; }).join("");
    var sorts = [["yield", "殖利率高→低"], ["pb", "PB 低→高"], ["roe", "ROE 高→低"], ["rev", "營收成長高→低"], ["pass", "通過項目多→少"], ["code", "代號"]]
      .map(function (x) { return '<option value="' + x[0] + '"' + (x[0] === state.sort ? " selected" : "") + ">" + x[1] + "</option>"; }).join("");
    app.innerHTML =
      (IS_DEMO ? '<div class="demo">尚未完成第一次更新，以下為示範資料。</div>' : "") +
      '<div class="tabs" role="tablist">' +
      '<button class="tab" data-tab="pick" aria-selected="' + (state.tab === "pick") + '">各產業優等生</button>' +
      '<button class="tab" data-tab="all" aria-selected="' + (state.tab === "all") + '">全部股票</button></div>' +
      '<div class="controls"><input id="q" type="search" placeholder="搜尋代號或名稱" value="' + esc(state.q) + '">' +
      '<select id="ind">' + indOpts + '</select><select id="sort">' + sorts + "</select></div>" +
      '<p class="hint">' + (state.tab === "pick" ? "五項全部通過才入選：" + esc(cond()) + "。方塊依序為 ROE／PB／殖利率／營收／負債，綠＝通過、紅＝未過。"
        : "所有上市櫃股票；點進去看五項條件的明細。") + "</p>" +
      '<div id="results"></div>';
    fillResults();
    Array.prototype.forEach.call(app.querySelectorAll(".tab"), function (b) {
      b.onclick = function () { state.tab = b.getAttribute("data-tab"); state.shown = PAGE; renderList(); };
    });
    var q = document.getElementById("q"), composing = false;
    q.addEventListener("compositionstart", function () { composing = true; });
    q.addEventListener("compositionend", function () { composing = false; state.q = q.value; state.shown = PAGE; fillResults(); });
    q.addEventListener("input", function () { if (composing) return; state.q = q.value; state.shown = PAGE; fillResults(); });
    document.getElementById("ind").onchange = function () { state.ind = this.value; state.shown = PAGE; fillResults(); };
    document.getElementById("sort").onchange = function () { state.sort = this.value; fillResults(); };
  }

  /* ---------- 個股頁 ---------- */
  function renderStock(code) {
    app.innerHTML = '<div class="empty">載入中…</div>';
    fetchJson((IS_DEMO ? "demo" : "data") + "/stocks/" + encodeURIComponent(code) + ".json").then(function (a) {
      var cls = a.ok ? "good" : a.ok === false ? "bad" : "na";
      var html = '<a class="back" href="#/">‹ 回清單</a>' +
        '<section class="sec"><div class="row"><div><span class="name">' + esc(a.name) + '</span><span class="code">' + esc(a.code) +
        " · " + esc(a.market || "") + " · " + esc(a.industry || "") + '</span></div><div class="price">' + fmt(a.price, 2) + "</div></div>" +
        '<div class="big ' + cls + '" style="margin-top:8px">' + esc(a.verdict) + "</div>" +
        (a.hl ? '<p class="note">' + esc(a.hl) + "</p>" : "") + "</section>";

      html += '<section class="sec"><h2>五項選股條件</h2>';
      (a.checks || []).forEach(function (c) {
        var mk = c.ok === true ? '<span class="ok-mk">✔</span>' : c.ok === false ? '<span class="no-mk">✘</span>' : '<span class="na-mk">—</span>';
        var v = c.key === "pb" ? fmt(c.v, 2, " 倍") : c.key === "debt" ? fmt(c.v, 1, "%") : fmt(c.v, 1, "%");
        var sub = c.key === "pb" ? "現價 ÷ 每股淨值 " + fmt(a.bv, 2) + "（" + esc(a.bv_per || "") + "）" :
          c.key === "yld" ? (a.yld_src || "") :
          c.key === "rev" ? "近四季 ÷ 前四季營收" + (a.rev_q && a.rev_q.length ? "（至 " + esc(a.rev_q[0]) + "）" : "") :
          c.key === "debt" ? "負債 ÷ 資產（" + esc(a.debt_per || "") + "）" : "近 " + a.cfg.roe_years + " 個年度的最低值";
        html += '<div class="ind"><div class="mk">' + mk + '</div><div class="t">' + esc(c.t) + '</div><div class="v">' + v + "</div>" +
          '<div class="s">' + esc(c.label) + "：" + esc(sub) + '</div><div class="std">標準 ' + esc(c.op) + " " + c.th + esc(c.u) + "</div></div>";
      });
      html += "</section>";

      if (a.roe_hist && a.roe_hist.length) {
        html += '<section class="sec"><h2>年度 ROE（稅後，%）</h2><div class="scroll"><table><tr><th>年度</th>' +
          a.roe_hist.map(function (r) { return "<th>" + esc(r.y || "") + "</th>"; }).join("") + "</tr><tr><td>ROE</td>" +
          a.roe_hist.map(function (r, i) {
            var c = !isNum(r.v) ? "" : (i < a.cfg.roe_years ? (r.v >= a.cfg.roe_min ? "good" : "bad") : "");
            return '<td class="' + c + '">' + fmt(r.v, 1) + "</td>";
          }).join("") + "</tr></table></div><p class=\"note\">綠／紅底為選股看的近 " + a.cfg.roe_years + " 年。</p></section>";
      }
      if (a.rev_vals && a.rev_vals.length) {
        html += '<section class="sec"><h2>季營收（百萬元）</h2><div class="scroll"><table><tr><th>季別</th>' +
          a.rev_q.map(function (q) { return "<th>" + esc(q) + "</th>"; }).join("") + "</tr><tr><td>營收</td>" +
          a.rev_vals.map(function (v, i) { return '<td class="' + (i < 4 ? "ok" : "") + '">' + fmt(v, 0) + "</td>"; }).join("") +
          "</tr></table></div><p class=\"note\">藍底＝近四季，與後面四季相比算成長率。</p></section>";
      }
      var L = a.links || {};
      html += '<section class="sec"><h2>相關連結</h2><div class="links">' +
        (L.profile ? '<a href="' + esc(L.profile) + '" target="_blank" rel="noopener">公司基本資料</a>' : "") +
        (L.report ? '<a href="' + esc(L.report) + '" target="_blank" rel="noopener">財報電子書</a>' : "") +
        '</div><p class="note">財報期別 ' + esc(a.fund_q || "—") + " · 財報抓取 " + tz(a.fund_at) + " · 股價 " + esc(a.price_date || "") + "</p></section>";
      app.innerHTML = html;
      window.scrollTo(0, 0);
    }).catch(function () {
      app.innerHTML = '<a class="back" href="#/">‹ 回清單</a><div class="empty">找不到這檔股票的資料。</div>';
    });
  }

  /* ---------- 說明頁 ---------- */
  function renderAbout() {
    app.innerHTML = '<a class="back" href="#/">‹ 回清單</a><section class="sec about"><h2>選股方法（V6）</h2>' +
      "<p>五項條件全部通過，才列入「各產業優等生」：</p><ol>" +
      "<li><b>近 " + CFG.roe_years + " 年 ROE 每年都 ≥ " + CFG.roe_min + "%</b>：每年都有基本獲利，沒有爛掉的年度。</li>" +
      "<li><b>股價淨值比 PB ≤ " + CFG.pb_max + "</b>：買得便宜（現價 ÷ 最新一季每股淨值）。</li>" +
      "<li><b>現金殖利率 ≥ " + CFG.yield_min + "%</b>：真的有發錢。</li>" +
      "<li><b>近四季營收沒有衰退</b>（對前四季成長 ≥ " + CFG.rev_growth_min + "%）。</li>" +
      "<li><b>負債比 ≤ " + CFG.debt_max + "%</b>。</li></ol>" +
      "<h3>回測結果（2015～2025 年，每年 4 月底換股，等權重，已扣手續費與證交稅）</h3><ul>" +
      "<li>年化報酬 17.2%；全部上市櫃平均 15.0%；0050 19.6%（2025 年 AI 行情大漲 119%）。</li>" +
      "<li>2015～2024 年：年化 16.6%，0050 為 12.6%。</li>" +
      "<li>最差一年 −1.2%（0050 有 3 年虧損，最差 −11%）；選中的股票平均約 1/3 會虧錢（全市場約一半）。</li>" +
      "<li>條件用 2015～2019 年找出，再用 2020～2025 年沒看過的資料驗證，效果一樣成立。</li></ul>" +
      "<h3>使用方式</h3><ul><li>每季財報公布後（5/15、8/14、11/14、3/31 前後），網站會在一週內自動重新篩選。</li>" +
      "<li>持有中的股票若不再五項全過，下次調整時換成名單內的其他股票。</li>" +
      "<li>名單不到 10 檔時，回測是把沒買滿的部分留現金。</li>" +
      "<li>金融保險業不適用。</li></ul>" +
      "<h3>限制</h3><ul><li>在科技股大多頭（例如 2025 年）會落後大盤；這是「穩、少虧」的方法。</li>" +
      "<li>殖利率可能因一次性的特別股利偏高，請點進個股確認。</li>" +
      "<li>資料來自富邦 eBroker 的財報頁面，可能延遲或有誤；僅供自我檢視，非投資建議。</li></ul></section>";
  }

  function route() {
    var h = location.hash || "#/";
    var m = h.match(/^#\/s\/(\w+)/);
    if (m) return renderStock(m[1]);
    if (h === "#/about") return renderAbout();
    renderList();
  }
  window.addEventListener("hashchange", route);
  load().then(route).catch(function (e) {
    app.innerHTML = '<div class="empty">資料載入失敗：' + esc(e.message) + "</div>";
  });
})();
