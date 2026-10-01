from typing import Dict
from pydantic import BaseModel, Field

class StreamingTokenBuffer(BaseModel):
    """
    Buffer deslizante para resolución de tokens anonimizados durante streaming Server-Sent Events (SSE).
    Evita la fragmentación y exposición de tokens rotos como '[N' o 'IF_1]' entre chunks TCP/HTTP.
    """
    max_token_len: int = Field(default=30, description="Longitud máxima esperada para un token sintético")
    buffer: str = Field(default="", description="Fragmentos acumulados pendientes de evaluación")
    in_token: bool = Field(default=False, description="Indica si se ha detectado '[' sin haber llegado a ']'")

    def feed(self, chunk: str, token_map: Dict[str, str]) -> str:
        """
        Procesa un chunk entrante, resolviendo tokens cerrados y reteniendo
        tokens incompletos hasta su resolución. Devuelve el texto listo para emitir.
        """
        self.buffer += chunk
        output = []

        while self.buffer:
            if not self.in_token:
                bracket_pos = self.buffer.find("[")
                if bracket_pos == -1:
                    output.append(self.buffer)
                    self.buffer = ""
                    break
                else:
                    output.append(self.buffer[:bracket_pos])
                    self.buffer = self.buffer[bracket_pos:]
                    self.in_token = True

            # Ahora el buffer comienza con '['
            close_pos = self.buffer.find("]")
            if close_pos != -1:
                candidate_token = self.buffer[:close_pos + 1]
                resolved = token_map.get(candidate_token, candidate_token)
                output.append(resolved)
                self.buffer = self.buffer[close_pos + 1:]
                self.in_token = False
            else:
                # Corchete abierto sin cerrar.
                # Si supera max_token_len, no es un token válido; vaciar el '[' como texto normal.
                if len(self.buffer) > self.max_token_len:
                    output.append(self.buffer[0])
                    self.buffer = self.buffer[1:]
                    self.in_token = False
                else:
                    # Esperar al siguiente chunk del stream
                    break

        return "".join(output)

    def flush(self, token_map: Dict[str, str]) -> str:
        """Vacía el residuo del buffer al finalizar el stream."""
        if not self.buffer:
            return ""
        candidate = self.buffer
        resolved = token_map.get(candidate, candidate)
        self.buffer = ""
        self.in_token = False
        return resolved
