#!/usr/bin/env python3
"""
Merlin Desktop TUI — terminal voice assistant with camera, mic, and full PC access.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.screen import Screen

from desktop.screens.launch_screen import LaunchScreen
from desktop.screens.main_screen import MainScreen


class MerlinTUI(App):
    SCREENS = {
        "launch": LaunchScreen,
        "main": MainScreen,
    }

    CSS = """
    Screen {
        background: #0a0a0a;
        color: #e0e0e0;
    }

    .title {
        text-align: center;
        color: #00e5ff;
        text-style: bold;
        padding: 1;
    }

    #launch-container {
        align: center middle;
        padding: 2 4;
    }

    #perm-results {
        margin: 1 2;
        padding: 1 2;
    }

    #start-btn {
        margin: 1 4;
        background: #00e5ff;
        color: #000;
    }

    #status-bar {
        background: #001a1a;
        padding: 0 1;
        height: 1;
    }

    #left-panel {
        width: 30%;
        border-right: solid #222;
        padding: 1;
    }

    #chat-view {
        width: 70%;
        padding: 1;
    }

    .panel {
        height: 100%;
    }

    #input-bar {
        height: 3;
        padding: 0 1;
    }

    #mode-selector {
        height: 3;
    }

    .label {
        text-style: bold;
        color: #888;
        padding: 0 1;
        margin-top: 1;
    }
    Select {
        margin: 0 1;
    }
    .sudo-dialog {
        align: center middle;
        padding: 2;
        background: #111;
        border: solid #00e5ff;
        width: 40;
    }

    .sudo-dialog Input {
        margin: 1 0;
    }

    Button {
        margin: 0 1;
    }
    """

    def on_mount(self):
        self.push_screen("launch")


if __name__ == "__main__":
    app = MerlinTUI()
    app.run()
