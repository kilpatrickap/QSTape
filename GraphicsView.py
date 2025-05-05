# GraphicsView.py (Partial - Focus on Pan/Zoom, basic event handling)
import math
from PyQt6.QtWidgets import QGraphicsView, QRubberBand
from PyQt6.QtGui import QPainter, QMouseEvent, QWheelEvent, QTransform, QColor, QPen, QPolygonF, QBrush
from PyQt6.QtCore import Qt, QRectF, QPointF, QRect, QPoint, pyqtSignal, QLineF


class GraphicsView(QGraphicsView):
    mouse_moved_scene_pos = pyqtSignal(QPointF)
    mouse_clicked_scene_pos = pyqtSignal(QPointF)
    mouse_double_clicked_scene_pos = pyqtSignal(QPointF) # For ending polygons etc.
    esc_pressed = pyqtSignal()
    selection_changed_signal = pyqtSignal(list) # Emit list of selected item IDs

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag) # Default to panning

        self._current_tool = "pan" # pan, select, measure_linear, measure_area, etc.
        self._is_panning = False
        self._pan_start_pos = QPoint()
        self._rubber_band = None
        self._selecting = False

        # Variables for drawing tools
        self._is_drawing = False
        self._start_point_scene = None
        self._current_points_scene = [] # For multi-point tools like area
        self._temp_item = None # Item being drawn (e.g., QGraphicsLineItem)


    def set_tool(self, tool_name):
        self._current_tool = tool_name
        print(f"Tool changed to: {tool_name}")
        self.reset_drawing_state() # Clear temps when switching tool
        if tool_name == "pan":
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif tool_name == "select":
             self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) # Or handle manually
             self.setCursor(Qt.CursorShape.ArrowCursor)
        else: # Drawing tools
            self.setDragMode(QGraphicsView.DragMode.NoDrag) # Disable built-in drag for drawing
            self.setCursor(Qt.CursorShape.CrossCursor)


    def get_tool(self):
        return self._current_tool

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = 1.0

        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        elif event.angleDelta().y() < 0:
            zoom_factor = zoom_out_factor
        else: # Should not happen with vertical wheel, but check anyway
            event.ignore()
            return

        # Prevent excessive zoom out/in (optional)
        current_scale = self.transform().m11() # Get current horizontal scale
        if current_scale * zoom_factor < 0.01: # Min zoom level
             return
        if current_scale * zoom_factor > 100: # Max zoom level
            return

        self.scale(zoom_factor, zoom_factor)
        event.accept() # Accept the event

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        print(f"Mouse Press at View:{event.pos()}, Scene:{scene_pos}") # Debug

        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            if self._current_tool == "pan":
                 # Let ScrollHandDrag handle it
                 super().mousePressEvent(event)
                 return
            elif self._current_tool == "select":
                # Could start rubber band selection here or let QGraphicsView handle it
                super().mousePressEvent(event) # Let view handle item selection start
                return

            elif self._current_tool in ["measure_linear", "set_scale"]:
                if not self._is_drawing:
                    self._is_drawing = True
                    self._start_point_scene = scene_pos
                    self._current_points_scene = [self._start_point_scene]
                    # Create a temporary visual item (e.g., line)
                    self._temp_item = self.scene().addLine(
                        QLineF(self._start_point_scene, self._start_point_scene),
                        QPen(QColor("red"), 1 / self.transform().m11(), Qt.PenStyle.DashLine) # Thin dashed line
                    )
                    self._temp_item.setZValue(1000) # Ensure it's on top
                    print("Linear/Scale: Started drawing")
                else: # Second click finishes linear/scale
                    self.finish_current_drawing(scene_pos)

            # --- Add logic for Area, Count, Text, Curve etc. ---
            elif self._current_tool == "measure_area":
                 self._is_drawing = True # Keep drawing flag until finished
                 self._current_points_scene.append(scene_pos)
                 self.update_temp_polygon()
                 print(f"Area: Added point {len(self._current_points_scene)}")

            else:
                 super().mousePressEvent(event) # Default behaviour for other cases

            self.mouse_clicked_scene_pos.emit(scene_pos) # Emit signal for MainWindow logic
            event.accept() # Accept event if handled here

        else:
            super().mousePressEvent(event) # Pass other buttons (like right-click) up

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        self.mouse_moved_scene_pos.emit(scene_pos) # Emit for status bar update

        if self._is_panning and event.buttons() & Qt.MouseButton.MiddleButton:
            delta = event.pos() - self._pan_start_pos
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x())
            vs.setValue(vs.value() - delta.y())
            self._pan_start_pos = event.pos()
            event.accept()
            return

        if self._is_drawing and event.buttons() & Qt.MouseButton.LeftButton:
            if self._current_tool in ["measure_linear", "set_scale"] and self._temp_item and self._start_point_scene:
                # Update temporary line end point
                self._temp_item.setLine(QLineF(self._start_point_scene, scene_pos))
                event.accept()
                return
            elif self._current_tool == "measure_area" and self._temp_item and len(self._current_points_scene) > 0:
                # Update the last segment of the temporary polygon preview
                if len(self._current_points_scene) >= 1:
                    preview_points = self._current_points_scene + [scene_pos]
                    poly = QPolygonF(preview_points)
                    self._temp_item.setPolygon(poly)
                event.accept()
                return
            # Add logic for other drawing tools if needed (e.g., rect, circle resize)

        # For selection rubber band
        super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        print(f"Mouse Release at View:{event.pos()}, Scene:{scene_pos}") # Debug

        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._current_tool == "pan" else self.cursor()) # Restore appropriate cursor
            event.accept()
            return

        elif event.button() == Qt.MouseButton.LeftButton:
             if self._current_tool == "pan":
                 super().mouseReleaseEvent(event)
                 return
             elif self._current_tool == "select":
                 super().mouseReleaseEvent(event)
                 # Emit signal with selected items AFTER the event is processed by QGraphicsView
                 selected_graphics_items = self.scene().selectedItems()
                 # Assume items have a custom 'db_id' property or similar
                 selected_db_ids = [item.data(Qt.ItemDataRole.UserRole + 1) for item in selected_graphics_items if item.data(Qt.ItemDataRole.UserRole + 1) is not None]
                 self.selection_changed_signal.emit(selected_db_ids)
                 return

             # Don't finish linear/scale on release, wait for second click in mousePressEvent
             # Area also continues until double-click or key press

             else:
                 super().mouseReleaseEvent(event)

        else: # Other buttons
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            if self._current_tool == "measure_area" and self._is_drawing and len(self._current_points_scene) >= 3:
                self.finish_current_drawing(scene_pos, is_double_click=True) # Final point is the double-click pos
                event.accept()
                return
            # Could be used for editing text items, etc.
            self.mouse_double_clicked_scene_pos.emit(scene_pos)

        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Escape pressed")
            if self._is_drawing:
                self.reset_drawing_state()
                self.set_tool(self.get_tool()) # Re-apply cursor etc.
            self.esc_pressed.emit() # Signal MainWindow if needed
            event.accept()
            return
        super().keyPressEvent(event)

    def reset_drawing_state(self):
        """Cleans up temporary items and resets drawing flags."""
        print("Resetting drawing state")
        if self._temp_item:
            self.scene().removeItem(self._temp_item)
            self._temp_item = None
        self._is_drawing = False
        self._start_point_scene = None
        self._current_points_scene = []

    def finish_current_drawing(self, end_pos_scene, is_double_click=False):
        """Finalizes the current drawing operation."""
        print(f"Finishing drawing for tool: {self._current_tool}")
        if not self._is_drawing:
            return

        final_points = []
        if self._current_tool in ["measure_linear", "set_scale"]:
             if self._start_point_scene:
                 final_points = [self._start_point_scene, end_pos_scene]
                 # Emit signal with points for MainWindow to handle calculation/saving
                 # Example: self.parent().handle_measurement_finished(self._current_tool, final_points)
                 print(f"Finished {self._current_tool}: {final_points}")

        elif self._current_tool == "measure_area":
             if is_double_click and len(self._current_points_scene) >= 3:
                 final_points = self._current_points_scene # Use points collected so far
                 # Emit signal
                 # Example: self.parent().handle_measurement_finished(self._current_tool, final_points)
                 print(f"Finished {self._current_tool} (double-click): {final_points}")
             elif not is_double_click: # Area requires double-click or key press to finish normally
                 return # Don't finish on single click


        # --- Add finishing logic for other tools ---

        # Emit a signal to the main window instead of calling directly
        if final_points:
            # Assuming MainWindow has a slot connected to this signal
            # self.measurement_complete.emit(self._current_tool, final_points)
            # For now, just print
            print(f"Measurement complete: Tool={self._current_tool}, Points={final_points}")


        self.reset_drawing_state() # Clean up temps and reset state for next measurement


    def update_temp_polygon(self):
         """Updates or creates the temporary polygon item for area drawing."""
         if not self._current_points_scene:
             return

         polygon = QPolygonF(self._current_points_scene)

         if self._temp_item is None:
             pen_width = 1 / self.transform().m11() # Scale pen width with zoom
             self._temp_item = self.scene().addPolygon(
                 polygon,
                 QPen(QColor("orange"), pen_width, Qt.PenStyle.DashLine),
                 QBrush(Qt.BrushStyle.NoBrush) # No fill for temp item
             )
             self._temp_item.setZValue(1000) # Ensure it's on top
         else:
              # Update existing temp polygon
             self._temp_item.setPolygon(polygon)


    def get_pixel_distance(self, p1: QPointF, p2: QPointF):
        """Calculate distance between two QPointF points."""
        return math.sqrt((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)