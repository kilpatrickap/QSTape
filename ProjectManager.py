# ProjectManager.py (Basic Structure)
import sqlite3
import json
import os

class ProjectManager:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        if db_path:
            self.connect(db_path)

    def connect(self, db_path):
        self.db_path = db_path
        new_db = not os.path.exists(db_path)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        if new_db:
            self.create_tables()
        print(f"Connected to database: {db_path}")

    def create_tables(self):
        if not self.cursor: return
        try:
            # Project Metadata
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS project (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    source_path TEXT, -- Path to PDF/Image
                    source_type TEXT, -- 'pdf' or 'image'
                    current_page INTEGER DEFAULT 0,
                    scale_p1_x REAL, scale_p1_y REAL,
                    scale_p2_x REAL, scale_p2_y REAL,
                    scale_real_dist REAL,
                    scale_unit TEXT,
                    scale_factor REAL -- Calculated: real_dist / pixel_dist
                )
            ''')
            # Layers
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS layers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    name TEXT UNIQUE,
                    visible INTEGER DEFAULT 1,
                    color TEXT DEFAULT '#FF0000', -- Default Red
                    FOREIGN KEY (project_id) REFERENCES project(id)
                )
            ''')
             # Add a default layer
            self.cursor.execute("INSERT OR IGNORE INTO layers (project_id, name) VALUES (?, ?)", (1, "Default Layer"))

            # Measurement Items
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER,
                    layer_id INTEGER,
                    type TEXT, -- 'linear', 'area', 'count', 'text', 'curve'
                    points TEXT, -- JSON list of [x, y] pixel coordinates
                    value REAL, -- Calculated real-world value (length, area)
                    unit TEXT,
                    text_content TEXT, -- For annotations
                    style TEXT, -- JSON for color, line width etc.
                    FOREIGN KEY (project_id) REFERENCES project(id),
                    FOREIGN KEY (layer_id) REFERENCES layers(id)
                )
            ''')
            self.conn.commit()
            print("Database tables created or verified.")
        except sqlite3.Error as e:
            print(f"Database error during table creation: {e}")


    def save_project_metadata(self, project_data):
        if not self.cursor: return False
        try:
            # Use INSERT OR REPLACE to handle existing project (id=1 assumed for simplicity)
            self.cursor.execute('''
                INSERT OR REPLACE INTO project
                (id, name, source_path, source_type, current_page, scale_p1_x, scale_p1_y, scale_p2_x, scale_p2_y, scale_real_dist, scale_unit, scale_factor)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_data.get('name', 'Untitled'),
                project_data.get('source_path'),
                project_data.get('source_type'),
                project_data.get('current_page', 0),
                project_data.get('scale_p1', (None, None))[0], project_data.get('scale_p1', (None, None))[1],
                project_data.get('scale_p2', (None, None))[0], project_data.get('scale_p2', (None, None))[1],
                project_data.get('scale_real_dist'),
                project_data.get('scale_unit'),
                project_data.get('scale_factor')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error saving project metadata: {e}")
            return False

    def load_project_metadata(self):
        if not self.cursor: return None
        try:
            self.cursor.execute("SELECT name, source_path, source_type, current_page, scale_p1_x, scale_p1_y, scale_p2_x, scale_p2_y, scale_real_dist, scale_unit, scale_factor FROM project WHERE id = 1")
            row = self.cursor.fetchone()
            if row:
                return {
                    'name': row[0], 'source_path': row[1], 'source_type': row[2],
                    'current_page': row[3],
                    'scale_p1': (row[4], row[5]), 'scale_p2': (row[6], row[7]),
                    'scale_real_dist': row[8], 'scale_unit': row[9], 'scale_factor': row[10]
                }
            return None # No project data found
        except sqlite3.Error as e:
            print(f"Error loading project metadata: {e}")
            return None

    def save_item(self, item_data):
        if not self.cursor: return None
        try:
            self.cursor.execute('''
                INSERT INTO items (project_id, layer_id, type, points, value, unit, text_content, style)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                1, # Assuming project_id is always 1 for simplicity
                item_data['layer_id'],
                item_data['type'],
                json.dumps(item_data['points']),
                item_data.get('value'),
                item_data.get('unit'),
                item_data.get('text_content'),
                json.dumps(item_data.get('style', {}))
            ))
            self.conn.commit()
            return self.cursor.lastrowid # Return the ID of the newly inserted item
        except sqlite3.Error as e:
            print(f"Error saving item: {e}")
            return None

    def load_items(self, project_id=1):
        if not self.cursor: return []
        try:
            self.cursor.execute("SELECT id, layer_id, type, points, value, unit, text_content, style FROM items WHERE project_id = ?", (project_id,))
            items = []
            for row in self.cursor.fetchall():
                 items.append({
                    'id': row[0], 'layer_id': row[1], 'type': row[2],
                    'points': json.loads(row[3]), # Deserialize points
                    'value': row[4], 'unit': row[5], 'text_content': row[6],
                    'style': json.loads(row[7]) # Deserialize style
                 })
            return items
        except sqlite3.Error as e:
            print(f"Error loading items: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from database: {e}")
            # Decide how to handle corrupted data - skip item, return empty, etc.
            return [] # Return empty list on decode error for safety

    def update_item_points(self, item_id, points):
        if not self.cursor: return False
        try:
            self.cursor.execute("UPDATE items SET points = ? WHERE id = ?", (json.dumps(points), item_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating item points: {e}")
            return False

    def delete_item(self, item_id):
        if not self.cursor: return False
        try:
            self.cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting item: {e}")
            return False

    # --- Layer Methods ---
    def load_layers(self, project_id=1):
        if not self.cursor: return []
        try:
            self.cursor.execute("SELECT id, name, visible, color FROM layers WHERE project_id = ?", (project_id,))
            return [{'id': r[0], 'name': r[1], 'visible': bool(r[2]), 'color': r[3]} for r in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error loading layers: {e}")
            return []

    def add_layer(self, name, project_id=1, color='#FF0000'):
         if not self.cursor: return None
         try:
             self.cursor.execute("INSERT INTO layers (project_id, name, color) VALUES (?, ?, ?)", (project_id, name, color))
             self.conn.commit()
             return self.cursor.lastrowid
         except sqlite3.IntegrityError:
             print(f"Layer '{name}' already exists.")
             return None # Indicate failure due to uniqueness constraint
         except sqlite3.Error as e:
             print(f"Error adding layer: {e}")
             return None


    def update_layer(self, layer_id, name=None, visible=None, color=None):
        if not self.cursor: return False
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if visible is not None:
            updates.append("visible = ?")
            params.append(1 if visible else 0)
        if color is not None:
            updates.append("color = ?")
            params.append(color)

        if not updates: return True # Nothing to update

        sql = f"UPDATE layers SET {', '.join(updates)} WHERE id = ?"
        params.append(layer_id)

        try:
            self.cursor.execute(sql, tuple(params))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating layer {layer_id}: {e}")
            return False

    def delete_layer(self, layer_id):
         if not self.cursor: return False
         try:
             # Optional: Decide what to do with items on this layer.
             # Delete them? Move to default? Prevent deletion if not empty?
             # Here, we'll just delete the layer for simplicity.
             self.cursor.execute("DELETE FROM items WHERE layer_id = ?", (layer_id,)) # Delete associated items first
             self.cursor.execute("DELETE FROM layers WHERE id = ?", (layer_id,))
             self.conn.commit()
             return True
         except sqlite3.Error as e:
             print(f"Error deleting layer {layer_id}: {e}")
             return False

    def close(self):
        if self.conn:
            self.conn.commit() # Ensure final commit
            self.conn.close()
            self.conn = None
            self.cursor = None
            print("Database connection closed.")