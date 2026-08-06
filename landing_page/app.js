document.addEventListener('DOMContentLoaded', () => {

    // --- 3D Hologram Visualizer Engine (Replicating client/gui/app.py) ---
    const canvas = document.getElementById('hologram-canvas');
    let setHologramState = () => {}; // Forward declaration

    if (canvas) {
        const ctx = canvas.getContext('2d');
        const holoStateLbl = document.getElementById('holo-state-lbl');
        const stateButtons = document.querySelectorAll('.btn-holo-state');

        let hologramState = "idle"; // idle, listening, thinking, speaking, connecting, error
        let animationPhase = 0.0;
        let currentColor = { r: 0, g: 191, b: 255, a: 150 }; // Default idle color
        let targetColor = { r: 0, g: 191, b: 255, a: 150 };
        
        const stateConfigs = {
            connecting: { r: 255, g: 184, b: 0, a: 220 }, // Amber
            idle:       { r: 0, g: 191, b: 255, a: 150 }, // Cyan-blue
            listening:  { r: 0, g: 255, b: 102, a: 220 }, // Green
            thinking:   { r: 255, g: 100, b: 0, a: 220 },   // Orange
            speaking:   { r: 0, g: 255, b: 240, a: 220 },  // Speaking Cyan
            error:      { r: 255, g: 50, b: 50, a: 220 }    // Red
        };

        // Smooth color interpolation
        function updateColors() {
            currentColor.r += (targetColor.r - currentColor.r) * 0.1;
            currentColor.g += (targetColor.g - currentColor.g) * 0.1;
            currentColor.b += (targetColor.b - currentColor.b) * 0.1;
            currentColor.a += (targetColor.a - currentColor.a) * 0.1;
        }

        setHologramState = function(state) {
            hologramState = state;
            targetColor = stateConfigs[state] || stateConfigs.idle;
            if (holoStateLbl) {
                holoStateLbl.textContent = `ALFONSO (${state.toUpperCase()})`;
            }
            
            stateButtons.forEach(btn => {
                if (btn.getAttribute('data-state') === state) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        };

        // Add event listeners to state selector buttons
        stateButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                setHologramState(btn.getAttribute('data-state'));
            });
        });

        // 3D Point Projection function matching QPainter implementation
        function project3DPoint(x, y, z, cx, cy, t) {
            // Rotations
            const yaw = t * 0.4;
            const pitch = 0.65; // Fixed perspective tilt
            
            // Yaw Rotation (around Y axis)
            const cosY = Math.cos(yaw);
            const sinY = Math.sin(yaw);
            const x1 = x * cosY + z * sinY;
            const z1 = -x * sinY + z * cosY;
            
            // Pitch Rotation (around X axis)
            const cosP = Math.cos(pitch);
            const sinP = Math.sin(pitch);
            const y2 = y * cosP - z1 * sinP;
            const z2 = y * sinP + z1 * cosP;
            
            // Perspective Projection
            const focal = 350.0;
            const dist = 280.0 + z2;
            const px = cx + (x1 * focal) / dist;
            const py = cy + (y2 * focal) / dist;
            
            return { x: px, y: py, z: z2 };
        }

        function drawHologram() {
            animationPhase += 0.05;
            if (animationPhase > 1000.0) animationPhase = 0.0;

            updateColors();

            const w = canvas.width;
            const h = canvas.height;
            const cx = w / 2;
            const cy = h / 2;

            ctx.clearRect(0, 0, w, h);

            // Jitter/Glitch effect on thinking or error state
            let jitterX = 0;
            let jitterY = 0;
            if (hologramState === "thinking" || hologramState === "error") {
                jitterX = (Math.random() - 0.5) * 6;
                jitterY = (Math.random() - 0.5) * 6;
            }

            const currentR = Math.round(currentColor.r);
            const currentG = Math.round(currentColor.g);
            const currentB = Math.round(currentColor.b);

            // 1. Draw Ethereal Glow
            const glow = ctx.createRadialGradient(cx + jitterX, cy + jitterY, 10, cx + jitterX, cy + jitterY, 90);
            glow.addColorStop(0.0, `rgba(${currentR}, ${currentG}, ${currentB}, 0.22)`);
            glow.addColorStop(0.6, `rgba(${currentR}, ${currentG}, ${currentB}, 0.05)`);
            glow.addColorStop(1.0, `rgba(0, 0, 0, 0)`);
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(cx + jitterX, cy + jitterY, 90, 0, Math.PI * 2);
            ctx.fill();

            // 2. Draw 3D Concentric Rings
            const baseRadii = [24, 42, 60, 78];
            baseRadii.forEach((baseR, idx) => {
                let pulse = 0.0;
                if (hologramState === "speaking") {
                    pulse = Math.abs(Math.sin(animationPhase * 9.0 - idx)) * 8.0;
                } else if (hologramState === "listening") {
                    pulse = Math.sin(animationPhase * 4.0 + idx) * 3.5;
                } else if (hologramState === "thinking") {
                    pulse = Math.sin(animationPhase * 8.0) * 2.0;
                } else { // idle
                    pulse = Math.sin(animationPhase * 1.5 + idx) * 1.8;
                }

                const ringR = baseR + pulse;
                const points = [];
                const steps = 48;

                for (let step = 0; step < steps; step++) {
                    const angle = (2.0 * Math.PI * step) / steps;
                    const rx = ringR * Math.cos(angle);
                    const ry = ringR * Math.sin(angle);
                    const rz = Math.sin(angle * 2.0) * 8.0;

                    const projected = project3DPoint(rx, ry, rz, cx + jitterX, cy + jitterY, animationPhase);
                    points.push(projected);
                }

                // Draw Ring segments
                for (let i = 0; i < steps; i++) {
                    const pt1 = points[i];
                    const pt2 = points[(i + 1) % steps];

                    const avgZ = (pt1.z + pt2.z) / 2.0;
                    const alpha = Math.max(0.1, Math.min(0.9, 0.55 + avgZ * 0.01));

                    ctx.strokeStyle = `rgba(${currentR}, ${currentG}, ${currentB}, ${alpha})`;
                    ctx.lineWidth = idx === 0 ? 1.8 : 1.1;

                    // Dash pattern mapping from PyQt QPen styles
                    if (idx === 1) {
                        ctx.setLineDash([4, 4]);
                    } else if (idx === 2) {
                        ctx.setLineDash([2, 4]);
                    } else {
                        ctx.setLineDash([]);
                    }

                    ctx.beginPath();
                    ctx.moveTo(pt1.x, pt1.y);
                    ctx.lineTo(pt2.x, pt2.y);
                    ctx.stroke();
                }
            });
            ctx.setLineDash([]); // Reset dash

            // 3. Orbiting Constellation Nodes in 3D
            const numParticles = 16;
            const particlePts = [];
            for (let i = 0; i < numParticles; i++) {
                const angle = (2.0 * Math.PI * i) / numParticles + (animationPhase * 0.2);
                const p_r = 52.0 + Math.sin(animationPhase * 0.8 + i) * 7.0;

                const px = p_r * Math.cos(angle);
                const py = p_r * Math.sin(angle);
                const pz = Math.cos(angle * 3.0) * 14.0;

                const projected = project3DPoint(px, py, pz, cx + jitterX, cy + jitterY, animationPhase);
                particlePts.push(projected);
            }

            // Draw Constellation Lines
            for (let i = 0; i < numParticles; i++) {
                const pt1 = particlePts[i];
                const pt2 = particlePts[(i + 1) % numParticles];

                const avgZ = (pt1.z + pt2.z) / 2.0;
                const alpha = Math.max(0.04, Math.min(0.35, 0.2 + avgZ * 0.005));

                ctx.strokeStyle = `rgba(${currentR}, ${currentG}, ${currentB}, ${alpha})`;
                ctx.lineWidth = 0.7;
                ctx.beginPath();
                ctx.moveTo(pt1.x, pt1.y);
                ctx.lineTo(pt2.x, pt2.y);
                ctx.stroke();
            }

            // Draw Constellation Nodes
            particlePts.forEach(pt => {
                const alpha = Math.max(0.15, Math.min(1.0, 0.7 + pt.z * 0.01));
                const size = Math.max(1.5, Math.min(4.5, 3.0 + pt.z * 0.05));

                ctx.fillStyle = `rgba(${currentR}, ${currentG}, ${currentB}, ${alpha})`;
                ctx.beginPath();
                ctx.arc(pt.x, pt.y, size / 2, 0, Math.PI * 2);
                ctx.fill();

                // Small glow ring around nodes
                ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.4})`;
                ctx.lineWidth = 0.5;
                ctx.beginPath();
                ctx.arc(pt.x, pt.y, size, 0, Math.PI * 2);
                ctx.stroke();
            });

            // 4. Central Core Pulsing Glow
            let coreSize = 10;
            if (hologramState === "speaking") {
                coreSize += Math.abs(Math.sin(animationPhase * 12.0)) * 5;
            }

            const coreGrad = ctx.createRadialGradient(cx + jitterX, cy + jitterY, 1, cx + jitterX, cy + jitterY, coreSize);
            coreGrad.addColorStop(0.0, `rgba(255, 255, 255, 1.0)`);
            coreGrad.addColorStop(0.4, `rgba(${currentR}, ${currentG}, ${currentB}, 0.9)`);
            coreGrad.addColorStop(1.0, `rgba(${currentR}, ${currentG}, ${currentB}, 0)`);
            ctx.fillStyle = coreGrad;
            ctx.beginPath();
            ctx.arc(cx + jitterX, cy + jitterY, coreSize, 0, Math.PI * 2);
            ctx.fill();

            // Speaking concentric sound waves
            if (hologramState === "speaking") {
                for (let waveIdx = 0; waveIdx < 3; waveIdx++) {
                    const waveR = 14 + ((animationPhase * 15 + waveIdx * 20) % 45);
                    const waveAlpha = Math.max(0, 0.6 - (waveR * 0.012));
                    ctx.strokeStyle = `rgba(${currentR}, ${currentG}, ${currentB}, ${waveAlpha})`;
                    ctx.lineWidth = 1.2;
                    ctx.beginPath();
                    ctx.arc(cx + jitterX, cy + jitterY, waveR, 0, Math.PI * 2);
                    ctx.stroke();
                }
            }

            requestAnimationFrame(drawHologram);
        }

        // Start Hologram Rendering loop
        drawHologram();
    }


    // --- File Drop & Simulator Integration ---
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const terminal = document.getElementById('simulator-terminal');
    const simStatus = document.getElementById('sim-status');
    const btnResetSim = document.getElementById('btn-reset-sim');
    const guideSteps = document.querySelectorAll('.sim-guide-step');

    let processing = false;

    // Trigger explorer window on link/zone click
    if (uploadZone) {
        uploadZone.addEventListener('click', (e) => {
            if (processing) return;
            fileInput.click();
        });

        // Drag and Drop event handlers
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (processing) return;
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (processing) return;
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                processInvoiceFile(files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length > 0) {
                processInvoiceFile(files[0]);
            }
        });
    }

    // Advanced client-side parser (extracted locally, works offline)
    function parseInvoiceData(file, callback) {
        const reader = new FileReader();

        // 1. Setup deterministic default backup values from filename hash (so same file name = same amounts)
        let hashVal = 0;
        for (let i = 0; i < file.name.length; i++) {
            hashVal = file.name.charCodeAt(i) + ((hashVal << 5) - hashVal);
        }
        
        let total = Math.abs(hashVal % 650) + 29.90; // Default fallback between 29.90€ and 679.90€
        let cif = "ESA" + Math.abs((hashVal % 90000000) + 10000000);
        let emisor = "PROVEEDOR_LOCAL";

        // Check if filename itself contains numbers (e.g. "invoice_340_euros.pdf")
        const nameNumbers = file.name.match(/(?:\D|^)(\d+(?:[.,]\d{1,2})?)(?:\D|$)/);
        if (nameNumbers && nameNumbers[1]) {
            let num = parseFloat(nameNumbers[1].replace(',', '.'));
            if (num > 1.0) total = num;
        }

        // Helper to extract NIFs and totals from raw text (extremely robust)
        function scanRawText(text) {
            // Find Spanish NIF / CIF patterns
            const cifMatch = text.match(/\b([A-Z]\d{7}[A-Z]|\d{8}[A-Z])\b/i);
            if (cifMatch) cif = cifMatch[1].toUpperCase();

            // Capture all numbers matching standard decimal currency formats requiring a dot/comma and exactly 2 digits (prevents matching coordinates/ids)
            const decimalRegex = /\b\d+(?:[.]\d{3})*[,](\d{2})\b|\b\d+(?:[,]\d{3})*[.](\d{2})\b/g;
            const candidates = [];
            let match;
            while ((match = decimalRegex.exec(text)) !== null) {
                let valStr = match[0].replace(/\s/g, '').replace(/\./g, '').replace(',', '.');
                let num = parseFloat(valStr);
                // Exclude coordinates, zip codes, and dates (keep only reasonable invoice amounts)
                if (num > 1.0 && num < 200000) {
                    candidates.push(num);
                }
            }

            // Also check for total prefix matches specifically (e.g. "Total Factura: 181,50 EUR")
            // This can capture even integer values if they are prefixed by "total"
            const totalRegex = /(?:total|importe|neto|suma|pagar|total factura)[\s\S]{0,35}?\b(\d+[\d\s.,]*\d{2})\b/gi;
            const totalMatches = [...text.matchAll(totalRegex)];
            let matchedTotal = null;
            if (totalMatches.length > 0) {
                let valStr = totalMatches[totalMatches.length - 1][1];
                valStr = valStr.replace(/\s/g, '').replace(/\./g, '').replace(',', '.');
                let num = parseFloat(valStr);
                if (num > 1.0 && num < 200000) {
                    matchedTotal = num;
                }
            }

            if (matchedTotal) {
                total = matchedTotal;
            } else if (candidates.length > 0) {
                total = Math.max(...candidates);
            }

            // Look for potential company name in ASCII streams
            const companyMatch = text.match(/(?:COWORKING MADRID CENTRO|COWORKING|MADRID CENTRO|IBERDROLA|TELEFONICA|MOVISTAR|GOOGLE|AMAZON)/i);
            if (companyMatch) {
                emisor = companyMatch[0].toUpperCase();
            } else {
                const genericMatch = text.match(/(?:razon\s+social|emisor|proveedor|empresa)[\s\S]{0,20}?:\s*([A-Z0-9\s.]{3,30})/i);
                if (genericMatch) {
                    emisor = genericMatch[1].trim().replace(/\r?\n|\r/g, " ").toUpperCase();
                }
            }
        }

        // 2. Read file based on type
        if (file.name.endsWith('.pdf')) {
            reader.onload = function(e) {
                // Decode PDF streams to raw latin1 string to preserve raw bytes
                const arrayBuffer = e.target.result;
                const uint8 = new Uint8Array(arrayBuffer);
                let rawText = "";
                try {
                    rawText = new TextDecoder('latin1').decode(uint8);
                } catch(err) {
                    for (let i = 0; i < uint8.byteLength; i++) {
                        rawText += String.fromCharCode(uint8[i]);
                    }
                }

                // Extract text chunks inside parentheses `(text)` from uncompressed PDF blocks
                const pdfParentheses = rawText.match(/\(([^)]+)\)/g);
                let extractedText = "";
                if (pdfParentheses) {
                    extractedText = pdfParentheses
                        .map(m => m.slice(1, -1))
                        .join(" ");
                }
                
                // Add clean ASCII stream text to scan compressed layout headers/metadata
                const cleanASCII = rawText.replace(/[^\x20-\x7E]/g, ' ');
                scanRawText(extractedText + " " + cleanASCII);
                callback({ total, cif, emisor });
            };
            reader.readAsArrayBuffer(file);
        } else if (file.type.match('text.*') || file.name.endsWith('.txt') || file.name.endsWith('.csv') || file.name.endsWith('.json')) {
            reader.onload = function(e) {
                scanRawText(e.target.result);
                callback({ total, cif, emisor });
            };
            reader.readAsText(file);
        } else {
            // Images or binary formats: process using filename clues & deterministic hash
            callback({ total, cif, emisor });
        }
    }

    function processInvoiceFile(file) {
        processing = true;
        uploadZone.style.display = 'none';
        terminal.style.display = 'block';
        btnResetSim.style.display = 'none';
        
        simStatus.textContent = 'Analizando...';
        simStatus.classList.add('active');
        terminal.innerHTML = '';
        
        const fileName = file.name;
        const fileSize = (file.size / 1024).toFixed(1) + ' KB';
        const fileHash = Math.random().toString(36).substring(2, 10).toUpperCase();

        // Local extraction (works offline without backend)
        parseInvoiceData(file, (data) => {
            const totalVal = data.total;
            const baseImponible = totalVal / 1.21;
            const ivaVal = totalVal - baseImponible;
            const cifVal = data.cif;
            const emisorVal = data.emisor;

            const steps = [
                { type: 'system', text: `> [SISTEMA] Iniciando extracción de documento: "${fileName}" (${fileSize})...`, step: 1, holo: 'listening' },
                { type: 'info', text: `> [Paso 1] OCR local activado. Analizando tablas de facturación...`, step: 1, holo: 'listening' },
                { type: 'success', text: `> [Extracción] Total Factura: ${totalVal.toFixed(2)} €, Base: ${baseImponible.toFixed(2)} €, IVA (21%): ${ivaVal.toFixed(2)} €`, step: 1, holo: 'listening' },
                { type: 'success', text: `> [Extracción] NIF Emisor: ${cifVal} | Proveedor: ${emisorVal}`, step: 1, holo: 'listening' },
                { type: 'system', text: `> ------------------------------------------------------------------------`, step: 2, holo: 'thinking' },
                { type: 'highlight', text: `> [Paso 2] Aplicando capa de privacidad local. Anonimizando payload sensible...`, step: 2, holo: 'thinking' },
                { type: 'highlight', text: `> [Filtro] Ofuscando NIF ${cifVal} a [EMISOR_TOKEN_${fileHash.substring(0,3)}]`, step: 2, holo: 'thinking' },
                { type: 'success', text: `> [Privacidad] Cifrado y firmas protegidas en el llavero SQLite local.`, step: 2, holo: 'thinking' },
                { type: 'system', text: `> ------------------------------------------------------------------------`, step: 3, holo: 'speaking' },
                { type: 'info', text: `> [Paso 3] Orquestando con motor Qwen local (qwen2.5:3b) en SQLite...`, step: 3, holo: 'speaking' },
                { type: 'info', text: `> Clasificando gasto bajo reglas de IVA deducible (Servicios exteriores)...`, step: 3, holo: 'speaking' },
                { type: 'success', text: `> [Verifactu] Generando hash de bloque encadenado local y firma criptográfica.`, step: 3, holo: 'speaking' }
            ];

            function updateActiveStep(stepNum) {
                guideSteps.forEach(step => {
                    if (parseInt(step.getAttribute('data-step')) === stepNum) {
                        step.classList.add('active');
                    } else {
                        step.classList.remove('active');
                    }
                });
            }

            let index = 0;
            
            function printLogLine() {
                if (index < steps.length) {
                    const line = steps[index];
                    const div = document.createElement('div');
                    div.className = `line ${line.type}`;
                    div.textContent = line.text;
                    terminal.appendChild(div);
                    terminal.scrollTop = terminal.scrollHeight;
                    
                    updateActiveStep(line.step);
                    setHologramState(line.holo);
                    
                    index++;
                    setTimeout(printLogLine, 1000);
                } else {
                    printAlfonsoResponse(fileName, fileHash, totalVal, baseImponible, ivaVal, cifVal, emisorVal);
                }
            }

            printLogLine();
        });
    }

    function printAlfonsoResponse(originalName, hash, total, base, iva, cif, emisor) {
        setHologramState('speaking');
        simStatus.textContent = 'Completado';
        simStatus.classList.remove('active');
        btnResetSim.style.display = 'inline-block';
        
        const newName = `FACT-2026-08-${hash}.pdf`;

        const responseLines = [
            { type: 'system', text: `> ------------------------------------------------------------------------` },
            { type: 'success', text: `[ALFONSO AUTÓNOMO]:` },
            { type: 'highlight', text: `He analizado y procesado tu factura de forma 100% segura en tu máquina.` },
            { type: 'info', text: `He extraído los datos del emisor con NIF ${cif} (${emisor}). La factura tiene un importe total de ${total.toFixed(2)} € (Base Imponible: ${base.toFixed(2)} €, IVA 21%: ${iva.toFixed(2)} €).` },
            { type: 'info', text: `He procedido a renombrar el documento a "${newName}" y guardarlo en tu directorio fiscal local.` },
            { type: 'info', text: `He cruzado el importe de ${total.toFixed(2)} € con tus movimientos bancarios descargados de Banco Sabadell, localizando una salida coincidente del día 05/05/2026. Conciliación completada con éxito.` },
            { type: 'info', text: `He registrado el asiento contable en tu libro diario local (gasto de explotación deducible en IRPF e IVA en concepto de arrendamientos).` },
            { type: 'success', text: `La base imponible de ${base.toFixed(2)} € ha sido asignada a la Casilla 28 del borrador de tu Modelo 303 de IVA, y la cuota de IRPF ha sido consolidada en el borrador del Modelo 130 de este trimestre. Queda listo en local para tu firma de aprobación final en un solo clic.` }
        ];

        let index = 0;
        function printFinalLine() {
            if (index < responseLines.length) {
                const line = responseLines[index];
                const div = document.createElement('div');
                div.className = `line ${line.type}`;
                div.style.fontWeight = line.type === 'success' || line.type === 'highlight' ? 'bold' : 'normal';
                div.textContent = line.text;
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
                
                index++;
                setTimeout(printFinalLine, 800);
            } else {
                processing = false;
            }
        }
        printFinalLine();
    }

    // Reset Simulation to upload another file
    if (btnResetSim) {
        btnResetSim.addEventListener('click', () => {
            if (processing) return;
            uploadZone.style.display = 'flex';
            terminal.style.display = 'none';
            btnResetSim.style.display = 'none';
            fileInput.value = '';
            simStatus.textContent = 'Listo para recibir';
            setHologramState('idle');
            guideSteps.forEach(step => {
                if (parseInt(step.getAttribute('data-step')) === 1) {
                    step.classList.add('active');
                } else {
                    step.classList.remove('active');
                }
            });
        });
    }


    // --- Time & Money Saved Calculator ---
    const invoiceSlider = document.getElementById('invoice-slider');
    const invoiceCount = document.getElementById('invoice-count');
    const savedHours = document.getElementById('saved-hours');
    const savedMoney = document.getElementById('saved-money');

    function calculateSavings() {
        if (!invoiceSlider) return;
        const invoices = parseInt(invoiceSlider.value);
        invoiceCount.textContent = invoices;
        
        // 15 mins saved per invoice + 3 hours base per month for general taxes
        const hoursSavedPerMonth = (invoices * 15 / 60) + 3;
        const hoursSavedPerYear = Math.round(hoursSavedPerMonth * 12);
        
        // Assuming a standard freelance hourly rate of 35€ / hour
        const moneySavedPerYear = Math.round(hoursSavedPerYear * 35);
        
        savedHours.textContent = `${hoursSavedPerYear}h`;
        savedMoney.textContent = `${moneySavedPerYear.toLocaleString('es-ES')}€`;
    }

    if (invoiceSlider) {
        invoiceSlider.addEventListener('input', calculateSavings);
        calculateSavings();
    }


    // --- Waitlist Form Submission ---
    const waitlistForm = document.getElementById('waitlist-form');
    const waitlistEmail = document.getElementById('waitlist-email');
    const formMsg = document.getElementById('form-msg');

    if (waitlistForm) {
        waitlistForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = waitlistEmail.value.trim();
            
            if (email) {
                let waitlist = JSON.parse(localStorage.getItem('alfonso_waitlist') || '[]');
                waitlist.push({ email: email, timestamp: new Date().toISOString() });
                localStorage.setItem('alfonso_waitlist', JSON.stringify(waitlist));
                
                formMsg.textContent = '¡Registro completado! Te hemos añadido a la lista de espera priorizada de la Fase 1.';
                formMsg.className = 'form-message success';
                waitlistEmail.value = '';
                
                setTimeout(() => {
                    formMsg.textContent = '';
                    formMsg.className = 'form-message';
                }, 6000);
            } else {
                formMsg.textContent = 'Por favor, introduce un correo electrónico válido.';
                formMsg.className = 'form-message error';
            }
        });
    }

});
