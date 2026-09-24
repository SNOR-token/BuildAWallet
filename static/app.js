/* Build-a-Wallet: chat, live preview, blueprint, option vault. */
(function () {
  "use strict";

  var $ = function (s) { return document.querySelector(s); };
  var SPEC = null, STATE = null, CAT = null, META = {};
  var view = "preview", screenTab = "home", busy = false, saved = null, filter = "", shownDone = false;

  /* ------------------------------------------------------------ helpers */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function md(s) {
    return esc(s).split(/\n{2,}/).map(function (p) {
      return "<p>" + p.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>") + "</p>";
    }).join("");
  }
  function hash(str) {
    var h = 2166136261, i;
    for (i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0);
  }
  function seeded(seed) {
    var t = seed >>> 0;
    return function () {
      t += 0x6D2B79F5;
      var r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }
  function money(n) {
    if (n >= 1000000) return "$" + (n / 1000000).toFixed(2) + "M";
    if (n >= 1000) return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
    return "$" + n.toFixed(2);
  }
  function has(id) {
    if (!SPEC) return false;
    var g = GROUP_OF[id];
    if (!g) return false;
    if (SINGLE[g]) return SPEC[g] === id;
    return (SPEC[g] || []).indexOf(id) >= 0;
  }
  function lab(id) { return (META[id] && META[id].label) || id; }
  function toast(msg) {
    var t = $("#toast");
    t.textContent = msg; t.classList.add("on");
    clearTimeout(t._t); t._t = setTimeout(function () { t.classList.remove("on"); }, 2200);
  }
  function delay(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  var DRAFT_KEY = "baw.draft.v1";

  function saveDraft() {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ spec: SPEC, state: STATE, at: Date.now() }));
    } catch (e) { /* private mode, no draft, no problem */ }
  }
  function readDraft() {
    try {
      var d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (!d || !d.spec) return null;
      if (Date.now() - (d.at || 0) > 1000 * 60 * 60 * 24 * 30) return null;
      return d;
    } catch (e) { return null; }
  }

  var SINGLE = { custody: 1, style: 1, theme: 1, accent: 1 };
  var GROUP_OF = {};
  var GROUP_TOPIC = { assets: "assets", networks: "networks", custody: "custody", security: "security",
    features: "features", platforms: "platforms", privacy: "privacy", style: "style", theme: "style", accent: "style" };

  /* -------------------------------------------------------------- icons */
  var P = {
    send: "M12 19V5M5 12l7-7 7 7",
    receive: "M12 5v14M5 12l7 7 7-7",
    buy: "M12 5v14M5 12h14",
    swap: "M7 4v13m0 0l-3-3m3 3l3-3M17 20V7m0 0l-3 3m3-3l3 3",
    stake: "M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3zm0 6l4 2.2v4.4L12 17.8 8 15.6v-4.4L12 9z",
    card: "M2 7h20v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7zm0 4h20M6 15h4",
    chart: "M4 19V5m0 14h16M8 15l3-4 3 3 4-6",
    grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    apps: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm3.5-12.5l-2 5-5 2 2-5 5-2z",
    home: "M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-8z",
    lock: "M6 11h12v9H6zM9 11V8a3 3 0 0 1 6 0v3",
    bell: "M6 10a6 6 0 1 1 12 0c0 4 2 5 2 5H4s2-1 2-5zM10 20a2 2 0 0 0 4 0",
    scan: "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3",
    earn: "M12 3v18M8 7h6a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h7",
    bridge: "M3 16h18M6 16V9m12 7V9M3 9c3-4 15-4 18 0",
    gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2-1.2L14.2 3H9.8l-.4 2.7a7 7 0 0 0-2 1.2l-2.3-1-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2 1.2l.4 2.7h4.4l.4-2.7a7 7 0 0 0 2-1.2l2.3 1 2-3.4-2-1.5c.06-.4.1-.8.1-1.2z"
  };
  function icon(name, size) {
    var d = P[name] || P.home;
    return '<svg class="g" width="' + (size || 16) + '" height="' + (size || 16) + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + d + '"/></svg>';
  }

  /* --------------------------------------------------------------- chat */
  function push(who, text) {
    var el = document.createElement("div");
    el.className = "msg " + who;
    var tag = who === "ai" ? "AI" : who === "me" ? "You" : "";
    el.innerHTML = '<div class="who">' + esc(tag) + "</div><div class='bubble'>" + md(text) + "</div>";
    var chips = $("#chips");
    if (chips && chips.parentNode === $("#chat")) $("#chat").insertBefore(el, chips);
    else $("#chat").appendChild(el);
    scrollChat();
    return el;
  }
  function scrollChat() {
    var c = $("#chat");
    c.scrollTop = c.scrollHeight;
  }
  function typing(on) {
    var old = $("#typing");
    if (old) old.remove();
    if (!on) return;
    var el = document.createElement("div");
    el.className = "msg ai"; el.id = "typing";
    el.innerHTML = '<div class="who">AI</div><div class="bubble typing"><span></span><span></span><span></span></div>';
    var chipbox = $("#chips");
    if (chipbox && chipbox.parentNode === $("#chat")) $("#chat").insertBefore(el, chipbox);
    else $("#chat").appendChild(el);
    scrollChat();
  }
  function renderChips(chips) {
    var box = $("#chips");
    if (box.parentNode !== $("#chat")) $("#chat").appendChild(box);
    else $("#chat").appendChild(box);
    box.innerHTML = "";
    (chips || []).forEach(function (c, i) {
      var b = document.createElement("button");
      b.className = "chip";
      b.textContent = c.label;
      b.style.animationDelay = (i * 35) + "ms";
      b.onclick = function () { send(c.send); };
      box.appendChild(b);
    });
    scrollChat();
  }

  function setView(name) {
    view = name;
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (x) {
      x.classList.toggle("on", x.getAttribute("data-view") === name);
    });
    render();
    if (window.innerWidth <= 960) {
      document.querySelector(".pane-build").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  var VIEW_CMD = [
    [/\b(blueprint|the spec|full spec|summary)\b/i, "blueprint", "Blueprint open on the right."],
    [/\b(vault|all the options|every option|option list|browse options)\b/i, "vault", "Vault open. Tap anything to add or remove it."],
    [/\b(preview|the phone|the wallet screen|show me the wallet)\b/i, "preview", "Preview open. Tap the tabs inside the phone."]
  ];

  async function send(text) {
    if (busy || !text || !text.trim()) return;
    for (var i = 0; i < VIEW_CMD.length; i++) {
      if (VIEW_CMD[i][0].test(text) && text.trim().split(/\s+/).length <= 6) {
        push("me", text);
        setView(VIEW_CMD[i][1]);
        push("sys", VIEW_CMD[i][2]);
        return;
      }
    }
    busy = true;
    $("#sendBtn").disabled = true;
    push("me", text);
    renderChips([]);
    typing(true);
    var started = Date.now();
    var r;
    try {
      r = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, spec: SPEC, state: STATE })
      }).then(function (res) { return res.json(); });
    } catch (e) {
      typing(false); push("ai", "The connection dropped. Say that again?");
      busy = false; $("#sendBtn").disabled = false; return;
    }
    var wait = 320 + Math.min(620, (r.reply || "").length * 3) - (Date.now() - started);
    if (wait > 0) await delay(wait);
    typing(false);
    SPEC = r.spec; STATE = r.state;
    push("ai", r.reply);
    renderChips(r.chips);
    setMeters(r.progress, r.count);
    saved = null;
    if (r.done && !shownDone) {
      shownDone = true;
      setView("blueprint");
    } else {
      render();
    }
    busy = false;
    $("#sendBtn").disabled = false;
  }

  function setMeters(progress, count) {
    $("#bar").style.width = (progress || 0) + "%";
    $("#chosen").textContent = count || 0;
  }

  /* ------------------------------------------------------------ preview */
  var PRICE = { btc: 61200, eth: 2950, sol: 148, xrp: 0.62, ada: 0.45, doge: 0.14, ltc: 72,
    bnb: 560, avax: 28, dot: 6.4, atom: 7.2, ton: 5.6, trx: 0.12, sui: 1.4, apt: 7.1,
    near: 4.3, xlm: 0.11, xmr: 158, zec: 31, link: 13.5, matic: 0.52, usdc: 1, usdt: 1,
    dai: 1, eurc: 1.08, meme: 0.0007, erc20: 2.4, nft_asset: 640, rwa: 100 };

  function assetRows() {
    var name = (SPEC.name || "wallet");
    return (SPEC.assets || []).map(function (id) {
      var rnd = seeded(hash(name + id));
      var price = PRICE[id] || 12;
      var target = 200 + rnd() * 6200;
      var amount = target / price;
      var change = (rnd() * 14 - 5);
      var m = META[id] || {};
      return { id: id, label: m.label || id, sym: m.sym || (m.label || id).slice(0, 3).toUpperCase(),
        color: m.color || "#7f8ea3", amount: amount, value: target, change: change };
    }).sort(function (a, b) { return b.value - a.value; });
  }

  var SHORT = { s_bio: "Face ID", s_pin: "PIN", s_passkey: "Passkey", s_2fa: "2FA", s_social: "Guardians",
    s_shamir: "Split backup", s_cloud: "Cloud backup", s_hwsupport: "Hardware", s_sim: "Simulated",
    s_scam: "Scam filter", s_allow: "Allowlist", s_limits: "Limits", s_delay: "Timelock",
    s_approve: "Approvals", s_duress: "Duress PIN", s_autolock: "Auto lock", s_audit: "Audited",
    s_open: "Open source", s_inherit: "Inheritance", s_airgap: "Air gap" };

  var TABS = [
    { id: "home", label: "Home", icon: "home", always: true },
    { id: "f_swap", label: "Swap", icon: "swap" },
    { id: "f_onramp", label: "Buy", icon: "buy" },
    { id: "f_portfolio", label: "Portfolio", icon: "chart" },
    { id: "f_earn", label: "Earn", icon: "earn" },
    { id: "f_stake", label: "Stake", icon: "stake" },
    { id: "f_nft", label: "NFTs", icon: "grid" },
    { id: "f_dapp", label: "Apps", icon: "apps" },
    { id: "f_card", label: "Card", icon: "card" },
    { id: "f_send", label: "Send", icon: "send" }
  ];

  function activeTabs() {
    var t = TABS.filter(function (x) { return x.always || has(x.id); });
    return t.slice(0, 5);
  }

  function accentHex() {
    var a = (CAT.accents || []).filter(function (x) { return x.id === SPEC.accent; })[0];
    return a ? a.hex : "#4ade9b";
  }

  function renderPhone() {
    var mode = SPEC.theme === "t_light" ? "light" : "dark";
    var style = SPEC.style || "st_minimal";
    var isGlasses = has("p_glasses");
    var tabs = activeTabs();
    if (!tabs.some(function (t) { return t.id === screenTab; })) screenTab = "home";
    var body = screen(screenTab);
    var html =
      '<div class="phone' + (isGlasses ? " is_glasses" : "") + '"><div class="screen ' + mode + " " + style + '" style="--w-accent:' + accentHex() + '">' +
        '<div class="w-status"><span>9:41</span><span>' + (SPEC.name ? esc(SPEC.name.slice(0, 14)) : "") + "</span><span>100%</span></div>" +
        '<div class="w-body"><div class="w-scroll">' + body + "</div></div>" +
        '<div class="w-tabs">' + tabs.map(function (t) {
          return '<button class="w-tab' + (t.id === screenTab ? " on" : "") + '" data-screen="' + t.id + '">' +
            icon(t.icon, 17) + esc(t.label) + "</button>";
        }).join("") + "</div>" +
      "</div></div>";
    return html;
  }

  var CUSTODY_SHORT = { c_seed: "Self custody, seed phrase", c_mpc: "MPC, no seed phrase",
    c_aa: "Smart account", c_hw: "Hardware first", c_multisig: "Multisig vault",
    c_custodial: "Custodial", c_hybrid: "Hybrid custody" };

  function walletHeader() {
    var custody = SPEC.custody ? (CUSTODY_SHORT[SPEC.custody] || lab(SPEC.custody)) : "No custody model yet";
    return '<div class="w-top"><div class="w-avatar"></div><div><div class="w-name">' +
      esc(SPEC.name || "Untitled wallet") + '</div><div class="w-sub">' + esc(custody) + "</div></div>" +
      '<div class="w-topright">' + (has("f_alerts") ? '<div class="w-icon">' + icon("bell", 13) + "</div>" : "") +
      (has("f_qr") ? '<div class="w-icon">' + icon("scan", 13) + "</div>" : "") +
      '<div class="w-icon">' + icon("gear", 13) + "</div></div></div>";
  }

  function secTags() {
    var ids = (SPEC.security || []).slice(0, 4);
    if (!ids.length) return "";
    return '<div class="w-sec">' + ids.map(function (id) {
      return '<span class="w-tag">' + esc(SHORT[id] || lab(id)) + "</span>";
    }).join("") + (SPEC.security.length > 4 ? '<span class="w-tag">+' + (SPEC.security.length - 4) + "</span>" : "") + "</div>";
  }

  function actionRow() {
    var acts = [];
    acts.push({ l: "Send", i: "send", p: true });
    acts.push({ l: "Receive", i: "receive" });
    if (has("f_onramp")) acts.push({ l: "Buy", i: "buy" });
    if (has("f_swap")) acts.push({ l: "Swap", i: "swap" });
    if (acts.length < 4 && has("f_stake")) acts.push({ l: "Stake", i: "stake" });
    if (acts.length < 4 && has("f_card")) acts.push({ l: "Card", i: "card" });
    if (acts.length < 4 && has("f_qr")) acts.push({ l: "Scan", i: "scan" });
    if (acts.length < 4 && has("f_history")) acts.push({ l: "Activity", i: "chart" });
    if (acts.length < 3) acts.push({ l: "Activity", i: "chart" });
    if (acts.length < 3) acts.push({ l: "Settings", i: "gear" });
    return '<div class="w-acts">' + acts.slice(0, 4).map(function (a) {
      return '<div class="w-act' + (a.p ? " primary" : "") + '">' + icon(a.i, 15) + esc(a.l) + "</div>";
    }).join("") + "</div>";
  }

  function sparkline(seed, w, h, color) {
    var rnd = seeded(seed), pts = [], i, v = 0.5;
    for (i = 0; i <= 26; i++) { v = Math.max(0.08, Math.min(0.94, v + (rnd() - 0.46) * 0.16)); pts.push(v); }
    var d = pts.map(function (p, ix) {
      return (ix ? "L" : "M") + (ix / 26 * w).toFixed(1) + " " + ((1 - p) * h).toFixed(1);
    }).join(" ");
    return '<svg class="w-chart" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none" width="100%">' +
      '<path d="' + d + " L" + w + " " + h + " L0 " + h + ' Z" fill="' + color + '" opacity="0.13"/>' +
      '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linejoin="round"/></svg>';
  }

  function screen(which) {
    var rows = assetRows();
    var total = rows.reduce(function (a, b) { return a + b.value; }, 0);
    var acc = accentHex();
    if (which === "home") {
      if (!rows.length) {
        return walletHeader() +
          '<div class="w-card"><div class="w-label">Total balance</div><div class="w-balance">$0.00</div>' +
          '<div class="w-delta">Waiting for your first decision</div></div>' +
          '<div class="w-empty">Nothing in here yet.<br>Tell the architect which coins it should hold and this screen fills in.</div>' +
          '<div class="w-rows">' + [0, 1, 2].map(function (i) {
            return '<div class="w-row ghost" style="animation-delay:' + (i * 140) + 'ms">' +
              '<div class="w-coin ghost-c"></div><div class="w-rowmain">' +
              '<i class="ln" style="width:' + (58 - i * 9) + '%"></i><i class="ln sm" style="width:' + (34 - i * 6) + '%"></i>' +
              "</div></div>";
          }).join("") + "</div>";
      }
      var rnd = seeded(hash(SPEC.name || "w"));
      var delta = (rnd() * 9 - 2.4);
      return walletHeader() +
        '<div class="w-card"><div class="w-label">Total balance</div><div class="w-balance">' + money(total) + "</div>" +
        '<div class="w-delta ' + (delta >= 0 ? "up" : "down") + '">' + (delta >= 0 ? "+" : "") + delta.toFixed(2) + "% today</div>" +
        (has("f_portfolio") ? sparkline(hash((SPEC.name || "w") + "total"), 260, 60, acc) : "") + "</div>" +
        actionRow() + secTags() +
        '<div class="w-rows">' + rows.slice(0, 7).map(function (r) {
          return '<div class="w-row"><div class="w-coin" style="background:' + r.color + '">' + esc(r.sym.slice(0, 4)) + "</div>" +
            '<div class="w-rowmain"><b>' + esc(r.label) + "</b><span>" + fmtAmount(r.amount) + " " + esc(r.sym) + "</span></div>" +
            '<div class="w-rowend"><b>' + money(r.value) + '</b><span class="' + (r.change >= 0 ? "up" : "down") + '">' +
            (r.change >= 0 ? "+" : "") + r.change.toFixed(1) + "%</span></div></div>";
        }).join("") + "</div>" +
        (rows.length > 7 ? '<div class="w-empty">and ' + (rows.length - 7) + " more assets</div>" : "");
    }
    if (which === "f_swap") {
      var STABLE = { usdc: 1, usdt: 1, dai: 1, eurc: 1 };
      var vol = rows.filter(function (r) { return !STABLE[r.id]; });
      var stable = rows.filter(function (r) { return STABLE[r.id]; });
      var a = vol[0] || rows[0] || { id: "eth", label: "Ethereum", sym: "ETH", color: "#7b8cf5" };
      var b = stable[0] || vol[1] || rows[1] || { id: "usdc", label: "USDC", sym: "USDC", color: "#2775ca" };
      var rate = (PRICE[a.id] || 1) / (PRICE[b.id] || 1);
      var payAmt = rate > 400 ? 0.5 : rate > 5 ? 2 : 100;
      var getAmt = payAmt * rate;
      return '<div class="w-top"><div class="w-name">Swap</div></div>' +
        '<div class="w-card"><div class="w-label">You pay</div><div style="display:flex;align-items:center;gap:9px;margin-top:7px">' +
        '<div class="w-coin" style="background:' + a.color + '">' + esc(a.sym.slice(0, 4)) + "</div>" +
        '<div class="w-balance" style="font-size:22px;margin:0">' + fmtAmount(payAmt) + '</div><div style="margin-left:auto" class="w-sub">' + esc(a.sym) + "</div></div></div>" +
        '<div style="text-align:center;margin:-6px 0 -4px;color:var(--w-accent)">' + icon("swap", 20) + "</div>" +
        '<div class="w-card"><div class="w-label">You receive</div><div style="display:flex;align-items:center;gap:9px;margin-top:7px">' +
        '<div class="w-coin" style="background:' + b.color + '">' + esc(b.sym.slice(0, 4)) + "</div>" +
        '<div class="w-balance" style="font-size:22px;margin:0">' + fmtAmount(getAmt) + '</div><div style="margin-left:auto" class="w-sub">' + esc(b.sym) + "</div></div></div>" +
        '<div class="w-rows" style="margin-top:10px">' +
        row("Route", has("f_bridge") ? "Best of 9 venues, 2 chains" : "Best of 9 venues") +
        row("Network fee", has("f_gas") ? "Sponsored, you pay nothing" : "$0.42") +
        (has("s_sim") ? row("Simulation", "Balance changes checked") : "") + "</div>" +
        '<div class="w-act primary" style="margin-top:12px;padding:12px">Review swap</div>';
    }
    if (which === "f_onramp") {
      return '<div class="w-top"><div class="w-name">Buy crypto</div></div>' +
        '<div class="w-card" style="text-align:center"><div class="w-label">Amount</div>' +
        '<div class="w-balance">$250</div><div class="w-sub">approx ' + (rows[0] ? fmtAmount(250 / (PRICE[rows[0].id] || 1)) + " " + rows[0].sym : "0.004 BTC") + "</div></div>" +
        '<div class="w-rows" style="margin-top:10px">' +
        row("Pay with", "Apple Pay") + row("Provider", "Best rate of 4") +
        row("Fee", "1.2%") + (has("v_nokyc") ? row("Identity", "Only needed to buy, not to hold") : row("Identity", "Verified once")) +
        "</div>" + '<div class="w-act primary" style="margin-top:12px;padding:12px">Confirm purchase</div>';
    }
    if (which === "f_portfolio") {
      return '<div class="w-top"><div class="w-name">Portfolio</div></div>' +
        '<div class="w-card"><div class="w-label">Net worth</div><div class="w-balance">' + money(total) + "</div>" +
        sparkline(hash((SPEC.name || "w") + "port"), 260, 80, acc) +
        '<div class="w-sub">Cost basis ' + money(total * 0.78) + ", up " + money(total * 0.22) + "</div></div>" +
        '<div class="w-rows" style="margin-top:10px">' + rows.slice(0, 5).map(function (r) {
          var pct = total ? (r.value / total * 100) : 0;
          return '<div class="w-row"><div class="w-coin" style="background:' + r.color + '">' + esc(r.sym.slice(0, 4)) + "</div>" +
            '<div class="w-rowmain"><b>' + esc(r.label) + "</b>" +
            '<div style="height:4px;border-radius:3px;background:var(--w-line);margin-top:5px"><i style="display:block;height:100%;border-radius:3px;width:' +
            pct.toFixed(0) + "%;background:" + r.color + '"></i></div></div>' +
            '<div class="w-rowend"><b>' + pct.toFixed(0) + "%</b></div></div>";
        }).join("") + "</div>" +
        (has("f_tax") ? '<div class="w-empty">Tax report ready to export</div>' : "");
    }
    if (which === "f_earn" || which === "f_stake") {
      var title = which === "f_earn" ? "Earn" : "Stake";
      var pool = rows.length ? rows : [{ label: "Ethereum", sym: "ETH", color: "#7b8cf5", value: 2400 }];
      return '<div class="w-top"><div class="w-name">' + title + '</div></div>' +
        '<div class="w-card"><div class="w-label">Earning now</div><div class="w-balance">' + money(total * 0.34) + "</div>" +
        '<div class="w-delta">+' + money(total * 0.0021) + " this week</div></div>" +
        '<div class="w-rows" style="margin-top:10px">' + pool.slice(0, 5).map(function (r, i) {
          var apy = (2.5 + (i * 1.7) % 9).toFixed(1);
          return '<div class="w-row"><div class="w-coin" style="background:' + r.color + '">' + esc(r.sym.slice(0, 4)) + "</div>" +
            '<div class="w-rowmain"><b>' + esc(r.label) + "</b><span>" + (which === "f_earn" ? "Vault" : "Validator set") + "</span></div>" +
            '<div class="w-rowend"><b class="up">' + apy + "%</b><span>APY</span></div></div>";
        }).join("") + "</div>";
    }
    if (which === "f_nft") {
      var names = ["Tidal #204", "Grain 019", "Pale Sun", "Meridian", "Lot 77", "Sable Cat"];
      return '<div class="w-top"><div class="w-name">Collectibles</div></div>' +
        '<div class="w-nfts">' + names.slice(0, 6).map(function (n, i) {
          var r = seeded(hash(n + (SPEC.name || "")));
          var h1 = Math.floor(r() * 360), h2 = Math.floor(r() * 360);
          return '<div class="w-nft" style="background:linear-gradient(' + Math.floor(r() * 360) + "deg,hsl(" + h1 + ",70%,55%),hsl(" + h2 + ',72%,42%))"><b>' + esc(n) + "</b></div>";
        }).join("") + "</div>" +
        '<div class="w-empty">Floor value ' + money(total * 0.2 + 380) + " across 6 items</div>";
    }
    if (which === "f_dapp") {
      var apps = [["Uniswap", "Swap anything"], ["Aave", "Lend and borrow"], ["Blur", "NFT marketplace"],
        ["Lido", "Liquid staking"], ["Farcaster", "Social"], ["Polymarket", "Prediction markets"]];
      return '<div class="w-top"><div class="w-name">Apps</div></div>' +
        '<div class="w-card"><div class="w-label">Connected</div><div class="w-sub" style="margin-top:4px">' +
        (has("f_wc") ? "3 sessions over WalletConnect" : "No live sessions") + "</div></div>" +
        '<div class="w-rows" style="margin-top:10px">' + apps.map(function (a, i) {
          var r = seeded(hash(a[0]));
          return '<div class="w-row"><div class="w-coin" style="background:hsl(' + Math.floor(r() * 360) + ',65%,55%)">' + esc(a[0].slice(0, 2).toUpperCase()) + "</div>" +
            '<div class="w-rowmain"><b>' + esc(a[0]) + "</b><span>" + esc(a[1]) + "</span></div></div>";
        }).join("") + "</div>" +
        (has("s_approve") ? '<div class="w-empty">4 token approvals open. Review them.</div>' : "");
    }
    if (which === "f_card") {
      return '<div class="w-top"><div class="w-name">Card</div></div>' +
        '<div class="w-card" style="background:linear-gradient(140deg,' + acc + ',#1b1f2a);color:#06120b;min-height:120px;display:flex;flex-direction:column;justify-content:space-between">' +
        '<div style="font-weight:700">' + esc(SPEC.name || "Wallet") + "</div>" +
        '<div><div style="font-size:15px;letter-spacing:.14em;font-weight:600">4821 •••• •••• 7390</div>' +
        '<div style="font-size:10px;opacity:.75;margin-top:3px">Spends from ' + esc(rows[0] ? rows[0].label : "your balance") + "</div></div></div>" +
        '<div class="w-rows" style="margin-top:12px">' +
        row("Groceries", "-$42.10") + row("Coffee", "-$4.80") + row("Flights", "-$318.00") +
        (has("f_goals") ? row("Rounded up to savings", "+$3.10") : "") + "</div>";
    }
    if (which === "f_send") {
      return '<div class="w-top"><div class="w-name">Send</div></div>' +
        '<div class="w-card"><div class="w-label">To</div><div style="margin-top:6px;font-weight:600">' +
        (has("f_names") ? "alice.eth" : "bc1q4x...8m2v") + '</div><div class="w-sub">' +
        (has("f_book") ? "Saved contact" : "Pasted address") + "</div></div>" +
        '<div class="w-card" style="margin-top:9px"><div class="w-label">Amount</div><div class="w-balance">$120.00</div></div>' +
        '<div class="w-rows" style="margin-top:10px">' +
        (has("s_sim") ? row("Simulation", "Sends $120, nothing else moves") : "") +
        (has("s_limits") ? row("Daily limit", "$120 of $2,000 used") : "") +
        row("Fee", has("f_gas") ? "Sponsored" : "$0.09") +
        (has("s_bio") ? row("Confirm with", "Face ID") : "") + "</div>" +
        '<div class="w-act primary" style="margin-top:12px;padding:12px">Slide to send</div>';
    }
    return '<div class="w-empty">This screen appears once you add the feature behind it.</div>';
  }

  function row(k, v) {
    return '<div class="w-row w-kv"><span class="k">' + esc(k) + '</span><b class="v">' + esc(v) + "</b></div>";
  }
  function fmtAmount(n) {
    if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
    if (n >= 1) return n.toFixed(2);
    return n.toFixed(n < 0.001 ? 6 : 4);
  }

  /* ---------------------------------------------------------- blueprint */
  function noteList() {
    var n = [], f = SPEC.features || [], a = SPEC.assets || [];
    if (SPEC.custody === "c_custodial") n.push(["Regulation", "Holding user keys makes you a regulated money business in most countries. Budget for licensing before launch."]);
    if (SPEC.custody === "c_mpc") n.push(["Infrastructure", "MPC means running signing nodes with real uptime targets. Plan for on-call from day one."]);
    if (SPEC.custody === "c_multisig") n.push(["Product surface", "Multisig needs invites, pending approvals and notifications. It is a second product bolted to the first."]);
    if (has("f_onramp") || has("f_offramp")) n.push(["Partners", "Card and bank rails come from a provider per region, each with its own KYC flow and its own country list."]);
    if (has("f_card")) n.push(["Long lead time", "A debit card needs a BIN sponsor and a compliance programme. Start that conversation months before the app is ready."]);
    if (!SPEC.security || SPEC.security.length < 3) n.push(["Thin security", "Fewer than three protections is light for something holding money. Transaction simulation and a scam filter are the cheapest wins."]);
    if (a.length > 12) n.push(["Breadth costs", a.length + " assets means that many price feeds, indexers and address formats to keep alive. Each one is ongoing work, not a one off."]);
    if (has("f_dapp") && has("p_ios")) n.push(["App store", "In-app browsers that reach token sales get rejected. The iOS build usually ships a curated app list instead."]);
    if (has("v_nokyc") && has("f_onramp")) n.push(["Tension", "No KYC and card purchases cannot both be true. Keep the wallet open and gate only the buy flow."]);
    if (has("f_stake") && !has("f_portfolio")) n.push(["Missing half", "People who stake want to watch it grow. Portfolio and P&L is the natural partner."]);
    if ((SPEC.platforms || []).length > 3) n.push(["Team shape", "Every extra platform is a separate build, review and release cycle. Three is already ambitious for a small team."]);
    if (has("f_ai")) n.push(["Copilot", "An in-app assistant needs guardrails: it explains and warns, it never signs."]);
    if (!n.length) n.push(["Looking clean", "Nothing in this build fights itself. Keep the first release small and let the rest wait."]);
    return n;
  }

  function weight() {
    var w = 3 + (SPEC.assets || []).length * 0.7 + (SPEC.networks || []).length * 0.9 +
      (SPEC.features || []).length * 0.9 + (SPEC.security || []).length * 0.45 +
      (SPEC.platforms || []).length * 2.2 + (SPEC.privacy || []).length * 0.6;
    if (SPEC.custody === "c_mpc" || SPEC.custody === "c_multisig") w += 4;
    if (SPEC.custody === "c_custodial") w += 6;
    if (has("f_card")) w += 5;
    if (has("f_onramp")) w += 3;
    var months = Math.max(2, Math.round(w / 6));
    return { points: Math.round(w), months: months };
  }

  function renderBlueprint() {
    var w = weight();
    var groups = CAT.groups.map(function (g) {
      var vals = SPEC[g.key];
      var ids = Array.isArray(vals) ? vals : (vals ? [vals] : []);
      return { title: g.title, ids: ids };
    });
    groups.push({ title: "Finish", ids: [SPEC.theme, SPEC.accent].filter(Boolean) });

    var html =
      '<div class="bp-head"><div><h2 class="bp-title">' + esc(SPEC.name || "Untitled wallet") + "</h2>" +
      '<p class="bp-sub">' + esc(SPEC.purpose || "No audience written down yet. Tell the architect who it is for.") + "</p></div>" +
      '<div class="bp-actions">' +
      '<button class="btn primary" id="saveBtn">Save and get a link</button>' +
      '<button class="btn" id="jsonBtn">Download spec</button>' +
      '<button class="btn" id="printBtn">Print</button></div></div>' +

      '<div class="stats">' +
      stat((SPEC.assets || []).length, "assets") +
      stat((SPEC.networks || []).length, "networks") +
      stat((SPEC.features || []).length, "features") +
      stat((SPEC.security || []).length, "protections") +
      stat((SPEC.platforms || []).length, "platforms") +
      stat(w.points, "build weight") +
      "</div>" +

      '<div class="share" id="saveOptions" style="display:' + (saved ? "none" : "block") + ';margin-bottom:20px">' +
      '<h3 style="font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--ink-3);margin:0 0 10px">Publishing options</h3>' +
      '<div style="display:flex;flex-direction:column;gap:10px">' +
      '<label style="display:flex;align-items:center;gap:8px;font-size:13px"><input type="checkbox" id="isPublic"> Show this build in the public gallery</label>' +
      '<p style="font-size:12px;color:var(--ink-3)">Anyone with the saved link can view this design. Do not include wallet secrets.</p>' +
      '</div></div>' +

      groups.map(function (g) {
        return '<div class="bp-group"><h3>' + esc(g.title) + " <em>" + g.ids.length + "</em></h3>" +
          (g.ids.length ? '<div class="bp-items">' + g.ids.map(function (id) {
            var m = META[id] || {};
            return '<span class="bp-item">' + esc(m.label || id) + "</span>";
          }).join("") + "</div>" : '<div class="bp-none">Nothing chosen yet.</div>') + "</div>";
      }).join("") +

      '<div class="notes"><h3 style="font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--ink-3);margin:0 0 6px">What this build implies</h3>' +
      noteList().map(function (n) {
        return '<div class="note"><span class="dot">▲</span><div><b>' + esc(n[0]) + ".</b> " + esc(n[1]) + "</div></div>";
      }).join("") +
      '<div class="note"><span class="dot" style="color:var(--brand)">■</span><div><b>Rough size.</b> ' +
      "Build weight " + w.points + " points, which is roughly " + w.months + " months of work for a small team " +
      "before anything regulated is counted. Indicative only.</div></div></div>" +

      '<div class="share" id="shareBox" style="display:none"></div>';
    return html;
  }
  function stat(n, l) { return '<div class="stat"><b>' + n + "</b><span>" + esc(l) + "</span></div>"; }

  /* -------------------------------------------------------------- vault */
  function renderVault() {
    var q = filter.toLowerCase();
    var groups = CAT.groups.slice();
    groups.push({ key: "theme", title: "Theme", multi: false, items: CAT.themes.map(function (t) { return { id: t.id, label: t.label, blurb: t.mode === "light" ? "Light interface" : "Dark interface" }; }) });
    groups.push({ key: "accent", title: "Accent colour", multi: false, items: CAT.accents.map(function (a) { return { id: a.id, label: a.label, blurb: a.hex }; }) });

    var body = groups.map(function (g) {
      var items = g.items.filter(function (i) {
        return !q || (i.label + " " + (i.blurb || "")).toLowerCase().indexOf(q) >= 0;
      });
      if (!items.length) return "";
      return '<div class="vgroup"><h3>' + esc(g.title) + " <em>" + items.length + (g.multi ? " to mix" : " pick one") + "</em></h3>" +
        '<div class="vitems">' + items.map(function (i) {
          var on = has(i.id);
          return '<button class="vitem' + (on ? " on" : "") + '" data-opt="' + i.id + '"><b>' + esc(i.label) + "</b>" +
            (i.blurb ? "<span>" + esc(i.blurb) + "</span>" : "") + "</button>";
        }).join("") + "</div></div>";
    }).join("");

    return '<div class="vault-head"><input class="search" id="vsearch" placeholder="Search all ' + CAT.total +
      ' options: staking, lightning, face id..." value="' + esc(filter) + '">' +
      '<button class="btn" id="clearAll">Clear the build</button></div>' +
      (body || '<div class="bp-none">Nothing matches that.</div>');
  }

  async function renderGallery() {
    var v = $("#view");
    v.innerHTML = '<div class="vault-head"><h2>Public Gallery</h2><div class="head-spacer"></div><button class="btn" id="refreshGallery">Refresh</button></div>' +
      '<div class="vitems" id="galleryItems"><div class="bp-none">Loading gallery...</div></div>';
    $("#refreshGallery").onclick = renderGallery;

    try {
      var r = await fetch("/api/gallery").then(function (res) { return res.json(); });
      var box = $("#galleryItems");
      if (!r.items || !r.items.length) {
        box.innerHTML = '<div class="bp-none">The gallery is empty. Be the first to publish a build!</div>';
        return;
      }
      box.innerHTML = r.items.map(function (it) {
        return '<button class="vitem" onclick="location.href=\'/w/' + esc(it.code) + '\'"><b>' + esc(it.name) + "</b>" +
          "<span>" + it.count + " options chosen • " + esc(it.code) + "</span></button>";
      }).join("");
    } catch (e) {
      $("#galleryItems").innerHTML = '<div class="bp-none">Could not load the gallery.</div>';
    }
  }

  function toggle(id) {
    var g = GROUP_OF[id];
    if (!g) return;
    if (SINGLE[g]) {
      SPEC[g] = SPEC[g] === id ? "" : id;
      if (g === "theme" && !SPEC[g]) SPEC[g] = "t_dark";
      if (g === "accent" && !SPEC[g]) SPEC[g] = "a_green";
    } else {
      SPEC[g] = SPEC[g] || [];
      var ix = SPEC[g].indexOf(id);
      if (ix >= 0) SPEC[g].splice(ix, 1); else SPEC[g].push(id);
    }
    var topic = GROUP_TOPIC[g];
    if (topic) {
      if (topic === "features" && STATE.answered.indexOf("features") >= 0) topic = "features2";
      if (STATE.answered.indexOf(topic) < 0) STATE.answered.push(topic);
    }
    saved = null;
    render();
    toast((has(id) ? "Added " : "Removed ") + lab(id));
  }

  /* ------------------------------------------------------------- render */
  function render() {
    var v = $("#view");
    v.classList.toggle("view-preview", view === "preview");
    if (view === "preview") {
      v.innerHTML = '<div class="stage">' + renderPhone() +
        '<p class="caption">This is your build, live. Tap the tabs inside the phone to walk through the screens your choices created.</p></div>';
      Array.prototype.forEach.call(v.querySelectorAll("[data-screen]"), function (b) {
        b.onclick = function () { screenTab = b.getAttribute("data-screen"); render(); };
      });
    } else if (view === "blueprint") {
      v.innerHTML = renderBlueprint();
      $("#saveBtn").onclick = saveBuild;
      $("#jsonBtn").onclick = downloadSpec;
      $("#printBtn").onclick = function () { window.print(); };
      if (saved) showShare(saved);
    } else if (view === "gallery") {
      renderGallery();
    } else {
      v.innerHTML = renderVault();
      var s = $("#vsearch");
      s.oninput = function () { filter = s.value; var pos = s.selectionStart; render(); var n = $("#vsearch"); n.focus(); n.setSelectionRange(pos, pos); };
      $("#clearAll").onclick = function () {
        ["assets", "networks", "security", "features", "platforms", "privacy"].forEach(function (k) { SPEC[k] = []; });
        SPEC.custody = ""; SPEC.style = "";
        render(); toast("Build cleared");
      };
      Array.prototype.forEach.call(v.querySelectorAll("[data-opt]"), function (b) {
        b.onclick = function () { toggle(b.getAttribute("data-opt")); };
      });
    }
    var count = ["assets", "networks", "security", "features", "platforms", "privacy"].reduce(function (a, k) {
      return a + (SPEC[k] || []).length;
    }, 0) + (SPEC.custody ? 1 : 0) + (SPEC.style ? 1 : 0) + 2;
    $("#chosen").textContent = count;

    var jump = $("#jump");
    if (count > 2) {
      jump.hidden = false;
      jump.innerHTML = "See the build: <b>" + esc(SPEC.name || "your wallet") + "</b>, " + count + " choices";
    } else {
      jump.hidden = true;
    }
    saveDraft();
  }

  /* --------------------------------------------------------------- save */
  async function saveBuild() {
    var btn = $("#saveBtn");
    var isPub = $("#isPublic") ? $("#isPublic").checked : false;

    btn.disabled = true; btn.textContent = "Saving...";
    try {
      var r = await fetch("/api/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec: SPEC, is_public: isPub })
      }).then(function (res) { return res.json(); });
      if (r.code) {
        saved = r.code;
        if ($("#saveOptions")) $("#saveOptions").style.display = "none";
        showShare(r.code); loadStats(); toast("Saved");
      }
      else toast(r.detail || "Could not save that");
    } catch (e) { toast("Could not save that"); }
    btn.disabled = false; btn.textContent = "Save and get a link";
  }

  function showShare(code) {
    var box = $("#shareBox");
    if (!box) return;
    var url = location.origin + "/w/" + code;
    box.style.display = "block";
    box.innerHTML = "<b>Saved.</b> This build now lives at its own address. Anyone opening it gets your wallet design, " +
      "loaded and editable." + "<code>" + esc(url) + "</code>" +
      '<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<button class="btn" id="copyBtn">Copy link</button>' +
      '<a class="btn" href="/w/' + esc(code) + '" target="_blank" rel="noopener">Open it</a></div>';
    $("#copyBtn").onclick = function () {
      navigator.clipboard.writeText(url).then(function () { toast("Link copied"); },
        function () { toast(url); });
    };
  }

  function downloadSpec() {
    var out = { name: SPEC.name, purpose: SPEC.purpose, generated_by: "Build-a-Wallet" };
    ["assets", "networks", "custody", "security", "features", "platforms", "privacy", "style", "theme", "accent"].forEach(function (k) {
      var v = SPEC[k];
      out[k] = Array.isArray(v) ? v.map(lab) : (v ? lab(v) : null);
    });
    var blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (SPEC.name || "wallet").toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-spec.json";
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }

  async function loadStats() {
    try {
      var s = await fetch("/api/stats").then(function (r) { return r.json(); });
      $("#builtPill").innerHTML = "<b>" + s.built + "</b> wallet" + (s.built === 1 ? "" : "s") + " designed here";
    } catch (e) { /* the pill is decoration */ }
  }

  /* --------------------------------------------------------------- boot */
  async function boot() {
    CAT = await fetch("/api/catalog").then(function (r) { return r.json(); });
    META = CAT.meta;
    CAT.groups.forEach(function (g) { g.items.forEach(function (i) { GROUP_OF[i.id] = g.key; }); });
    CAT.themes.forEach(function (t) { GROUP_OF[t.id] = "theme"; });
    CAT.accents.forEach(function (a) { GROUP_OF[a.id] = "accent"; });
    $("#total").textContent = CAT.total;

    var start = await fetch("/api/start").then(function (r) { return r.json(); });
    SPEC = start.spec; STATE = start.state;

    var draft = readDraft();
    var m = location.pathname.match(/^\/w\/([a-z0-9]{4,32})$/i);
    if (draft && !m) {
      SPEC = draft.spec; STATE = draft.state || STATE;
      push("ai", start.reply);
      push("sys", "Your last build was still here, so I picked it up: **" + (SPEC.name || "untitled") + "**. " +
        "Carry on, or say start over for a blank one.");
      renderChips([{ label: "Carry on", send: "what else could I add?" },
        { label: "Show the blueprint", send: "show me the blueprint" },
        { label: "Start over", send: "start over" }]);
      setMeters(90, 0);
      render();
      loadStats();
      return;
    }
    if (m) {
      try {
        var wl = await fetch("/api/wallet/" + m[1]).then(function (r) { return r.ok ? r.json() : null; });
        if (wl) {
          SPEC = wl.spec;
          STATE.answered = ["name", "purpose", "assets", "networks", "custody", "security", "features", "platforms", "privacy", "style"];
          STATE.finished = true;
          push("sys", "Opened a saved build: " + (wl.name || "untitled") + ".");
          push("ai", "This is **" + (wl.name || "an untitled wallet") + "**, built by somebody else. It is yours to change now: " +
            "add a coin, swap the custody model, strip it back. Nothing you do here touches their copy.");
          renderChips([{ label: "What would you change?", send: "what would you change about this?" },
            { label: "Add more features", send: "what else could I add?" },
            { label: "Start my own", send: "start over" }]);
          setMeters(100, 0);
          view = "blueprint";
          Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
            t.classList.toggle("on", t.getAttribute("data-view") === "blueprint");
          });
        }
      } catch (e) { /* fall through to a normal build */ }
    }

    if (!m || !STATE.finished) {
      push("ai", start.reply);
      renderChips(start.chips);
      setMeters(start.progress, start.count);
    }
    render();
    loadStats();
  }

  /* --------------------------------------------------------------- wire */
  $("#form").addEventListener("submit", function (e) {
    e.preventDefault();
    var i = $("#input");
    var t = i.value;
    i.value = ""; i.style.height = "auto";
    send(t);
  });
  $("#input").addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(130, this.scrollHeight) + "px";
  });
  $("#input").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#form").dispatchEvent(new Event("submit")); }
  });
  $("#jump").onclick = function () {
    document.querySelector(".pane-build").scrollIntoView({ behavior: "smooth", block: "start" });
  };
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
    t.onclick = function () {
      view = t.getAttribute("data-view");
      Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (x) { x.classList.remove("on"); });
      t.classList.add("on");
      render();
    };
  });

  boot().catch(function () {
    push("sys", "The wallet builder cannot connect to its service right now. Please try again later.");
    $("#view").innerHTML = '<div class="empty">The live preview will appear when the builder service is available.</div>';
    $("#sendBtn").disabled = true;
  });
})();
