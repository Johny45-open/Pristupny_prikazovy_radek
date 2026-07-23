from accessible_output2.outputs.auto import Auto


class TtsEngine:
    def __init__(self):
        self.output = Auto()

    def speak(self, text: str) -> None:
        try:
            self.output.speak(text)
        except Exception as e:
            print(f"CHYBA HLASU: {e}")
