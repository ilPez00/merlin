from textual.widgets import TabbedContent, TabPane


MODES = ["WORK", "LIFT", "WALK", "TALK", "NOTES", "SCOUT", "RECON"]


class ModeSelector(TabbedContent):
    """Activity mode tabs at the bottom."""

    def compose(self):
        with self:
            for m in MODES:
                with TabPane(m, id=m):
                    pass
