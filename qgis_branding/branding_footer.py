# -*- coding: utf-8 -*-
from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QRectF, QSize, Qt, QUrl
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from typing import Iterable, List, Optional, Tuple

from . import resources_rc  # noqa: F401  # registers :/branding/...

DEFAULT_LOGO_PATH = ":/branding/icons/logo.svg"
DEFAULT_MAX_LOGO_WIDTH = 150
DEFAULT_MAX_LOGO_HEIGHT = None
DEFAULT_SUBTITLE_TEXT = "© 2026 Michał Sikora, Radosław Seweryn | OnGeo sp. z o.o."
DEFAULT_LINKS: Tuple[Tuple[str, str], ...] = (
    ("Szkolenia OnGeo", "https://szkolenia.ongeo.pl/"),
    ("Raporty o Terenie OnGeo", "https://ongeo.pl/"),
    ("Geoportal Krajowy Na Mapie", "https://geoportal-krajowy.pl/na-mapie/"),
    ("OnGeo Intelligence", "https://ongeo-intelligence.com/"),
)


def open_url(url: str):
    """Open a URL in the default system browser."""
    QtGui.QDesktopServices.openUrl(QUrl(url))


class LinkButton(QPushButton):
    """Flat button styled to look like a hyperlink."""

    def __init__(self, title: str, url: str, parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self._url = url
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(
            """
            QPushButton {
                color: palette(link);
                text-decoration: underline;
                background: transparent;
                border: none;
                padding: 2px 8px;
            }
            QPushButton:hover { color: palette(highlight); }
            """
        )
        self.clicked.connect(self._open_link)

    def _open_link(self):
        open_url(self._url)


class AspectRatioSvgWidget(QWidget):
    """Display an SVG while preserving its aspect ratio."""

    def __init__(
        self,
        svg_path: str,
        max_width: Optional[int] = DEFAULT_MAX_LOGO_WIDTH,
        max_height: Optional[int] = DEFAULT_MAX_LOGO_HEIGHT,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("AspectRatioSvgWidget")
        self._renderer = QSvgRenderer(svg_path, self)

        view_box = self._renderer.viewBoxF()
        natural_width = view_box.width() if view_box.width() > 0 else 1.0
        natural_height = view_box.height() if view_box.height() > 0 else 1.0
        self._aspect = natural_width / natural_height

        size = self._compute_target_size(max_width, max_height)
        width = size.width()
        height = size.height()

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumSize(width, height)
        self.setMaximumSize(width, height)
        self.setFixedSize(width, height)

    def _compute_target_size(self, max_w: Optional[int], max_h: Optional[int]) -> QSize:
        if max_w and not max_h:
            target_width = float(max_w)
            target_height = target_width / self._aspect
        elif max_h and not max_w:
            target_height = float(max_h)
            target_width = target_height * self._aspect
        elif max_w and max_h:
            box_aspect = float(max_w) / float(max_h)
            if self._aspect >= box_aspect:
                target_width = float(max_w)
                target_height = target_width / self._aspect
            else:
                target_height = float(max_h)
                target_width = target_height * self._aspect
        else:
            target_width = float(DEFAULT_MAX_LOGO_WIDTH or 160.0)
            target_height = target_width / self._aspect
        return QSize(int(round(target_width)), int(round(target_height)))

    def sizeHint(self) -> QSize:
        return self.maximumSize()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform,
            on=True,
        )
        self._renderer.render(painter, QRectF(0, 0, self.width(), self.height()))
        painter.end()


class BrandingFooter(QWidget):
    """Footer with logo, subtitle and a row of links."""

    def __init__(
        self,
        links: Optional[Iterable[Tuple[str, str]]] = None,
        logo_path: str = DEFAULT_LOGO_PATH,
        max_logo_width: Optional[int] = DEFAULT_MAX_LOGO_WIDTH,
        max_logo_height: Optional[int] = DEFAULT_MAX_LOGO_HEIGHT,
        subtitle_text: Optional[str] = DEFAULT_SUBTITLE_TEXT,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("BrandingFooter")

        self._links: List[Tuple[str, str]] = list(links or DEFAULT_LINKS)
        self._link_buttons: List[LinkButton] = []

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(8, 8, 8, 8)
        self.root_layout.setSpacing(6)

        self.logo_wrap = QWidget(self)
        self.logo_layout = QHBoxLayout(self.logo_wrap)
        self.logo_layout.setContentsMargins(0, 0, 0, 0)
        self.logo_layout.setSpacing(0)

        self.logo_widget = AspectRatioSvgWidget(
            svg_path=logo_path,
            max_width=max_logo_width,
            max_height=max_logo_height,
            parent=self,
        )
        self.logo_layout.addStretch(1)
        self.logo_layout.addWidget(self.logo_widget, 0, Qt.AlignCenter)
        self.logo_layout.addStretch(1)
        self.root_layout.addWidget(self.logo_wrap)

        self.subtitle_label = QLabel(subtitle_text or "")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.subtitle_label.setStyleSheet(
            """
            QLabel {
                color: rgba(0,0,0,0.65);
                font-size: 11px;
                padding: 2px 8px 0 8px;
            }
            """
        )
        self.root_layout.addWidget(self.subtitle_label)

        self.links_wrap = QWidget(self)
        self.links_layout = QHBoxLayout(self.links_wrap)
        self.links_layout.setContentsMargins(0, 0, 0, 0)
        self.links_layout.setSpacing(0)
        self.links_layout.addStretch(1)

        for title, url in self._links:
            self._add_link_button(title, url)
        self.links_layout.addStretch(1)
        self.root_layout.addWidget(self.links_wrap)

        self.setStyleSheet(
            """
            QWidget#BrandingFooter {
                border-top: 1px solid rgba(0,0,0,35);
                background: transparent;
            }
            """
        )

    def _add_link_button(self, title: str, url: str):
        button = LinkButton(title, url, self)
        self._link_buttons.append(button)
        self.links_layout.addWidget(button, 0, Qt.AlignVCenter)
        return button

    def add_link(self, title: str, url: str):
        """Add a new hyperlink to the footer."""
        self._links.append((title, url))
        button = LinkButton(title, url, self)
        self._link_buttons.append(button)
        insert_index = max(0, self.links_layout.count() - 1)
        self.links_layout.insertWidget(insert_index, button, 0, Qt.AlignVCenter)
