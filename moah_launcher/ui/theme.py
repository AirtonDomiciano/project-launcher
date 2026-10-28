from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

STYLESHEET = """
QWidget {
    color: #e8eaef;
    background: #16181d;
    font-size: 13px;
}
QLabel#title {
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}
QLabel#hint, QLabel#empty {
    color: #8b93a7;
    background: transparent;
}
QLabel#banner {
    background: #3a2e1e;
    color: #f0c674;
    border: 1px solid #6b5424;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit {
    background: #2a2f3a;
    border: 1px solid #4c78c8;
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: #345088;
    min-height: 22px;
}
QLineEdit#search {
    font-size: 15px;
}
QPushButton {
    background: #2a2f3a;
    border: 1px solid #3c4352;
    border-radius: 6px;
    padding: 5px 10px;
}
QPushButton:hover {
    background: #343b4a;
}
QPushButton:checked {
    background: #2d3c5a;
    border-color: #6ea8fe;
    color: #f4f7fb;
}
QPushButton:disabled {
    color: #6d7588;
    background: #22262f;
}
QTableWidget {
    background: #1b1e26;
    alternate-background-color: #20242d;
    gridline-color: transparent;
    selection-background-color: #2d3c5a;
    selection-color: #f4f7fb;
    border: 1px solid #323846;
    border-radius: 6px;
}
QHeaderView::section {
    background: #21242c;
    color: #8b93a7;
    border: none;
    padding: 6px 8px;
    font-weight: 600;
}
QTableWidget::item {
    padding: 4px 6px;
}
QStatusBar {
    background: #12141a;
    color: #8b93a7;
}
QScrollBar:vertical {
    background: #1b1e26;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3c4352;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar:horizontal {
    background: #1b1e26;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #3c4352;
    border-radius: 4px;
}
QListWidget {
    background: #1b1e26;
    border: 1px solid #323846;
    border-radius: 6px;
}
QListWidget::item {
    padding: 4px 2px;
}
QListWidget::item:selected {
    background: #2d3c5a;
}
QMessageBox {
    background: #1b1e26;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#16181d"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eaef"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1b1e26"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#20242d"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eaef"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2a2f3a"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8eaef"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2d3c5a"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#f4f7fb"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2a2f3a"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eaef"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8b93a7"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
