// content.js - Alfonso Autónomo Guardián Fiscal
console.log("Alfonso Autónomo Guardián activado en esta página.");

let socket = null;
let buttonBlocked = true;

// 1. Conexión WebSocket al Backend Local de Alfonso
function connectWebSocket() {
    socket = new WebSocket("ws://localhost:7860/ws/guardian");

    socket.onopen = () => {
        console.log("Conectado con Alfonso Core local.");
        updateBannerStatus("Conectado", "Alfonso está vigilando este trámite de forma segura en local.");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Comando recibido de Alfonso Core:", data);
        if (data.action === "guardian.alert") {
            showNotification(data.params.message, data.params.type || "warning");
        } else if (data.action === "guardian.autofill") {
            autofillForm(data.params.fields);
        }
    };

    socket.onclose = () => {
        console.log("Desconectado de Alfonso Core. Reintentando...");
        updateBannerStatus("Desconectado", "Alfonso está desconectado. Sincronización inactiva.");
        setTimeout(connectWebSocket, 3000); // Reintento
    };
}

// 2. Crear y Estilizar el Banner de Alfonso (Estilo Glassmorphism Premium)
function createAlfonsoBanner() {
    if (document.getElementById("alfonso-guardian-banner")) return;

    const banner = document.createElement("div");
    banner.id = "alfonso-guardian-banner";
    banner.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 60px;
        background: rgba(31, 73, 125, 0.9);
        backdrop-filter: blur(10px);
        color: white;
        z-index: 10000000;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 20px;
        box-sizing: border-box;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        border-bottom: 2px solid rgba(255, 255, 255, 0.2);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 14px;
        transition: all 0.3s ease;
    `;

    const leftSection = document.createElement("div");
    leftSection.style.display = "flex";
    leftSection.style.alignItems = "center";
    leftSection.innerHTML = `
        <span style="font-size: 20px; margin-right: 10px;">🤖</span>
        <div>
            <strong style="color: #00FFCC; font-size: 15px; letter-spacing: 0.5px;">ALFONSO AUTÓNOMO</strong>
            <span id="alfonso-banner-status" style="margin-left: 10px; font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(0, 255, 204, 0.2); color: #00FFCC; border: 1px solid rgba(0, 255, 204, 0.4);">Conectando...</span>
            <div id="alfonso-banner-desc" style="font-size: 11px; color: #E0E0E0; margin-top: 2px;">Cargando copiloto fiscal...</div>
        </div>
    `;

    const rightSection = document.createElement("div");
    rightSection.id = "alfonso-banner-actions";
    rightSection.style.display = "flex";
    rightSection.style.gap = "10px";

    const btnOK = document.createElement("button");
    btnOK.id = "alfonso-btn-ok";
    btnOK.innerText = "Revisión OK (Liberar Firma)";
    btnOK.style.cssText = `
        background: #00FFCC;
        color: #1F497D;
        border: none;
        padding: 8px 14px;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
        font-size: 12px;
        transition: transform 0.2s;
    `;
    btnOK.onclick = () => {
        buttonBlocked = false;
        btnOK.style.background = "#808080";
        btnOK.innerText = "Firma Liberada";
        btnOK.disabled = true;
        showNotification("Trámite verificado. Ya puedes proceder a firmar de forma segura en la web.", "success");
    };

    const btnCancel = document.createElement("button");
    btnCancel.innerText = "Cancelar y Corregir";
    btnCancel.style.cssText = `
        background: rgba(255, 80, 80, 0.2);
        color: #FF8080;
        border: 1px solid rgba(255, 80, 80, 0.5);
        padding: 8px 14px;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
        font-size: 12px;
    `;
    btnCancel.onclick = () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "user_cancel", message: "El usuario ha abortado el trámite." }));
        }
        showNotification("Trámite cancelado. Alfonso te asistirá en local.", "error");
        buttonBlocked = true;
        btnOK.style.background = "#00FFCC";
        btnOK.innerText = "Revisión OK (Liberar Firma)";
        btnOK.disabled = false;
    };

    rightSection.appendChild(btnCancel);
    rightSection.appendChild(btnOK);
    banner.appendChild(leftSection);
    banner.appendChild(rightSection);
    document.body.prepend(banner);

    // Ajustar el margen del body para no tapar contenido
    document.body.style.marginTop = "60px";
}

function updateBannerStatus(status, description) {
    const statusEl = document.getElementById("alfonso-banner-status");
    const descEl = document.getElementById("alfonso-banner-desc");
    if (statusEl) statusEl.innerText = status;
    if (descEl) descEl.innerText = description;
}

// 3. Notificación Flotante Estilizada
function showNotification(message, type = "warning") {
    const toast = document.createElement("div");
    let bg = "#1F497D";
    if (type === "success") bg = "#2ECC71";
    if (type === "error") bg = "#E74C3C";

    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${bg};
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        z-index: 10000001;
        font-family: sans-serif;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        font-weight: bold;
        transition: all 0.3s ease;
    `;
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}

// 4. Interceptar y Bloquear Botón de Envío/Firma
function interceptSubmitButton() {
    document.addEventListener("click", (event) => {
        const target = event.target;
        // Detectar si el clic es en un botón de envío típico del gobierno
        const isSubmitButton = 
            target.tagName === "BUTTON" && 
            (target.innerText.includes("Firmar") || 
             target.innerText.includes("Presentar") || 
             target.innerText.includes("Enviar") ||
             target.id.includes("submit") ||
             target.id.includes("firmar"));

        if (isSubmitButton && buttonBlocked) {
            event.preventDefault();
            event.stopPropagation();
            showNotification("Alfonso bloqueó el envío temporalmente. Debes verificar y pulsar 'Revisión OK' en el banner superior.", "warning");
        }
    }, true);
}

// 5. Simulación de Auto-relleno de Formularios
function autofillForm(fields) {
    for (const [selector, value] of Object.entries(fields)) {
        const el = document.querySelector(selector);
        if (el) {
            el.value = value;
            // Disparar eventos para que la página detecte el cambio de texto
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`Auto-rellenado: ${selector} -> ${value}`);
        }
    }
    showNotification("Formulario rellenado automáticamente por Alfonso.", "success");
}

// Inicializar
createAlfonsoBanner();
connectWebSocket();
interceptSubmitButton();
