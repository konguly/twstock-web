/* 存股雷達：純靜態網頁(無外部套件)。資料來自 data/index.json 與 data/stocks/<代號>.json */
(function () {
  "use strict";
  var app = document.getElementById("app");
  var updatedEl = document.getElementById("updated");
  var INDEX = null, IS_DEMO = false, MIN_SCORE = 13;
  var state = { tab: "elite", q: "", ind: "", sort: "score", shown: 60 };
  var PAGE = 60;

  /* ---------- 小工具 ---------- */
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
  function pct(v, d) { return fmt(v, d == null ? 1 : d, "%"); }
  function signCls(v) { return !isNum(v) ? "" : v >= 0 ? "pos" : "neg"; }
  function gradeClass(g) {
    if (!g) return "";
    if (g.indexOf("A") === 0) return "good";
    if (g.indexOf("B") === 0) return "ok";
    if (g.indexOf("C") === 0) return "warn";
    if (g.indexOf("RO") === 0) return "bad";
    return "";
  }
  function gshort(g) {
    if (!g) return "·";
    if (g.indexOf("RO") === 0) return "×";
    return g.slice(0, 2).replace("優", "").replace("列", "").replace("不", "");
  }
  function catClass(cat) { return cat === "buy" ? "good" : cat === "avoid" ? "bad" : cat === "watch" ? "warn" : "na"; }
  function qualClass(q) { return q === "通過" ? "good" : q === "未通過" ? "bad" : ""; }
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

  /* ---------- 載入 ---------- */
  function load() {
    return fetchJson("data/index.json").catch(function () {
      IS_DEMO = true;
      return fetchJson("demo/index.json");
    }).then(function (j) {
      INDEX = j;
      MIN_SCORE = (j.meta.config && j.meta.config.min_score_elite) || 13;
      var m = j.meta;
      updatedEl.textContent = (IS_DEMO ? "示範資料 · " : "") + "更新於 " + tz(m.updated_at) + " · " + m.n_stocks + " 檔";
    });
  }

  /* ---------- 清單頁 ---------- */
  function filtered() {
    var q = state.q.trim().toLowerCase();
    var list = INDEX.stocks.filter(function (s) {
      if (state.ind && s.i !== state.ind) return false;
      if (q && (s.c.toLowerCase().indexOf(q) < 0 && (s.n || "").toLowerCase().indexOf(q) < 0)) return false;
      if (state.tab === "elite" && s.s < MIN_SCORE) return false;
      if (state.tab === "buy" && s.cat !== "buy") return false;
      return true;
    });
    var cmp = {
      score: function (a, b) { return b.s - a.s || (b.up == null ? -999 : b.up) - (a.up == null ? -999 : a.up); },
      upside: function (a, b) { return (b.up == null ? -999 : b.up) - (a.up == null ? -999 : a.up); },
      yield: function (a, b) { return (b.y == null ? -1 : b.y) - (a.y == null ? -1 : a.y); },
      code: function (a, b) { return a.c < b.c ? -1 : 1; }
    }[state.sort] || null;
    if (state.tab === "elite" && state.sort === "score") {
      list.sort(function (a, b) { return (a.i || "").localeCompare(b.i || "", "zh-TW") || b.s - a.s || (b.up || -999) - (a.up || -999); });
    } else if (cmp) list.sort(cmp);
    return list;
  }

  function cardHtml(s) {
    var sq = (s.gr || []).slice(0, 5).map(function (g) {
      return '<i class="' + gradeClass(g) + '">' + esc(gshort(g)) + "</i>";
    }).join("");
    var up = isNum(s.up) ? '<span class="up ' + signCls(s.up) + '">本益比法 ' + (s.up >= 0 ? "+" : "") + fmt(s.up, 0, "%") + "</span>" : "";
    return '<a class="card" href="#/s/' + esc(s.c) + '">' +
      '<div class="row"><div><span class="name">' + esc(s.n) + '</span><span class="code">' + esc(s.c) + "</span></div>" +
      '<div class="price">' + (isNum(s.p) ? fmt(s.p, 2) : "—") + "</div></div>" +
      '<div class="meta"><span>' + esc(s.i || "") + "</span>" +
      '<span class="sq" title="近4季＋近4年的獲利矩陣等級">' + sq + "</span>" +
      '<span class="chip ' + (s.s >= MIN_SCORE ? "good" : "") + '">積分 ' + s.s + "</span>" +
      '<span class="chip">5年 ' + esc(String(s.g || "").split("（")[0]) + "</span>" +
      '<span class="chip ' + (s.k >= 8 ? "good" : s.k >= 6 ? "warn" : "bad") + '">9項 ' + s.k + "/9</span></div>" +
      '<div class="sig"><span class="chip ' + catClass(s.cat) + '">' + esc(s.sig) + "</span> " + up + "</div>" +
      (s.hl ? '<div class="meta">' + esc(s.hl) + "</div>" : "") + "</a>";
  }

  function fillResults() {
    var MINS = MIN_SCORE;
    var list = filtered();
    var hints = {
      elite: "獲利矩陣積分 ≥ " + MIN_SCORE + "（A=3、B1=2、B2=1，看近4季＋近4年，滿分15）。",
      buy: "品質通過，且折衷版預估EPS下現價落在「低估區」或「合理偏低」。",
      all: "所有已分析的股票。"
    };
    var h = '<p class="hint">' + hints[state.tab] + " 共 " + list.length + " 檔。</p>";
    if (!list.length) h += '<div class="empty">沒有符合的股票</div>';
    var shown = list.slice(0, state.shown), lastInd = null;
    shown.forEach(function (s) {
      if (state.tab === "elite" && state.sort === "score" && s.i !== lastInd) {
        var cnt = list.filter(function (x) { return x.i === s.i; }).length;
        h += '<div class="group-h"><span>' + esc(s.i || "其他") + "</span><span>" + cnt + " 檔</span></div>";
        lastInd = s.i;
      }
      h += cardHtml(s);
    });
    if (list.length > shown.length) h += '<button class="more" id="more">顯示更多（還有 ' + (list.length - shown.length) + " 檔）</button>";
    
    document.getElementById("results").innerHTML = h;
    var more = document.getElementById("more");
    if (more) more.onclick = function () { state.shown += PAGE; renderList(); };
  }

  function renderList() {
    var industries = {};
    INDEX.stocks.forEach(function (s) { if (s.i) industries[s.i] = 1; });
    var inds = Object.keys(industries).sort(function (a, b) { return a.localeCompare(b, "zh-TW"); });
    var tabs = [["elite", "各產業優等生"], ["buy", "買點"], ["all", "全部"]];
    var h = IS_DEMO ? '<div class="demo">目前顯示的是示範資料。第一次執行 GitHub Actions 更新後，這裡會換成真實資料。</div>' : "";
    h += '<div class="tabs" role="tablist">' + tabs.map(function (t) {
      return '<button class="tab" role="tab" data-tab="' + t[0] + '" aria-selected="' + (state.tab === t[0]) + '">' + t[1] + "</button>";
    }).join("") + "</div>";
    h += '<div class="controls"><input id="q" type="search" inputmode="search" placeholder="搜尋代號或名稱" value="' + esc(state.q) + '">' +
      '<select id="ind"><option value="">全部產業</option>' + inds.map(function (i) {
        return '<option' + (state.ind === i ? " selected" : "") + ">" + esc(i) + "</option>";
      }).join("") + "</select>" +
      '<select id="sort">' + [["score", state.tab === "elite" ? "依產業、積分" : "積分高→低"], ["upside", "增值潛力高→低"], ["yield", "殖利率高→低"], ["code", "代號"]]
        .map(function (o) { return '<option value="' + o[0] + '"' + (state.sort === o[0] ? " selected" : "") + ">" + o[1] + "</option>"; }).join("") + "</select></div>";
    h += '<div id="results"></div>';
    app.innerHTML = h;
    fillResults();
    app.querySelectorAll(".tab").forEach(function (b) {
      b.onclick = function () { state.tab = b.dataset.tab; state.shown = PAGE; if (state.tab === "elite") state.sort = "score"; renderList(); };
    });
    var q = document.getElementById("q");
    var composing = false;
    q.addEventListener("compositionstart", function () { composing = true; });
    q.addEventListener("compositionend", function () { composing = false; state.q = q.value; state.shown = PAGE; fillResults(); });
    q.addEventListener("input", function (e) {
      if (composing || e.isComposing) return;   // 注音/拼音輸入中先不重畫，避免打斷輸入法
      state.q = q.value; state.shown = PAGE; fillResults();
    });
    document.getElementById("ind").onchange = function (e) { state.ind = e.target.value; state.shown = PAGE; renderList(); };
    document.getElementById("sort").onchange = function (e) { state.sort = e.target.value; state.shown = PAGE; renderList(); };
  }

  /* ---------- 個股頁 ---------- */
  function bandSvg(price, b, e) {
    if (!isNum(price) || !b || !isNum(b[0]) || !isNum(b[1]) || !isNum(b[2])) return "";
    var lo = Math.min(price, b[0]) * 0.9, hi = Math.max(price, b[2]) * 1.08;
    var W = 320, x = function (v) { return 10 + (v - lo) / (hi - lo) * (W - 20); };
    var mid = (b[0] + b[1]) / 2;
    var seg = function (a, c, cls) { return '<rect x="' + x(a).toFixed(1) + '" y="22" width="' + Math.max(0, x(c) - x(a)).toFixed(1) + '" height="14" class="' + cls + '"/>'; };
    var lab = function (v, t, y) { return '<text x="' + x(v).toFixed(1) + '" y="' + y + '" text-anchor="middle" font-size="10" fill="currentColor">' + t + "</text>"; };
    return '<div class="bandwrap"><svg viewBox="0 0 ' + W + ' 66" width="100%" role="img" aria-label="現價與本益比價格帶">' +
      "<style>.g1{fill:#16a34a}.g2{fill:#86efac}.g3{fill:#fde68a}.g4{fill:#fca5a5}</style>" +
      seg(lo, b[0], "g1") + seg(b[0], mid, "g2") + seg(mid, b[1], "g3") + seg(b[1], b[2], "g3") + seg(b[2], hi, "g4") +
      '<line x1="' + x(price).toFixed(1) + '" x2="' + x(price).toFixed(1) + '" y1="14" y2="42" stroke="currentColor" stroke-width="2.5"/>' +
      lab(price, "現價 " + fmt(price, 1), 10) + lab(b[0], fmt(b[0], 0), 52) + lab(b[1], fmt(b[1], 0), 52) + lab(b[2], fmt(b[2], 0), 52) +
      '<text x="10" y="64" font-size="9" fill="currentColor" opacity=".7">低估</text><text x="' + (W - 10) + '" y="64" text-anchor="end" font-size="9" fill="currentColor" opacity=".7">過熱</text>' +
      "</svg></div>";
  }

  function matrixTable(a) {
    var cols = a.matrix.slice(0, 6);
    var h = '<div class="scroll"><table><thead><tr><th>期別</th>' + cols.map(function (c) { return "<th>" + esc(c.label || "—") + "</th>"; }).join("") + "</tr></thead><tbody>";
    h += "<tr><td>ROE %</td>" + cols.map(function (c) { return "<td>" + fmt(c.roe, 1) + "</td>"; }).join("") + "</tr>";
    h += "<tr><td>" + (a.is_fin ? "每股淨值年增" : "每股自由現金流") + "</td>" + cols.map(function (c) { return "<td>" + fmt(c.fcf, 1) + "</td>"; }).join("") + "</tr>";
    h += "<tr><td>等級</td>" + cols.map(function (c) { return '<td class="g ' + gradeClass(c.grade) + '">' + esc(gshort(c.grade)) + "</td>"; }).join("") + "</tr></tbody></table></div>";
    return h;
  }

  function indList(a) {
    var rows = a.ind9.concat(a.extra.map(function (e, i) { return { n: "+", name: "補充：" + e.name, std: e.std, val: e.val, ok: e.ok, higher: true, note: e.note }; }));
    return rows.map(function (r) {
      var mk = r.ok === true ? '<span class="ok-mk">✔</span>' : r.ok === false ? '<span class="no-mk">✘</span>' : '<span class="na-mk">—</span>';
      var unit = /\(%\)/.test(r.name) ? "%" : "";
      return '<div class="ind"><div class="mk">' + mk + '</div><div class="t">' + (r.n === "+" ? "" : r.n + " ") + esc(r.name) + '</div><div class="v">' + fmt(r.val, 1) + unit + "</div>" +
        '<div class="s">' + esc(r.note) + '</div><div class="std">標準 ' + (r.higher ? ">" : "<") + " " + r.std + "</div></div>";
    }).join("");
  }

  function valTable(a) {
    var v = a.valuation, names = ["保守版", "趨勢版", "折衷版"];
    var h = '<div class="scroll"><table><thead><tr><th></th>' + names.map(function (n) { return "<th>" + n + "</th>"; }).join("") + "</tr></thead><tbody>";
    var row = function (label, fn) { return "<tr><td>" + label + "</td>" + [0, 1, 2].map(function (i) { return "<td>" + fn(i) + "</td>"; }).join("") + "</tr>"; };
    h += row("預估 EPS", function (i) { return fmt(v.eps_est[i], 2); });
    h += row("預估本益比", function (i) { return fmt(v.pe_now[i], 1); });
    h += row("低估價 (" + v.pe.low + "倍)", function (i) { return fmt(v.bands[i][0], 1); });
    h += row("合理價 (" + v.pe.mid + "倍)", function (i) { return fmt(v.bands[i][1], 1); });
    h += row("高估價 (" + v.pe.high + "倍)", function (i) { return fmt(v.bands[i][2], 1); });
    h += row("現價所在", function (i) { return esc(v.zones[i] || "—"); });
    return h + "</tbody></table></div>";
  }

  function gordonTable(a) {
    var names = ["保守版", "趨勢版", "折衷版"], g = a.gordon;
    var h = '<div class="scroll"><table><thead><tr><th></th>' + names.map(function (n) { return "<th>" + n + "</th>"; }).join("") + "</tr></thead><tbody>";
    var row = function (label, fn) { return "<tr><td>" + label + "</td>" + [0, 1, 2].map(function (i) { return "<td>" + fn(g[i]) + "</td>"; }).join("") + "</tr>"; };
    h += row("殖利率 Y %", function (d) { return fmt(d.Y, 1); });
    h += row("成長率 G %", function (d) { return fmt(d.G, 1); });
    h += row("高登報酬率 %", function (d) { return fmt(d.ret, 1); });
    h += row("彼得林區比值", function (d) { return fmt(d.lynch, 2); });
    h += row("適用性", function (d) { return esc(d.fit || "—"); });
    h += row("建議買進區間", function (d) { return d.range ? fmt(d.range[0], 0) + " ~ " + fmt(d.range[1], 0) : "—"; });
    h += row("判斷", function (d) { return esc(d.judge || "—"); });
    return h + "</tbody></table></div>";
  }

  function renderDetail(code) {
    app.innerHTML = '<a class="back" href="#/">‹ 返回</a><div class="empty">載入中…</div>';
    var base = IS_DEMO ? "demo/stocks/" : "data/stocks/";
    fetchJson(base + code + ".json").then(function (a) {
      var v = a.verdict, g5 = a.grade5, z = a.valuation.zones[2];
      var h = '<a class="back" href="#/">‹ 返回</a>';
      h += '<div class="sec"><div class="row"><div><span class="name" style="font-size:22px">' + esc(a.name) + '</span><span class="code">' + esc(a.code) + "</span></div>" +
        '<div class="price" style="font-size:22px">' + fmt(a.price, 2) + "</div></div>" +
        '<div class="meta"><span>' + esc(a.industry || "") + " · " + esc(a.market || "") + "</span><span>收盤 " + esc(a.price_date || "—") + "</span></div>" +
        (a.hl ? '<div class="meta">亮點：' + esc(a.hl) + "</div>" : "") +
        '<div class="links"><a href="' + esc(a.links.profile) + '" target="_blank" rel="noopener">公司簡介</a>' +
        '<a href="' + esc(a.links.report) + '" target="_blank" rel="noopener">最新財報 PDF</a>' +
        '<a href="https://fubon-ebrokerdj.fbs.com.tw/z/zc/zca/zca_' + esc(a.code) + '.djhtm" target="_blank" rel="noopener">富邦基本資料</a></div></div>';

      h += '<div class="sec"><h2>結論</h2><div class="big ' + catClass(v.cat) + '">' + esc(v.signal) + "</div>" +
        '<div class="chips"><span class="chip ' + qualClass(v.quality) + '">品質檢查：' + esc(v.quality) + "</span>" +
        '<span class="chip">5年級別 ' + esc(g5.grade) + "</span><span class=\"chip\">趨勢 " + esc(g5.trend) + "</span>" +
        '<span class="chip">獲利矩陣積分 ' + a.score + "/15</span></div>" +
        (v.warnings.length ? '<div class="chips">' + v.warnings.map(function (w) { return '<span class="chip warn">⚠ ' + esc(w) + "</span>"; }).join("") + "</div>" : '<div class="note">無警示項目</div>') +
        '<div class="kv"><div>增值潛力（本益比法・折衷）<b class="' + signCls(v.upside_pe) + '">' + (isNum(v.upside_pe) ? (v.upside_pe >= 0 ? "+" : "") + fmt(v.upside_pe, 0, "%") : "—") + "</b></div>" +
        '<div>增值潛力（高登法・折衷）<b class="' + signCls(v.upside_gordon) + '">' + (isNum(v.upside_gordon) ? (v.upside_gordon >= 0 ? "+" : "") + fmt(v.upside_gordon, 0, "%") : "不適用") + "</b></div>" +
        "<div>盈餘殖利率<b>" + pct(v.earn_yield) + '</b></div><div>現金股利殖利率<b>' + pct(v.div_yield) + "</b></div></div>" +
        (v.ey_ok === false ? '<div class="note">盈餘殖利率低於無風險利率(' + v.rf + '%)的 2 倍。</div>' : "") +
        (v.note ? '<div class="note">' + esc(v.note) + "</div>" : "") + "</div>";

      h += '<div class="sec"><h2>獲利矩陣</h2>' + matrixTable(a) +
        '<div class="note">A＝ROE≥15% 且自由現金流>0；B1＝ROE≥15% 但現金流≤0；B2＝ROE 10~15% 且現金流>0。積分＝近4季＋近4年的 A×3＋B1×2＋B2×1。' + (a.matrix_note ? "<br>" + esc(a.matrix_note) : "") + "</div></div>";

      h += '<div class="sec"><h2>9 大指標檢核 <span class="chip ' + (a.pass9 >= 8 ? "good" : a.pass9 >= 6 ? "warn" : "bad") + '">' + a.pass9 + "/9 · " + esc(a.pass9_label) + "</span></h2>" + indList(a) +
        '<div class="note">未通過項目：' + esc(a.fail9) + "；「—」代表資料不足。</div></div>";

      h += '<div class="sec"><h2>5 年綜合級別</h2><div class="kv">' +
        "<div>級別<b>" + esc(g5.grade) + "</b></div><div>趨勢<b>" + esc(g5.trend) + "</b></div>" +
        "<div>5年自由現金皆為正<b>" + esc(g5.all_fcf_pos) + "</b></div><div>5年皆發現金股利<b>" + esc(g5.all_div) + "</b></div>" +
        "<div>股息÷自由現金（5年）<b>" + pct(g5.fcf_payout5, 0) + "</b></div><div>連續2年現金流為負<b>" + esc(g5.neg2) + "</b></div></div>" +
        (g5.trend_note ? '<div class="note">' + esc(g5.trend_note) + "</div>" : "") + "</div>";

      var b = a.valuation.bands[2];
      h += '<div class="sec"><h2>估價：本益比價格帶</h2>' + bandSvg(a.price, b, a.valuation.eps_est[2]) + valTable(a) +
        '<div class="note">歷史本益比：' + fmt(a.valuation.hist_pe_min, 1) + " ~ " + fmt(a.valuation.hist_pe_max, 1) + " 倍。景氣循環股、虧損或一次性損益要另外判斷。</div></div>";

      h += '<div class="sec"><h2>估價：高登公式報酬率</h2>' + gordonTable(a) +
        '<div class="note">報酬率＝殖利率Y＋保留盈餘成長率G；<10% 或級別不足時不適用（書 p.198–211）。</div></div>';

      h += '<div class="note" style="margin:0 4px 16px">資料時間：財報 ' + tz(a.fund_at) + "、股價 " + tz(a.px_at) + "。僅供自我檢視，非投資建議。</div>";
      app.innerHTML = h;
      window.scrollTo(0, 0);
    }).catch(function () {
      app.innerHTML = '<a class="back" href="#/">‹ 返回</a><div class="empty">找不到這檔股票的資料（代號 ' + esc(code) + "）</div>";
    });
  }

  function renderAbout() {
    var c = (INDEX && INDEX.meta.config) || {};
    var m = (INDEX && INDEX.meta) || {};
    app.innerHTML = '<a class="back" href="#/">‹ 返回</a><div class="sec about"><h2>怎麼看這些數字</h2>' +
      "<p><b>獲利矩陣</b>：每一期用 ROE 與自由現金流把公司分級（A／B1／B2…）。積分＝近4季＋近4年的 A×3＋B1×2＋B2×1，滿分 15。「各產業優等生」列出積分 ≥ " + (c.min_score_elite || 13) + " 的公司，依產業分組。</p>" +
      "<p><b>9 大指標</b>：ROE 近5年平均 >15%、近1年 >20%、營業利益率 >10%、每股自由現金流（5年平均 >0、近1年 >1）、營業現金對淨利比 >50%、董監持股 >10%、質押 <10%、上市櫃超過 5 年。</p>" +
      "<p><b>估價</b>：用預估 EPS（保守／趨勢／折衷）乘上本益比 " + c.pe_low + "／" + c.pe_mid + "／" + c.pe_high + " 倍得到低估／合理／高估價；另用高登公式（殖利率＋成長率）交叉檢查。</p>" +
      "<p><b>買進訊號</b>：品質檢查通過，才看價格；價格在低估區是「符合買點」、合理偏低是「可分批」，偏貴或過熱則等待。</p>" +
      "<h2 style='margin-top:16px'>資料與限制</h2><ul>" +
      "<li>財報與股價來自富邦 eBroker DJ 公開頁面，股票清單來自證交所 ISIN 公告；由 GitHub Actions 定時抓取、計算，網頁只顯示結果。</li>" +
      "<li>股價每個交易日更新；財報約每週輪流更新。資料可能延遲、缺漏或有誤。</li>" +
      "<li>金融保險業用「每股淨值年增」取代自由現金流，估價僅供參考。</li>" +
      "<li>想調整本益比區間等參數：修改專案根目錄的 <code>config.json</code>，下次更新就會套用。</li>" +
      "<li>最後更新：" + esc(tz(m.updated_at)) + "；本次輪流更新財報 " + (m.n_fund_updated || 0) + " 檔、股價 " + (m.n_price_updated || 0) + " 檔。</li></ul>" +
      "<p class='note'>本站為依書中方法整理的自我檢視工具，不構成任何投資建議；投資有風險，請自行判斷。</p></div>";
  }

  /* ---------- 路由 ---------- */
  function route() {
    var h = location.hash || "#/";
    var m = h.match(/^#\/s\/(\w+)/);
    if (m) return renderDetail(m[1]);
    if (h === "#/about") return renderAbout();
    renderList();
  }
  window.addEventListener("hashchange", route);
  load().then(route).catch(function (e) {
    updatedEl.textContent = "資料載入失敗";
    app.innerHTML = '<div class="empty">還沒有資料。請先到 GitHub 的 Actions 執行一次「更新資料並發布」。<br><small>' + esc(e.message) + "</small></div>";
  });
})();
