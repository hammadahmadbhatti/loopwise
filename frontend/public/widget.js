/*!
 * Loopwise feedback widget. Embed with:
 * <script src="https://YOUR-LOOPWISE/widget.js" data-key="pk_..." data-api="https://YOUR-LOOPWISE" async></script>
 * Optional: data-color="#4f46e5", data-label="Feedback", data-position="right|left".
 * No cookies, no tracking. Renders in a shadow root so it never clashes with the host page's CSS.
 */
(function () {
  "use strict";
  var script = document.currentScript || document.querySelector('script[data-key][src*="widget.js"]');
  if (!script || window.__loopwiseWidget) return;
  window.__loopwiseWidget = true;

  var key = script.getAttribute("data-key");
  var api = (script.getAttribute("data-api") || new URL(script.src).origin).replace(/\/$/, "");
  var color = script.getAttribute("data-color") || "#4f46e5";
  var label = script.getAttribute("data-label") || "Feedback";
  var side = script.getAttribute("data-position") === "left" ? "left" : "right";
  if (!key) { console.warn("[loopwise] missing data-key"); return; }

  var host = document.createElement("div");
  host.setAttribute("data-loopwise", "");
  document.body.appendChild(host);
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  root.innerHTML =
    '<style>' +
    ':host{all:initial}*{box-sizing:border-box;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
    '.btn{position:fixed;bottom:20px;' + side + ':20px;z-index:2147483646;background:' + color + ';color:#fff;border:0;border-radius:999px;padding:11px 18px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 8px 24px rgba(15,23,42,.18)}' +
    '.panel{position:fixed;bottom:76px;' + side + ':20px;z-index:2147483647;width:320px;max-width:calc(100vw - 40px);background:#fff;border:1px solid #e2e8f0;border-radius:16px;box-shadow:0 20px 50px rgba(15,23,42,.2);padding:16px;display:none;color:#0f172a}' +
    '.panel.open{display:block}h3{margin:0 0 4px;font-size:15px}p{margin:0 0 12px;font-size:12px;color:#64748b}' +
    'textarea,input{width:100%;border:1px solid #e2e8f0;border-radius:10px;padding:9px 10px;font-size:14px;margin-bottom:8px;color:#0f172a;background:#fff}' +
    'textarea{min-height:96px;resize:vertical}textarea:focus,input:focus{outline:2px solid ' + color + '33;border-color:' + color + '}' +
    '.stars{display:flex;gap:4px;margin-bottom:10px}.star{background:none;border:0;font-size:20px;cursor:pointer;color:#cbd5e1;padding:0}.star.on{color:#f59e0b}' +
    '.send{width:100%;background:' + color + ';color:#fff;border:0;border-radius:10px;padding:10px;font-size:14px;font-weight:600;cursor:pointer}.send:disabled{opacity:.6;cursor:default}' +
    '.hp{position:absolute;left:-9999px;opacity:0;height:0;width:0}.msg{font-size:13px;margin-top:8px}.ok{color:#047857}.err{color:#be123c}' +
    '</style>' +
    '<button class="btn" type="button" aria-haspopup="dialog">' + label + '</button>' +
    '<form class="panel" role="dialog" aria-label="Send feedback">' +
    '<h3>Share your feedback</h3><p>Any language is welcome. We read everything.</p>' +
    '<div class="stars" role="radiogroup" aria-label="Rating"></div>' +
    '<textarea name="text" required minlength="3" maxlength="5000" placeholder="What can we improve?"></textarea>' +
    '<input name="email" type="email" placeholder="Email (optional, for updates)">' +
    '<input name="website" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">' +
    '<button class="send" type="submit">Send</button><div class="msg" aria-live="polite"></div>' +
    '</form>';

  var btn = root.querySelector(".btn");
  var panel = root.querySelector(".panel");
  var stars = root.querySelector(".stars");
  var msg = root.querySelector(".msg");
  var send = root.querySelector(".send");
  var rating = null;

  for (var i = 1; i <= 5; i++) {
    (function (n) {
      var s = document.createElement("button");
      s.type = "button"; s.className = "star"; s.textContent = "★"; s.setAttribute("aria-label", n + " star" + (n > 1 ? "s" : ""));
      s.onclick = function () {
        rating = rating === n ? null : n;
        var all = stars.querySelectorAll(".star");
        for (var j = 0; j < all.length; j++) all[j].className = "star" + (rating && j < rating ? " on" : "");
      };
      stars.appendChild(s);
    })(i);
  }

  btn.onclick = function () {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) panel.querySelector("textarea").focus();
  };

  panel.onsubmit = function (e) {
    e.preventDefault();
    var data = {
      text: panel.elements.text.value.trim(),
      email: panel.elements.email.value.trim() || null,
      website: panel.elements.website.value,
      rating: rating,
      page_url: location.href.slice(0, 1000),
      meta: { language: navigator.language || "", screen: screen.width + "x" + screen.height },
    };
    if (data.text.length < 3) return;
    send.disabled = true; msg.textContent = ""; msg.className = "msg";
    fetch(api + "/api/public/widget/" + encodeURIComponent(key) + "/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status === 429 ? "Too many messages, please try later." : "Could not send, please try again.");
      panel.reset(); rating = null;
      var all = stars.querySelectorAll(".star");
      for (var j = 0; j < all.length; j++) all[j].className = "star";
      msg.textContent = "Thank you! Your feedback was sent."; msg.className = "msg ok";
      setTimeout(function () { panel.classList.remove("open"); msg.textContent = ""; }, 2500);
    }).catch(function (err) {
      msg.textContent = err.message; msg.className = "msg err";
    }).then(function () { send.disabled = false; });
  };
})();
