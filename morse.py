"""Morse code timing.

timing() turns text into a list of signed integers in dit units: positive is
key down for that many dits, negative is key up. Standard spacing: dash = 3,
gap between elements = 1, between characters = 3, between words = 7.
"""

_CODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "=": "-...-",
    "-": "-....-",
}


def timing(text):
    out = []
    for word in text.upper().split():
        chars = [_CODE[c] for c in word if c in _CODE]
        if not chars:
            continue
        if out:
            out.append(-7)
        for ci, code in enumerate(chars):
            if ci:
                out.append(-3)
            for ei, symbol in enumerate(code):
                if ei:
                    out.append(-1)
                out.append(1 if symbol == "." else 3)
    return out


def dit_us(wpm):
    """Length of one dit in microseconds (PARIS standard: 1200 ms / wpm)."""
    return 1200000 // wpm
