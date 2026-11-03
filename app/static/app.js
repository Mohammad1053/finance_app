// Shared helpers for money inputs: live thousands separators and clean submit.

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

// Convert Persian and Arabic-Indic digits to ASCII
const toAscii = (s) =>
  s
    .replace(/[۰-۹]/g, (d) => FA_DIGITS.indexOf(d))
    .replace(/[٠-٩]/g, (d) => AR_DIGITS.indexOf(d));

// Keep only the digits of a string, as ASCII
const digitsOnly = (s) => toAscii(s).replace(/[^0-9]/g, "");

// "1000000" -> "۱،۰۰۰،۰۰۰"
function formatMoney(digits) {
  return digits
    .replace(/\B(?=(\d{3})+(?!\d))/g, "،")
    .replace(/[0-9]/g, (d) => FA_DIGITS[d]);
}

// Reformat the field on every keystroke and keep the caret in a sensible place
document.addEventListener("input", (event) => {
  const el = event.target;
  if (!el.classList || !el.classList.contains("money-input")) return;

  const caret = el.selectionStart ?? el.value.length;
  const digitsBeforeCaret = digitsOnly(el.value.slice(0, caret)).length;

  const digits = digitsOnly(el.value).replace(/^0+(?=[0-9])/, "");
  el.value = formatMoney(digits);

  // Put the caret after the same number of digits as before
  let pos = 0;
  let seen = 0;
  while (pos < el.value.length && seen < digitsBeforeCaret) {
    if (el.value[pos] !== "،") seen++;
    pos++;
  }
  el.setSelectionRange(pos, pos);
});

// Before HTMX sends a request, turn the formatted values back into plain digits
const MONEY_FIELDS = ["amount", "target_amount", "min_amount", "max_amount"];

document.addEventListener("htmx:configRequest", (event) => {
  for (const name of MONEY_FIELDS) {
    const value = event.detail.parameters[name];
    if (typeof value === "string") {
      event.detail.parameters[name] = digitsOnly(value);
    }
  }
});


// Date inputs: show Persian digits while typing; the server accepts both forms
document.addEventListener("input", (event) => {
  const el = event.target;
  if (!el.classList || !el.classList.contains("date-input")) return;

  const caret = el.selectionStart ?? el.value.length;
  el.value = el.value.replace(/[0-9]/g, (d) => FA_DIGITS[d]);
  el.setSelectionRange(caret, caret);
});


// Download an export that respects the filter form values on the main page
function exportWithFilters(path) {
  const form = document.querySelector('form[hx-get="/ui/table"]');
  const params = new URLSearchParams();
  if (form) {
    for (const [key, value] of new FormData(form)) {
      if (value === "") continue;
      params.set(key, MONEY_FIELDS.includes(key) ? digitsOnly(String(value)) : String(value));
    }
  }
  window.location.href = `${path}?${params.toString()}`;
}


// Greet the user once per browser session
document.addEventListener("DOMContentLoaded", () => {
  const banner = document.getElementById("welcome-banner");
  if (!banner) return;
  try {
    if (sessionStorage.getItem("greeted")) return;
    sessionStorage.setItem("greeted", "1");
  } catch (error) {
    // Storage unavailable: show the greeting on every page load instead
  }
  banner.hidden = false;
  setTimeout(() => { banner.hidden = true; }, 6000);
});