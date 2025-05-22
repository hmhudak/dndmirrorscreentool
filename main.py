import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QVBoxLayout, QWidget, QLabel, QFileDialog, QSizePolicy,
    QToolBar, QPushButton, QSlider, QMenuBar, QScrollBar, QTabWidget
)
from PySide6.QtGui import (
    QPainter, QPixmap, QWheelEvent, QImage, QColor, QMouseEvent,
    QAction, Qt, QCursor
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect


class MyGraphicsView(QGraphicsView):
    """
    Interactive view (zoom, drag, erase, paint).
    """
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._interaction_start_callback = None
        self._interaction_end_callback = None
        self._update_callback = None

        # Overlay
        self.overlay_image = None
        self.overlay_item = None

        self.tool = "none"  # "none", "erase", "paint"
        self.brush_radius = 20

    def set_overlay(self, overlay_img: QImage, overlay_item: QGraphicsPixmapItem):
        self.overlay_image = overlay_img
        self.overlay_item = overlay_item

    def set_interaction_callbacks(self, start_callback, end_callback, update_callback):
        self._interaction_start_callback = start_callback
        self._interaction_end_callback = end_callback
        self._update_callback = update_callback

    def set_tool(self, tool_name: str):
        self.tool = tool_name
        if self.tool == "none":
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.update_cursor()

    def set_brush_radius(self, radius: int):
        self.brush_radius = radius
        if self.tool in ("erase", "paint"):
            self.update_cursor()

    def update_cursor(self):
        """
        V móde erase/paint => polopriehľadny biely kruh, ktorý dynamicky zohľadňuje aktuálny zoom.
        """
        if self.tool not in ("erase", "paint"):
            self.setCursor(Qt.ArrowCursor)
            return

        transform = self.transform()
        scale_x = transform.m11()
        scale_y = transform.m22()
        scale_factor = (scale_x + scale_y) / 2.0

        screen_radius = max(1, int(self.brush_radius * scale_factor))

        size = max(64, screen_radius * 2 + 10)
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 100))
        center = size // 2
        painter.drawEllipse(center - screen_radius, center - screen_radius,
                            screen_radius * 2, screen_radius * 2)
        painter.end()

        pix = QPixmap.fromImage(img)
        cursor = QCursor(pix, center, center)
        self.setCursor(cursor)

    def wheelEvent(self, event: QWheelEvent):
        if self.tool != "none":
            return
        if self._interaction_start_callback:
            self._interaction_start_callback()

        old_pos = self.mapToScene(event.position().toPoint())
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        self.scale(zoom_factor, zoom_factor)

        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

        if self._update_callback:
            self._update_callback()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.tool in ["erase", "paint"]:
                if self._interaction_start_callback:
                    self._interaction_start_callback()
                self.apply_brush(event.pos())
                if self._update_callback:
                    self._update_callback()
            else:
                if self._interaction_start_callback:
                    self._interaction_start_callback()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.tool in ["erase", "paint"]:
                if self._update_callback:
                    self._update_callback()
                if self._interaction_end_callback:
                    self._interaction_end_callback()
            else:
                if self._update_callback:
                    self._update_callback()
                if self._interaction_end_callback:
                    self._interaction_end_callback()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.tool in ["erase", "paint"] and (event.buttons() & Qt.LeftButton):
            self.apply_brush(event.pos())
            if self._update_callback:
                self._update_callback()
        super().mouseMoveEvent(event)

    def apply_brush(self, view_pos: QPoint):
        if not self.overlay_image or not self.overlay_item:
            return
        scene_point = self.mapToScene(view_pos)
        item_point = self.overlay_item.mapFromScene(scene_point)
        x = int(item_point.x())
        y = int(item_point.y())

        painter = QPainter(self.overlay_image)
        r = self.brush_radius
        if self.tool == "erase":
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.setPen(Qt.NoPen)
            painter.setBrush(Qt.white)
        elif self.tool == "paint":
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0,0,0,255))

        painter.drawEllipse(x - r, y - r, r * 2, r * 2)
        painter.end()

        self.overlay_item.setPixmap(QPixmap.fromImage(self.overlay_image))


class PreviewGraphicsView(QGraphicsView):
    """
    Vrchný (polopriehľadný) pohľad – admin vidí originálny obrázok cez overlay.
    """
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)


class MirrorWindow(QMainWindow):
    """
    Interaktívne zrkadlo: zobrazuje screenshot z MyGraphicsView (tak ako doteraz).
    Nedá sa zavrieť, pokým beží hlavné okno.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Interactive Mirror")
        self.label = QLabel("Mirror content here.")
        self.label.setScaledContents(True)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self.label)
        self.setCentralWidget(w)

    def set_mirror_pixmap(self, pm: QPixmap):
        self.label.setPixmap(pm)

    def closeEvent(self, event):
        if self.main_window and self.main_window.isVisible():
            event.ignore()
        else:
            super().closeEvent(event)


class StaticMirrorWindow(QMainWindow):
    """
    Statické zrkadlo: zobrazuje rovnaký statický obrázok ako je v tab2 (Static).
    Prispôsobený veľkosti okna s pomerom strán.
    Nedá sa zavrieť, pokým beží hlavné okno.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Static Mirror")

        self.label = QLabel()
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setScaledContents(False)  # riadime scaling manuálne

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self.label)
        self.setCentralWidget(w)

        self.original_pixmap = None

    def set_image(self, pixmap: QPixmap):
        """
        Uloží si pixmap a hneď ho skalujeme do labelu.
        """
        self.original_pixmap = pixmap
        self.update_display()

    def update_display(self):
        """Pri zmene veľkosti okna znovu skalujeme obrázok s KeepAspectRatio."""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        size = self.label.size()
        scaled = self.original_pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()

    def closeEvent(self, event):
        if self.main_window and self.main_window.isVisible():
            event.ignore()
        else:
            super().closeEvent(event)


class MainWindow(QMainWindow):
    """
    Hlavné okno s dvomi tabmi:
      - Tab 0: Interaktívny obraz (MyGraphicsView + overlay) + PreviewGraphicsView.
      - Tab 1: Statický obraz (QLabel).

    MirrorWindow = zrkadlo interaktívneho pohľadu,
    StaticMirrorWindow = zrkadlo statického obrázka.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Main with 2 Tabs + 2 Mirrors")

        # --------------------
        # Vytvoríme QTabWidget, ktorý bude centrálnym widgetom
        # --------------------
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --------------------
        # Tab 0 (Interactive)
        # --------------------
        self.interactive_scene = QGraphicsScene(self)
        self.pixmap_item = QGraphicsPixmapItem()
        self.interactive_scene.addItem(self.pixmap_item)

        self.overlay_item = QGraphicsPixmapItem()
        self.overlay_item.setZValue(1)
        self.interactive_scene.addItem(self.overlay_item)

        self.view = MyGraphicsView(self.interactive_scene, self)

        # Vnoríme do layoutu, ktorý je child pre tab 0
        self.tab0_widget = QWidget()
        tab0_layout = QVBoxLayout(self.tab0_widget)
        tab0_layout.setContentsMargins(0, 0, 0, 0)
        tab0_layout.addWidget(self.view)
        self.tabs.addTab(self.tab0_widget, "Interactive")

        # Polopriehľadný preview (len pre tab 0):
        self.preview_scene = QGraphicsScene(self)
        self.preview_item = QGraphicsPixmapItem()
        self.preview_item.setOpacity(0.3)
        self.preview_scene.addItem(self.preview_item)

        self.preview_view = PreviewGraphicsView(self.preview_scene, self.tab0_widget)
        self.preview_view.setGeometry(QRect(self.view.x(), self.view.y(),
                                            self.view.width(), self.view.height()))
        self.preview_view.show()
        self.preview_view.raise_()

        # --------------------
        # Tab 1 (Static)
        # --------------------
        self.tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(self.tab1_widget)
        tab1_layout.setContentsMargins(0, 0, 0, 0)

        self.static_label = QLabel("No image loaded yet")
        self.static_label.setAlignment(Qt.AlignCenter)
        self.static_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.static_label.setScaledContents(False)
        tab1_layout.addWidget(self.static_label)

        self.tabs.addTab(self.tab1_widget, "Static")

        # --------------------
        # Mirror okná
        # --------------------
        self.mirror_window = MirrorWindow(self)
        self.mirror_window.show()

        self.static_mirror_window = StaticMirrorWindow(self)
        self.static_mirror_window.show()

        # --------------------
        # Toolbar s Erase, Paint, Slider
        # --------------------
        tb = QToolBar("Tools", self)
        self.addToolBar(tb)

        self.erase_btn = QPushButton("Erase", self)
        self.erase_btn.setCheckable(True)
        self.erase_btn.clicked.connect(self.on_erase_clicked)
        tb.addWidget(self.erase_btn)

        self.paint_btn = QPushButton("Paint", self)
        self.paint_btn.setCheckable(True)
        self.paint_btn.clicked.connect(self.on_paint_clicked)
        tb.addWidget(self.paint_btn)

        self.brush_slider = QSlider(Qt.Horizontal)
        self.brush_slider.setRange(1, 200)
        self.brush_slider.setValue(20)
        self.brush_slider.setFixedWidth(120)
        self.brush_slider.valueChanged.connect(self.on_brush_slider_changed)
        tb.addWidget(self.brush_slider)

        # --------------------
        # Menu
        # --------------------
        open_act = QAction("Open Image...", self)
        open_act.triggered.connect(self.on_open_image)
        mbar = self.menuBar()
        file_menu = mbar.addMenu("File")
        file_menu.addAction(open_act)

        # --------------------
        # Interakčný timer (20 FPS)
        # --------------------
        self.interaction_timer = QTimer(self)
        self.interaction_timer.setInterval(50)
        self.interaction_timer.timeout.connect(self.update_mirror)

        # Callbacks pre MyGraphicsView
        self.view.set_interaction_callbacks(
            start_callback=self.on_interaction_start,
            end_callback=self.on_interaction_end,
            update_callback=self.update_mirror
        )
        self.view.horizontalScrollBar().valueChanged.connect(self.sync_preview_transform)
        self.view.verticalScrollBar().valueChanged.connect(self.sync_preview_transform)

    # ---------------------------------------------------------------------
    # Funkcie na otvorenie obrázka podľa toho, ktorý tab je práve aktívny
    # ---------------------------------------------------------------------
    def on_open_image(self):
        """
        Jediný dialóg na otvorenie obrázka. Podľa toho, či sme v Tab 0 alebo 1,
        načíta obrázok buď do MyGraphicsView (interactive) alebo do static_label.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return

        pm = QPixmap(path)
        if pm.isNull():
            return

        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            # Tab 0 => Interaktívny
            self.load_interactive_image(pm)
        else:
            # Tab 1 => Static
            self.load_static_image(pm)

    def load_interactive_image(self, pixmap: QPixmap):
        """
        Nastaví obrázok pre spodnú scénu + overlay + preview (tab 0).
        """
        self.pixmap_item.setPixmap(pixmap)
        self.interactive_scene.setSceneRect(pixmap.rect())
        self.view.fitInView(self.interactive_scene.sceneRect(), Qt.KeepAspectRatio)

        overlay_img = QImage(pixmap.width(), pixmap.height(), QImage.Format_ARGB32)
        overlay_img.fill(QColor(0,0,0,255))
        self.overlay_item.setPixmap(QPixmap.fromImage(overlay_img))
        self.view.set_overlay(overlay_img, self.overlay_item)

        self.preview_item.setPixmap(pixmap)
        self.preview_scene.setSceneRect(pixmap.rect())
        self.preview_view.setTransform(self.view.transform())

        # Tool reset
        self.erase_btn.setChecked(False)
        self.paint_btn.setChecked(False)
        self.view.set_tool("none")

        self.update_mirror()

    def load_static_image(self, pixmap: QPixmap):
        """
        Nastaví obrázok do static_label (tab 1) a do statického mirroru.
        """
        self.static_label.setText("")  # zmažeme text
        # Prispôsobenie do labelu (KeepAspectRatio)
        size = self.static_label.size()
        scaled = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.static_label.setPixmap(scaled)

        # Mirror
        self.static_mirror_window.set_image(pixmap)

    # ---------------------------------------------------------------------
    # Erase/Paint funkcie
    # ---------------------------------------------------------------------
    def on_erase_clicked(self, checked):
        if checked:
            self.paint_btn.setChecked(False)
            self.view.set_tool("erase")
        else:
            if not self.paint_btn.isChecked():
                self.view.set_tool("none")

    def on_paint_clicked(self, checked):
        if checked:
            self.erase_btn.setChecked(False)
            self.view.set_tool("paint")
        else:
            if not self.erase_btn.isChecked():
                self.view.set_tool("none")

    def on_brush_slider_changed(self, val):
        self.view.set_brush_radius(val)

    # ---------------------------------------------------------------------
    # Interakčný timer (mirror refresh)
    # ---------------------------------------------------------------------
    def on_interaction_start(self):
        if not self.interaction_timer.isActive():
            self.interaction_timer.start()

    def on_interaction_end(self):
        if self.interaction_timer.isActive():
            self.interaction_timer.stop()

    def update_mirror(self):
        """
        MirrorWindow: screenshot MyGraphicsView.
        """
        screenshot = self.view.grab()
        self.mirror_window.set_mirror_pixmap(screenshot)

        self.sync_preview_transform()
        if self.view.tool in ("erase", "paint"):
            self.view.update_cursor()

    def sync_preview_transform(self):
        tr = self.view.transform()
        self.preview_view.setTransform(tr)
        self.preview_view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value())
        self.preview_view.verticalScrollBar().setValue(self.view.verticalScrollBar().value())

    # ---------------------------------------------------------------------
    # Events
    # ---------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.tabs.currentIndex() == 0:
            # Nastavíme geometriu preview_view nad interactive view
            self.preview_view.setGeometry(self.view.geometry())
            self.preview_view.raise_()
        else:
            # Tab 1 - netreba preview
            pass

    def closeEvent(self, event):
        # Uvoľníme mirror okná, aby sa teraz dali zavrieť
        self.mirror_window.main_window = None
        self.mirror_window.close()

        self.static_mirror_window.main_window = None
        self.static_mirror_window.close()

        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
