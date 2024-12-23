import sys
import time
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QColorDialog,
                               QSpinBox, QFileDialog, QSlider, QFrame, QScrollArea,
                               QInputDialog, QFontDialog)
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

class TextItem:
    def __init__(self, text, pos, font, color):
        self.text = text
        self.pos = pos
        self.font = font
        self.color = color
        self.scale = 1.0
        self.rotation = 0
        self.selected = False
        self.dragging = False
        self.drag_start = None
        self.original_pos = None
        self.show_controls = False
        self.last_click_time = 0

class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.init_canvas()
        self.degree_text = ""
        self.snap_text = ""
        self.degree_pos = None
        self.is_snapped = False
        
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
        self.text_items = {}
        self.selected_text = None
        self.rotating = False
        self.scaling = False
        self.rotation_start = None
        self.scale_start = None
        
        self.max_tiles_in_memory = 500
        self.tile_access_times = {}
        self.cleanup_counter = 0
        self.cleanup_threshold = 25
        self.base_tile_limit = 500
        
        self.visible_rect = QRectF(0, 0, self.width(), self.height())
        
        self.setMouseTracking(True)
        self.buffer_image = QPixmap(self.tile_size * 2, self.tile_size * 2)
        self.buffer_image.fill(Qt.transparent)
        
    def get_tile(self, tx, ty):
        key = (tx, ty)
        self.tile_access_times[key] = time.time()
        
        if key not in self.tiles:
            self.cleanup_counter += 1
            if self.cleanup_counter >= self.cleanup_threshold:
                self.cleanup_unused_tiles()
                self.cleanup_counter = 0
            
            self.tiles[key] = CanvasTile(self.tile_size)
        return self.tiles[key]
        
    def get_visible_tiles(self):
        visible_rect = QRectF(-self.offset.x(), -self.offset.y(),
                            self.width() / self.zoom,
                            self.height() / self.zoom)
        
        min_tx = int(visible_rect.left() // self.tile_size) - 1
        max_tx = int(visible_rect.right() // self.tile_size) + 1
        min_ty = int(visible_rect.top() // self.tile_size) - 1
        max_ty = int(visible_rect.bottom() // self.tile_size) + 1
        
        return [(tx, ty) for tx in range(min_tx, max_tx + 1)
                        for ty in range(min_ty, max_ty + 1)]
        
    def point_to_tile(self, point):
        tx = int(point.x() // self.tile_size)
        ty = int(point.y() // self.tile_size)
        local_x = point.x() - tx * self.tile_size
        local_y = point.y() - ty * self.tile_size
        return (tx, ty), QPointF(local_x, local_y)
        
    def draw_line_between_points(self, start, end):
        start_tile, start_local = self.point_to_tile(start)
        end_tile, end_local = self.point_to_tile(end)
        
        min_tx = min(start_tile[0], end_tile[0]) - 1
        max_tx = max(start_tile[0], end_tile[0]) + 1
        min_ty = min(start_tile[1], end_tile[1]) - 1
        max_ty = max(start_tile[1], end_tile[1]) + 1
        
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                tile = self.get_tile(tx, ty)
                
                tile_start = QPointF(start.x() - (tx * self.tile_size - 1),
                                   start.y() - (ty * self.tile_size - 1))
                tile_end = QPointF(end.x() - (tx * self.tile_size - 1),
                                 end.y() - (ty * self.tile_size - 1))
                
                painter = QPainter(tile.pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                
                if self.tool in ["pen", "brush"]:
                    pen = QPen()
                    pen.setWidthF(self.brush_size / self.zoom)
                    pen.setColor(self.brush_color)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setOpacity(self.opacity)
                    painter.setPen(pen)
                    painter.drawLine(tile_start, tile_end)
                elif self.tool == "eraser":
                    painter.setCompositionMode(QPainter.CompositionMode_Clear)
                    pen = QPen()
                    pen.setWidthF(self.brush_size * 2 / self.zoom)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.drawLine(tile_start, tile_end)
                
                painter.end()
                tile.dirty = True

    def add_text(self, text, pos, font, color):
        font.setPointSize(12)
        text_item = TextItem(text, pos, font, color)
        tx = int(pos.x() // self.tile_size)
        ty = int(pos.y() // self.tile_size)
        tile_key = (tx, ty)
        
        if tile_key not in self.text_items:
            self.text_items[tile_key] = []
        self.text_items[tile_key].append(text_item)
        
        self.selected_text = text_item
        text_item.selected = True
        self.update()

    def get_text_bounds(self, text_item):
        temp_pixmap = QPixmap(1, 1)
        painter = QPainter(temp_pixmap)
        painter.setFont(text_item.font)
        text_rect = painter.fontMetrics().boundingRect(text_item.text)
        painter.end()
        
        width = text_rect.width() * text_item.scale
        height = text_rect.height() * text_item.scale
        
        transform = QTransform()
        transform.translate(text_item.pos.x(), text_item.pos.y())
        transform.rotate(text_item.rotation)
        
        points = [
            transform.map(QPointF(-width/2, -height/2)),
            transform.map(QPointF(width/2, -height/2)),
            transform.map(QPointF(width/2, height/2)),
            transform.map(QPointF(-width/2, height/2))
        ]
        
        return points

    def get_text_handles(self, text_item):
        bounds = self.get_text_bounds(text_item)
        center = text_item.pos
        rotation_offset = 30 / self.zoom
        top_center = QPointF(center.x(), min(p.y() for p in bounds) - rotation_offset)
        bottom_right = QPointF(max(p.x() for p in bounds), max(p.y() for p in bounds))
        
        return top_center, bottom_right

    def is_point_in_text(self, point, text_item):
        bounds = self.get_text_bounds(text_item)
        path = QPainterPath()
        path.moveTo(bounds[0])
        for p in bounds[1:]:
            path.lineTo(p)
        path.closeSubpath()
        return path.contains(point)

    def is_near_point(self, point1, point2, threshold=15):
        scaled_threshold = threshold / self.zoom
        return (point1 - point2).manhattanLength() < scaled_threshold

    def draw_text_items(self, painter):
        visible_tiles = self.get_visible_tiles()
        
        for tx, ty in visible_tiles:
            if (tx, ty) in self.text_items:
                for item in self.text_items[(tx, ty)]:
                    painter.save()
                    painter.scale(self.zoom, self.zoom)
                    painter.translate(self.offset.x(), self.offset.y())
                    painter.translate(item.pos.x(), item.pos.y())
                    painter.rotate(item.rotation)
                    painter.scale(item.scale, item.scale)
                    
                    painter.setFont(item.font)
                    painter.setPen(QPen(item.color))
                    
                    text_rect = painter.fontMetrics().boundingRect(item.text)
                    painter.drawText(-text_rect.width()/2, text_rect.height()/2, item.text)
                    
                    if item.selected and item.show_controls:
                        painter.resetTransform()
                        painter.scale(self.zoom, self.zoom)
                        painter.translate(self.offset.x(), self.offset.y())
                        bounds = self.get_text_bounds(item)
                        painter.setPen(QPen(Qt.blue, 1/self.zoom, Qt.DashLine))
                        path = QPainterPath()
                        path.moveTo(bounds[0])
                        for p in bounds[1:]:
                            path.lineTo(p)
                        path.closeSubpath()
                        painter.drawPath(path)
                        rotation_handle, scale_handle = self.get_text_handles(item)
                        
                        painter.setPen(QPen(Qt.blue, 2/self.zoom))
                        painter.setBrush(Qt.white)
                        
                        handle_size = 12/self.zoom
                        painter.drawEllipse(rotation_handle, handle_size/2, handle_size/2)
                        painter.drawLine(item.pos, rotation_handle)
                        
                        painter.drawRect(QRectF(scale_handle.x() - handle_size/2, 
                                              scale_handle.y() - handle_size/2,
                                              handle_size, handle_size))
                    
                    painter.restore()

    def mousePressEvent(self, event):
        pos = self.map_to_image(event.position())
        
        if event.button() == Qt.LeftButton:
            if self.tool in ["text", "select"]:
                if self.selected_text:
                    rotation_handle, scale_handle = self.get_text_handles(self.selected_text)
                    if self.is_near_point(pos, rotation_handle):
                        self.rotating = True
                        center = self.selected_text.pos
                        self.rotation_start = math.degrees(math.atan2(pos.y() - center.y(), 
                                                                    pos.x() - center.x()))
                        self.initial_rotation = self.selected_text.rotation
                    elif self.is_near_point(pos, scale_handle):
                        self.scaling = True
                        self.scale_start = pos
                        self.scale_origin = self.selected_text.pos
                        self.start_scale = self.selected_text.scale
                        self.start_dist = math.sqrt((pos.x() - self.scale_origin.x())**2 + 
                                                  (pos.y() - self.scale_origin.y())**2)
                    else:
                        self.selected_text.dragging = True
                        self.selected_text.drag_start = pos
                        self.selected_text.original_pos = self.selected_text.pos
                else:
                    if self.selected_text:
                        self.selected_text.selected = False
                        self.selected_text.show_controls = False
                        self.selected_text = None
                    
                    clicked_text = None
                    for tile_texts in self.text_items.values():
                        for item in reversed(tile_texts):
                            if self.is_point_in_text(pos, item):
                                clicked_text = item
                                break
                        if clicked_text:
                            break
                    
                    if clicked_text:
                        self.selected_text = clicked_text
                        self.selected_text.selected = True
                        self.selected_text.show_controls = True
                    elif self.tool == "text":
                        text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
                        if ok and text:
                            font_ok, font = QFontDialog.getFont()
                            if font_ok:
                                self.add_text(text, pos, font, self.brush_color)
            else:
                if self.selected_text:
                    self.selected_text.selected = False
                    self.selected_text.show_controls = False
                    self.selected_text = None
                self.drawing = True
                self.last_point = pos
                self.start_point = pos

    def mouseMoveEvent(self, event):
        pos = self.map_to_image(event.position())
        
        if event.button() == Qt.MiddleButton and self.pan_start:
            delta = event.position() - self.pan_start
            self.offset += delta / self.zoom
            self.pan_start = event.position()
            self.update_window_title()
            self.update()
            
        if self.drawing and self.last_point:
            if self.tool in ["pen", "brush", "eraser"]:
                self.draw_line_between_points(self.last_point, pos)
            self.last_point = pos
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.selected_text:
                if self.selected_text.dragging:
                    self.selected_text.dragging = False
                elif self.rotating:
                    self.rotating = False
                elif self.scaling:
                    self.scaling = False
                self.selected_text.show_controls = True
            elif self.drawing:
                if self.tool in ["rectangle", "circle", "line"]:
                    pos = self.map_to_image(event.position())
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
        
        # Draw canvas content
        painter.fillRect(event.rect(), self.background_color)
        
        painter.scale(self.zoom, self.zoom)
        painter.translate(self.offset.x(), self.offset.y())
        
        visible_tiles = self.get_visible_tiles()
        
        for tx, ty in visible_tiles:
            tile = self.get_tile(tx, ty)
            x = tx * self.tile_size - 1
            y = ty * self.tile_size - 1
            painter.drawPixmap(x, y, tile.pixmap)
        
        if self.drawing and self.tool in ["rectangle", "circle", "line"]:
            painter.drawPixmap(0, 0, self.buffer_image)
        
        painter.resetTransform()
        self.draw_text_items(painter)
        
        if self.rotating and self.selected_text and self.degree_pos:
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            
            degree_text = f"{int(self.selected_text.rotation)}°"
            
            text_rect = painter.fontMetrics().boundingRect(degree_text)
            text_rect.moveCenter(self.degree_pos.toPoint())
            text_rect.adjust(-5, -2, 5, 2)
            
            painter.fillRect(text_rect, QColor(0, 120, 215))
            painter.setPen(Qt.white)
            painter.drawText(self.degree_pos, degree_text)
        
    def clear_canvas(self):
        self.tiles.clear()
        self.update()
        
    def save_image(self, file_path):
        if not self.tiles:
            return False
            
        min_tx = min(x for x, y in self.tiles.keys())
        max_tx = max(x for x, y in self.tiles.keys())
        min_ty = min(y for x, y in self.tiles.keys())
        max_ty = max(y for x, y in self.tiles.keys())
        
        width = (max_tx - min_tx + 1) * self.tile_size
        height = (max_ty - min_ty + 1) * self.tile_size
        
        result = QImage(width, height, QImage.Format_ARGB32)
        result.fill(Qt.white)
        
        painter = QPainter(result)
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                if (tx, ty) in self.tiles:
                    tile = self.tiles[(tx, ty)]
                    x = (tx - min_tx) * self.tile_size
                    y = (ty - min_ty) * self.tile_size
                    painter.drawImage(x, y, tile.pixmap.toImage())
        painter.end()
        
        return result.save(file_path)
        
    def load_image(self, image):
        self.clear_canvas()
        
        if isinstance(image, QPixmap):
            image = image.toImage()
        
        width = image.width()
        height = image.height()
        
        tiles_x = (width + self.tile_size - 1) // self.tile_size
        tiles_y = (height + self.tile_size - 1) // self.tile_size
        
        chunk_size = 10 
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
                
                self.cleanup_unused_tiles()
        
        self.update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if self.selected_text:
                self.selected_text.show_controls = False
            
            zoom_factor = 1.2
            if event.angleDelta().y() < 0:
                zoom_factor = 1 / zoom_factor
                
            old_zoom = self.zoom
            self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * zoom_factor))
            
            if old_zoom != self.zoom:
                mouse_pos = event.position()
                self.offset = mouse_pos/self.zoom - mouse_pos/old_zoom + self.offset
            
            self.update()
        else:
            super().wheelEvent(event)

    def get_max_tiles_for_zoom(self):
        if self.zoom < 0.1:  
            return int(self.base_tile_limit * 0.3)  
        elif self.zoom < 0.5:
            return int(self.base_tile_limit * 0.6)  
        elif self.zoom > 5.0:
            return int(self.base_tile_limit * 1.5)  
        else:
            return self.base_tile_limit

    def cleanup_unused_tiles(self):
        current_max_tiles = self.get_max_tiles_for_zoom()
        if len(self.tiles) <= current_max_tiles:
            return
            
        visible = set(self.get_visible_tiles())
        
        sorted_tiles = sorted(
            self.tile_access_times.items(),
            key=lambda x: x[1]
        )
        
        for (tx, ty), _ in sorted_tiles:
            if len(self.tiles) <= current_max_tiles:
                break
                
            if (tx, ty) not in visible:
                self.tiles.pop((tx, ty), None)
                self.tile_access_times.pop((tx, ty), None)

    def update_window_title(self):
        zoom_percentage = int(self.zoom * 100)
        self.parent().setWindowTitle(f"Paint X - {zoom_percentage}% Zoom")

class PaintX(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        icon = QIcon("icons/icon.png")
        self.setWindowIcon(icon)
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Paint X - 100% Zoom")
        self.setMinimumSize(800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(1, 1, 1, 1)
        
        top_toolbar = QHBoxLayout()
        top_toolbar.setSpacing(2)
        main_layout.addLayout(top_toolbar)
        
        tools_frame = QFrame()
        tools_frame.setMaximumHeight(50)
        tools_layout = QHBoxLayout(tools_frame)
        tools_layout.setSpacing(2)
        tools_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(tools_frame)
        
        self.tool_buttons = {}
        tools = [
            ("🖱️", "select", "Selection Tool", "icons/mouse.png"),
            ("✏️", "pen", "Pen Tool", "icons/pen.png"),
            ("🖌️", "brush", "Brush Tool", "icons/brush.png"),
            ("⬜", "rectangle", "Rectangle Tool", "icons/rectangle.png"),
            ("⭕", "circle", "Circle Tool", "icons/circle.png"),
            ("📏", "line", "Line Tool", "icons/line.png"),
            ("🧽", "eraser", "Eraser Tool", "icons/eraser.png"),
            ("T", "text", "Text Tool", "icons/text.png")
        ]

        for text, tool, tooltip, icon_path in tools:
            btn = ToolButton(text, icon_name=icon_path, tooltip=tooltip, dark_mode=self.dark_mode)
            btn.clicked.connect(lambda checked, t=tool: self.set_tool(t))
            tools_layout.addWidget(btn)
            self.tool_buttons[tool] = btn
        
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setMaximumHeight(30)
        top_toolbar.addWidget(separator)
        
        colors_frame = QFrame()
        colors_frame.setMaximumHeight(50)
        colors_layout = QHBoxLayout(colors_frame)
        colors_layout.setSpacing(0)
        colors_layout.setContentsMargins(4, 4, 4, 4)
        top_toolbar.addWidget(colors_frame)
        
        primary_colors = [
            "#000000", "#ffffff", "#808080",  
            "#ff0000", "#ff8000", "#ffff00",  
            "#00ff00", "#00ffff", "#0000ff",  
            "#ff00ff", "#800000", "#008000"  
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
        
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setMaximumHeight(30)
        top_toolbar.addWidget(separator2)
        
        settings_frame = QFrame()
        settings_frame.setMaximumHeight(50)
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setSpacing(4)
        settings_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(settings_frame)
        
        size_label = QLabel("Size:")
        size_label.setFixedWidth(35)
        size_label.setStyleSheet("font-size: 12px;")
        settings_layout.addWidget(size_label)
        
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
        
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setFixedHeight(20)
        self.size_slider.setRange(0, 100)
        self.size_slider.setValue(10)
        self.size_slider.valueChanged.connect(self.change_size)
        settings_layout.addWidget(self.size_slider)
        
        self.update_size_preview(10)
        
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
        
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.VLine)
        separator3.setFrameShadow(QFrame.Sunken)
        separator3.setMaximumHeight(30)
        top_toolbar.addWidget(separator3)
        
        file_frame = QFrame()
        file_frame.setMaximumHeight(50)
        file_layout = QHBoxLayout(file_frame)
        file_layout.setSpacing(2)
        file_layout.setContentsMargins(2, 2, 2, 2)
        top_toolbar.addWidget(file_frame)
        
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
        
        top_toolbar.addStretch(1)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)
        
        canvas_frame = QFrame()
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = Canvas()
        canvas_layout.addWidget(self.canvas)
        
        scroll_area.setWidget(canvas_frame)
        
        self.set_tool("pen")
        
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
        for btn in self.findChildren(ColorButton):
            btn.setChecked(btn.color == color.name())
        
    def set_tool(self, tool):
        self.canvas.tool = tool
        for t, btn in self.tool_buttons.items():
            btn.setChecked(t == tool)
        
    def change_size(self, value):
        if value <= 30:
            size = 1 + (value * 19) / 30
        else:
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
        
        painter.fillRect(pixmap.rect(), Qt.white)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        
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