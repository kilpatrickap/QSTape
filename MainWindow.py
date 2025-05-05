# MainWindow.py (Partial - Core structure, PDF/Image loading, basic actions)
import os
import math
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFileDialog, QMessageBox,
    QGraphicsScene, QLabel, QStatusBar, QDockWidget, QListWidget,
    QInputDialog, QLineEdit, QDialog, QPushButton, QFormLayout, QSpinBox,
    QListWidgetItem, QMenu, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QImage, QAction, QIcon, QColor, QPen, QPainterPath, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QSize, pyqtSlot, QLineF
import fitz # PyMuPDF
from PyQt6.QtGui import QImage, QPixmap # Make sure QImage is imported

# Assume other imports like GraphicsView, ProjectManager are available
from GraphicsView import GraphicsView # Assuming GraphicsView.py exists
from ProjectManager import ProjectManager # Assuming ProjectManager.py exists
# from items import LinearMeasurementItem, AreaMeasurementItem # etc. - Placeholder


# Helper function (consider moving to utils.py)
def calculate_distance(p1: QPointF, p2: QPointF):
    """Calculates Euclidean distance between two QPointF points."""
    return math.sqrt((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)

# Placeholder for custom graphics items (move to items.py later)
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush

class LinearMeasurementItem(QGraphicsLineItem):
    def __init__(self, p1, p2, db_id=None, layer_id=None, value=0, unit="", parent=None):
        super().__init__(p1.x(), p1.y(), p2.x(), p2.y(), parent)
        self.setPen(QPen(QColor("green"), 2, Qt.PenStyle.SolidLine)) # Example style
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable) # Basic move
        self.db_id = db_id
        self.layer_id = layer_id
        self.value = value
        self.unit = unit
        self.item_type = "linear"
        self.setData(Qt.ItemDataRole.UserRole + 1, self.db_id) # Store db_id for easy retrieval

    def get_data_for_db(self):
        line = self.line()
        return {
            'id': self.db_id,
            'layer_id': self.layer_id,
            'type': self.item_type,
            'points': [(line.p1().x(), line.p1().y()), (line.p2().x(), line.p2().y())],
            'value': self.value,
            'unit': self.unit,
            'style': {'color': self.pen().color().name(), 'width': self.pen().width()}
        }

# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyTakeoff - Advanced")
        self.setGeometry(100, 100, 1200, 800)

        # --- State Variables ---
        self.project_manager = ProjectManager()
        self.current_project_path = None
        self.project_data = {} # Holds metadata like scale, source path, etc.
        self.pdf_images = [] # Holds QPixmap pages if PDF is loaded
        self.current_page_index = 0
        self.background_item = None # QGraphicsPixmapItem for the image/PDF page

        # Active Layer Tracking
        self.layers = [] # List of layer dicts {'id': ..., 'name': ..., 'visible': ..., 'color': ...}
        self.active_layer_id = None

        # --- Central Widget ---
        self.scene = QGraphicsScene(self)
        self.view = GraphicsView(self.scene, self)
        self.setCentralWidget(self.view)

        # --- UI Elements ---
        self.create_actions()
        self.create_docks() # For Layers and potentially Results
        self.create_menus()
        self.create_toolbars()
        self.create_status_bar()

        # --- Connect Signals ---
        self.view.mouse_moved_scene_pos.connect(self.update_status_mouse_pos)
        self.view.esc_pressed.connect(self.handle_escape_press)
        # Connect drawing finish signals (conceptual - need signal in GraphicsView)
        # self.view.measurement_complete.connect(self.handle_measurement_finished)
        self.view.mouse_clicked_scene_pos.connect(self.handle_view_click)
        self.view.mouse_double_clicked_scene_pos.connect(self.handle_view_double_click)


        # --- Initialization ---
        self.set_status("Ready. Create or Open a Project.")
        self._update_actions_state() # Disable actions initially


    def create_actions(self):
        # File Actions
        self.new_project_action = QAction(QIcon.fromTheme("document-new"), "&New Project...", self)
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action = QAction(QIcon.fromTheme("document-open"), "&Open Project...", self)
        self.open_project_action.triggered.connect(self.open_project)
        self.save_project_action = QAction(QIcon.fromTheme("document-save"), "&Save Project", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.save_project_as_action = QAction(QIcon.fromTheme("document-save-as"), "Save Project &As...", self)
        self.save_project_as_action.triggered.connect(self.save_project_as)
        self.exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", self)
        self.exit_action.triggered.connect(self.close)

        # View Actions (Zoom/Pan are handled by view interaction, but could have buttons)
        self.zoom_in_action = QAction(QIcon.fromTheme("zoom-in"), "Zoom &In", self)
        self.zoom_in_action.triggered.connect(lambda: self.view.scale(1.2, 1.2))
        self.zoom_out_action = QAction(QIcon.fromTheme("zoom-out"), "Zoom &Out", self)
        self.zoom_out_action.triggered.connect(lambda: self.view.scale(1/1.2, 1/1.2))
        self.zoom_fit_action = QAction(QIcon.fromTheme("zoom-fit-best"), "Zoom to &Fit", self)
        self.zoom_fit_action.triggered.connect(self.zoom_to_fit)

        # Tool Actions
        self.select_tool_action = QAction(QIcon.fromTheme("edit-select"), "&Select Tool", self, checkable=True)
        self.select_tool_action.triggered.connect(lambda: self.set_tool("select"))
        self.pan_tool_action = QAction(QIcon.fromTheme("transform-move"), "&Pan Tool", self, checkable=True)
        self.pan_tool_action.triggered.connect(lambda: self.set_tool("pan"))
        self.set_scale_action = QAction(QIcon.fromTheme("measurement-length"), "Set &Scale", self, checkable=True)
        self.set_scale_action.triggered.connect(lambda: self.set_tool("set_scale"))
        self.measure_linear_action = QAction(QIcon.fromTheme("draw-line"), "Measure &Linear", self, checkable=True)
        self.measure_linear_action.triggered.connect(lambda: self.set_tool("measure_linear"))
        self.measure_area_action = QAction(QIcon.fromTheme("draw-polygon"), "Measure &Area", self, checkable=True)
        self.measure_area_action.triggered.connect(lambda: self.set_tool("measure_area"))
        # Add actions for Count, Text, Curve, Shapes...

        # PDF Page Navigation (Disabled initially)
        self.prev_page_action = QAction(QIcon.fromTheme("go-previous"), "&Previous Page", self)
        self.prev_page_action.triggered.connect(self.prev_page)
        self.next_page_action = QAction(QIcon.fromTheme("go-next"), "&Next Page", self)
        self.next_page_action.triggered.connect(self.next_page)
        self.goto_page_action = QAction(QIcon.fromTheme("go-jump"), "&Go To Page...", self)
        self.goto_page_action.triggered.connect(self.goto_page)

        # Layer Actions
        self.add_layer_action = QAction(QIcon.fromTheme("list-add"), "Add Layer...", self)
        self.add_layer_action.triggered.connect(self.add_layer)
        self.remove_layer_action = QAction(QIcon.fromTheme("list-remove"), "Remove Layer", self)
        self.remove_layer_action.triggered.connect(self.remove_layer)
        self.rename_layer_action = QAction(QIcon.fromTheme("edit-rename"), "Rename Layer...", self)
        self.rename_layer_action.triggered.connect(self.rename_layer)


        # Group tools for radio-button behavior
        self.tool_actions = [
            self.select_tool_action, self.pan_tool_action,
            self.set_scale_action, self.measure_linear_action, self.measure_area_action
            # Add other tool actions here
        ]


    def create_menus(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addAction(self.save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit Menu (Placeholder)
        edit_menu = menu_bar.addMenu("&Edit")
        # Add Undo/Redo, Copy/Paste, Delete actions later

        # View Menu
        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_fit_action)
        view_menu.addSeparator()
        view_menu.addAction(self.prev_page_action)
        view_menu.addAction(self.next_page_action)
        view_menu.addAction(self.goto_page_action)
        view_menu.addSeparator()
        # Option to show/hide docks
        view_menu.addAction(self.layers_dock.toggleViewAction())


        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self.select_tool_action)
        tools_menu.addAction(self.pan_tool_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.set_scale_action)
        tools_menu.addAction(self.measure_linear_action)
        tools_menu.addAction(self.measure_area_action)
        # Add other tools

        # Layers Menu (Could also be managed via Dock context menu)
        layer_menu = menu_bar.addMenu("&Layers")
        layer_menu.addAction(self.add_layer_action)
        layer_menu.addAction(self.remove_layer_action)
        layer_menu.addAction(self.rename_layer_action)


    def create_toolbars(self):
        # File Toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.addAction(self.new_project_action)
        file_toolbar.addAction(self.open_project_action)
        file_toolbar.addAction(self.save_project_action)

        # View Toolbar
        view_toolbar = self.addToolBar("View")
        view_toolbar.addAction(self.zoom_in_action)
        view_toolbar.addAction(self.zoom_out_action)
        view_toolbar.addAction(self.zoom_fit_action)
        view_toolbar.addAction(self.prev_page_action)
        view_toolbar.addAction(self.next_page_action)


        # Tools Toolbar
        tools_toolbar = self.addToolBar("Tools")
        tools_toolbar.addAction(self.select_tool_action)
        tools_toolbar.addAction(self.pan_tool_action)
        tools_toolbar.addSeparator()
        tools_toolbar.addAction(self.set_scale_action)
        tools_toolbar.addAction(self.measure_linear_action)
        tools_toolbar.addAction(self.measure_area_action)
        # Add other tools...


    def create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label_main = QLabel("Ready")
        self.status_label_coords = QLabel("X: --- Y: ---")
        self.status_label_scale = QLabel("Scale: Not Set")
        self.status_label_page = QLabel("Page: -/-")

        self.status_bar.addWidget(self.status_label_main, 1) # Stretch factor 1
        self.status_bar.addPermanentWidget(self.status_label_page)
        self.status_bar.addPermanentWidget(self.status_label_scale)
        self.status_bar.addPermanentWidget(self.status_label_coords)

    def create_docks(self):
        # Layers Dock
        self.layers_dock = QDockWidget("Layers", self)
        self.layers_list_widget = QListWidget()
        self.layers_list_widget.itemClicked.connect(self.layer_clicked)
        self.layers_list_widget.itemDoubleClicked.connect(self.rename_layer_from_list) # Allow rename on double-click
        self.layers_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layers_list_widget.customContextMenuRequested.connect(self.show_layer_context_menu)

        # Add buttons within the dock (alternative to menu/toolbar actions)
        layer_button_layout = QVBoxLayout()
        add_layer_btn = QPushButton(QIcon.fromTheme("list-add"), "")
        add_layer_btn.setToolTip("Add Layer")
        add_layer_btn.clicked.connect(self.add_layer)
        rem_layer_btn = QPushButton(QIcon.fromTheme("list-remove"), "")
        rem_layer_btn.setToolTip("Remove Selected Layer")
        rem_layer_btn.clicked.connect(self.remove_layer)
        # Add more buttons (rename, visibility toggle?) if desired

        layer_widget = QWidget()
        main_layer_layout = QVBoxLayout(layer_widget)
        main_layer_layout.addWidget(self.layers_list_widget)
        button_hbox = QHBoxLayout()
        button_hbox.addWidget(add_layer_btn)
        button_hbox.addWidget(rem_layer_btn)
        button_hbox.addStretch()
        main_layer_layout.addLayout(button_hbox)
        main_layer_layout.setContentsMargins(2,2,2,2) # Reduce margins


        self.layers_dock.setWidget(layer_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layers_dock)

        # Results Dock (Placeholder - populate later)
        self.results_dock = QDockWidget("Measurements", self)
        self.results_list_widget = QListWidget() # Or a QTreeView for more structure
        self.results_dock.setWidget(self.results_list_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.results_dock)

        # Tabify docks if desired
        self.tabifyDockWidget(self.layers_dock, self.results_dock)


    # --- Project Handling ---

    def new_project(self):
        if self.check_unsaved_changes():
            # Ask for source file (PDF or Image)
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Source File", "",
                "PDF and Image Files (*.pdf *.png *.jpg *.jpeg *.bmp *.gif);;PDF Files (*.pdf);;Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if not file_path:
                return # User cancelled

            # Ask for project save location
            project_path, _ = QFileDialog.getSaveFileName(
                 self, "Save Project As", "", "PyTakeoff Project (*.ptf)"
            )
            if not project_path:
                return # User cancelled

            # Ensure correct extension
            if not project_path.lower().endswith(".ptf"):
                 project_path += ".ptf"

            # Close existing project if any
            self.close_project()

            # Create new DB
            self.current_project_path = project_path
            self.project_manager.connect(self.current_project_path)

            # Load the source file
            if not self.load_source_file(file_path):
                # Loading failed, cleanup
                self.close_project()
                QMessageBox.critical(self,"Error", f"Failed to load source file:\n{file_path}")
                return

            # Initialize project data
            self.project_data = {
                'name': os.path.basename(project_path).replace('.ptf', ''),
                'source_path': file_path,
                'source_type': 'pdf' if file_path.lower().endswith('.pdf') else 'image',
                'current_page': 0,
                'scale_p1': (None, None), 'scale_p2': (None, None),
                'scale_real_dist': None, 'scale_unit': None, 'scale_factor': None
            }
            self.current_page_index = 0


            # Save initial metadata (important!)
            self.project_manager.save_project_metadata(self.project_data)
            # Load initial layers (should be just the default one now)
            self.load_layers_from_db()
            self.update_ui_from_project_data()
            self.set_status(f"New project created: {self.project_data['name']}")

        else:
            # User cancelled saving previous project
             pass


    def open_project(self):
        if self.check_unsaved_changes():
            project_path, _ = QFileDialog.getOpenFileName(
                self, "Open Project", "", "PyTakeoff Project (*.ptf)"
            )
            if project_path:
                self.close_project() # Close current before opening new
                try:
                    self.current_project_path = project_path
                    self.project_manager.connect(self.current_project_path)
                    self.project_data = self.project_manager.load_project_metadata()

                    if not self.project_data or not self.project_data.get('source_path'):
                        raise ValueError("Project file is missing essential data (like source path).")

                    if not self.load_source_file(self.project_data['source_path']):
                         raise ValueError(f"Failed to load the source file linked to the project:\n{self.project_data['source_path']}")

                    # Set current page if PDF
                    if self.project_data['source_type'] == 'pdf' and self.pdf_images:
                        page_to_load = self.project_data.get('current_page', 0)
                        if 0 <= page_to_load < len(self.pdf_images):
                             self.current_page_index = page_to_load
                             self.display_page(self.current_page_index)
                        else:
                             print(f"Warning: Saved page index {page_to_load} out of bounds. Loading page 0.")
                             self.current_page_index = 0
                             self.display_page(self.current_page_index)


                    self.load_layers_from_db()
                    self.load_items_from_db() # Load measurements
                    self.update_ui_from_project_data()
                    self.set_status(f"Project opened: {self.project_data.get('name', 'Unknown')}")

                except Exception as e:
                    QMessageBox.critical(self, "Error Opening Project", f"Failed to open project:\n{e}")
                    self.close_project() # Clean up on failure
        else:
            # User cancelled saving previous project
            pass


    def save_project(self):
        if not self.current_project_path:
            return self.save_project_as() # If never saved, use Save As

        if not self.project_manager.conn:
             QMessageBox.warning(self, "Save Error", "No active project database connection.")
             return False

        print(f"Saving project to: {self.current_project_path}")

        # Update project data before saving (e.g., current page)
        self.project_data['current_page'] = self.current_page_index

        # 1. Save Metadata
        if not self.project_manager.save_project_metadata(self.project_data):
             QMessageBox.critical(self, "Save Error", "Failed to save project metadata.")
             return False

        # 2. Save Layers (Assume layer state is managed elsewhere and updated in DB)
        # Layer visibility, name changes etc should ideally update the DB immediately
        # or be collected and saved here.

        # 3. Save Items (Items should ideally be saved/updated as they are created/modified)
        # If items are only stored in memory (on scene), iterate and save them.
        # For simplicity, let's assume items are added/updated in DB when created/modified.
        # We might need to save modifications to existing items (e.g., moved items)
        for item in self.scene.items():
            # Check if it's one of our custom measurement items
            if isinstance(item, (LinearMeasurementItem, )): # Add other item types
                if hasattr(item, 'get_data_for_db') and hasattr(item, 'db_id'):
                    item_data = item.get_data_for_db()
                    if item.db_id is None: # Item was created but not saved yet
                        new_id = self.project_manager.save_item(item_data)
                        if new_id:
                            item.db_id = new_id
                            item.setData(Qt.ItemDataRole.UserRole + 1, new_id) # Update item data
                        else:
                             print(f"Warning: Failed to save new item {item}")
                    else:
                        # Check if item was modified (needs a 'dirty' flag or compare geometry)
                        # For now, just update points as an example
                        self.project_manager.update_item_points(item.db_id, item_data['points'])


        self.set_status(f"Project saved: {self.project_data.get('name', 'Unknown')}")
        self.setWindowModified(False) # Mark window as not modified
        return True


    def save_project_as(self):
         if not self.project_manager.conn:
             QMessageBox.warning(self, "Save As Error", "No active project loaded to save.")
             return False

         project_path, _ = QFileDialog.getSaveFileName(
             self, "Save Project As", "", "PyTakeoff Project (*.ptf)"
         )
         if not project_path:
             return False # User cancelled

         if not project_path.lower().endswith(".ptf"):
              project_path += ".ptf"

         # Get current data before potentially closing the old connection
         current_metadata = self.project_data.copy()
         current_layers = self.project_manager.load_layers()
         current_items = self.project_manager.load_items()

         # Close old connection
         self.project_manager.close()

         # Connect to new DB file
         self.current_project_path = project_path
         self.project_manager.connect(self.current_project_path)

         # Update metadata with new name if needed
         current_metadata['name'] = os.path.basename(project_path).replace('.ptf', '')
         self.project_data = current_metadata # Update internal state

         # Save data to the new database
         if not self.project_manager.save_project_metadata(current_metadata): return False # Abort on error

         # Re-save layers and items to the new database
         layer_id_map = {} # To map old layer IDs to new ones
         for layer in current_layers:
             old_id = layer['id']
             # Don't save the ID from the old DB, let the new DB assign one
             new_id = self.project_manager.add_layer(layer['name'], color=layer['color'])
             if new_id:
                 layer_id_map[old_id] = new_id
                 self.project_manager.update_layer(new_id, visible=layer['visible']) # Save visibility too
             else:
                  print(f"Warning: Failed to re-save layer '{layer['name']}'")

         for item in current_items:
             old_layer_id = item['layer_id']
             new_layer_id = layer_id_map.get(old_layer_id)
             if new_layer_id is None:
                  print(f"Warning: Could not find new layer ID for item {item.get('id', '?')}, skipping.")
                  continue # Or assign to default layer?

             item['layer_id'] = new_layer_id
             # Don't save the old item ID
             item.pop('id', None)
             # Re-save the item
             new_item_id = self.project_manager.save_item(item)
             if not new_item_id:
                 print(f"Warning: Failed to re-save item (Type: {item.get('type','?')})")


         self.update_ui_from_project_data() # Update window title etc.
         self.set_status(f"Project saved as: {self.project_data['name']}")
         self.setWindowModified(False)
         return True


    def close_project(self):
        # Clear scene
        self.scene.clear() # Removes all items, including background
        self.background_item = None
        # Clear data
        self.pdf_images = []
        self.current_page_index = 0
        self.project_data = {}
        self.current_project_path = None
        self.layers = []
        self.active_layer_id = None
        # Close DB connection
        self.project_manager.close()
        # Reset UI
        self.update_ui_from_project_data()
        self.layers_list_widget.clear()
        self.results_list_widget.clear()
        self.set_status("Project closed. Ready.")
        self.setWindowModified(False)


    def check_unsaved_changes(self):
        if self.isWindowModified() and self.current_project_path: # Check if modified AND a project is loaded
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         'You have unsaved changes. Save before proceeding?',
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save)
            if reply == QMessageBox.StandardButton.Save:
                return self.save_project() # Returns True if save successful/not needed, False if cancelled/failed
            elif reply == QMessageBox.StandardButton.Cancel:
                return False # User cancelled the operation
            else: # Discard
                return True # Proceed without saving
        return True # No unsaved changes or no project loaded


    def closeEvent(self, event):
        if self.check_unsaved_changes():
            self.project_manager.close() # Ensure DB is closed properly
            event.accept() # Close the window
        else:
            event.ignore() # Don't close the window


    # --- Source File Handling ---

    def load_source_file(self, file_path):
        """Loads PDF or Image and displays the first page/image using PyMuPDF for PDFs."""
        self.scene.clear()
        self.pdf_images = []
        self.background_item = None
        file_path_lower = file_path.lower()

        try:
            if file_path_lower.endswith('.pdf'):
                self.project_data['source_type'] = 'pdf'
                print(f"Loading PDF using PyMuPDF: {file_path}")

                try:
                    doc = fitz.open(file_path)
                    num_pages = doc.page_count
                    if num_pages == 0:
                        raise ValueError("PDF has no pages or could not be opened correctly.")

                    print(f"Found {num_pages} pages.")

                    for page_num in range(num_pages):
                        page = doc.load_page(page_num)

                        # Render page to a pixmap (image)
                        # Adjust DPI as needed for quality vs. performance/memory
                        dpi = 150
                        zoom = dpi / 72  # Calculate zoom factor based on standard PDF DPI
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)  # alpha=False for RGB

                        # Convert MuPDF pixmap to QImage
                        # Format mapping might be needed for different PDF types,
                        # but RGB888 is common for standard rendering.
                        if pix.alpha:  # Check if pixmap has alpha channel (RGBA)
                            qimage_format = QImage.Format.Format_RGBA8888
                        else:  # Assume RGB
                            qimage_format = QImage.Format.Format_RGB888

                        # Create QImage directly from pix.samples byte buffer
                        qimage = QImage(pix.samples, pix.width, pix.height, pix.stride, qimage_format)

                        # Check if successful, maybe swap RGB<->BGR if needed (often not required with newer Qt/MuPDF)
                        if qimage.isNull():
                            print(f"Warning: Failed to create QImage for page {page_num}")
                            continue  # Skip this page

                        # Optional: If colors look swapped (Blue <-> Red), uncomment the next line
                        # qimage = qimage.rgbSwapped()

                        self.pdf_images.append(QPixmap.fromImage(qimage))
                        print(f"  Loaded page {page_num + 1}")

                    doc.close()  # Close the document when done

                    if not self.pdf_images:
                        raise ValueError("Failed to convert any PDF pages.")

                    self.current_page_index = 0
                    self.display_page(self.current_page_index)

                except Exception as e:
                    QMessageBox.critical(self, "PDF Load Error (PyMuPDF)", f"Failed to process PDF:\n{e}")
                    # Clean up state if loading fails
                    self.scene.clear()
                    self.pdf_images = []
                    self._update_actions_state()
                    self.update_page_status()
                    return False  # Indicate failure

            elif any(file_path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']):
                # --- Image loading logic remains the same ---
                self.project_data['source_type'] = 'image'
                pixmap = QPixmap(file_path)
                if pixmap.isNull():
                    raise ValueError("Failed to load image file.")
                self.background_item = self.scene.addPixmap(pixmap)
                self.background_item.setZValue(-1)
                self.scene.setSceneRect(self.background_item.boundingRect())
                self.zoom_to_fit()
                # ---------------------------------------------
            else:
                raise ValueError("Unsupported file type.")

            # General success state update
            self.project_data['source_path'] = file_path
            self._update_actions_state()
            self.update_page_status()
            return True  # Indicate success

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{file_path}\nError: {e}")
            self.scene.clear()
            self.pdf_images = []
            self.background_item = None
            self._update_actions_state()
            self.update_page_status()
            return False  # Indicate failure

    def display_page(self, page_index):
        if self.project_data.get('source_type') != 'pdf' or not self.pdf_images:
            return
        if 0 <= page_index < len(self.pdf_images):
            self.current_page_index = page_index
            if self.background_item:
                self.scene.removeItem(self.background_item) # Remove previous page

            pixmap = self.pdf_images[page_index]
            self.background_item = self.scene.addPixmap(pixmap)
            self.background_item.setZValue(-1)
            self.scene.setSceneRect(self.background_item.boundingRect())
            # Optionally preserve zoom/pan or reset view
            # self.zoom_to_fit() # Reset view for new page
            self.update_page_status()
            self._update_actions_state()
            # Might need to reload/filter items specific to this page if implemented
            print(f"Displayed page {page_index + 1}/{len(self.pdf_images)}")
        else:
             print(f"Error: Page index {page_index} out of bounds.")


    def prev_page(self):
        if self.current_page_index > 0:
            self.display_page(self.current_page_index - 1)

    def next_page(self):
        if self.pdf_images and self.current_page_index < len(self.pdf_images) - 1:
            self.display_page(self.current_page_index + 1)

    def goto_page(self):
        if not self.pdf_images: return
        page, ok = QInputDialog.getInt(self, "Go To Page", "Enter page number:",
                                       self.current_page_index + 1, 1, len(self.pdf_images))
        if ok:
            self.display_page(page - 1)

    def zoom_to_fit(self):
        if self.background_item:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            # Maybe fit based on items if no background?
            items_rect = self.scene.itemsBoundingRect()
            if not items_rect.isNull():
                 self.view.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)


    # --- UI Updates ---

    def set_status(self, message):
        self.status_label_main.setText(message)

    @pyqtSlot(QPointF)
    def update_status_mouse_pos(self, scene_pos):
        # Display scene coordinates
        self.status_label_coords.setText(f"X: {scene_pos.x():.2f} Y: {scene_pos.y():.2f}")
        # Could also display real-world coordinates if scale is set
        if self.project_data.get('scale_factor'):
            real_x = scene_pos.x() * self.project_data['scale_factor']
            real_y = scene_pos.y() * self.project_data['scale_factor'] # Or adjust based on origin
            unit = self.project_data.get('scale_unit', 'units')
            self.status_label_coords.setText(f"X: {scene_pos.x():.1f} Y: {scene_pos.y():.1f} [{real_x:.2f} {unit}, {real_y:.2f} {unit}]")


    def update_scale_status(self):
        if self.project_data.get('scale_factor') and self.project_data.get('scale_unit'):
            p1 = self.project_data.get('scale_p1')
            p2 = self.project_data.get('scale_p2')
            dist = self.project_data.get('scale_real_dist')
            unit = self.project_data.get('scale_unit')
            factor = self.project_data.get('scale_factor')
            if dist and unit and factor:
                 self.status_label_scale.setText(f"Scale: {dist:.2f} {unit} = {calculate_distance(QPointF(*p1), QPointF(*p2)):.1f}px (1px = {factor:.4f} {unit})")
                 return
        self.status_label_scale.setText("Scale: Not Set")


    def update_page_status(self):
        if self.pdf_images:
            self.status_label_page.setText(f"Page: {self.current_page_index + 1}/{len(self.pdf_images)}")
        elif self.background_item:
            self.status_label_page.setText("Page: 1/1")
        else:
            self.status_label_page.setText("Page: -/-")

    def _update_actions_state(self):
        """Enable/disable actions based on project state."""
        has_project = bool(self.current_project_path)
        has_source = bool(self.background_item)
        has_scale = bool(self.project_data.get('scale_factor'))
        is_pdf = self.project_data.get('source_type') == 'pdf' and len(self.pdf_images) > 1

        self.save_project_action.setEnabled(has_project)
        self.save_project_as_action.setEnabled(has_project)
        self.zoom_in_action.setEnabled(has_source)
        self.zoom_out_action.setEnabled(has_source)
        self.zoom_fit_action.setEnabled(has_source)

        self.set_scale_action.setEnabled(has_source)
        self.measure_linear_action.setEnabled(has_source and has_scale)
        self.measure_area_action.setEnabled(has_source and has_scale)
        # Enable other measurement tools similarly

        # Layer actions enabled if project exists
        self.add_layer_action.setEnabled(has_project)
        # Enable remove/rename based on selection in list widget (handle elsewhere)
        selected_layer = bool(self.layers_list_widget.currentItem())
        is_default_layer = False
        if selected_layer:
             # Prevent deleting/renaming the 'Default Layer' (or layer ID 1)
             item_data = self.layers_list_widget.currentItem().data(Qt.ItemDataRole.UserRole)
             is_default_layer = item_data.get('name') == "Default Layer" # Or check item_data['id'] == 1? Safer to use name?

        self.remove_layer_action.setEnabled(has_project and selected_layer and not is_default_layer)
        self.rename_layer_action.setEnabled(has_project and selected_layer and not is_default_layer)

        # PDF Nav
        self.prev_page_action.setEnabled(is_pdf and self.current_page_index > 0)
        self.next_page_action.setEnabled(is_pdf and self.current_page_index < len(self.pdf_images) - 1)
        self.goto_page_action.setEnabled(is_pdf)


    def update_ui_from_project_data(self):
        """Updates window title, status bar, actions based on loaded project."""
        if self.project_data:
            title = f"{self.project_data.get('name', 'Untitled')} - PyTakeoff"
            if self.current_project_path:
                title += f" [{os.path.basename(self.current_project_path)}]"
            self.setWindowTitle(title)
            self.update_scale_status()
            self.update_page_status()
            # Mark window as unmodified when loading/saving
            self.setWindowModified(False)
        else:
            self.setWindowTitle("PyTakeoff - Advanced")
            self.update_scale_status() # Resets scale text
            self.update_page_status() # Resets page text
            self.setWindowModified(False)

        self._update_actions_state() # Update enabled state


    # --- Tool Handling ---

    def set_tool(self, tool_name):
        self.view.set_tool(tool_name) # Inform the view
        self.set_status(f"Tool selected: {tool_name.replace('_', ' ').title()}")

        # Update checked state of toolbar actions
        for action in self.tool_actions:
            action.setChecked(action.text().split('&')[-1].strip().lower().replace(' ', '_') == tool_name)

        # Show specific instructions
        if tool_name == "set_scale":
            self.set_status("Set Scale: Click start point of known dimension.")
        elif tool_name == "measure_linear":
            self.set_status("Measure Linear: Click start point.")
        elif tool_name == "measure_area":
            self.set_status("Measure Area: Click polygon vertices. Double-click or Esc to finish.")


    # --- Event Handling ---

    def handle_escape_press(self):
        """Handle Escape key press, usually to cancel current tool action."""
        current_tool = self.view.get_tool()
        print(f"MainWindow received Esc press. Current tool: {current_tool}")
        # Reset tool state in the view is handled by the view itself
        # We might want to reset the tool selection to 'pan' or 'select'
        if current_tool not in ["pan", "select"]:
            self.set_tool("pan") # Default back to pan tool after cancelling
            self.pan_tool_action.setChecked(True)
            self.set_status("Drawing cancelled. Pan tool selected.")
        else:
            # Maybe clear selection if select tool active?
             if current_tool == "select":
                  self.scene.clearSelection()
                  self.view.selection_changed_signal.emit([]) # Notify change


    @pyqtSlot(QPointF)
    def handle_view_click(self, scene_pos):
        """Process single clicks based on the current tool."""
        tool = self.view.get_tool()
        print(f"Handling click for tool {tool} at {scene_pos}")

        # The view now handles the start/continuation of drawing internally.
        # This MainWindow slot might be used for things *after* the view's action,
        # or for tools that don't involve drawing (like 'count' maybe).

        if tool == "set_scale":
            if not self.view._is_drawing: # Just finished drawing the line
                 points = self.view._current_points_scene # Get points from the view's finished state
                 if len(points) == 2:
                     self.prompt_for_scale(points[0], points[1])
                     # It's better if finish_current_drawing emits a signal with points
                     # And this function connects to that signal
            else: # First click
                 self.set_status("Set Scale: Click end point of known dimension.")

        elif tool == "measure_linear":
             if not self.view._is_drawing: # Just finished drawing
                 points = self.view._current_points_scene
                 if len(points) == 2:
                    self.create_linear_measurement(points[0], points[1])
                    # Need signal from finish_current_drawing
             else: # First click
                 self.set_status("Measure Linear: Click end point.")

        elif tool == "measure_area":
             # Area points are added on click by the view. We only act on finish (double-click/esc).
             num_points = len(self.view._current_points_scene)
             if num_points > 0:
                 self.set_status(f"Measure Area: Added point {num_points}. Click next or Double-click/Esc to finish.")

        # Add Count tool logic here: create count item on click


    @pyqtSlot(QPointF)
    def handle_view_double_click(self, scene_pos):
         """Process double clicks, primarily for finishing area polygons."""
         tool = self.view.get_tool()
         print(f"Handling double-click for tool {tool} at {scene_pos}")

         if tool == "measure_area":
             # The view's finish_current_drawing should have been called before this or handle it.
             # We get the final points and create the measurement.
             # Need signal from finish_current_drawing
             final_points = self.view._current_points_scene # Assume view stores this on finish
             if len(final_points) >= 3:
                 self.create_area_measurement(final_points)
             else:
                  print("Not enough points for area after double-click.")
             # Reset the tool in the view (already done in finish_current_drawing)
             self.set_status("Measure Area: Click first vertex for new area.") # Ready for next

         # Could also handle editing text items on double-click


    # --- Measurement Creation ---

    def prompt_for_scale(self, p1: QPointF, p2: QPointF):
        """Ask user for real distance after drawing scale line."""
        pixel_dist = calculate_distance(p1, p2)
        if pixel_dist < 1e-6:
            QMessageBox.warning(self, "Set Scale", "Scale line has zero length.")
            return

        # More robust dialog than simple QInputDialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Set Scale")
        layout = QFormLayout(dialog)

        dist_input = QLineEdit()
        unit_input = QLineEdit(self.project_data.get('scale_unit', 'm')) # Default or last used unit
        info_label = QLabel(f"Measured pixel distance: {pixel_dist:.2f} px")

        layout.addRow(info_label)
        layout.addRow("Real Distance:", dist_input)
        layout.addRow("Unit:", unit_input)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)

        if dialog.exec():
            try:
                real_dist = float(dist_input.text())
                unit = unit_input.text().strip()
                if not unit:
                    raise ValueError("Unit cannot be empty.")
                if real_dist <= 0:
                    raise ValueError("Distance must be positive.")

                self.project_data['scale_p1'] = (p1.x(), p1.y())
                self.project_data['scale_p2'] = (p2.x(), p2.y())
                self.project_data['scale_real_dist'] = real_dist
                self.project_data['scale_unit'] = unit
                self.project_data['scale_factor'] = real_dist / pixel_dist # real units per pixel

                self.update_scale_status()
                self._update_actions_state() # Enable measurement tools
                self.set_status(f"Scale set: 1 pixel = {self.project_data['scale_factor']:.4f} {unit}")
                self.setWindowModified(True) # Mark project as modified

                # Optional: Draw the scale line permanently on scene
                # Need a specific layer for scale visuals?
                scale_line_item = self.scene.addLine(QLineF(p1, p2), QPen(QColor("blue"), 2))
                # Add text label?

            except ValueError as e:
                QMessageBox.warning(self, "Invalid Input", f"Invalid scale value or unit: {e}")
                # Keep the set_scale tool active? Or reset?
                self.set_tool("set_scale") # Stay in scale tool
            except Exception as e:
                 QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")


    def create_linear_measurement(self, p1: QPointF, p2: QPointF):
        """Creates a permanent linear measurement item on the scene and saves it."""
        if not self.project_data.get('scale_factor'):
            QMessageBox.warning(self, "Measurement Error", "Scale not set.")
            return # Should not happen if action is disabled, but check anyway

        if self.active_layer_id is None:
            QMessageBox.warning(self, "Measurement Error", "No active layer selected.")
            # Optionally, force selection or use default layer
            # Find default layer ID
            default_layer = next((layer for layer in self.layers if layer['name'] == "Default Layer"), None)
            if default_layer:
                self.active_layer_id = default_layer['id']
                print("Warning: No active layer, using Default Layer.")
            else:
                return # Cannot proceed without a layer


        pixel_dist = calculate_distance(p1, p2)
        real_dist = pixel_dist * self.project_data['scale_factor']
        unit = self.project_data.get('scale_unit', 'units')

        # Create graphics item (Using placeholder class for now)
        item = LinearMeasurementItem(p1, p2, layer_id=self.active_layer_id, value=real_dist, unit=unit)
        self.scene.addItem(item)

        # Save item to database
        item_data = item.get_data_for_db()
        new_id = self.project_manager.save_item(item_data)
        if new_id:
            item.db_id = new_id # Update item with its database ID
            item.setData(Qt.ItemDataRole.UserRole + 1, new_id) # Make ID accessible
            self.add_measurement_result(f"Linear ({item.db_id}): {real_dist:.2f} {unit}")
            self.setWindowModified(True)
            self.set_status(f"Measured: {real_dist:.2f} {unit}. Click start point for next line.")
        else:
            QMessageBox.warning(self, "Save Error", "Failed to save measurement to database.")
            self.scene.removeItem(item) # Remove item if save failed


    def create_area_measurement(self, points: list[QPointF]):
         """Creates a permanent area measurement item on the scene and saves it."""
         if not self.project_data.get('scale_factor'):
             QMessageBox.warning(self, "Measurement Error", "Scale not set.")
             return
         if self.active_layer_id is None:
              QMessageBox.warning(self, "Measurement Error", "No active layer selected.")
              # Find default layer ID
              default_layer = next((layer for layer in self.layers if layer['name'] == "Default Layer"), None)
              if default_layer:
                 self.active_layer_id = default_layer['id']
                 print("Warning: No active layer, using Default Layer.")
              else:
                 return # Cannot proceed without a layer


         if len(points) < 3: return # Should be caught earlier

         # Calculate pixel area (Shoelace formula)
         pixel_area = 0.0
         for i in range(len(points)):
             j = (i + 1) % len(points)
             pixel_area += points[i].x() * points[j].y()
             pixel_area -= points[j].x() * points[i].y()
         pixel_area = abs(pixel_area) / 2.0

         scale_factor_sq = self.project_data['scale_factor'] ** 2
         real_area = pixel_area * scale_factor_sq
         unit = self.project_data.get('scale_unit', 'units')
         area_unit = f"sq {unit}"

         # Create graphics item (Needs an AreaMeasurementItem class)
         polygon = QPolygonF(points)
         # Placeholder: Use basic QGraphicsPolygonItem
         item = QGraphicsPolygonItem(polygon)
         item.setPen(QPen(QColor("purple"), 2))
         item.setBrush(Qt.BrushStyle.NoBrush) # No fill for measurement outline
         item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
         item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
         item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable) # Needed for delete key?
         self.scene.addItem(item)

         # Prepare data for DB (Adapt for actual AreaMeasurementItem class)
         item_data = {
             'layer_id': self.active_layer_id,
             'type': 'area',
             'points': [(p.x(), p.y()) for p in points],
             'value': real_area,
             'unit': area_unit,
             'style': {'color': "purple", 'width': 2, 'fill': None} # Example style
         }

         new_id = self.project_manager.save_item(item_data)
         if new_id:
             # Store db_id in the graphics item if possible (e.g., item.db_id = new_id or using setData)
             item.setData(Qt.ItemDataRole.UserRole + 1, new_id)
             self.add_measurement_result(f"Area ({new_id}): {real_area:.2f} {area_unit}")
             self.setWindowModified(True)
             self.set_status(f"Measured: {real_area:.2f} {area_unit}. Click vertices for next area.")
         else:
             QMessageBox.warning(self, "Save Error", "Failed to save area measurement.")
             self.scene.removeItem(item)


    def add_measurement_result(self, text):
        """Add entry to the results list widget."""
        self.results_list_widget.addItem(text)
        self.results_list_widget.scrollToBottom()


    # --- Item Loading ---
    def load_items_from_db(self):
        if not self.project_manager.conn: return
        items_data = self.project_manager.load_items()
        self.results_list_widget.clear() # Clear old results display

        # Get current visibility state of layers
        layer_visibility = {layer['id']: layer['visible'] for layer in self.layers}

        for data in items_data:
            item = None
            points_qpointf = [QPointF(p[0], p[1]) for p in data['points']]
            layer_id = data['layer_id']
            db_id = data['id']
            value = data.get('value', 0)
            unit = data.get('unit', '')

            try:
                if data['type'] == 'linear' and len(points_qpointf) == 2:
                    item = LinearMeasurementItem(points_qpointf[0], points_qpointf[1], db_id, layer_id, value, unit)
                    # Apply style from DB if needed
                    # item.setPen(...)
                    self.add_measurement_result(f"Linear ({db_id}): {value:.2f} {unit}")

                elif data['type'] == 'area' and len(points_qpointf) >= 3:
                    polygon = QPolygonF(points_qpointf)
                    # Use basic polygon item for now
                    item = QGraphicsPolygonItem(polygon)
                    item.setPen(QPen(QColor("purple"), 2)) # Apply style from DB later
                    item.setBrush(Qt.BrushStyle.NoBrush)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                    item.setData(Qt.ItemDataRole.UserRole + 1, db_id) # Store DB ID
                    # item.layer_id = layer_id # Store layer ID if custom item class used
                    self.add_measurement_result(f"Area ({db_id}): {value:.2f} {unit}")

                # Add loading for other item types (Count, Text, Curve...)

                if item:
                    item.setVisible(layer_visibility.get(layer_id, True)) # Set visibility based on layer
                    self.scene.addItem(item)

            except Exception as e:
                 print(f"Error loading item ID {db_id} from database: {e}")
                 print(f"Problematic data: {data}")


    # --- Layer Management ---

    def load_layers_from_db(self):
         if not self.project_manager.conn: return
         self.layers = self.project_manager.load_layers()
         self.update_layer_list_widget()
         # Set active layer (e.g., the first one or the default one)
         if self.layers:
             default_layer = next((layer for layer in self.layers if layer['name'] == "Default Layer"), self.layers[0])
             self.set_active_layer(default_layer['id'])
         else:
             # Should not happen if DB creates default layer, but handle anyway
             self.active_layer_id = None


    def update_layer_list_widget(self):
        self.layers_list_widget.clear()
        active_item = None
        for layer in sorted(self.layers, key=lambda x: x.get('id', 0)): # Sort by ID or name?
            item = QListWidgetItem(layer['name'])
            item.setData(Qt.ItemDataRole.UserRole, layer) # Store full layer dict
            # Set visual cues (checkbox for visibility, maybe color?)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if layer['visible'] else Qt.CheckState.Unchecked)
            # item.setForeground(QColor(layer['color'])) # Optional: Color the text

            self.layers_list_widget.addItem(item)
            if layer['id'] == self.active_layer_id:
                active_item = item

        if active_item:
             self.layers_list_widget.setCurrentItem(active_item)
             # Maybe add bold font or background to indicate active layer visually
             font = active_item.font()
             font.setBold(True)
             active_item.setFont(font)

        self._update_actions_state() # Update remove/rename action status


    def set_active_layer(self, layer_id):
        print(f"Setting active layer to ID: {layer_id}")
        self.active_layer_id = layer_id
        # Update visual representation in the list widget
        for i in range(self.layers_list_widget.count()):
            item = self.layers_list_widget.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            font = item.font()
            if item_data and item_data['id'] == layer_id:
                font.setBold(True)
            else:
                 font.setBold(False)
            item.setFont(font)


    def layer_clicked(self, item):
        layer_data = item.data(Qt.ItemDataRole.UserRole)
        if layer_data:
            # Check if checkbox was clicked
            click_x = self.layers_list_widget.mapFromGlobal(self.cursor().pos()).x()
            checkbox_rect_width = 20 # Approximate width of the checkbox area
            if click_x < checkbox_rect_width:
                 self.toggle_layer_visibility(layer_data['id'], item.checkState() == Qt.CheckState.Checked)
            else:
                # Otherwise, set layer as active
                self.set_active_layer(layer_data['id'])

        self._update_actions_state() # Update enabled state of remove/rename


    def toggle_layer_visibility(self, layer_id, is_visible):
         print(f"Toggling visibility for layer {layer_id} to {is_visible}")
         # Update database
         if not self.project_manager.update_layer(layer_id, visible=is_visible):
             QMessageBox.warning(self, "Layer Error", "Failed to update layer visibility in database.")
             # Revert checkbox state?
             item = self.find_layer_item(layer_id)
             if item:
                 item.setCheckState(Qt.CheckState.Unchecked if is_visible else Qt.CheckState.Checked)
             return

         # Update internal layer list
         for layer in self.layers:
             if layer['id'] == layer_id:
                 layer['visible'] = is_visible
                 break

         # Update visibility of items on the scene
         for scene_item in self.scene.items():
             # Need a consistent way to get layer ID from items
             item_layer_id = None
             if isinstance(scene_item, (LinearMeasurementItem, )): # Add other custom types
                  item_layer_id = scene_item.layer_id
             # Or using setData: item_layer_id = scene_item.data(Qt.ItemDataRole.UserRole + 2) # If layer ID stored there

             if item_layer_id == layer_id:
                 scene_item.setVisible(is_visible)

         self.setWindowModified(True)


    def add_layer(self):
         if not self.project_manager.conn: return
         layer_name, ok = QInputDialog.getText(self, "Add Layer", "Enter new layer name:")
         if ok and layer_name:
             # TODO: Add color picker dialog
             new_id = self.project_manager.add_layer(layer_name)
             if new_id:
                 # Reload layers from DB to get the new one correctly
                 self.load_layers_from_db()
                 self.set_active_layer(new_id) # Make the new layer active
                 self.setWindowModified(True)
             else:
                 # Error message handled by project_manager (e.g., duplicate name)
                 QMessageBox.warning(self, "Add Layer Failed", f"Could not add layer '{layer_name}'. It might already exist.")


    def remove_layer(self):
         current_item = self.layers_list_widget.currentItem()
         if not current_item: return
         layer_data = current_item.data(Qt.ItemDataRole.UserRole)
         if not layer_data: return

         layer_id = layer_data['id']
         layer_name = layer_data['name']

         # Prevent deleting the default layer (important!)
         if layer_name == "Default Layer": # Or check ID == 1?
             QMessageBox.warning(self, "Remove Layer", "Cannot remove the default layer.")
             return

         reply = QMessageBox.question(self, "Remove Layer",
                                      f"Remove layer '{layer_name}' and all its measurements?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

         if reply == QMessageBox.StandardButton.Yes:
             # Remove items from scene first
             items_to_remove = []
             for scene_item in self.scene.items():
                 item_layer_id = None
                 if isinstance(scene_item, (LinearMeasurementItem,)): # Add other types
                      item_layer_id = scene_item.layer_id
                 # Or item_layer_id = scene_item.data(Qt.ItemDataRole.UserRole + 2)

                 if item_layer_id == layer_id:
                     items_to_remove.append(scene_item)

             for scene_item in items_to_remove:
                  self.scene.removeItem(scene_item)


             # Remove from database (ProjectManager handles deleting items and layer)
             if self.project_manager.delete_layer(layer_id):
                 # Reload layers
                 self.load_layers_from_db()
                 self.setWindowModified(True)
                 # Active layer might have been deleted, set_active_layer(None) or default?
                 if self.active_layer_id == layer_id:
                      self.set_active_layer(None) # Or find default layer ID
             else:
                 QMessageBox.critical(self, "Remove Layer Failed", "Failed to remove layer from database.")
                 # Might need to reload items if only layer deletion failed but items were removed from scene


    def rename_layer(self):
        current_item = self.layers_list_widget.currentItem()
        if not current_item: return
        layer_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not layer_data: return

        layer_id = layer_data['id']
        old_name = layer_data['name']

        if old_name == "Default Layer":
             QMessageBox.warning(self, "Rename Layer", "Cannot rename the default layer.")
             return

        new_name, ok = QInputDialog.getText(self, "Rename Layer", "Enter new name:", QLineEdit.EchoMode.Normal, old_name)

        if ok and new_name and new_name != old_name:
            if self.project_manager.update_layer(layer_id, name=new_name):
                 # Update internal list and UI
                 layer_data['name'] = new_name
                 current_item.setText(new_name)
                 current_item.setData(Qt.ItemDataRole.UserRole, layer_data) # Update stored data
                 self.setWindowModified(True)
            else:
                 QMessageBox.warning(self, "Rename Failed", f"Could not rename layer to '{new_name}'. Name might be in use.")


    def rename_layer_from_list(self, item):
        """Connected to itemDoubleClicked"""
        self.rename_layer() # Just call the existing rename logic

    def find_layer_item(self, layer_id):
         """Find the QListWidgetItem corresponding to a layer ID."""
         for i in range(self.layers_list_widget.count()):
             item = self.layers_list_widget.item(i)
             item_data = item.data(Qt.ItemDataRole.UserRole)
             if item_data and item_data['id'] == layer_id:
                 return item
         return None

    def show_layer_context_menu(self, pos):
        item = self.layers_list_widget.itemAt(pos)
        menu = QMenu()

        if item: # Actions specific to a selected layer
            layer_data = item.data(Qt.ItemDataRole.UserRole)
            is_default = layer_data.get('name') == "Default Layer"

            set_active_action = menu.addAction("Set Active")
            set_active_action.triggered.connect(lambda: self.set_active_layer(layer_data['id']))

            rename_action = menu.addAction(QIcon.fromTheme("edit-rename"), "Rename Layer...")
            rename_action.triggered.connect(self.rename_layer)
            rename_action.setEnabled(not is_default)

            remove_action = menu.addAction(QIcon.fromTheme("list-remove"), "Remove Layer")
            remove_action.triggered.connect(self.remove_layer)
            remove_action.setEnabled(not is_default)

            # Add visibility toggle? Color change?
            menu.addSeparator()

        # Actions always available
        add_action = menu.addAction(QIcon.fromTheme("list-add"), "Add New Layer...")
        add_action.triggered.connect(self.add_layer)

        menu.exec(self.layers_list_widget.mapToGlobal(pos))


# --- Need QDialogButtonBox ---
from PyQt6.QtWidgets import QDialogButtonBox