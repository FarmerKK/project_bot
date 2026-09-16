// Google Form Automation Dashboard - Frontend Logic

let currentConfig = null;
let isPolling = false;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initControls();
  initScanner();
  initRules();
  initDataPreview();
  initModal();
  
  // Initial loads
  loadStatus();
  loadDataPreview();
  loadRulesConfig();

  // Start continuous polling for bot status
  setInterval(loadStatus, 600);
});

// Tab Navigation
function initTabs() {
  const navItems = document.querySelectorAll(".nav-item[data-tab]");
  const panes = document.querySelectorAll(".tab-pane");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetId = item.getAttribute("data-tab");
      navItems.forEach(n => n.classList.remove("active"));
      item.classList.add("active");

      panes.forEach(p => {
        p.style.display = p.id === targetId ? "block" : "none";
      });

      if (targetId === "tab-rules") loadRulesConfig();
      if (targetId === "tab-data") loadDataPreview();
    });
  });
}

// Controller Controls
function initControls() {
  const delaySlider = document.getElementById("control-delay");
  const delayVal = document.getElementById("delay-val");
  delaySlider.addEventListener("input", (e) => {
    delayVal.innerText = `${parseFloat(e.target.value).toFixed(1)}s`;
  });

  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const modeSelect = document.getElementById("control-mode");

  btnStart.addEventListener("click", async () => {
    btnStart.disabled = true;
    try {
      const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: modeSelect.value,
          delay: parseFloat(delaySlider.value)
        })
      });
      const data = await res.json();
      if (data.status !== "success") {
        alert(data.message || "เกิดข้อผิดพลาด");
        btnStart.disabled = false;
      }
    } catch (err) {
      alert("ไม่สามารถติดต่อเซิร์ฟเวอร์ได้: " + err);
      btnStart.disabled = false;
    }
  });

  btnStop.addEventListener("click", async () => {
    try {
      await fetch("/api/stop", { method: "POST" });
    } catch (err) {
      console.error(err);
    }
  });

  document.getElementById("btn-clear-logs").addEventListener("click", () => {
    document.getElementById("terminal-logs").innerHTML = "";
  });

  document.getElementById("btn-quick-generate").addEventListener("click", () => {
    document.querySelector('.nav-item[data-tab="tab-data"]').click();
  });
}

// Poll Status
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const status = await res.json();

    document.getElementById("stat-total").innerText = status.total || 0;
    document.getElementById("stat-success").innerText = status.success_count || 0;
    document.getElementById("stat-failed").innerText = status.fail_count || 0;
    document.getElementById("stat-percent").innerText = `${status.percent || 0}%`;

    const progBar = document.getElementById("progress-bar");
    progBar.style.width = `${status.percent || 0}%`;
    document.getElementById("progress-text").innerText = `${status.current || 0} / ${status.total || 0}`;

    const btnStart = document.getElementById("btn-start");
    const btnStop = document.getElementById("btn-stop");
    const statusText = document.getElementById("bot-status-text");

    if (status.is_running) {
      btnStart.disabled = true;
      btnStop.disabled = false;
      statusText.innerText = `กำลังส่งข้อมูล (${status.percent}%)`;
      statusText.style.color = "var(--accent-cyan)";
    } else {
      btnStart.disabled = false;
      btnStop.disabled = true;
      statusText.innerText = "พร้อมทำงาน";
      statusText.style.color = "var(--text-secondary)";
    }

    // Render terminal logs
    const terminal = document.getElementById("terminal-logs");
    if (status.logs && status.logs.length > 0) {
      terminal.innerHTML = status.logs.map(log => {
        let cls = "log-info";
        if (log.type === "success") cls = "log-success";
        if (log.type === "error") cls = "log-error";
        if (log.type === "warning") cls = "log-warning";
        return `<div class="log-entry ${cls}"><span class="log-time">[${log.time}]</span> ${escapeHtml(log.text)}</div>`;
      }).join("");
      terminal.scrollTop = terminal.scrollHeight;
    }
  } catch (err) {
    // server might be busy or restarting
  }
}

// Form Scanner
function initScanner() {
  const btnScan = document.getElementById("btn-scan");
  const inputUrl = document.getElementById("scan-url");
  const resultCard = document.getElementById("scan-result-card");

  btnScan.addEventListener("click", async () => {
    const url = inputUrl.value.trim();
    if (!url) {
      alert("กรุณาวางลิงก์ Google Form");
      return;
    }

    btnScan.innerText = "⏳ กำลังสแกน...";
    btnScan.disabled = true;

    try {
      const res = await fetch("/api/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const data = await res.json();

      if (data.status === "success") {
        document.getElementById("form-info-title").innerText = data.title || "(ไม่มีชื่อ)";
        document.getElementById("form-info-desc").innerText = data.description || "-";
        document.getElementById("form-info-pages").innerText = data.page_count || 1;

        const tbody = document.getElementById("scan-questions-tbody");
        tbody.innerHTML = data.questions.map((q, idx) => `
          <tr>
            <td>${idx + 1}</td>
            <td style="color: var(--accent-cyan); font-family: monospace;">${q.entry_id}</td>
            <td>${q.type}</td>
            <td>${q.required ? '<span style="color:var(--accent-rose);">ใช่</span>' : 'ไม่'}</td>
            <td><strong>${escapeHtml(q.title)}</strong></td>
            <td>${q.options.length ? escapeHtml(q.options.join(", ")) : '-'}</td>
          </tr>
        `).join("");

        resultCard.style.display = "block";
        alert("✔ สแกนแบบฟอร์มสำเร็จ! ระบบบันทึกการตั้งค่าแล้ว");
      } else {
        alert("เกิดข้อผิดพลาด: " + data.message);
      }
    } catch (err) {
      alert("เกิดข้อผิดพลาดในการเชื่อมต่อ: " + err);
    } finally {
      btnScan.innerText = "🔍 สแกนฟอร์ม";
      btnScan.disabled = false;
    }
  });
}

// Rules Customizer with Percentage & Weights Support
function initRules() {
  // Bulk Preset Listeners
  const presetInputs = document.querySelectorAll(".preset-weight");
  presetInputs.forEach(input => {
    input.addEventListener("input", updatePresetTotalBadge);
  });

  const btnNormalize = document.getElementById("btn-normalize-preset");
  if (btnNormalize) {
    btnNormalize.addEventListener("click", () => {
      let vals = [
        parseFloat(document.getElementById("preset-5").value) || 0,
        parseFloat(document.getElementById("preset-4").value) || 0,
        parseFloat(document.getElementById("preset-3").value) || 0,
        parseFloat(document.getElementById("preset-2").value) || 0,
        parseFloat(document.getElementById("preset-1").value) || 0,
      ];
      let sum = vals.reduce((a, b) => a + b, 0);
      if (sum <= 0) {
        document.getElementById("preset-5").value = 50;
        document.getElementById("preset-4").value = 35;
        document.getElementById("preset-3").value = 15;
        document.getElementById("preset-2").value = 0;
        document.getElementById("preset-1").value = 0;
      } else {
        let scaled = vals.map(v => Math.round((v / sum) * 100));
        let newSum = scaled.reduce((a, b) => a + b, 0);
        scaled[0] += (100 - newSum);
        document.getElementById("preset-5").value = Math.max(0, scaled[0]);
        document.getElementById("preset-4").value = Math.max(0, scaled[1]);
        document.getElementById("preset-3").value = Math.max(0, scaled[2]);
        document.getElementById("preset-2").value = Math.max(0, scaled[3]);
        document.getElementById("preset-1").value = Math.max(0, scaled[4]);
      }
      updatePresetTotalBadge();
    });
  }

  const btnApply = document.getElementById("btn-apply-preset");
  if (btnApply) {
    btnApply.addEventListener("click", () => {
      const p5 = parseFloat(document.getElementById("preset-5").value) || 0;
      const p4 = parseFloat(document.getElementById("preset-4").value) || 0;
      const p3 = parseFloat(document.getElementById("preset-3").value) || 0;
      const p2 = parseFloat(document.getElementById("preset-2").value) || 0;
      const p1 = parseFloat(document.getElementById("preset-1").value) || 0;

      const presetMap = {
        "5": p5, "5 มากที่สุด": p5,
        "4": p4, "4 มาก": p4,
        "3": p3, "3 ปานกลาง": p3,
        "2": p2, "2 น้อย": p2,
        "1": p1, "1 น้อยที่สุด": p1
      };

      let appliedCount = 0;
      const ruleCards = document.querySelectorAll(".rule-card");
      ruleCards.forEach(card => {
        const qType = card.getAttribute("data-type") || "";
        const optionCards = card.querySelectorAll(".option-card");
        
        let hasRating = false;
        optionCards.forEach(oc => {
          const val = oc.getAttribute("data-value").trim();
          if (presetMap.hasOwnProperty(val) || val.startsWith("5") || val.startsWith("4") || val.startsWith("3")) {
            hasRating = true;
          }
        });

        if (hasRating || qType.toLowerCase().includes("grid") || qType.toLowerCase().includes("scale")) {
          optionCards.forEach(oc => {
            const val = oc.getAttribute("data-value").trim();
            let targetWeight = 0;
            if (presetMap.hasOwnProperty(val)) {
              targetWeight = presetMap[val];
            } else if (val.startsWith("5")) targetWeight = p5;
            else if (val.startsWith("4")) targetWeight = p4;
            else if (val.startsWith("3")) targetWeight = p3;
            else if (val.startsWith("2")) targetWeight = p2;
            else if (val.startsWith("1")) targetWeight = p1;

            const checkbox = oc.querySelector('input[type="checkbox"]');
            const weightInput = oc.querySelector(".option-weight");

            if (targetWeight > 0) {
              checkbox.checked = true;
              oc.classList.remove("inactive");
              oc.classList.add("active");
              weightInput.disabled = false;
              weightInput.value = targetWeight;
            } else {
              checkbox.checked = false;
              oc.classList.remove("active");
              oc.classList.add("inactive");
              weightInput.disabled = true;
              weightInput.value = 0;
            }
          });
          updateSingleCardSum(card);
          appliedCount++;
        }
      });

      alert(`✔ นำสัดส่วนเปอร์เซ็นต์ไปใช้กับคำถามประเมินทั้งหมด ${appliedCount} ข้อเรียบร้อยแล้ว!\n(อย่าลืมคลิกปุ่ม "บันทึกการตั้งค่าทั้งหมด" เพื่อบันทึก)`);
    });
  }

  // Add Conditional Rule Button Listener
  const btnAddCond = document.getElementById("btn-add-cond-rule");
  if (btnAddCond) {
    btnAddCond.addEventListener("click", () => {
      addConditionalRuleCard();
    });
  }

  // Save Settings
  document.getElementById("btn-save-rules").addEventListener("click", async () => {
    if (!currentConfig) return;

    // 1. Collect Field Weights & Options
    const ruleCards = document.querySelectorAll(".rule-card");
    ruleCards.forEach(card => {
      const entryId = card.getAttribute("data-entry-id");
      if (currentConfig.fields && currentConfig.fields[entryId]) {
        const optionCards = Array.from(card.querySelectorAll(".option-card"));
        const allOptions = [];
        const allWeights = [];

        optionCards.forEach(oc => {
          const optVal = oc.getAttribute("data-value");
          const isChecked = oc.querySelector('input[type="checkbox"]')?.checked;
          const weightVal = parseFloat(oc.querySelector(".option-weight")?.value) || 0;
          allOptions.push(optVal);
          allWeights.push(isChecked ? Math.max(0, weightVal) : 0);
        });

        currentConfig.fields[entryId].options = allOptions;
        currentConfig.fields[entryId].weights = allWeights;
      }
    });

    // 2. Collect Conditional Rules
    const condCards = document.querySelectorAll(".cond-rule-card");
    const savedRules = [];
    condCards.forEach(card => {
      const enabled = card.querySelector(".cond-rule-enable")?.checked ?? true;
      const ifField = card.querySelector(".cond-if-field")?.value;
      const thenField = card.querySelector(".cond-then-field")?.value;
      const thenSet = card.querySelector(".cond-then-set")?.value;
      const activePills = Array.from(card.querySelectorAll(".cond-pill.active")).map(p => p.getAttribute("data-val"));

      if (ifField && thenField && activePills.length > 0 && thenSet) {
        savedRules.push({
          if_field: ifField,
          if_in: activePills,
          then_field: thenField,
          then_set: thenSet,
          enabled: enabled,
          description: `${ifField} [${activePills.join(', ')}] ➔ ล็อก ${thenField}: ${thenSet}`
        });
      }
    });
    currentConfig.conditional_rules = savedRules;

    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentConfig)
      });
      const data = await res.json();
      alert("✔ " + (data.message || "บันทึกเรียบร้อยแล้ว"));
    } catch (err) {
      alert("บันทึกล้มเหลว: " + err);
    }
  });
}

async function loadRulesConfig() {
  try {
    const res = await fetch("/api/config");
    currentConfig = await res.json();
    const container = document.getElementById("rules-container");

    const fields = currentConfig.fields || {};
    if (Object.keys(fields).length === 0) {
      container.innerHTML = `<div class="glass-card" style="text-align: center; color: var(--text-secondary);">ยังไม่มีข้อมูลฟอร์ม กรุณาสแกนฟอร์มก่อนในแท็บ "สแกนแบบฟอร์ม"</div>`;
      return;
    }

    // Render Conditional Rules
    renderConditionalRules(currentConfig.conditional_rules || [], fields);

    container.innerHTML = Object.entries(fields).map(([entryId, fData]) => {
      const options = fData.options || [];
      const weights = fData.weights || [];

      return `
        <div class="rule-card" data-entry-id="${entryId}" data-type="${escapeHtml(fData.type || '')}">
          <div class="rule-header">
            <div>
              <h4 style="margin-bottom: 4px;">${escapeHtml(fData.title || entryId)}</h4>
              <span style="font-size: 0.75rem; color: var(--accent-cyan); font-family: monospace;">${entryId} (${fData.type || 'Field'})</span>
            </div>
            ${options.length ? `
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="sum-badge valid" id="sum-${entryId}">รวม: 100%</span>
                <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;" onclick="normalizeCardWeights('${entryId}')">⚡ 100%</button>
              </div>
            ` : ''}
          </div>
          ${options.length ? `
            <div class="rule-options-grid">
              ${options.map((opt, idx) => {
                let weight = 100;
                if (weights.length === options.length) {
                  weight = weights[idx];
                } else {
                  weight = Math.round(100 / options.length);
                }
                const isActive = weight > 0;
                return `
                  <div class="option-card ${isActive ? 'active' : 'inactive'}" data-value="${escapeHtml(opt)}">
                    <label class="option-label">
                      <input type="checkbox" ${isActive ? 'checked' : ''} onchange="toggleOptionCard(this)">
                      <span>${escapeHtml(opt)}</span>
                    </label>
                    <div class="weight-input-wrapper option-card-weight">
                      <input type="number" class="input-text option-weight" min="0" max="100" value="${weight}" ${isActive ? '' : 'disabled'} oninput="updateCardSum(this)">
                      <span class="weight-unit">%</span>
                    </div>
                  </div>
                `;
              }).join("")}
            </div>
          ` : `<div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 6px;">ช่องข้อความทั่วไป (กรอกตามค่าเริ่มต้น)</div>`}
        </div>
      `;
    }).join("");

    // Calculate sum for each card
    Object.keys(fields).forEach(entryId => {
      const card = document.querySelector(`.rule-card[data-entry-id="${entryId}"]`);
      if (card) updateSingleCardSum(card);
    });

    updatePresetTotalBadge();
  } catch (err) {
    console.error(err);
  }
}

function toggleOptionCard(checkbox) {
  const card = checkbox.closest(".option-card");
  const weightInput = card.querySelector(".option-weight");
  if (checkbox.checked) {
    card.classList.remove("inactive");
    card.classList.add("active");
    weightInput.disabled = false;
    if (parseFloat(weightInput.value) <= 0) {
      weightInput.value = 10;
    }
  } else {
    card.classList.remove("active");
    card.classList.add("inactive");
    weightInput.disabled = true;
    weightInput.value = 0;
  }
  updateCardSum(weightInput);
}

function updateCardSum(inputElem) {
  const ruleCard = inputElem.closest(".rule-card");
  if (ruleCard) updateSingleCardSum(ruleCard);
}

function updateSingleCardSum(ruleCard) {
  const badge = ruleCard.querySelector(".sum-badge");
  if (!badge) return;

  const activeOptionCards = ruleCard.querySelectorAll(".option-card.active");
  let sum = 0;
  activeOptionCards.forEach(oc => {
    sum += parseFloat(oc.querySelector(".option-weight")?.value) || 0;
  });

  badge.innerText = `รวม: ${Math.round(sum)}%`;
  if (Math.round(sum) === 100) {
    badge.className = "sum-badge valid";
  } else {
    badge.className = "sum-badge invalid";
  }
}

function normalizeCardWeights(entryId) {
  const ruleCard = document.querySelector(`.rule-card[data-entry-id="${entryId}"]`);
  if (!ruleCard) return;

  const activeOptionCards = Array.from(ruleCard.querySelectorAll(".option-card.active"));
  if (activeOptionCards.length === 0) return;

  let vals = activeOptionCards.map(oc => parseFloat(oc.querySelector(".option-weight")?.value) || 0);
  let sum = vals.reduce((a, b) => a + b, 0);

  if (sum <= 0) {
    let eq = Math.round(100 / activeOptionCards.length);
    activeOptionCards.forEach((oc, idx) => {
      oc.querySelector(".option-weight").value = (idx === 0) ? (100 - eq * (activeOptionCards.length - 1)) : eq;
    });
  } else {
    let scaled = vals.map(v => Math.round((v / sum) * 100));
    let newSum = scaled.reduce((a, b) => a + b, 0);
    scaled[0] += (100 - newSum);
    activeOptionCards.forEach((oc, idx) => {
      oc.querySelector(".option-weight").value = Math.max(0, scaled[idx]);
    });
  }
  updateSingleCardSum(ruleCard);
}

function updatePresetTotalBadge() {
  const p5 = parseFloat(document.getElementById("preset-5")?.value) || 0;
  const p4 = parseFloat(document.getElementById("preset-4")?.value) || 0;
  const p3 = parseFloat(document.getElementById("preset-3")?.value) || 0;
  const p2 = parseFloat(document.getElementById("preset-2")?.value) || 0;
  const p1 = parseFloat(document.getElementById("preset-1")?.value) || 0;
  const total = Math.round(p5 + p4 + p3 + p2 + p1);

  const badge = document.getElementById("preset-total-badge");
  if (!badge) return;
  badge.innerText = `รวม: ${total}%`;
  if (total === 100) {
    badge.style.background = "rgba(16, 185, 129, 0.2)";
    badge.style.color = "var(--accent-emerald)";
  } else {
    badge.style.background = "rgba(245, 158, 11, 0.2)";
    badge.style.color = "var(--accent-amber)";
  }
}

// Conditional Rules UI Helpers
function renderConditionalRules(rules, fields) {
  const container = document.getElementById("conditional-rules-container");
  if (!container) return;

  // If no rules exist or list is empty, supply the default age -> student rule if fields exist
  if (!rules || rules.length === 0) {
    const ageFieldKey = Object.keys(fields).find(k => (fields[k].title || '').includes('อายุ')) || 'ช่วงอายุ';
    const occFieldKey = Object.keys(fields).find(k => (fields[k].title || '').includes('อาชีพ')) || 'อาชีพ';
    rules = [
      {
        if_field: fields[ageFieldKey]?.title || ageFieldKey,
        if_in: ["ต่ำกว่า 15 ปี", "15–18 ปี", "19–22 ปี"],
        then_field: fields[occFieldKey]?.title || occFieldKey,
        then_set: "นักเรียน/นักศึกษา",
        enabled: true,
        description: "ช่วงอายุ ต่ำกว่า 15 ปี, 15–18 ปี, 19–22 ปี ➔ ล็อกอาชีพ: นักเรียน/นักศึกษา"
      }
    ];
  }

  container.innerHTML = rules.map((r, idx) => getConditionalRuleCardHTML(r, idx, fields)).join("");
}

function getConditionalRuleCardHTML(rule, idx, fields) {
  const choiceFields = Object.entries(fields).filter(([k, v]) => (v.options || []).length > 0);
  if (choiceFields.length === 0) return '';
  
  // Find current if_field entry
  const ifEntry = choiceFields.find(([k, v]) => (v.title || '').trim() === (rule.if_field || '').trim() || k === rule.if_field) || choiceFields[0];
  const ifOptions = ifEntry ? (ifEntry[1].options || []) : [];
  
  // Find current then_field entry
  const thenEntry = choiceFields.find(([k, v]) => (v.title || '').trim() === (rule.then_field || '').trim() || k === rule.then_field) || (choiceFields[1] || choiceFields[0]);
  const thenOptions = thenEntry ? (thenEntry[1].options || []) : [];

  const ruleIfIn = rule.if_in || [];
  const normRuleIfIn = ruleIfIn.map(s => String(s).replace(/–|—/g, '-').trim());

  return `
    <div class="cond-rule-card ${rule.enabled === false ? 'disabled' : ''}" data-rule-idx="${idx}">
      <div class="cond-rule-header">
        <div class="cond-rule-title-area">
          <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <input type="checkbox" class="cond-rule-enable" ${rule.enabled !== false ? 'checked' : ''} onchange="toggleCondRuleActive(this)">
            <span class="cond-rule-badge">กฎที่ ${idx + 1}</span>
            <span class="cond-rule-desc">${escapeHtml(rule.description || 'กฎเงื่อนไข')}</span>
          </label>
        </div>
        <div class="cond-rule-actions">
          <button type="button" class="btn-delete-rule" onclick="deleteCondRule(this)" title="ลบกฎนี้">🗑️</button>
        </div>
      </div>

      <div class="cond-rule-grid">
        <div class="cond-block if-block">
          <div class="cond-block-title">
            <span>📌 ถ้าคำตอบ (IF)</span>
          </div>
          <select class="input-text cond-if-field" onchange="onIfFieldChange(this)">
            ${choiceFields.map(([k, v]) => {
              const selected = ((v.title || '').trim() === (rule.if_field || '').trim() || k === rule.if_field);
              return `<option value="${escapeHtml(v.title || k)}" ${selected ? 'selected' : ''}>${escapeHtml(v.title || k)}</option>`;
            }).join("")}
          </select>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 8px;">ตรงกับค่าใดค่าหนึ่งในนี้ (คลิกเพื่อเลือก/ยกเลิก):</div>
          <div class="cond-pills-container">
            ${ifOptions.map(opt => {
              const normOpt = String(opt).replace(/–|—/g, '-').trim();
              const isSelected = ruleIfIn.includes(opt) || normRuleIfIn.includes(normOpt);
              return `<span class="cond-pill ${isSelected ? 'active' : ''}" data-val="${escapeHtml(opt)}" onclick="toggleCondPill(this)">${escapeHtml(opt)}</span>`;
            }).join("")}
          </div>
        </div>

        <div class="cond-block then-block">
          <div class="cond-block-title">
            <span>🎯 ให้ล็อกผลลัพธ์ (THEN LOCK TO)</span>
          </div>
          <div style="margin-bottom: 8px;">
            <label style="font-size: 0.75rem; color: var(--text-muted);">คำถามปลายทาง:</label>
            <select class="input-text cond-then-field" onchange="onThenFieldChange(this)">
              ${choiceFields.map(([k, v]) => {
                const selected = ((v.title || '').trim() === (rule.then_field || '').trim() || k === rule.then_field);
                return `<option value="${escapeHtml(v.title || k)}" ${selected ? 'selected' : ''}>${escapeHtml(v.title || k)}</option>`;
              }).join("")}
            </select>
          </div>
          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted);">ล็อกคำตอบเป็นค่า:</label>
            <select class="input-text cond-then-set">
              ${thenOptions.map(opt => {
                const selected = (opt === rule.then_set);
                return `<option value="${escapeHtml(opt)}" ${selected ? 'selected' : ''}>${escapeHtml(opt)}</option>`;
              }).join("")}
            </select>
          </div>
        </div>
      </div>
    </div>
  `;
}

function toggleCondRuleActive(checkbox) {
  const card = checkbox.closest(".cond-rule-card");
  if (card) {
    card.classList.toggle("disabled", !checkbox.checked);
  }
}

function toggleCondPill(pill) {
  pill.classList.toggle("active");
  updateRuleCardDesc(pill.closest(".cond-rule-card"));
}

function updateRuleCardDesc(card) {
  if (!card) return;
  const ifField = card.querySelector(".cond-if-field")?.value || "";
  const thenField = card.querySelector(".cond-then-field")?.value || "";
  const thenSet = card.querySelector(".cond-then-set")?.value || "";
  const activePills = Array.from(card.querySelectorAll(".cond-pill.active")).map(p => p.getAttribute("data-val"));
  const descElem = card.querySelector(".cond-rule-desc");
  if (descElem) {
    if (activePills.length > 0) {
      descElem.innerText = `${ifField}: [${activePills.join(', ')}] ➔ ล็อก ${thenField}: ${thenSet}`;
    } else {
      descElem.innerText = `โปรดเลือกอย่างน้อย 1 ตัวเลือกในเงื่อนไข IF`;
    }
  }
}

function deleteCondRule(btn) {
  const card = btn.closest(".cond-rule-card");
  if (card) card.remove();
}

function onIfFieldChange(select) {
  const card = select.closest(".cond-rule-card");
  if (!card || !currentConfig) return;
  const fields = currentConfig.fields || {};
  const selectedFieldTitle = select.value.trim();
  const entry = Object.entries(fields).find(([k, v]) => (v.title || k).trim() === selectedFieldTitle);
  const options = entry ? (entry[1].options || []) : [];
  
  const pillsContainer = card.querySelector(".cond-pills-container");
  if (pillsContainer) {
    pillsContainer.innerHTML = options.map((opt, idx) => 
      `<span class="cond-pill ${idx === 0 ? 'active' : ''}" data-val="${escapeHtml(opt)}" onclick="toggleCondPill(this)">${escapeHtml(opt)}</span>`
    ).join("");
  }
  updateRuleCardDesc(card);
}

function onThenFieldChange(select) {
  const card = select.closest(".cond-rule-card");
  if (!card || !currentConfig) return;
  const fields = currentConfig.fields || {};
  const selectedFieldTitle = select.value.trim();
  const entry = Object.entries(fields).find(([k, v]) => (v.title || k).trim() === selectedFieldTitle);
  const options = entry ? (entry[1].options || []) : [];
  
  const thenSetSelect = card.querySelector(".cond-then-set");
  if (thenSetSelect) {
    thenSetSelect.innerHTML = options.map(opt => 
      `<option value="${escapeHtml(opt)}">${escapeHtml(opt)}</option>`
    ).join("");
  }
  updateRuleCardDesc(card);
}

function addConditionalRuleCard() {
  const container = document.getElementById("conditional-rules-container");
  if (!container || !currentConfig) return;
  const fields = currentConfig.fields || {};
  const choiceFields = Object.entries(fields).filter(([k, v]) => (v.options || []).length > 0);
  if (choiceFields.length < 2) {
    alert("แบบฟอร์มต้องมีคำถามแบบมีตัวเลือกอย่างน้อย 2 ข้อ จึงจะสร้างกฎเงื่อนไขได้");
    return;
  }
  const idx = container.querySelectorAll(".cond-rule-card").length;
  const newRule = {
    if_field: choiceFields[0][1].title || choiceFields[0][0],
    if_in: [choiceFields[0][1].options[0] || ''],
    then_field: choiceFields[1][1].title || choiceFields[1][0],
    then_set: choiceFields[1][1].options[0] || '',
    enabled: true,
    description: "กฎเงื่อนไขใหม่"
  };
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = getConditionalRuleCardHTML(newRule, idx, fields);
  container.appendChild(tempDiv.firstElementChild);
}

// Data Preview
function initDataPreview() {
  document.getElementById("btn-generate-dataset").addEventListener("click", async () => {
    const count = parseInt(document.getElementById("gen-count").value) || 100;
    const btn = document.getElementById("btn-generate-dataset");
    btn.innerText = "⏳ กำลังสร้าง...";
    btn.disabled = true;

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count })
      });
      const data = await res.json();
      if (data.status === "success") {
        alert("✔ " + data.message);
        loadDataPreview();
      } else {
        alert("เกิดข้อผิดพลาด: " + data.message);
      }
    } catch (err) {
      alert("เกิดข้อผิดพลาด: " + err);
    } finally {
      btn.innerText = "✨ สุ่มสร้างข้อมูล";
      btn.disabled = false;
    }
  });
}

async function loadDataPreview() {
  try {
    const res = await fetch("/api/data");
    const data = await res.json();

    document.getElementById("data-total-count").innerText = `${data.total || 0} แถว`;
    const thead = document.getElementById("preview-thead");
    const tbody = document.getElementById("preview-tbody");

    if (!data.headers || data.headers.length === 0) {
      thead.innerHTML = "<tr><th>ไม่มีข้อมูล</th></tr>";
      tbody.innerHTML = `<tr><td style="color:var(--text-muted); text-align:center; padding: 2rem;">ไม่พบไฟล์ข้อมูลคำตอบ กรุณากด "สุ่มสร้างข้อมูล"</td></tr>`;
      return;
    }

    thead.innerHTML = `<tr><th>#</th>${data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join("")}</tr>`;
    tbody.innerHTML = data.rows.map((r, idx) => `
      <tr>
        <td style="color:var(--text-muted);">${idx + 1}</td>
        ${data.headers.map(h => `<td>${escapeHtml(r[h] || '')}</td>`).join("")}
      </tr>
    `).join("");
  } catch (err) {
    console.error(err);
  }
}

// Modal Timestamp Tool
function initModal() {
  const modal = document.getElementById("timestamp-modal");
  const btnOpen = document.getElementById("btn-open-timestamp-modal");
  const btnClose = document.getElementById("btn-close-modal");
  const btnClose2 = document.getElementById("btn-close-modal-2");
  const btnCopy = document.getElementById("btn-copy-script");

  btnOpen.addEventListener("click", () => modal.classList.add("active"));
  btnClose.addEventListener("click", () => modal.classList.remove("active"));
  btnClose2.addEventListener("click", () => modal.classList.remove("active"));

  btnCopy.addEventListener("click", () => {
    const code = document.getElementById("script-code").innerText;
    navigator.clipboard.writeText(code).then(() => {
      btnCopy.innerText = "✔ คัดลอกแล้ว!";
      setTimeout(() => { btnCopy.innerText = "📋 คัดลอกโค้ดสคริปต์"; }, 2000);
    });
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
