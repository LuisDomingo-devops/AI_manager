document.addEventListener("DOMContentLoaded", () => {
  // Mobile navigation
  const menu = document.getElementById("mobile-menu");
  const nav = document.getElementById("nav-links");

  if (menu && nav) {
    menu.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      menu.setAttribute("aria-expanded", String(open));
    });

    nav.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => {
        nav.classList.remove("open");
        menu.setAttribute("aria-expanded", "false");
      });
    });
  }

  // Local demo: intentionally limited to browser-side metadata.
  // It does NOT claim to OCR/parse real PDF contents.
  const uploadZone = document.getElementById("upload-zone");
  const fileInput = document.getElementById("file-input");
  const result = document.getElementById("demo-result");
  const reset = document.getElementById("reset-demo");

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function showFile(file) {
    if (!file || !result) return;

    const allowed = [
      "application/pdf",
      "image/png",
      "image/jpeg",
      "text/plain"
    ];

    if (!allowed.includes(file.type) && !/\.(pdf|png|jpe?g|txt)$/i.test(file.name)) {
      result.hidden = false;
      result.innerHTML = "<strong>Formato no compatible.</strong><br>Selecciona un PDF, PNG, JPG o TXT.";
      reset.hidden = false;
      return;
    }

    const now = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    result.hidden = false;
    result.innerHTML = `
      <strong>Documento recibido.</strong><br>
      Archivo: ${escapeHtml(file.name)}<br>
      Tamaño: ${formatBytes(file.size)} · Tipo: ${escapeHtml(file.type || "desconocido")}<br>
      <span style="color:#67e1b2">✓ Demo local completada a las ${now}.</span>
      <br><small>En esta demo no se envía el archivo a un servidor ni se afirma que se haya realizado OCR fiscal real.</small>
    `;
    reset.hidden = false;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[char]));
  }

  if (fileInput) fileInput.addEventListener("change", e => showFile(e.target.files[0]));

  if (uploadZone) {
    ["dragenter", "dragover"].forEach(eventName => {
      uploadZone.addEventListener(eventName, e => {
        e.preventDefault();
        uploadZone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach(eventName => {
      uploadZone.addEventListener(eventName, e => {
        e.preventDefault();
        uploadZone.classList.remove("dragover");
      });
    });

    uploadZone.addEventListener("drop", e => {
      const file = e.dataTransfer.files?.[0];
      if (file) showFile(file);
    });
  }

  if (reset) {
    reset.addEventListener("click", () => {
      if (fileInput) fileInput.value = "";
      if (result) {
        result.hidden = true;
        result.innerHTML = "";
      }
      reset.hidden = true;
    });
  }

  // Time/money calculator
  const slider = document.getElementById("invoice-slider");
  const minutes = document.getElementById("minutes-input");
  const hourValue = document.getElementById("hour-value");
  const invoiceCount = document.getElementById("invoice-count");
  const savedHours = document.getElementById("saved-hours");
  const savedMoney = document.getElementById("saved-money");

  function updateCalculator() {
    if (!slider || !minutes || !hourValue) return;

    const invoices = Number(slider.value);
    const mins = Math.max(1, Number(minutes.value) || 1);
    const hourly = Math.max(0, Number(hourValue.value) || 0);

    const annualHours = (invoices * mins * 12) / 60;
    const annualValue = annualHours * hourly;

    invoiceCount.textContent = invoices;
    savedHours.textContent = `${Math.round(annualHours)} h`;
    savedMoney.textContent = new Intl.NumberFormat("es-ES", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0
    }).format(annualValue);
  }

  [slider, minutes, hourValue].forEach(el => {
    if (el) el.addEventListener("input", updateCalculator);
  });
  updateCalculator();

  // Waitlist form: front-end placeholder only.
  // Replace this handler with the real API/form endpoint before production.
  const form = document.getElementById("waitlist-form");
  const email = document.getElementById("email");
  const message = document.getElementById("form-message");

  if (form) {
    form.addEventListener("submit", event => {
      event.preventDefault();
      const value = email.value.trim();

      if (!value || !email.checkValidity()) {
        message.textContent = "Introduce un email válido.";
        message.style.color = "#ff8a8a";
        return;
      }

      message.textContent = "¡Gracias! El formulario está listo para conectarse a tu backend de waitlist.";
      message.style.color = "#67e1b2";
      form.reset();
    });
  }
  // Calculadora interactiva VERI*FACTU
  const verifactuForm = document.getElementById("verifactu-quiz-form");
  const verifactuResults = document.getElementById("verifactu-results");

  if (verifactuForm && verifactuResults) {
    verifactuForm.addEventListener("submit", event => {
      event.preventDefault();

      const q1 = Number(document.getElementById("q1").value || 0);
      const q2 = Number(document.getElementById("q2").value || 0);
      const q3 = Number(document.getElementById("q3").value || 0);
      const q4 = Number(document.getElementById("q4").value || 0);
      const emailInput = document.getElementById("verifactu-email");
      const email = emailInput ? emailInput.value.trim() : "";

      if (!email) return;

      const totalScore = q1 + q2 + q3 + q4; // Puntuación máxima: 8 puntos

      // Registro/Envío del Lead (preparado para API/Webhook)
      console.log("VERI*FACTU Lead Capturado:", { email, score: totalScore, date: new Date() });

      const badge = document.getElementById("verifactu-badge");
      const title = document.getElementById("verifactu-title");
      const desc = document.getElementById("verifactu-desc");
      const emailDisplay = document.getElementById("verifactu-user-email");

      if (emailDisplay) emailDisplay.textContent = email;

      if (totalScore <= 3) {
        badge.style.backgroundColor = "rgba(239, 68, 68, 0.15)";
        badge.style.color = "#ff6b6b";
        badge.style.border = "1px solid rgba(239, 68, 68, 0.3)";
        badge.textContent = "⚠️ RIESGO ALTO DE INCUMPLIMIENTO";
        title.textContent = "Tu negocio NO está preparado para VERI*FACTU";
        desc.textContent = "Actualmente utilizas métodos que no garantizan la inalterabilidad ni la trazabilidad solicitadas por la Agencia Tributaria. Emitir facturas con sistemas no adaptados expondrá a tu empresa a sanciones de hasta 50.000 € por ejercicio.";
      } else if (totalScore <= 6) {
        badge.style.backgroundColor = "rgba(245, 158, 11, 0.15)";
        badge.style.color = "#ffc84d";
        badge.style.border = "1px solid rgba(245, 158, 11, 0.3)";
        badge.textContent = "⚡ ADAPTACIÓN PARCIAL";
        title.textContent = "Estás cerca, pero necesitas ajustes técnicos";
        desc.textContent = "Dispones de una base digital, pero te faltan requisitos esenciales como la generación estructurada de registros, encadenamiento de facturas o conexión transparente con la AEAT.";
      } else {
        badge.style.backgroundColor = "rgba(34, 197, 139, 0.15)";
        badge.style.color = "#67e1b2";
        badge.style.border = "1px solid rgba(34, 197, 139, 0.3)";
        badge.textContent = "✅ NEGOCIO PREPARADO";
        title.textContent = "¡Enhorabuena! Tu sistema cumple con el estándar";
        desc.textContent = "Tu modelo de facturación cuenta con los elementos de trazabilidad, integridad e inalterabilidad para trabajar bajo la normativa VERI*FACTU de forma segura.";
      }

      verifactuForm.hidden = true;
      verifactuResults.hidden = false;
    });
  }
});

/* Premium time-value calculator */
(function(){
  const hours=document.getElementById('hoursInput'), hourValue=document.getElementById('hourValueInput');
  const hoursOutput=document.getElementById('hoursOutput'), hourValueOutput=document.getElementById('hourValueOutput');
  const monthly=document.getElementById('monthlySaving'), annual=document.getElementById('annualSaving');
  const saved=document.getElementById('savedHours'), timeValue=document.getElementById('timeValue');
  if(!hours||!hourValue)return;
  const fmt=new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR',maximumFractionDigits:0});
  function range(i){const p=(Number(i.value)-Number(i.min))/(Number(i.max)-Number(i.min))*100;i.style.setProperty('--range-progress',p+'%')}
  function update(){const h=+hours.value,v=+hourValue.value,m=h*v;hoursOutput.textContent=h+' h';hourValueOutput.textContent=v+' €/h';monthly.textContent=fmt.format(m);annual.textContent=fmt.format(m*12);saved.textContent=h+' h/mes';timeValue.textContent=v+' €/h';range(hours);range(hourValue)}
  hours.addEventListener('input',update);hourValue.addEventListener('input',update);update();
})();
