from textual.widgets import TabbedContent, TabPane


MODES = ["WORK", "LIFT", "WALK", "TALK", "NOTES", "SCOUT", "RECON", "DRIVE", "SKI"]


class ModeSelector(TabbedContent):
    """Activity mode tabs at the bottom."""

    def compose(self):
        for m in MODES:
            yield TabPane(m, id=m)
