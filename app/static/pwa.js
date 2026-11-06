// "Add to home screen" suggestion shown on the first visit (the welcome page).

(function () {
  const banner = document.getElementById("install-banner");
  const DISMISS_KEY = "install-dismissed";

  // Register the service worker (required for installability)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
  }

  if (!banner) return;

  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
  };

  const alreadyInstalled =
    window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  if (alreadyInstalled || store.get(DISMISS_KEY)) return;

  const text = document.getElementById("install-text");
  const accept = document.getElementById("install-accept");
  const dismiss = document.getElementById("install-dismiss");
  let deferredPrompt = null;

  dismiss.addEventListener("click", () => {
    store.set(DISMISS_KEY, "1");
    banner.hidden = true;
  });

  // Chrome, Edge and Android browsers: the browser tells us when installation is possible
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    banner.hidden = false;
  });

  accept.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    store.set(DISMISS_KEY, "1");
    banner.hidden = true;
  });

  window.addEventListener("appinstalled", () => {
    store.set(DISMISS_KEY, "1");
    banner.hidden = true;
  });

  // iOS Safari has no install event: show manual instructions instead
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (isIos) {
    text.textContent = "در Safari دکمه‌ی اشتراک‌گذاری را بزنید و «Add to Home Screen» را انتخاب کنید.";
    accept.hidden = true;
    banner.hidden = false;
  }
})();
