(function () {
  const form = document.getElementById("order-form");
  if (!form) return;

  const priceIndividual = parseInt(form.dataset.priceIndividual || "400", 10);
  const priceSixPack = parseInt(form.dataset.priceSixPack || "2000", 10);
  const deliveryFee = parseInt(form.dataset.deliveryFee || "0", 10);
  const deliveryMin = parseInt(form.dataset.deliveryMin || "2000", 10);

  const fulfillmentInputs = form.querySelectorAll('input[name="fulfillment"]');
  const deliveryFields = document.getElementById("delivery-fields");
  const subtotalEl = document.getElementById("subtotal-display");
  const deliveryEl = document.getElementById("delivery-display");
  const totalEl = document.getElementById("total-display");
  const packSumEl = document.getElementById("pack-sum");
  const packHintEl = document.getElementById("pack-hint");
  const singleSumEl = document.getElementById("single-sum");

  // ── Totals ──────────────────────────────────────────────

  function money(cents) {
    return "$" + (cents / 100).toFixed(2);
  }

  function sumInputs(prefix) {
    let total = 0;
    form.querySelectorAll('input[name^="' + prefix + '_"]').forEach(function (input) {
      total += Math.max(0, parseInt(input.value || "0", 10) || 0);
    });
    return total;
  }

  function fulfillment() {
    const checked = form.querySelector('input[name="fulfillment"]:checked');
    return checked ? checked.value : "pickup";
  }

  function recalc() {
    const singleTotal = sumInputs("single");
    const packTotal = sumInputs("pack");
    const packs = Math.floor(packTotal / 6);
    const packRemainder = packTotal % 6;

    let subtotal = singleTotal * priceIndividual + packs * priceSixPack;
    const fee = fulfillment() === "delivery" ? deliveryFee : 0;

    if (subtotalEl) subtotalEl.textContent = money(subtotal);
    if (deliveryEl) deliveryEl.textContent = money(fee);
    if (totalEl) totalEl.textContent = money(subtotal + fee);

    const minEl = document.getElementById("delivery-min-feedback");
    if (minEl) {
      if (fulfillment() === "delivery" && subtotal < deliveryMin) {
        minEl.textContent =
          "Delivery needs a cookie total of at least " +
          money(deliveryMin) +
          ". Add more cookies or choose pickup.";
        minEl.className = "pack-hint warn";
      } else {
        minEl.textContent = "";
        minEl.className = "pack-hint";
      }
    }

    if (singleSumEl) {
      singleSumEl.textContent =
        singleTotal === 0
          ? "No individual cookies selected"
          : singleTotal + " cookie(s) × " + money(priceIndividual);
    }

    if (packSumEl) {
      packSumEl.textContent = packTotal + " / 6 selected";
    }
    if (packHintEl) {
      if (packTotal === 0) {
        packHintEl.textContent = "Add 6 cookies across flavors for one half-dozen box.";
        packHintEl.className = "pack-hint";
      } else if (packRemainder === 0) {
        packHintEl.textContent =
          packs + " complete 6-pack(s) · " + money(packs * priceSixPack);
        packHintEl.className = "pack-hint ok";
      } else {
        packHintEl.textContent =
          "Need " + (6 - packRemainder) + " more cookie(s) to complete a 6-pack.";
        packHintEl.className = "pack-hint warn";
      }
    }
  }

  let allowedZips = [];
  try {
    allowedZips = JSON.parse(form.dataset.allowedZips || "[]");
  } catch (e) {
    allowedZips = [];
  }

  const zipInput = document.getElementById("delivery_zip");
  const zipFeedback = document.getElementById("zip-feedback");

  function digitsZip(value) {
    return String(value || "").replace(/\D/g, "").slice(0, 5);
  }

  function checkZip() {
    if (!zipFeedback) return;
    if (fulfillment() !== "delivery") {
      zipFeedback.textContent = "";
      zipFeedback.className = "pack-hint";
      return;
    }
    const zip = digitsZip(zipInput && zipInput.value);
    if (zip.length < 5) {
      zipFeedback.textContent = "Enter a 5-digit ZIP in our delivery area.";
      zipFeedback.className = "pack-hint";
      return;
    }
    if (allowedZips.indexOf(zip) !== -1) {
      zipFeedback.textContent = zip + " is in our delivery area.";
      zipFeedback.className = "pack-hint ok";
    } else {
      zipFeedback.textContent =
        zip + " is outside our delivery area. Please choose pickup, or see the map.";
      zipFeedback.className = "pack-hint warn";
    }
  }

  function syncDelivery() {
    if (!deliveryFields) return;
    if (fulfillment() === "delivery") {
      deliveryFields.classList.add("show");
      if (zipInput) zipInput.required = true;
      window.setTimeout(function () {
        document.querySelectorAll(".delivery-map").forEach(function (el) {
          if (el._leaflet_id && typeof L !== "undefined") {
            const map = el._leaflet_map;
            if (map) map.invalidateSize();
          }
        });
      }, 200);
    } else {
      deliveryFields.classList.remove("show");
      if (zipInput) zipInput.required = false;
    }
    checkZip();
    recalc();
  }

  if (zipInput) {
    zipInput.addEventListener("input", checkZip);
    zipInput.addEventListener("change", checkZip);
  }

  fulfillmentInputs.forEach(function (el) {
    el.addEventListener("change", syncDelivery);
  });

  form.querySelectorAll('input[type="number"]').forEach(function (el) {
    el.addEventListener("input", recalc);
    el.addEventListener("change", recalc);
  });

  form.querySelectorAll("[data-step]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const target = form.querySelector("#" + btn.dataset.step);
      if (!target) return;
      const delta = parseInt(btn.dataset.delta || "0", 10);
      const next = Math.max(0, Math.min(100, (parseInt(target.value || "0", 10) || 0) + delta));
      target.value = String(next);
      recalc();
    });
  });

  // ── Pickup calendar ─────────────────────────────────────

  let slots = [];
  try {
    slots = JSON.parse(form.dataset.pickupSlots || "[]");
  } catch (e) {
    slots = [];
  }

  const slotByDate = {};
  slots.forEach(function (s) {
    slotByDate[s.date] = s;
  });

  const pickupInput = document.getElementById("pickup_date");
  const selectedLabel = document.getElementById("pickup-selected-label");
  const calGrid = document.getElementById("cal-grid");
  const calMonthLabel = document.getElementById("cal-month-label");
  const calPrev = document.getElementById("cal-prev");
  const calNext = document.getElementById("cal-next");

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];

  // View range from earliest to latest slot
  let minMonth = null;
  let maxMonth = null;
  if (slots.length) {
    const first = slots[0].date.split("-");
    const last = slots[slots.length - 1].date.split("-");
    minMonth = { y: parseInt(first[0], 10), m: parseInt(first[1], 10) - 1 };
    maxMonth = { y: parseInt(last[0], 10), m: parseInt(last[1], 10) - 1 };
  }

  const today = new Date();
  let viewY = today.getFullYear();
  let viewM = today.getMonth();

  // If current month has no slots, jump to first slot month
  if (minMonth) {
    const curKey = viewY * 12 + viewM;
    const minKey = minMonth.y * 12 + minMonth.m;
    const maxKey = maxMonth.y * 12 + maxMonth.m;
    if (curKey < minKey) {
      viewY = minMonth.y;
      viewM = minMonth.m;
    } else if (curKey > maxKey) {
      viewY = maxMonth.y;
      viewM = maxMonth.m;
    }
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function isoFromYMD(y, m, d) {
    return y + "-" + pad(m + 1) + "-" + pad(d);
  }

  function setSelected(iso) {
    if (pickupInput) pickupInput.value = iso || "";
    if (selectedLabel) {
      if (!iso) {
        selectedLabel.textContent = "No pickup date selected";
        selectedLabel.className = "pack-status";
      } else {
        const slot = slotByDate[iso];
        selectedLabel.textContent = slot
          ? "Selected: " + slot.label
          : "Selected: " + iso;
        selectedLabel.className = "pack-status ok-box";
      }
    }
    // Refresh selected styles
    if (calGrid) {
      calGrid.querySelectorAll(".cal-day").forEach(function (el) {
        el.classList.toggle("is-selected", el.dataset.date === iso);
      });
    }
  }

  function renderCalendar() {
    if (!calGrid || !calMonthLabel) return;

    calMonthLabel.textContent = monthNames[viewM] + " " + viewY;

    if (calPrev) {
      const atMin =
        minMonth && viewY === minMonth.y && viewM === minMonth.m;
      calPrev.disabled = !!atMin;
    }
    if (calNext) {
      const atMax =
        maxMonth && viewY === maxMonth.y && viewM === maxMonth.m;
      calNext.disabled = !!atMax;
    }

    calGrid.innerHTML = "";
    const firstDow = new Date(viewY, viewM, 1).getDay(); // 0=Sun
    const daysInMonth = new Date(viewY, viewM + 1, 0).getDate();
    const selected = pickupInput ? pickupInput.value : "";

    // Leading empty cells
    for (let i = 0; i < firstDow; i++) {
      const empty = document.createElement("div");
      empty.className = "cal-day empty";
      calGrid.appendChild(empty);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const iso = isoFromYMD(viewY, viewM, day);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cal-day";
      cell.textContent = String(day);
      cell.dataset.date = iso;

      const slot = slotByDate[iso];
      const dow = new Date(viewY, viewM, day).getDay(); // 0 Sun … 5 Fri 6 Sat
      const isWeekendPickup = dow === 5 || dow === 6;

      if (!isWeekendPickup) {
        cell.classList.add("muted");
        cell.disabled = true;
        cell.title = "Pickup is Friday or Saturday only";
      } else if (!slot) {
        // Fri/Sat outside our booking horizon
        cell.classList.add("locked");
        cell.disabled = true;
        cell.title = "Outside booking window";
      } else if (!slot.available) {
        cell.classList.add("locked");
        cell.disabled = true;
        cell.title = slot.reason || "Unavailable (past weekly cutoff)";
      } else {
        cell.classList.add("available");
        cell.title = "Pickup " + slot.label;
        cell.addEventListener("click", function () {
          setSelected(iso);
        });
      }

      if (selected && iso === selected) {
        cell.classList.add("is-selected");
      }

      calGrid.appendChild(cell);
    }
  }

  if (calPrev) {
    calPrev.addEventListener("click", function () {
      viewM -= 1;
      if (viewM < 0) {
        viewM = 11;
        viewY -= 1;
      }
      renderCalendar();
    });
  }
  if (calNext) {
    calNext.addEventListener("click", function () {
      viewM += 1;
      if (viewM > 11) {
        viewM = 0;
        viewY += 1;
      }
      renderCalendar();
    });
  }

  // Restore selection from form / data attribute
  const preselected =
    (pickupInput && pickupInput.value) || form.dataset.selectedPickup || "";
  if (preselected && slotByDate[preselected] && slotByDate[preselected].available) {
    // Jump view to that month
    const parts = preselected.split("-");
    viewY = parseInt(parts[0], 10);
    viewM = parseInt(parts[1], 10) - 1;
    setSelected(preselected);
  } else if (preselected && (!slotByDate[preselected] || !slotByDate[preselected].available)) {
    setSelected("");
  }

  renderCalendar();
  if (preselected && slotByDate[preselected] && slotByDate[preselected].available) {
    setSelected(preselected);
  }

  // Block submit without a valid date
  form.addEventListener("submit", function (e) {
    const val = pickupInput ? pickupInput.value : "";
    if (!val || !slotByDate[val] || !slotByDate[val].available) {
      e.preventDefault();
      if (selectedLabel) {
        selectedLabel.textContent =
          "Please select an available Friday or Saturday on the calendar.";
        selectedLabel.className = "pack-status warn-box";
      }
      const cal = document.getElementById("pickup-calendar");
      if (cal) cal.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  syncDelivery();
  recalc();
})();
