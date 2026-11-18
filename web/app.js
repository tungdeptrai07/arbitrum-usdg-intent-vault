const srcInput = document.getElementById("srcInput");
const dstInput = document.getElementById("dstInput");
const amountInput = document.getElementById("amountInput");
const feeInput = document.getElementById("feeInput");
const createBtn = document.getElementById("createBtn");
const msgBox = document.getElementById("msgBox");
const reservesBox = document.getElementById("reservesBox");
const intentsList = document.getElementById("intentsList");
const volPill = document.getElementById("volPill");

const CHAIN_NAMES = {
  42161: "Arbitrum One",
  421614: "Arbitrum Sepolia",
  4663: "Robinhood Chain",
};

let staticState = {
  contracts: {
    solidityContract: "USDGIntentVault.sol",
    solidityValid: true,
    stylusRustContract: "lib.rs",
    stylusValid: true,
    stablecoin: "Paxos USDG (Global Dollar)",
  },
  reserves: {
    arbitrumUsdg: 500000,
    robinhoodChainUsdg: 350000,
    totalVolumeUsdg: 0,
  },
  intents: [],
};

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function showMsg(m) {
  msgBox.hidden = false;
  msgBox.textContent = m;
}

function render(state) {
  const r = state.reserves || {};
  const c = state.contracts || {};
  volPill.textContent = `Volume: $${Number(r.totalVolumeUsdg || 0).toFixed(2)} USDG`;

  reservesBox.innerHTML = `
    <div><strong>Stablecoin Asset:</strong> <span class="ok">${esc(c.stablecoin)}</span></div>
    <div style="margin-top:6px"><strong>Arbitrum USDG Reserve:</strong> $${Number(r.arbitrumUsdg || 0).toLocaleString()} USDG</div>
    <div style="margin-top:4px"><strong>Robinhood Chain (4663) USDG Reserve:</strong> $${Number(r.robinhoodChainUsdg || 0).toLocaleString()} USDG</div>
    <div style="margin-top:6px" class="muted">Solidity Vault: ${esc(c.solidityContract)} (Verified) · Stylus Verifier: ${esc(c.stylusRustContract)} (Verified)</div>
  `;

  if ((state.intents || []).length) {
    intentsList.innerHTML = state.intents.map((it) => `
      <div class="item-box">
        <div class="row-between">
          <strong>Intent #${it.intent_id} · ${esc(it.src_chain_name)} (${it.src_chain_id}) → ${esc(it.dst_chain_name)} (${it.dst_chain_id})</strong>
          <span class="ok">${esc(it.status)}</span>
        </div>
        <div style="margin-top:4px">
          In: <strong>${it.amount_in_usdg} USDG</strong> → Stylus Quoted Out: <strong>${it.quoted_out_usdg} USDG</strong>
          (Min Out: ${it.min_amount_out_usdg} USDG · Impact: ${it.price_impact_bps} bps)
        </div>
        ${it.status === "OPEN" ? `
          <div style="margin-top:8px">
            <button type="button" class="btn ok" data-settle="${it.intent_id}">Settle Intent with Stylus Proof (`settleIntentWithStylusQuote`)</button>
          </div>
        ` : `
          <div class="muted" style="margin-top:4px">Settlement Proof: ${esc(it.settlement_proof_hex)}</div>
        `}
      </div>
    `).join("");

    intentsList.querySelectorAll("button[data-settle]").forEach((btn) => {
      btn.addEventListener("click", () => settleIntent(Number(btn.dataset.settle)));
    });
  }
}

async function loadState() {
  try {
    const res = await fetch("/api/state");
    const ct = res.headers.get("content-type") || "";
    if (res.ok && ct.includes("application/json")) {
      staticState = await res.json();
    }
  } catch {
    // Use client-side fallback on static GitHub Pages.
  }
  render(staticState);
}

createBtn.addEventListener("click", async () => {
  const srcChainId = Number(srcInput.value);
  const dstChainId = Number(dstInput.value);
  const amountInUsdg = Number(amountInput.value) || 1500;
  const solverFeeBps = Number(feeInput.value) || 10;

  try {
    const res = await fetch("/api/create_intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ srcChainId, dstChainId, amountInUsdg, solverFeeBps, slippageBps: 40 }),
    });
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) throw new Error("Static fallback");
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || "Failed");
    staticState = d.state;
    showMsg(`Created Intent #${d.intent.intent_id} — Stylus quoted ${d.intent.quoted_out_usdg} USDG.`);
    render(staticState);
  } catch (e) {
    if (e.message !== "Static fallback") {
      showMsg(e.message);
      return;
    }
    if (srcChainId === dstChainId) {
      showMsg("Source and destination chains must differ.");
      return;
    }
    const netIn = amountInUsdg * (10000 - solverFeeBps) / 10000;
    const quoted = Number((netIn * 0.9994).toFixed(4));
    const minOut = Number((amountInUsdg * 0.996).toFixed(4));
    const iid = staticState.intents.length + 1;
    staticState.intents.unshift({
      intent_id: iid,
      src_chain_id: srcChainId,
      src_chain_name: CHAIN_NAMES[srcChainId],
      dst_chain_id: dstChainId,
      dst_chain_name: CHAIN_NAMES[dstChainId],
      amount_in_usdg: amountInUsdg,
      quoted_out_usdg: quoted,
      min_amount_out_usdg: minOut,
      price_impact_bps: 0.6,
      status: "OPEN",
      settlement_proof_hex: null,
    });
    staticState.reserves.totalVolumeUsdg += amountInUsdg;
    showMsg(`Created Intent #${iid} — Stylus quoted ${quoted} USDG (Static Preview Mode).`);
    render(staticState);
  }
});

async function settleIntent(intentId) {
  try {
    const res = await fetch("/api/settle_intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intentId }),
    });
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) throw new Error("Static fallback");
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || "Failed");
    staticState = d.state;
    showMsg(`Settled Intent #${intentId} with Stylus proof ${d.intent.settlement_proof_hex.slice(0, 20)}…`);
    render(staticState);
  } catch (e) {
    if (e.message !== "Static fallback") {
      showMsg(e.message);
      return;
    }
    staticState.intents = staticState.intents.map((it) =>
      it.intent_id === intentId
        ? { ...it, status: "SETTLED", settlement_proof_hex: "0x" + Math.random().toString(16).slice(2).padEnd(64, "c") }
        : it
    );
    showMsg(`Settled Intent #${intentId} in Static Preview Mode.`);
    render(staticState);
  }
}

loadState();
