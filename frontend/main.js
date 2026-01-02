// Utility: POST JSON
async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// Simple neon chart renderer (no external libs)
function renderCountsChart(canvas, counts) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const keys = ["HIGH", "MEDIUM", "LOW"];
  const colors = {
    HIGH: "#ef4444",
    MEDIUM: "#f59e0b",
    LOW: "#22c55e",
  };
  const maxVal = Math.max(1, ...keys.map(k => counts[k] || 0));
  const barWidth = 120;
  const gap = 60;
  const leftPad = (W - (barWidth * keys.length + gap * (keys.length - 1))) / 2;
  const bottom = H - 40;

  // Glow background
  ctx.fillStyle = "#0b1018";
  ctx.fillRect(0, 0, W, H);

  keys.forEach((k, i) => {
    const val = counts[k] || 0;
    const x = leftPad + i * (barWidth + gap);
    const bh = Math.round((val / maxVal) * (H - 120));

    // Neon shadow
    ctx.shadowColor = colors[k];
    ctx.shadowBlur = 18;

    // Bar
    const grad = ctx.createLinearGradient(x, bottom - bh, x + barWidth, bottom);
    grad.addColorStop(0, colors[k]);
    grad.addColorStop(1, "#06b6d4");
    ctx.fillStyle = grad;
    ctx.fillRect(x, bottom - bh, barWidth, bh);

    // Reset shadow
    ctx.shadowBlur = 0;

    // Label
    ctx.fillStyle = "#9fb0c4";
    ctx.font = "14px Orbitron, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`${k}`, x + barWidth / 2, bottom + 20);
    ctx.fillStyle = "#eaf1ff";
    ctx.font = "700 16px Orbitron, sans-serif";
    ctx.fillText(`${val}`, x + barWidth / 2, bottom - bh - 10);
  });

  // Title
  ctx.fillStyle = "#7c3aed";
  ctx.font = "600 18px Orbitron, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Moved counts (neon)", W / 2, 24);
}

// Train - collect samples
document.getElementById("btn-train").addEventListener("click", async () => {
  const startDate = document.getElementById("train-date").value;
  const limit = parseInt(document.getElementById("train-limit").value || "0", 10);
  const out = document.getElementById("train-results");
  const labelArea = document.getElementById("label-area");
  const submitBtn = document.getElementById("btn-submit-labels");

  out.textContent = "";
  labelArea.innerHTML = "";
  submitBtn.classList.add("hidden");

  if (!startDate || !limit || limit < 1) {
    out.textContent = "Provide a valid date and positive sample count.";
    return;
  }

  try {
    const data = await postJSON("/api/train", { start_date: startDate, limit });
    out.textContent = data.message || "";
    if (data.samples && data.samples.length) {
      data.samples.forEach((s, i) => {
        const div = document.createElement("div");
        div.className = "item";
        div.innerHTML = `
          <div class="subject">${i + 1}. ${s.subject}</div>
          <div>${s.summary}</div>
          <div style="margin-top:8px">
            <label><input type="radio" name="label_${i}" value="HIGH"> HIGH</label>
            <label><input type="radio" name="label_${i}" value="MEDIUM"> MEDIUM</label>
            <label><input type="radio" name="label_${i}" value="LOW"> LOW</label>
          </div>
        `;
        labelArea.appendChild(div);
      });
      submitBtn.classList.remove("hidden");
      submitBtn.onclick = async () => {
        const items = [];
        data.samples.forEach((s, i) => {
          const sel = document.querySelector(`input[name="label_${i}"]:checked`);
          if (sel) {
            items.push({
              email_id: s.email_id,
              subject: s.subject,
              summary: s.summary,
              label: sel.value
            });
          }
        });
        if (!items.length) {
          alert("Please label at least one item.");
          return;
        }
        try {
          const resp = await postJSON("/api/label", { items });
          alert(resp.message || "Labels submitted.");
        } catch (e) {
          alert(`Error: ${e.message}`);
        }
      };
    }
  } catch (e) {
    out.textContent = `Error: ${e.message}`;
  }
});

// Process emails
document.getElementById("btn-process").addEventListener("click", async () => {
  const startDate = document.getElementById("process-date").value;
  const out = document.getElementById("process-results");
  out.innerHTML = "";

  if (!startDate) {
    out.textContent = "Provide a start date.";
    return;
  }

  try {
    const data = await postJSON("/api/process", { start_date: startDate });
    const counts = data.moved_counts || {};
    const header = document.createElement("div");
    header.innerHTML = `<strong>Moved:</strong> HIGH ${counts.HIGH || 0}, MEDIUM ${counts.MEDIUM || 0}, LOW ${counts.LOW || 0}`;
    out.appendChild(header);

    data.items.forEach((item) => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `
        <div class="subject">${item.subject}
          <span class="badge ${item.priority}">${item.priority}</span>
        </div>
        <div>${item.summary}</div>
        <div style="margin-top:6px"><a href="${item.gmail_link}" target="_blank">Open in Gmail</a></div>
      `;
      out.appendChild(div);
    });

    const canvas = document.getElementById("countsChart");
    renderCountsChart(canvas, counts);
  } catch (e) {
    out.textContent = `Error: ${e.message}`;
  }
});

// Recovery view + promote
document.getElementById("btn-recovery").addEventListener("click", async () => {
  const startDate = document.getElementById("recovery-date").value;
  const out = document.getElementById("recovery-results");
  out.innerHTML = "";

  if (!startDate) {
    out.textContent = "Provide a start date.";
    return;
  }

  try {
    const data = await postJSON("/api/recovery", { start_date: startDate });
    if (!data.items || !data.items.length) {
      out.textContent = "No recovery emails since the given date.";
      return;
    }

    data.items.forEach((item, i) => {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `
        <div class="subject">${i + 1}. ${item.subject}</div>
        <div>${item.summary}</div>
        <div style="margin-top:6px"><a href="${item.gmail_link}" target="_blank">Open in Gmail</a></div>
        <div style="margin-top:8px; display:flex; gap:8px;">
          <button class="btn-glow promote" data-id="${item.email_id}" data-to="HIGH">Promote HIGH</button>
          <button class="btn-glow promote" data-id="${item.email_id}" data-to="MEDIUM">Promote MEDIUM</button>
        </div>
      `;
      out.appendChild(div);
    });

    out.querySelectorAll(".promote").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const id = e.target.getAttribute("data-id");
        const to = e.target.getAttribute("data-to");
        try {
          const resp = await postJSON("/api/promote", { email_id: id, new_priority: to });
          alert(resp.message || "Promoted");
          // Refresh list
          document.getElementById("btn-recovery").click();
        } catch (err) {
          alert(`Error: ${err.message}`);
        }
      });
    });
  } catch (e) {
    out.textContent = `Error: ${e.message}`;
  }
});
