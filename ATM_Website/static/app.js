const el = (id) => document.getElementById(id);

let activeInput = null;
let appState = null;

function formatMoney(value) {
  return Number(value || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function showAlert(message, ok = true) {
  const banner = el("alertBanner");
  banner.textContent = message;
  banner.className = `alert ${ok ? "ok" : "err"}`;
}

function clearAlert() {
  el("alertBanner").className = "alert hidden";
}

async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

async function apiPost(url, payload = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

function setReceipt(info) {
  if (!info) return;
  if (info.receipt_text) {
    el("receiptPreview").textContent = info.receipt_text;
  }
  if (info.receipt_path) {
    el("receiptPathNote").textContent = `Saved receipt file: ${info.receipt_path}`;
  }
  const box = el("dispensedNotesBox");
  if (info.notes) {
    box.classList.remove("empty");
    box.innerHTML = Object.entries(info.notes)
      .sort((a, b) => Number(b[0]) - Number(a[0]))
      .map(([denom, count]) => `<span class="banknote-chip">${count} &times; ${Number(denom).toLocaleString()}</span>`)
      .join("");
  }
}

function renderCustomer(state) {
  el("atmCashPill").textContent = `ATM Cash: ${formatMoney(state.atm_total_cash)}`;

  if (!state.logged_in || !state.current_account) {
    el("loginScreen").classList.remove("hidden");
    el("dashboardScreen").classList.add("hidden");
    return;
  }

  const acc = state.current_account;
  el("loginScreen").classList.add("hidden");
  el("dashboardScreen").classList.remove("hidden");

  el("welcomeTitle").textContent = `Welcome, ${acc.owner}.`;
  el("accountTypeBadge").textContent = acc.type;
  el("accountMeta").textContent = `Account No: ${acc.account_number}`;
  el("balanceValue").textContent = formatMoney(acc.balance);
  el("perTxLimit").textContent = formatMoney(acc.per_tx_limit);
  el("dailyLimitInfo").textContent = `${formatMoney(acc.daily_withdrawn)} / ${formatMoney(acc.daily_limit)}`;

  if (acc.type === "Savings") {
    el("extraRuleLabel").textContent = "Monthly Withdrawals";
    el("extraRuleValue").textContent = `${acc.monthly_withdrawals} / ${acc.monthly_withdrawal_limit}`;
    el("btnApplyInterest").disabled = false;
    el("interestDesc").textContent = `Savings accounts earn ${(acc.interest_rate * 100).toFixed(1)}% interest on positive balances.`;
  } else if (acc.type === "Current") {
    el("extraRuleLabel").textContent = "Overdraft Limit";
    el("extraRuleValue").textContent = formatMoney(acc.overdraft_limit);
    el("btnApplyInterest").disabled = true;
    el("interestDesc").textContent = "Interest is only available for Savings accounts.";
  } else {
    el("extraRuleLabel").textContent = "Minimum Balance";
    el("extraRuleValue").textContent = formatMoney(acc.min_balance);
    el("btnApplyInterest").disabled = true;
    el("interestDesc").textContent = "Interest is only available for Savings accounts.";
  }

  // Recipient dropdown
  const select = el("transferPick");
  const currentVal = select.value;
  select.innerHTML = '<option value="">-- Select recipient --</option>';
  for (const item of state.accounts_list) {
    if (item.account_number !== acc.account_number) {
      const opt = document.createElement("option");
      opt.value = item.account_number;
      opt.textContent = `${item.account_number} - ${item.owner} (${item.type})`;
      select.appendChild(opt);
    }
  }
  select.value = currentVal;

  // Mini-statement
  const tbody = el("statementBody");
  if (!acc.mini_statement || acc.mini_statement.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">No transactions recorded yet.</td></tr>';
  } else {
    tbody.innerHTML = [...acc.mini_statement]
      .reverse()
      .map(
        (tx) => `
        <tr>
          <td>${tx.timestamp}</td>
          <td>${tx.type}</td>
          <td class="num">${formatMoney(tx.amount)}</td>
          <td class="num">${formatMoney(tx.balance_after)}</td>
          <td>${tx.details || ""}</td>
        </tr>`
      )
      .join("");
  }
}

async function renderAdmin() {
  if (!appState || !appState.admin_logged_in) {
    el("adminLoginCard").classList.remove("hidden");
    el("adminDashboard").classList.add("hidden");
    return;
  }

  const data = await apiGet("/api/admin/overview");
  if (!data.ok) {
    el("adminLoginCard").classList.remove("hidden");
    el("adminDashboard").classList.add("hidden");
    return;
  }

  el("adminLoginCard").classList.add("hidden");
  el("adminDashboard").classList.remove("hidden");
  el("atmCashPill").textContent = `ATM Cash: ${formatMoney(data.atm_total_cash)}`;

  const blockedCount = data.accounts.filter((a) => a.is_blocked).length;
  el("kpiAccounts").textContent = data.accounts.length;
  el("kpiBlocked").textContent = blockedCount;
  el("kpiCash").textContent = formatMoney(data.atm_total_cash);
  el("kpiTx").textContent = data.statistics.total_transactions;

  el("adminAccountsBody").innerHTML = data.accounts
    .map(
      (acc) => `
      <tr>
        <td><strong>${acc.account_number}</strong></td>
        <td>${acc.owner}</td>
        <td>${acc.type}</td>
        <td class="num">${formatMoney(acc.balance)}</td>
        <td><span class="status-pill ${acc.is_blocked ? "blocked" : "active"}">${acc.is_blocked ? "BLOCKED" : "Active"}</span></td>
        <td>${
          acc.is_blocked
            ? `<button type="button" class="btn btn-small unblock-btn" data-acc="${acc.account_number}">Unblock</button>`
            : "-"
        }</td>
      </tr>`
    )
    .join("");

  document.querySelectorAll(".unblock-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const res = await apiPost("/api/admin/unblock", { account_number: btn.dataset.acc });
      showAlert(res.message, res.ok);
      await refreshAll();
    });
  });

  el("notesInventory").innerHTML = Object.entries(data.notes)
    .sort((a, b) => Number(b[0]) - Number(a[0]))
    .map(
      ([denom, count]) => `
      <div class="note-badge">
        <span>${Number(denom).toLocaleString()} note</span>
        <strong>${count} left</strong>
      </div>`
    )
    .join("");

  const st = data.statistics;
  const typesList = Object.entries(st.counts_by_type)
    .map(([k, v]) => `${k}: <strong>${v}</strong>`)
    .join(" &bull; ");
  const maxDep = st.largest_deposit
    ? `${formatMoney(st.largest_deposit[0])} (Acc ${st.largest_deposit[1]})`
    : "None";
  const maxWdr = st.largest_withdrawal
    ? `${formatMoney(st.largest_withdrawal[0])} (Acc ${st.largest_withdrawal[1]})`
    : "None";
  const busy = st.busiest_hour
    ? `${String(st.busiest_hour[0]).padStart(2, "0")}:00 (${st.busiest_hour[1]} tx)`
    : "N/A";

  el("statsContent").innerHTML = `
    <div><strong>By Type:</strong> ${typesList || "None yet"}</div>
    <div><strong>Largest Deposit:</strong> ${maxDep}</div>
    <div><strong>Largest Withdrawal:</strong> ${maxWdr}</div>
    <div><strong>Busiest Hour:</strong> ${busy}</div>
  `;
}

async function refreshAll() {
  appState = await apiGet("/api/state");
  renderCustomer(appState);
  if (appState.admin_logged_in) {
    await renderAdmin();
  }
}

function setupEvents() {
  // Track active input for ATM keypad
  ["loginAccount", "loginPin"].forEach((id) => {
    const input = el(id);
    input.addEventListener("focus", () => {
      activeInput = input;
    });
  });
  activeInput = el("loginAccount");

  el("atmKeypad").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn || !activeInput) return;
    const key = btn.dataset.key;
    if (key === "CLR") {
      activeInput.value = "";
    } else if (key === "DEL") {
      activeInput.value = activeInput.value.slice(0, -1);
    } else {
      if (activeInput.id === "loginPin" && activeInput.value.length >= 4) return;
      activeInput.value += key;
    }
    activeInput.focus();
  });

  // Demo quick-fill buttons
  document.querySelectorAll(".demo-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      el("loginAccount").value = chip.dataset.acc;
      el("loginPin").value = chip.dataset.pin;
      clearAlert();
    });
  });

  // Mode toggle
  el("btnCustomerMode").addEventListener("click", () => {
    el("btnCustomerMode").classList.add("active");
    el("btnAdminMode").classList.remove("active");
    el("customerView").classList.remove("hidden");
    el("adminView").classList.add("hidden");
    clearAlert();
  });

  el("btnAdminMode").addEventListener("click", async () => {
    el("btnAdminMode").classList.add("active");
    el("btnCustomerMode").classList.remove("active");
    el("customerView").classList.add("hidden");
    el("adminView").classList.remove("hidden");
    clearAlert();
    await renderAdmin();
  });

  // Tabs
  document.querySelectorAll(".tab").forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tabBtn.classList.add("active");
      el(`tab-${tabBtn.dataset.tab}`).classList.add("active");
    });
  });

  // Quick withdraw buttons
  document.querySelectorAll(".amt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      el("withdrawAmount").value = btn.dataset.amt;
    });
  });

  el("transferPick").addEventListener("change", (e) => {
    if (e.target.value) {
      el("transferTarget").value = e.target.value;
    }
  });

  // Login
  el("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/login", {
      account_number: el("loginAccount").value,
      pin: el("loginPin").value,
    });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("loginPin").value = "";
    }
    await refreshAll();
  });

  // Logout
  el("btnLogout").addEventListener("click", async () => {
    const res = await apiPost("/api/logout");
    showAlert(res.message, res.ok);
    await refreshAll();
  });

  // Withdraw
  el("withdrawForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/withdraw", { amount: el("withdrawAmount").value });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("withdrawAmount").value = "";
      setReceipt(res.info);
    }
    await refreshAll();
  });

  // Deposit
  el("depositForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/deposit", { amount: el("depositAmount").value });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("depositAmount").value = "";
      setReceipt(res.info);
    }
    await refreshAll();
  });

  // Transfer
  el("transferForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/transfer", {
      to_account_number: el("transferTarget").value,
      amount: el("transferAmount").value,
    });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("transferAmount").value = "";
      setReceipt(res.info);
    }
    await refreshAll();
  });

  // Change PIN
  el("changePinForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/change-pin", {
      old_pin: el("oldPin").value,
      new_pin: el("newPin").value,
    });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("oldPin").value = "";
      el("newPin").value = "";
    }
  });

  // Apply Interest
  el("btnApplyInterest").addEventListener("click", async () => {
    const res = await apiPost("/api/apply-interest");
    showAlert(res.message, res.ok);
    if (res.ok) {
      setReceipt(res.info);
    }
    await refreshAll();
  });

  // Admin Login / Logout / Create / Restock
  el("adminLoginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/admin/login", { pin: el("adminPinInput").value });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("adminPinInput").value = "";
    }
    await refreshAll();
    await renderAdmin();
  });

  el("btnAdminLogout").addEventListener("click", async () => {
    const res = await apiPost("/api/admin/logout");
    showAlert(res.message, res.ok);
    await refreshAll();
    await renderAdmin();
  });

  el("createAccountForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/admin/create-account", {
      account_number: el("newAccNum").value,
      owner: el("newAccOwner").value,
      pin: el("newAccPin").value,
      account_type: el("newAccType").value,
      initial_balance: el("newAccBal").value,
    });
    showAlert(res.message, res.ok);
    if (res.ok) {
      e.target.reset();
    }
    await refreshAll();
  });

  el("restockForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await apiPost("/api/admin/restock", {
      denomination: el("restockDenom").value,
      count: el("restockCount").value,
    });
    showAlert(res.message, res.ok);
    if (res.ok) {
      el("restockCount").value = "";
    }
    await refreshAll();
  });

  el("btnPrintSlip").addEventListener("click", () => window.print());
}

document.addEventListener("DOMContentLoaded", async () => {
  setupEvents();
  await refreshAll();
});
