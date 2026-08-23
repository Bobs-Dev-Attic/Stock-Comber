/* Shared site navigation for the sub-pages: a ☰ menu button that opens a slide-in
   drawer with links to every page. Self-contained — injects its own styles and
   markup so each static page only needs <script src="/nav.js" defer></script>.
   (The dashboard index.html has its own built-in drawer and does not load this.)
   Leaves each page's existing theme toggle alone. */
(function () {
  "use strict";
  if (window.__scNavLoaded) return;           // guard against double-injection
  window.__scNavLoaded = true;

  var LINKS = [
    { href: "/", label: "🏠 Dashboard" },
    { href: "/settings.html", label: "⚙️ Settings" },
    { href: "/about.html", label: "ℹ️ About" },
    { href: "/glossary.html", label: "📖 Definition of terms" },
    { href: "/strategies.html", label: "🎯 Strategies" },
    { div: true },
    { href: "/analytics.html", label: "📊 Analytics" },
    { href: "/backtest.html", label: "🧪 Backtest" },
    { href: "/history.html", label: "🕓 History" },
    { href: "/thesis.html", label: "🎯 Theses" },
  ];

  var css =
    ".sc-navbtn{position:fixed;top:.7rem;right:3.3rem;z-index:55;border:1px solid var(--line,#e3e6ea);" +
    "background:var(--panel,#fff);color:var(--ink,#1a1d23);width:2.2rem;height:2.2rem;border-radius:8px;" +
    "cursor:pointer;font-size:1.1rem;line-height:1;box-shadow:var(--shadow,0 1px 3px rgba(0,0,0,.1))}" +
    ".sc-navdrawer{position:fixed;inset:0;z-index:60;visibility:hidden}" +
    ".sc-navdrawer.open{visibility:visible}" +
    ".sc-navback{position:absolute;inset:0;background:rgba(0,0,0,.5);opacity:0;transition:opacity .22s ease}" +
    ".sc-navdrawer.open .sc-navback{opacity:1}" +
    ".sc-navpane{position:absolute;top:0;right:0;height:100%;width:min(320px,86vw);background:var(--panel,#fff);" +
    "border-left:1px solid var(--line,#e3e6ea);box-shadow:-8px 0 30px rgba(0,0,0,.18);padding:1rem;" +
    "transform:translateX(100%);transition:transform .24s ease;overflow-y:auto}" +
    ".sc-navdrawer.open .sc-navpane{transform:none}" +
    ".sc-navpane-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;font-weight:700}" +
    ".sc-navclose{border:none;background:none;color:var(--ink,#1a1d23);font-size:1.4rem;line-height:1;cursor:pointer}" +
    ".sc-navlink{display:block;padding:.6rem;border-radius:8px;text-decoration:none;color:var(--ink,#1a1d23);font-size:.95rem}" +
    ".sc-navlink:hover,.sc-navlink:focus{background:color-mix(in srgb,var(--accent,#1f7a4d) 12%,transparent);outline:none}" +
    ".sc-navlink.here{font-weight:700;color:var(--accent,#1f7a4d)}" +
    ".sc-navdiv{height:1px;background:var(--line,#e3e6ea);margin:.5rem 0}" +
    "@media (prefers-reduced-motion:reduce){.sc-navback,.sc-navpane{transition:none}}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var here = location.pathname.replace(/\/index\.html$/, "/") || "/";
  var linksHtml = LINKS.map(function (l) {
    if (l.div) return '<div class="sc-navdiv"></div>';
    var cur = (l.href === here) ? " here" : "";
    return '<a class="sc-navlink' + cur + '" href="' + l.href + '">' + l.label + "</a>";
  }).join("");

  var btn = document.createElement("button");
  btn.className = "sc-navbtn";
  btn.id = "sc-nav-btn";
  btn.type = "button";
  btn.setAttribute("aria-haspopup", "true");
  btn.setAttribute("aria-expanded", "false");
  btn.setAttribute("aria-controls", "sc-nav-drawer");
  btn.setAttribute("aria-label", "Menu");
  btn.title = "Menu";
  btn.textContent = "☰";              // ☰

  var drawer = document.createElement("div");
  drawer.className = "sc-navdrawer";
  drawer.id = "sc-nav-drawer";
  drawer.setAttribute("aria-hidden", "true");
  drawer.innerHTML =
    '<div class="sc-navback" id="sc-nav-back"></div>' +
    '<nav class="sc-navpane" role="dialog" aria-modal="true" aria-label="Menu">' +
    '<div class="sc-navpane-h"><span>Menu</span>' +
    '<button class="sc-navclose" id="sc-nav-close" type="button" aria-label="Close menu">×</button></div>' +
    linksHtml + "</nav>";

  document.body.appendChild(btn);
  document.body.appendChild(drawer);

  var lastFocus = null;
  function open() {
    lastFocus = document.activeElement;
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    btn.setAttribute("aria-expanded", "true");
    var first = drawer.querySelector(".sc-navclose");
    if (first) first.focus();
  }
  function close() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    btn.setAttribute("aria-expanded", "false");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  btn.addEventListener("click", function (e) { e.stopPropagation(); open(); });
  drawer.querySelector("#sc-nav-close").addEventListener("click", close);
  drawer.querySelector("#sc-nav-back").addEventListener("click", close);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && drawer.classList.contains("open")) close();
  });
})();
