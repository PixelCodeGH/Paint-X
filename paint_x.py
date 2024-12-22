import sys
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QColorDialog,
                               QSpinBox, QFileDialog, QSlider, QFrame, QScrollArea)
from PySide6.QtCore import Qt, QPoint, QSize, QRect, QTimer, QPointF, QRectF
from PySide6.QtGui import (QPainter, QPen, QColor, QPixmap, QPainterPath,
                          QImage, QIcon, QLinearGradient, QBrush, QPalette, QTransform)

class ToolButton(QPushButton):
    def __init__(self, text, icon_name=None, tooltip=None, dark_mode=False):
        super().__init__(text)
        self.setFixedSize(40, 40)
        self.dark_mode = dark_mode
        
        if icon_name:
            icon = QIcon(icon_name)
            self.setIcon(icon)
            self.setIconSize(QSize(24, 24))
            
        self.update_style()
        self.setCheckable(True)
        if tooltip:
            self.setToolTip(tooltip)
            
    def update_style(self):
        bg_color = "#2b2b2b" if self.dark_mode else "#f8f9fa"
        text_color = "#ffffff" if self.dark_mode else "#212529"
        hover_color = "#3b3b3b" if self.dark_mode else "#e9ecef"
        checked_color = "#0d6efd"
        
        self.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: 4px;
                background-color: {bg_color};
                color: {text_color};
                font-size: 18px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:checked {{
                background-color: {checked_color};
                color: white;
            }}
        """)

class ColorButton(QPushButton):
    def __init__(self, color, dark_mode=False):
        super().__init__()
        self.setFixedSize(24, 24)
        self.color = color
        self.dark_mode = dark_mode
        self.update_style()
        
    def update_style(self):
        border_color = "#555555" if self.dark_mode else "#dee2e6"
        hover_color = "#0d6efd"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                border: 1px solid {border_color};
                border-radius: 4px;
                margin: 2px;
            }}
            QPushButton:hover {{
                border: 2px solid {hover_color};
            }}
            QPushButton:checked {{
                border: 2px solid {hover_color};
            }}
        """)

class CanvasTile:
    def __init__(self, size=512):
        self.pixmap = QPixmap(size + 2, size + 2)
        self.pixmap.fill(Qt.transparent)
        self.size = size
        self.dirty = False

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.init_canvas()
        
    def init_canvas(self):
        self.tile_size = 256
        self.tiles = {}
        self.last_point = None
        self.drawing = False
        self.brush_size = 3
        self.brush_color = QColor("#000000")
        self.tool = "pen"
        self.opacity = 1.0
        self.zoom = 1.0
        self.min_zoom = 0.05
        self.max_zoom = 10.0
        self.pan_start = None
        self.offset = QPointF(0, 0)
        self.background_color = Qt.white
        
        # Memory optimization
        self.max_tiles_in_memory = 500
        self.tile_access_times = {}
        self.cleanup_counter = 0
        self.cleanup_threshold = 25
        
        # Dynamic tile limit based on zoom
        self.base_tile_limit = 500
        
        self.visible_rect = QRectF(0, 0, self.width(), self.height())
        
        self.setMouseTracking(True)
        self.buffer_image = QPixmap(self.tile_size * 2, self.tile_size * 2)
        self.buffer_image.fill(Qt.transparent)
        
    def get_tile(self, tx, ty):
        """Get or create a tile at the specified coordinates"""
        key = (tx, ty)
        self.tile_access_times[key] = time.time()  # Update access time
        
        if key not in self.tiles:
            # Check if we need to clean up tiles
            self.cleanup_counter += 1
            if self.cleanup_counter >= self.cleanup_threshold:
                self.cleanup_unused_tiles()
                self.cleanup_counter = 0
            
            self.tiles[key] = CanvasTile(self.tile_size)
        return self.tiles[key]
        
    def get_visible_tiles(self):
        """Get the coordinates of all visible tiles"""
        visible_rect = QRectF(self.visible_rect)
        visible_rect.translate(-self.offset * self.zoom)
        visible_rect = QRectF(visible_rect.topLeft() / self.zoom, visible_rect.bottomRight() / self.zoom)
        
        # Adjust padding based on zoom level
        if self.zoom < 0.1:
            padding = 0  # No padding at very low zoom
        elif self.zoom < 0.5:
            padding = 1  # Minimal padding at low zoom
        else:
            padding = 2  # Normal padding at higher zoom
        
        min_tx = int(visible_rect.left() // self.tile_size) - padding
        max_tx = int(visible_rect.right() // self.tile_size) + padding
        min_ty = int(visible_rect.top() // self.tile_size) - padding
        max_ty = int(visible_rect.bottom() // self.tile_size) + padding
        
        return [(tx, ty) for tx in range(min_tx, max_tx + 1)
                        for ty in range(min_ty, max_ty + 1)]
        
    def point_to_tile(self, point):
        """Convert a point to tile coordinates and local position"""
        tx = int(point.x() // self.tile_size)
        ty = int(point.y() // self.tile_size)
        local_x = point.x() - tx * self.tile_size
        local_y = point.y() - ty * self.tile_size
        return (tx, ty), QPointF(local_x, local_y)
        
    def draw_line_between_points(self, start, end):
        """Draw a line that may cross multiple tiles"""
        start_tile, start_local = self.point_to_tile(start)
        end_tile, end_local = self.point_to_tile(end)
        
        # Get affected tiles
        min_tx = min(start_tile[0], end_tile[0]) - 1
        max_tx = max(start_tile[0], end_tile[0]) + 1
        min_ty = min(start_tile[1], end_tile[1]) - 1
        max_ty = max(start_tile[1], end_tile[1]) + 1
        
        # Draw on each affected tile
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                tile = self.get_tile(tx, ty)
                
                # Transform points to tile's local coordinates
                tile_start = QPointF(start.x() - (tx * self.tile_size - 1),
                                   start.y() - (ty * self.tile_size - 1))
                tile_end = QPointF(end.x() - (tx * self.tile_size - 1),
                                 end.y() - (ty * self.tile_size - 1))
                
                painter = QPainter(tile.pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                
                if self.tool in ["pen", "brush"]:
                    pen = QPen()
                    pen.setWidth(self.brush_size / self.zoom)
                    pen.setColor(self.brush_color)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setOpacity(self.opacity)
                    painter.setPen(pen)
                    painter.drawLine(tile_start, tile_end)
                elif self.tool == "eraser":
                    # Use composition mode to erase
                    painter.setCompositionMode(QPainter.CompositionMode_Clear)
                    pen = QPen()
                    pen.setWidth(self.brush_size * 2 / self.zoom)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.drawLine(tile_start, tile_end)
                
                painter.end()
                tile.dirty = True
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = self.map_to_image(event.position())
            self.drawing = True
            self.last_point = pos
            
            if self.tool in ["rectangle", "circle", "line"]:
                self.start_point = pos
                self.buffer_image.fill(Qt.transparent)
        elif event.button() == Qt.MiddleButton:
            self.pan_start = event.position()
            
    def mouseMoveEvent(self, event):
        if self.drawing:
            pos = self.map_to_image(event.position())
            
            if self.tool in ["rectangle", "circle", "line"]:
                self.buffer_image.fill(Qt.transparent)
                painter = QPainter(self.buffer_image)
                painter.setRenderHint(QPainter.Antialiasing)
                
                pen = QPen(self.brush_color)
                pen.setWidth(self.brush_size)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                
                if self.tool == "rectangle":
                    painter.drawRect(QRectF(self.start_point, pos))
                elif self.tool == "circle":
                    painter.drawEllipse(QRectF(self.start_point, pos))
                elif self.tool == "line":
                    painter.drawLine(self.start_point, pos)
                
                painter.end()
            else:
                self.draw_line_between_points(self.last_point, pos)
                self.last_point = pos
            
            self.update()
        elif event.buttons() & Qt.MiddleButton and self.pan_start is not None:
            delta = event.position() - self.pan_start
            self.offset += delta / self.zoom
            self.pan_start = event.position()
            self.update()
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.tool in ["rectangle", "circle", "line"]:
                pos = self.map_to_image(event.position())
                # Draw the shape on affected tiles
                min_x = min(self.start_point.x(), pos.x())
                max_x = max(self.start_point.x(), pos.x())
                min_y = min(self.start_point.y(), pos.y())
                max_y = max(self.start_point.y(), pos.y())
                
                min_tx = int(min_x // self.tile_size) - 1
                max_tx = int(max_x // self.tile_size) + 1
                min_ty = int(min_y // self.tile_size) - 1
                max_ty = int(max_y // self.tile_size) + 1
                
                for tx in range(min_tx, max_tx + 1):
                    for ty in range(min_ty, max_ty + 1):
                        tile = self.get_tile(tx, ty)
                        painter = QPainter(tile.pixmap)
                        painter.setRenderHint(QPainter.Antialiasing)
                        
                        # Transform points to tile's local coordinates
                        local_start = QPointF(self.start_point.x() - tx * self.tile_size,
                                            self.start_point.y() - ty * self.tile_size)
                        local_end = QPointF(pos.x() - tx * self.tile_size,
                                          pos.y() - ty * self.tile_size)
                        
                        pen = QPen(self.brush_color)
                        pen.setWidth(self.brush_size)
                        pen.setCapStyle(Qt.RoundCap)
                        pen.setJoinStyle(Qt.RoundJoin)
                        painter.setPen(pen)
                        
                        if self.tool == "rectangle":
                            painter.drawRect(QRectF(local_start, local_end))
                        elif self.tool == "circle":
                            painter.drawEllipse(QRectF(local_start, local_end))
                        elif self.tool == "line":
                            painter.drawLine(local_start, local_end)
                        
                        painter.end()
                        tile.dirty = True
                
                self.buffer_image.fill(Qt.transparent)
            
            self.drawing = False
            self.last_point = None
            self.update()
        elif event.button() == Qt.MiddleButton:
            self.pan_start = None
            
    def map_to_image(self, pos):
        return pos / self.zoom - self.offset
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.visible_rect = QRectF(0, 0, self.width(), self.height())
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(event.rect(), self.background_color)
        
        painter.translate(self.offset * self.zoom)
        painter.scale(self.zoom, self.zoom)
        
        visible_tiles = self.get_visible_tiles()
        
        for tx, ty in visible_tiles:
            tile = self.get_tile(tx, ty)
            x = tx * self.tile_size - 1
            y = ty * self.tile_size - 1
            painter.drawPixmap(x, y, tile.pixmap)
        
        if self.drawing and self.tool in ["rectangle", "circle", "line"]:
            painter.drawPixmap(0, 0, self.buffer_image)
            
    def clear_canvas(self):
        self.tiles.clear()
        self.update()
        
    def save_image(self, file_path):
        """Save only the used portion of the canvas"""
        if not self.tiles:
            return False
            
        # Find the actual bounds of drawn content
        min_tx = min(x for x, y in self.tiles.keys())
        max_tx = max(x for x, y in self.tiles.keys())
        min_ty = min(y for x, y in self.tiles.keys())
        max_ty = max(y for x, y in self.tiles.keys())
        
        # Create a minimal size result image
        width = (max_tx - min_tx + 1) * self.tile_size
        height = (max_ty - min_ty + 1) * self.tile_size
        
        # Use QImage instead of QPixmap for better memory handling
        result = QImage(width, height, QImage.Format_ARGB32)
        result.fill(Qt.white)
        
        painter = QPainter(result)
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                if (tx, ty) in self.tiles:
                    tile = self.tiles[(tx, ty)]
                    x = (tx - min_tx) * self.tile_size
                    y = (ty - min_ty) * self.tile_size
                    # Convert QPixmap to QImage for better memory handling
                    painter.drawImage(x, y, tile.pixmap.toImage())
        painter.end()
        
        return result.save(file_path)
        
    def load_image(self, image):
        """Load image with better memory handling"""
        self.clear_canvas()
        
        # Convert QPixmap to QImage for better memory handling
        if isinstance(image, QPixmap):
            image = image.toImage()
        
        # Calculate number of tiles needed
        width = image.width()
        height = image.height()
        
        tiles_x = (width + self.tile_size - 1) // self.tile_size
        tiles_y = (height + self.tile_size - 1) // self.tile_size
        
        # Process tiles in chunks to manage memory
        chunk_size = 10  # Process 10 tiles at a time
        for tx_chunk in range(0, tiles_x, chunk_size):
            for ty_chunk in range(0, tiles_y, chunk_size):
                tx_end = min(tx_chunk + chunk_size, tiles_x)
                ty_end = min(ty_chunk + chunk_size, tiles_y)
                
                for tx in range(tx_chunk, tx_end):
                    for ty in range(ty_chunk, ty_end):
                        tile = self.get_tile(tx, ty)
                        tile.pixmap.fill(Qt.transparent)
                        
                        painter = QPainter(tile.pixmap)
                        source_rect = QRect(tx * self.tile_size, ty * self.tile_size,
                                          self.tile_size, self.tile_size)
                        target_rect = QRect(0, 0, self.tile_size, self.tile_size)
                        painter.drawImage(target_rect, image, source_rect)
                        painter.end()
                
                # Force cleanup after each chunk
                self.cleanup_unused_tiles()
        
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            # Get the position before zoom
            old_pos = self.map_to_image(event.position())
            
            # Calculate zoom factor with smoother steps at extreme zooms
            if self.zoom < 0.1:
                zoom_factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1  # Smaller steps
            elif self.zoom > 5.0:
                zoom_factor = 1.05 if event.angleDelta().y() > 0 else 1/1.05  # Smaller steps
            else:
                zoom_factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2  # Normal steps
            
            new_zoom = self.zoom * zoom_factor
            
            # Clamp zoom level
            new_zoom = max(self.min_zoom, min(new_zoom, self.max_zoom))
            
            # Only update if zoom actually changed
            if new_zoom != self.zoom:
                self.zoom = new_zoom
                
                # Get the position after zoom
                new_pos = self.map_to_image(event.position())
                
                # Adjust offset to keep the point under cursor fixed
                self.offset += (new_pos - old_pos) * self.zoom
                
                # Force cleanup on zoom change
                self.cleanup_unused_tiles()
                
                self.update()
                
                # Update the window title with current zoom level
                if hasattr(self, 'window'):
                    zoom_percent = int(self.zoom * 100)
                    self.window().setWindowTitle(f"Paint X - Zoom: {zoom_percent}%")

    def get_max_tiles_for_zoom(self):
        """Calculate maximum allowed tiles based on current zoom level"""
        if self.zoom < 0.1:  # At very low zoom
            return int(self.base_tile_limit * 0.3)  # 30% of base limit
        elif self.zoom < 0.5:  # At low zoom
            return int(self.base_tile_limit * 0.6)  # 60% of base limit
        elif self.zoom > 5.0:  # At high zoom
            return int(self.base_tile_limit * 1.5)  # 150% of base limit
        else:
            return self.base_tile_limit

    def cleanup_unused_tiles(self):
        """Remove least recently used tiles if we're over the limit"""
        current_max_tiles = self.get_max_tiles_for_zoom()
        if len(self.tiles) <= current_max_tiles:
            return
            
        # Get visible tiles to ensure we don't remove them
        visible = set(self.get_visible_tiles())
        
        # Sort tiles by access time
        sorted_tiles = sorted(
            self.tile_access_times.items(),
            key=lambda x: x[1]
        )
        
        # Remove old tiles until we're under the limit
        for (tx, ty), _ in sorted_tiles:
            if len(self.tiles) <= current_max_tiles:
                break
                
            if (tx, ty) not in visible:
                self.tiles.pop((tx, ty), None)
                self.tile_access_times.pop((tx, ty), None)

class PaintX(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        
        # Set window icon
        icon = QIcon("icons/icon.png")
        self.setWindowIcon(icon)
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Paint X")
        self.setMinimumSize(800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(1, 1, 1, 1)
        
        # Top toolbar
        top_toolbar = QHBoxLayout()
        top_toolbar.setSpacing(2)
        main_layout.addLayout(top_toolbar)
        
        # Tools group
        tools_frame = QFrame()
        tools_frame.setMaximumHeight(50)
        tools_layout = QHBoxLayout(tools_frame)
        tools_layout.setSpacing(2)
        tools_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(tools_frame)
        
        # Tool buttons
        self.tool_buttons = {}
        tools = [
            ("✏️", "pen", "Pen Tool", "icons/pen.png"),
            ("🖌️", "brush", "Brush Tool", "icons/brush.png"),
            ("⬜", "rectangle", "Rectangle Tool", "icons/rectangle.png"),
            ("⭕", "circle", "Circle Tool", "icons/circle.png"),
            ("📏", "line", "Line Tool", "icons/line.png"),
            ("🧽", "eraser", "Eraser Tool", "icons/eraser.png")
        ]
        
        for text, tool, tooltip, icon_path in tools:
            btn = ToolButton(text, icon_name=icon_path, tooltip=tooltip, dark_mode=self.dark_mode)
            btn.clicked.connect(lambda checked, t=tool: self.set_tool(t))
            tools_layout.addWidget(btn)
            self.tool_buttons[tool] = btn
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setMaximumHeight(30)
        top_toolbar.addWidget(separator)
        
        # Color group
        colors_frame = QFrame()
        colors_frame.setMaximumHeight(50)
        colors_layout = QHBoxLayout(colors_frame)
        colors_layout.setSpacing(0)
        colors_layout.setContentsMargins(4, 4, 4, 4)
        top_toolbar.addWidget(colors_frame)
        
        # Primary colors
        primary_colors = [
            "#000000", "#ffffff", "#808080",  # Black, White, Gray
            "#ff0000", "#ff8000", "#ffff00",  # Red, Orange, Yellow
            "#00ff00", "#00ffff", "#0000ff",  # Green, Cyan, Blue
            "#ff00ff", "#800000", "#008000"   # Magenta, Dark Red, Dark Green
        ]
        
        for color in primary_colors:
            btn = ColorButton(color, dark_mode=self.dark_mode)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=color: self.set_color(QColor(c)))
            colors_layout.addWidget(btn)
            
        custom_color_btn = QPushButton()
        custom_color_btn.setFixedSize(24, 24)
        custom_color_btn.setIcon(QIcon("icons/color_picker.png"))
        custom_color_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin: 2px;
            }
            QPushButton:hover {
                border: 2px solid #0d6efd;
            }
        """)
        custom_color_btn.clicked.connect(self.choose_color)
        colors_layout.addWidget(custom_color_btn)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setMaximumHeight(30)
        top_toolbar.addWidget(separator2)
        
        # Settings group
        settings_frame = QFrame()
        settings_frame.setMaximumHeight(50)
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setSpacing(4)
        settings_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(settings_frame)
        
        # Size control
        size_label = QLabel("Size:")
        size_label.setFixedWidth(35)
        size_label.setStyleSheet("font-size: 12px;")
        settings_layout.addWidget(size_label)
        
        # Size preview
        self.size_preview = QLabel()
        self.size_preview.setFixedSize(32, 32)
        self.size_preview.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        settings_layout.addWidget(self.size_preview)
        
        # Size slider with non-linear scaling
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setFixedHeight(20)
        self.size_slider.setRange(0, 100)
        self.size_slider.setValue(10)
        self.size_slider.valueChanged.connect(self.change_size)
        settings_layout.addWidget(self.size_slider)
        
        # Update initial size preview
        self.update_size_preview(10)
        
        # Opacity control
        opacity_label = QLabel("Opacity:")
        opacity_label.setFixedWidth(50)
        opacity_label.setStyleSheet("font-size: 12px;")
        settings_layout.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setFixedWidth(100)
        self.opacity_slider.setFixedHeight(20)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        settings_layout.addWidget(self.opacity_slider)
        
        # Separator
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.VLine)
        separator3.setFrameShadow(QFrame.Sunken)
        separator3.setMaximumHeight(30)
        top_toolbar.addWidget(separator3)
        
        # File operations
        file_frame = QFrame()
        file_frame.setMaximumHeight(50)
        file_layout = QHBoxLayout(file_frame)
        file_layout.setSpacing(2)
        file_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(file_frame)
        
        # File operation buttons
        file_buttons = [
            ("💾", self.save_image, "icons/save.png"),
            ("📂", self.load_image, "icons/load.png"),
            ("🗑️", self.clear_canvas, "icons/clear.png"),
            ("🌙", self.toggle_dark_mode, "icons/dark_mode.png")
        ]
        
        for text, func, icon_path in file_buttons:
            btn = QPushButton(text)
            btn.setFixedSize(32, 32)
            if icon_path:
                icon = QIcon(icon_path)
                btn.setIcon(icon)
                btn.setIconSize(QSize(20, 20))
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
            """)
            btn.clicked.connect(func)
            file_layout.addWidget(btn)
        
        # Add stretch at the end to push everything to the left
        top_toolbar.addStretch(1)
        
        # Scroll area for canvas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)
        
        # Canvas
        canvas_frame = QFrame()
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = Canvas()
        canvas_layout.addWidget(self.canvas)
        
        scroll_area.setWidget(canvas_frame)
        
        # Set initial tool
        self.set_tool("pen")
        
        # Update styles
        self.update_styles()
        
    def update_styles(self):
        bg_color = "#2b2b2b" if self.dark_mode else "#f8f9fa"
        text_color = "#ffffff" if self.dark_mode else "#212529"
        border_color = "#555555" if self.dark_mode else "#dee2e6"
        
        self.setStyleSheet(f"""
            QMainWindow, QFrame {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                font-size: 11px;
                padding: 0px;
                margin: 0px;
            }}
            QSlider {{
                margin: 0px;
                padding: 0px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {border_color};
                height: 3px;
                background: {border_color};
                margin: 0px;
                border-radius: 1px;
            }}
            QSlider::handle:horizontal {{
                background: {'#ffffff' if self.dark_mode else '#0d6efd'};
                border: none;
                width: 10px;
                margin: -4px 0;
                border-radius: 5px;
            }}
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 2px;
                padding: 1px;
            }}
            QPushButton:hover {{
                background-color: {'#3b3b3b' if self.dark_mode else '#e9ecef'};
            }}
            QScrollArea {{
                border: none;
            }}
            QFrame[frameShape="5"] {{  /* Vertical line */
                background-color: {border_color};
                max-width: 1px;
                margin: 2px;
            }}
        """)
        
        # Update tool buttons
        for btn in self.tool_buttons.values():
            btn.dark_mode = self.dark_mode
            btn.update_style()
            
    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.update_styles()
        
    def choose_color(self):
        color = QColorDialog.getColor(initial=self.canvas.brush_color)
        if color.isValid():
            self.set_color(color)
            
    def set_color(self, color):
        self.canvas.brush_color = color
        # Update color button states
        for btn in self.findChildren(ColorButton):
            btn.setChecked(btn.color == color.name())
        
    def set_tool(self, tool):
        self.canvas.tool = tool
        for t, btn in self.tool_buttons.items():
            btn.setChecked(t == tool)
        
    def change_size(self, value):
        # Non-linear scaling: first 30% of slider covers sizes 1-20
        # remaining 70% covers sizes 21-100
        if value <= 30:
            # Linear mapping from 0-30 to 1-20
            size = 1 + (value * 19) / 30
        else:
            # Linear mapping from 31-100 to 21-100
            size = 20 + ((value - 30) * 80) / 70
            
        self.canvas.brush_size = int(size)
        self.update_size_preview(int(size))
        
    def change_opacity(self, value):
        self.canvas.opacity = value / 100.0
        
    def clear_canvas(self):
        self.canvas.clear_canvas()
        
    def save_image(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "",
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*.*)"
        )
        if file_path:
            self.canvas.save_image(file_path)
            
    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*.*)"
        )
        if file_path:
            image = QPixmap(file_path)
            if not image.isNull():
                self.canvas.load_image(image)

    def update_size_preview(self, size):
        pixmap = QPixmap(self.size_preview.size())
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw white background
        painter.fillRect(pixmap.rect(), Qt.white)
        
        # Draw black dot in center
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        
        # Calculate dot size (max 28px)
        dot_size = min(size, 28)
        center = pixmap.rect().center()
        painter.drawEllipse(center, dot_size/2, dot_size/2)
        
        painter.end()
        self.size_preview.setPixmap(pixmap)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PaintX()
    window.show()
    sys.exit(app.exec()) 