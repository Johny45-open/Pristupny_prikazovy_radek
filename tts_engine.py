from accessible_output2.outputs.auto import Auto


class TtsEngine:
    def __init__(self):
        self.output = Auto()

    def speak(self, text: str) -> None:
        if not text or not text.strip():
            return
        try:
            self.output.speak(text)
        except Exception as e:
            print(f"CHYBA HLASU: {e}")

    def stop(self) -> None:
        """Prerusi aktualni promluvu, pokud to vystup podporuje."""
        try:
            # accessible_output2 NVDA/SAPI5 ma metodu silence/stop/braille?
            # Zkusime postupne dostupne metody
            if hasattr(self.output, "silence"):
                self.output.silence()
            elif hasattr(self.output, "stop"):
                self.output.stop()
            elif hasattr(self.output, "cancel"):
                self.output.cancel()
            else:
                # fallback: pokus o speak("") u nekterych backendu prerusi frontu
                pass
        except Exception as e:
            print(f"CHYBA HLASU stop: {e}")

    def is_screen_reader_active(self) -> bool:
        """Vraci True pokud Auto zvolilo NVDA/JAWS/SAPI s aktivni cteckou."""
        try:
            name = self.output.__class__.__name__.lower()
            # Auto dynamicky voli backend – zkusime i atributy
            detected = getattr(self.output, "output", None)
            if detected is not None:
                name = detected.__class__.__name__.lower()
            if any(k in name for k in ("nvda", "jaws", "auto")):
                # Auto ma vlastnost is_active u nekterych verzi
                if hasattr(self.output, "is_active"):
                    try:
                        return bool(self.output.is_active())
                    except Exception:
                        pass
                return True
            # fallback: zkus primo dostupne vystupy
            return False
        except Exception:
            return False

    def get_backend_name(self) -> str:
        try:
            out = getattr(self.output, "output", self.output)
            return out.__class__.__name__
        except Exception:
            return self.output.__class__.__name__
