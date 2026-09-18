"""
cliente.py — Cliente de voz para Alfonso (versión corregida).

Cambios respecto a la versión anterior:
- --device ya NO tiene valor por defecto hardcodeado (era 28, tu USB).
  Si no lo pasas, AudioService detecta automáticamente el micrófono integrado.
- --threshold por defecto es None → se calibra automáticamente en arrange().
- Al arrancar muestra qué dispositivo y samplerate va a usar.
- El loop de silencio emite nivel en DEBUG para poder diagnósticar sin --debug.
"""



from __future__ import annotations

import os
import sys
from pathlib import Path

client_dir = os.path.dirname(os.path.abspath(__file__))
if client_dir not in sys.path:
    sys.path.insert(0, client_dir)

root_dir = os.path.dirname(client_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

pass

import argparse
import base64
import uuid
from typing import Optional

import numpy as np

from core.config import (
    DEFAULT_SERVER,
    CHUNK_SECONDS,
    SILENCE_THRESHOLD,
    MAX_SILENCE_SECONDS,
)
from services.audio import AudioService, auto_select_device
from core.api_client import AlfonsoAPI
from core.processor import ResponseProcessor

pass
# ---------------------------------------------------------------------------
# Calibración de umbral automática
# ---------------------------------------------------------------------------

def calibrate_threshold(audio: AudioService, device: Optional[int], seconds: float = 2.0) -> int:
    """
    Graba `seconds` segundos de silencio ambiente y calcula el umbral.
    Devuelve max(nivel_ambiente * 3, 80) para tener margen.
    """
    pass
    try:
        raw  = audio.record_raw(seconds, device=device)
        # Convertir a int16 para usar la misma escala que has_voice
        amp_i16 = int(np.abs(raw).mean() * 32767)
        threshold = max(amp_i16 * 3, 80)
        pass
        return threshold
    except Exception as exc:
        pass
        return SILENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def run(
    server_url: str,
    keyword: str,
    voice: Optional[str],
    device: Optional[int],
    output_device: Optional[int],
    model: str,
    threshold: Optional[int],
    debug: bool,
) -> None:
    
    pass

    # Cargar o crear Session ID persistente en ui/logs/session_config.json
    import os, json
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(ui_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    config_path = os.path.join(logs_dir, "session_config.json")
    
    session_id = None
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                session_id = json.load(f).get("session_id")
        except Exception:
            pass
    if not session_id:
        session_id = str(uuid.uuid4())
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id}, f, indent=4)
        except Exception:
            pass
    api        = AlfonsoAPI(server_url)
    processor  = ResponseProcessor()

    # AudioService con auto-detección si no se especificó dispositivo
    audio = AudioService(device=device, auto_detect=(device is None))

    # Mostrar el dispositivo que se va a usar
    import sounddevice as sd

    pass
    effective_device = audio.device
    device_name = "predeterminado del sistema"
    pass
    if effective_device is not None:
        try:
            pass
            device_name = sd.query_devices(effective_device)["name"]
        except Exception:
            pass
            pass

    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass

    pass
    if not api.ping():
        pass
        pass
        pass
        sys.exit(1)
    pass

    # Calibración de umbral si no se pasó explícitamente
    if threshold is None:
        threshold = calibrate_threshold(audio, effective_device)
    pass

    if debug:
        devs = audio.list_input_devices()
        pass
        for d in devs:
            marker = " ← EN USO" if d["index"] == effective_device else ""
            pass
        pass

    pass

    try:
        pass
        while True:
            # ── FASE 1: esperar wake word ──────────────────────────────
            pass

            try:
                pass
                wav = audio.record_chunk(int(CHUNK_SECONDS), device=effective_device)
            except Exception as exc:
                pass
                continue

            # Detección de Wake Word local mediante STT local
            if not audio.has_voice(wav, threshold):
                continue
            
            pass
            wakeword_text = audio.transcribe_local(wav)
            
            if keyword.lower() not in wakeword_text.lower():
                pass
                continue
            
            # Si llegamos aquí, es que el keyword está en el texto transcrito localmente.
            # No necesitamos wakeword_res porque la validación es local.
            if not wakeword_text:
                pass
                continue

            pass

            # ── FASE 2: loop de conversación ───────────────────────────
            first_order = processor.extract_order(wakeword_text, keyword)
            pass

            while True:
                if first_order:
                    pass
                    user_text  = first_order
                    first_order = None
                    pass
                else:
                    pass
                    audio_buffer = []
                    silence_time = 0.0
                    chunk_dur    = 0.8

                    while True:
                        try:
                            pass
                            chunk = audio.record_raw(chunk_dur, device=effective_device)
                        except Exception as exc:
                            pass
                            break

                        level = int(np.abs(chunk).mean() * 32767)
                        if level > threshold:
                            audio_buffer.append(chunk)
                            silence_time = 0.0
                            pass
                        else:
                            silence_time += chunk_dur
                            if audio_buffer:
                                pass
                                if silence_time >= MAX_SILENCE_SECONDS:
                                    break
                            elif silence_time >= 5.0:
                                break

                    if not audio_buffer:
                        pass
                        break

                    pass
                    wav_order = audio.get_audio_bytes(audio_buffer)
                    pass

                    # Transcripción local para evitar el 404 del endpoint /stt
                    user_text = audio.transcribe_local(wav_order)

                    if not user_text:
                        pass
                        continue

                    pass

                if processor.is_exit_command(user_text):
                    pass
                    pass
                    break

                pass
                chat = api.send_chat(user_text, session_id)
                
                status = chat.get("status") if isinstance(chat, dict) else "unknown"
                pass

                if debug:
                    pass

                if not isinstance(chat, dict) or chat.get("status") not in ("ok", "success"):
                    err_msg = chat.get('message', 'Formato de respuesta inválido') if isinstance(chat, dict) else 'Error de red/conexión'
                    pass
                    continue

                result_data   = chat.get("result", {})
                response_text = processor.format_response(result_data)
                pass

                audio_b64 = result_data.get("audio")
                if audio_b64:
                    audio.play_audio(base64.b64decode(audio_b64), device=output_device)
                elif response_text:
                     # Si el servidor no devuelve audio, generamos el TTS localmente en el cliente
                     import asyncio
                     try:
                         # Intentar generar voz humana con Edge-TTS
                         audio_path = asyncio.run(audio.text_to_speech_human(response_text))
                         if audio_path:
                             audio.play_audio_file(audio_path)
                         else:
                             # Fallback a voz robótica local
                             audio_bytes = audio.text_to_wav_bytes(response_text)
                             if audio_bytes:
                                 audio.play_audio(audio_bytes, device=output_device)
                     except Exception as e:
                         # Silencioso en modo normal, mostrar en debug
                         if debug:
                             pass

    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cliente de voz Alfonso")
    p.add_argument("--url",           default=DEFAULT_SERVER)
    p.add_argument("--gui",           action="store_true", help="Lanzar la interfaz gráfica")
    p.add_argument("--keyword",       default="alfonso")
    p.add_argument("--voice",         default=None)
    p.add_argument("--device",        type=int, default=None,
                   help="Índice del micrófono (None = auto-detecta el integrado)")
    p.add_argument("--output-device", type=int, default=None,
                   help="Índice del altavoz (None = predeterminado del sistema)")
    p.add_argument("--model",         default="tiny")
    p.add_argument("--threshold",     type=int, default=None,
                   help="Umbral de silencio (None = calibración automática al arrancar)")
    p.add_argument("--debug",         action="store_true")
    p.add_argument("--list-devices",  action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    pass
    if args.list_devices:
        pass
        svc = AudioService(auto_detect=False)
        pass
        for d in svc.list_input_devices():
            auto = " <- integrado detectado" if d["index"] == auto_select_device() else ""
            pass
        pass
        for d in svc.list_output_devices():
            pass
        sys.exit(0)

    if args.gui:
        pass
        from gui.app import launch
        config = vars(args)
        config["url"] = config["url"].rstrip("/")
        launch(config)
    else:
        pass
        run(
            server_url    = args.url.rstrip("/"),
            keyword       = args.keyword,
            voice         = args.voice,
            device        = args.device,
            output_device = getattr(args, "output_device", None),
            model         = args.model,
            threshold     = args.threshold,
            debug         = args.debug,
        )
