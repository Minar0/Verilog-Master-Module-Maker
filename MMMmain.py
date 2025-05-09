import sys
import re
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, 
                             QGraphicsView, QGraphicsItem, QMenu, QAction, 
                             QGraphicsSceneMouseEvent, QInputDialog, QFileDialog,
                             QListWidget, QDockWidget, QVBoxLayout, QWidget, 
                             QToolBar, QComboBox, QLabel, QSlider, QSpinBox,
                             QHBoxLayout, QPushButton, QToolTip, QMessageBox)
from PyQt5.QtCore import Qt, QPointF, QRectF, QSizeF, QDateTime
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QFont, QFontMetrics, QImage


class SystemVerilogParser:
    """Parse SystemVerilog files to extract module information using pure regex"""
    
    @staticmethod
    def parse_file(filename):
        """Parse SystemVerilog file and extract module information"""
        modules = {}
        
        try:
            with open(filename, 'r') as f:
                content = f.read()
            
            # Remove comments
            content = re.sub(r'//.*?\n', '\n', content)  # Remove single-line comments
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)  # Remove multi-line comments
            
            # Find module definitions
            module_pattern = r'module\s+(\w+)\s*(?:#\s*\([^)]*\))?\s*\((.*?)\);(.*?)endmodule'
            module_matches = re.finditer(module_pattern, content, flags=re.DOTALL)
            
            for module_match in module_matches:
                module_name = module_match.group(1)
                port_list_text = module_match.group(2)
                module_body = module_match.group(3)
                
                print(f"\nParsing module: {module_name}")
                
                # Parse ANSI-style port list that contains direction information
                inputs, outputs, inouts = SystemVerilogParser.parse_ansi_port_list(port_list_text)
                
                print(f"  From ANSI port list - Inputs: {inputs}")
                print(f"  From ANSI port list - Outputs: {outputs}")
                
                # Get all port names
                all_port_names = inputs + outputs + inouts
                
                # If no ANSI-style ports were found, try to parse as non-ANSI style
                if not all_port_names:
                    all_port_names = SystemVerilogParser.parse_port_list(port_list_text)
                    print(f"  From non-ANSI port list - All ports: {all_port_names}")
                    
                    # Find port declarations in the module body for non-ANSI style
                    body_inputs, body_outputs, body_inouts = SystemVerilogParser.parse_module_body(module_body, all_port_names)
                    
                    inputs = body_inputs
                    outputs = body_outputs
                    inouts = body_inouts
                
                # Handle special case: if port is in the port list but not found in any declarations,
                # it might be an implicit input
                for port in all_port_names:
                    if port not in inputs and port not in outputs and port not in inouts:
                        inputs.append(port)
                
                # Save the module info
                modules[module_name] = {
                    "inputs": inputs,
                    "outputs": outputs + inouts  # Treat inouts as outputs for the GUI
                }
                
                # Debug output
                print(f"Final Parsed module: {module_name}")
                print(f"  Inputs: {inputs}")
                print(f"  Outputs: {outputs}")
                print(f"  Inouts: {inouts}")
        
        except Exception as e:
            print(f"Error parsing file {filename}: {e}")
            import traceback
            traceback.print_exc()
        
        return modules
    
    @staticmethod
    def extract_port_width(port_decl):
        """Extract port width from a declaration"""
        # Look for width specifications like [7:0], [31:0], [WIDTH-1:0], etc.
        width_match = re.search(r'\[(.*?)\]', port_decl)
        if width_match:
            return width_match.group(1)
        return ""
    
    @staticmethod
    def parse_ansi_port_list(port_list_text):
        """Parse ANSI-style port list with direction information"""
        inputs = []
        outputs = []
        inouts = []
        
        # Clean up port list by removing extra whitespace and newlines
        clean_port_list = re.sub(r'\s+', ' ', port_list_text).strip()
        
        # Extract port declarations by direction for better handling of comma-separated lists
        input_pattern = r'input\s+(?:wire|reg|logic)?\s*(?:\[[^\]]+\])?\s*([\w\s,]+?)(?:,|\s*$|\s*(?:input|output|inout)\s+)'
        output_pattern = r'output\s+(?:wire|reg|logic)?\s*(?:\[[^\]]+\])?\s*([\w\s,]+?)(?:,|\s*$|\s*(?:input|output|inout)\s+)'
        inout_pattern = r'inout\s+(?:wire|reg|logic)?\s*(?:\[[^\]]+\])?\s*([\w\s,]+?)(?:,|\s*$|\s*(?:input|output|inout)\s+)'
        
        # Find all input port declarations
        full_port_list = " " + clean_port_list + " " # Add space to help with regex matching
        
        # Process one direction at a time
        cursor_pos = 0
        while cursor_pos < len(full_port_list):
            # Look for input declaration
            if match := re.search(r'input\s+', full_port_list[cursor_pos:]):
                start_pos = cursor_pos + match.start()
                cursor_pos = start_pos + len(match.group())
                
                # Skip type if present
                if type_match := re.search(r'^(?:wire|reg|logic)\s+', full_port_list[cursor_pos:]):
                    cursor_pos += len(type_match.group())
                
                # Extract width if present
                width = ""
                if dim_match := re.search(r'^\s*\[(.*?)\]\s*', full_port_list[cursor_pos:]):
                    width = dim_match.group(1)
                    cursor_pos += len(dim_match.group())
                
                # Find the end of this port declaration group
                end_pos = cursor_pos
                bracket_depth = 0
                
                while end_pos < len(full_port_list):
                    char = full_port_list[end_pos]
                    
                    # Track bracket depth
                    if char == '[':
                        bracket_depth += 1
                    elif char == ']':
                        bracket_depth -= 1
                    # Look for next direction keyword or end of port list
                    elif bracket_depth == 0 and re.search(r'^\s*(?:input|output|inout)\s+', full_port_list[end_pos:]):
                        break
                    
                    end_pos += 1
                
                # Extract the port list
                port_list = full_port_list[cursor_pos:end_pos].strip()
                
                # Handle potential trailing comma
                if port_list.endswith(','):
                    port_list = port_list[:-1]
                
                # Split by commas (outside of brackets)
                ports = SystemVerilogParser.split_comma_list(port_list)
                
                # Add width to port names if present
                if width:
                    ports = [f"{p}[{width}]" for p in ports]
                
                inputs.extend(ports)
                
                cursor_pos = end_pos
                continue
            
            # Look for output declaration
            if match := re.search(r'output\s+', full_port_list[cursor_pos:]):
                start_pos = cursor_pos + match.start()
                cursor_pos = start_pos + len(match.group())
                
                # Skip type if present
                if type_match := re.search(r'^(?:wire|reg|logic)\s+', full_port_list[cursor_pos:]):
                    cursor_pos += len(type_match.group())
                
                # Extract width if present
                width = ""
                if dim_match := re.search(r'^\s*\[(.*?)\]\s*', full_port_list[cursor_pos:]):
                    width = dim_match.group(1)
                    cursor_pos += len(dim_match.group())
                
                # Find the end of this port declaration group
                end_pos = cursor_pos
                bracket_depth = 0
                
                while end_pos < len(full_port_list):
                    char = full_port_list[end_pos]
                    
                    # Track bracket depth
                    if char == '[':
                        bracket_depth += 1
                    elif char == ']':
                        bracket_depth -= 1
                    # Look for next direction keyword or end of port list
                    elif bracket_depth == 0 and re.search(r'^\s*(?:input|output|inout)\s+', full_port_list[end_pos:]):
                        break
                    
                    end_pos += 1
                
                # Extract the port list
                port_list = full_port_list[cursor_pos:end_pos].strip()
                
                # Handle potential trailing comma
                if port_list.endswith(','):
                    port_list = port_list[:-1]
                
                # Split by commas (outside of brackets)
                ports = SystemVerilogParser.split_comma_list(port_list)
                
                # Add width to port names if present
                if width:
                    ports = [f"{p}[{width}]" for p in ports]
                
                outputs.extend(ports)
                
                cursor_pos = end_pos
                continue
            
            # Look for inout declaration
            if match := re.search(r'inout\s+', full_port_list[cursor_pos:]):
                start_pos = cursor_pos + match.start()
                cursor_pos = start_pos + len(match.group())
                
                # Skip type if present
                if type_match := re.search(r'^(?:wire|reg|logic)\s+', full_port_list[cursor_pos:]):
                    cursor_pos += len(type_match.group())
                
                # Extract width if present
                width = ""
                if dim_match := re.search(r'^\s*\[(.*?)\]\s*', full_port_list[cursor_pos:]):
                    width = dim_match.group(1)
                    cursor_pos += len(dim_match.group())
                
                # Find the end of this port declaration group
                end_pos = cursor_pos
                bracket_depth = 0
                
                while end_pos < len(full_port_list):
                    char = full_port_list[end_pos]
                    
                    # Track bracket depth
                    if char == '[':
                        bracket_depth += 1
                    elif char == ']':
                        bracket_depth -= 1
                    # Look for next direction keyword or end of port list
                    elif bracket_depth == 0 and re.search(r'^\s*(?:input|output|inout)\s+', full_port_list[end_pos:]):
                        break
                    
                    end_pos += 1
                
                # Extract the port list
                port_list = full_port_list[cursor_pos:end_pos].strip()
                
                # Handle potential trailing comma
                if port_list.endswith(','):
                    port_list = port_list[:-1]
                
                # Split by commas (outside of brackets)
                ports = SystemVerilogParser.split_comma_list(port_list)
                
                # Add width to port names if present
                if width:
                    ports = [f"{p}[{width}]" for p in ports]
                
                inouts.extend(ports)
                
                cursor_pos = end_pos
                continue
            
            # If no match found, move to the end
            cursor_pos = len(full_port_list)
        
        return inputs, outputs, inouts
    
    @staticmethod
    def split_comma_list(port_list):
        """Split a comma-separated list of ports while respecting brackets"""
        ports = []
        current = ""
        bracket_depth = 0
        
        for char in port_list + ',':  # Add comma at end to handle the last port
            if char == '[':
                bracket_depth += 1
                current += char
            elif char == ']':
                bracket_depth -= 1
                current += char
            elif char == ',' and bracket_depth == 0:
                if current.strip():
                    # Clean up the port name - remove dimensions
                    port_name = SystemVerilogParser.extract_port_name(current.strip())
                    if port_name:
                        ports.append(port_name)
                current = ""
            else:
                current += char
        
        return ports
    
    @staticmethod
    def extract_port_name(port_text):
        """Extract just the port name from port text that might have dimensions"""
        # Remove array dimensions if present
        port_text = re.sub(r'\[.*?\]', '', port_text)
        
        # Return the trimmed text as the port name
        return port_text.strip()
    
    @staticmethod
    def parse_port_list(port_list_text):
        """Parse module port list to extract port names (for non-ANSI style)"""
        port_names = []
        
        # Clean up port list by removing extra whitespace and newlines
        clean_port_list = re.sub(r'\s+', ' ', port_list_text).strip()
        
        # Handle potential parameter lists in the port list
        clean_port_list = re.sub(r'\([^()]*\)', '', clean_port_list)
        
        # Split by commas outside of brackets
        ports = SystemVerilogParser.split_comma_list(clean_port_list)
        
        return ports
    
    @staticmethod
    def parse_module_body(module_body, port_names):
        """Parse module body to find port declarations for non-ANSI style"""
        inputs = []
        outputs = []
        inouts = []
        
        # Extract declaration blocks by type
        input_blocks = re.findall(r'input\s+(?:wire|reg|logic)?\s*(?:\[(.*?)\])?\s*([\w\s,]+)\s*;', module_body)
        output_blocks = re.findall(r'output\s+(?:wire|reg|logic)?\s*(?:\[(.*?)\])?\s*([\w\s,]+)\s*;', module_body)
        inout_blocks = re.findall(r'inout\s+(?:wire|reg|logic)?\s*(?:\[(.*?)\])?\s*([\w\s,]+)\s*;', module_body)
        
        # Process input blocks
        for width, block in input_blocks:
            ports = SystemVerilogParser.split_comma_list(block)
            for port in ports:
                if port in port_names and port not in inputs:
                    if width:
                        inputs.append(f"{port}[{width}]")
                    else:
                        inputs.append(port)
        
        # Process output blocks
        for width, block in output_blocks:
            ports = SystemVerilogParser.split_comma_list(block)
            for port in ports:
                if port in port_names and port not in outputs:
                    if width:
                        outputs.append(f"{port}[{width}]")
                    else:
                        outputs.append(port)
        
        # Process inout blocks
        for width, block in inout_blocks:
            ports = SystemVerilogParser.split_comma_list(block)
            for port in ports:
                if port in port_names and port not in inouts:
                    if width:
                        inouts.append(f"{port}[{width}]")
                    else:
                        inouts.append(port)
        
        return inputs, outputs, inouts


class ModuleItem(QGraphicsItem):
    """Represents a SystemVerilog module in the design canvas"""
    
    def __init__(self, name, ports=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.ports = ports or {"inputs": [], "outputs": []}
        self.port_widths = {}  # Store register widths for each port
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)  # Enable hover events for tooltips
        
        # Default module dimensions
        self.min_width = 150  # Increased to accommodate register widths
        self.max_text_length = 15  # Default max characters to display
        self.port_spacing = 15
        self.port_radius = 5
        self.text_margin = 15
        
        # Parse port names to extract register widths
        self.parse_port_widths()
        
        # Calculate the width based on port names
        self.recalculate_dimensions()
        
        self.port_positions = {}  # Will store positions of ports for connections
        self.highlight_port = None
        self.drag_start_pos = None  # Track drag position
    
    def parse_port_widths(self):
        """Extract register widths from port names"""
        # Format expected: portname[width]
        # Example: data[31:0] or addr[7:0]
        
        for port_type in ["inputs", "outputs"]:
            new_ports = []
            for port in self.ports[port_type]:
                # Check if port has width information
                match = re.search(r'(\w+)(?:\[([^\]]+)\])?', port)
                if match:
                    port_name = match.group(1)
                    width = match.group(2) if match.group(2) else ""
                    self.port_widths[port_name] = width
                    new_ports.append(port_name)
                else:
                    self.port_widths[port] = ""
                    new_ports.append(port)
            
            # Update ports with clean names (without width notation)
            self.ports[port_type] = new_ports
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        port = self.find_port_at_position(event.pos())
        if port:
            # If clicking on a port, let the parent scene handle it for wire creation
            event.ignore()
        else:
            # If not clicking on a port, allow normal drag behavior by accepting the event
            self.drag_start_pos = event.pos()
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        super().mouseMoveEvent(event)
        # Update connected wires when the module is moved
        scene = self.scene()
        if scene:
            for wire in scene.wires:
                if wire.start_module == self:
                    wire.start_pos = self.mapToScene(self.port_positions[wire.start_port])
                    wire.update()
                if wire.end_module == self:
                    wire.end_pos = self.mapToScene(self.port_positions[wire.end_port])
                    wire.update()
    
    def recalculate_dimensions(self):
        """Calculate dimensions based on current settings"""
        # Get font metrics to calculate text widths
        font = QFont("Arial", 9)
        metrics = QFontMetrics(font)
        
        # Calculate the width needed for input ports (including register width)
        input_width = 0
        for port in self.ports["inputs"]:
            # Calculate port name width (truncated if needed)
            port_text = self.truncate_text(port)
            port_width = metrics.width(port_text)
            
            # Add width text if available
            width_text = f"[{self.port_widths[port]}]" if self.port_widths.get(port, "") else ""
            if width_text:
                port_width += metrics.width(width_text) + 5  # Add extra spacing
            
            input_width = max(input_width, port_width)
        
        # Calculate the width needed for output ports (including register width)
        output_width = 0
        for port in self.ports["outputs"]:
            # Calculate port name width (truncated if needed)
            port_text = self.truncate_text(port)
            port_width = metrics.width(port_text)
            
            # Add width text if available
            width_text = f"[{self.port_widths[port]}]" if self.port_widths.get(port, "") else ""
            if width_text:
                port_width += metrics.width(width_text) + 5  # Add extra spacing
            
            output_width = max(output_width, port_width)
        
        # Set module width based on port names and width information
        text_width = self.text_margin + input_width + output_width + self.text_margin + 30
        self.width = max(self.min_width, text_width)
        
        # Calculate height based on number of ports
        port_count = max(len(self.ports["inputs"]), len(self.ports["outputs"]))
        self.height = max(80, 30 + self.port_spacing * port_count)
    
    def set_max_text_length(self, length):
        """Set the maximum text length to display"""
        self.max_text_length = length
        self.recalculate_dimensions()
        self.update()
    
    def set_port_spacing(self, spacing):
        """Set the spacing between ports"""
        self.port_spacing = spacing
        self.recalculate_dimensions()
        self.update()
    
    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)
    
    def truncate_text(self, text):
        """Truncate text if longer than max_text_length"""
        if len(text) > self.max_text_length:
            return text[:self.max_text_length-3] + "..."
        return text
    
    def paint(self, painter, option, widget):
        # Draw module box
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(QColor(220, 220, 255)))
        painter.drawRect(0, 0, self.width, self.height)
        
        # Draw module name
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(10, 20, self.name)
        font.setBold(False)
        painter.setFont(font)
        
        # Draw input ports on left side
        y_offset = 30
        for i, port in enumerate(self.ports["inputs"]):
            pos_y = y_offset + i * self.port_spacing
            
            # Highlight port if it's being hovered
            if self.highlight_port == port:
                painter.setBrush(QBrush(Qt.yellow))
                painter.setPen(QPen(Qt.red, 2))
            else:
                painter.setBrush(QBrush(Qt.red))
                painter.setPen(QPen(Qt.black, 2))
                
            painter.drawEllipse(0, pos_y, self.port_radius * 2, self.port_radius * 2)
            
            # Draw truncated port name
            truncated_port = self.truncate_text(port)
            painter.drawText(self.text_margin, pos_y + 8, truncated_port)
            
            # Draw port width if available
            if self.port_widths.get(port, ""):
                width_text = f"[{self.port_widths[port]}]"
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(self.text_margin + painter.fontMetrics().width(truncated_port) + 5, 
                               pos_y + 8, width_text)
                painter.setPen(QPen(Qt.black))
            
            self.port_positions[port] = QPointF(0, pos_y + self.port_radius)
            
        # Draw output ports on right side
        for i, port in enumerate(self.ports["outputs"]):
            pos_y = y_offset + i * self.port_spacing
            
            # Highlight port if it's being hovered
            if self.highlight_port == port:
                painter.setBrush(QBrush(Qt.yellow))
                painter.setPen(QPen(Qt.green, 2))
            else:
                painter.setBrush(QBrush(Qt.green))
                painter.setPen(QPen(Qt.black, 2))
                
            painter.drawEllipse(self.width - self.port_radius * 2, pos_y, 
                               self.port_radius * 2, self.port_radius * 2)
            
            # Draw truncated port name
            truncated_port = self.truncate_text(port)
            
            # Calculate width of port name for alignment
            text_width = painter.fontMetrics().width(truncated_port)
            
            # Calculate width of port width text if available
            width_text = f"[{self.port_widths[port]}]" if self.port_widths.get(port, "") else ""
            width_text_width = painter.fontMetrics().width(width_text)
            
            # Position for port name
            text_x = self.width - text_width - self.text_margin - width_text_width - 5
            if width_text:
                text_x -= 5  # Additional spacing if width is present
            
            painter.drawText(text_x, pos_y + 8, truncated_port)
            
            # Draw port width if available
            if width_text:
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(self.width - width_text_width - self.text_margin, 
                               pos_y + 8, width_text)
                painter.setPen(QPen(Qt.black))
            
            self.port_positions[port] = QPointF(self.width, pos_y + self.port_radius)
    
    def find_port_at_position(self, pos):
        """Find if a port exists at the given position"""
        for port, port_pos in self.port_positions.items():
            if (port_pos - pos).manhattanLength() < 10:
                return port
        return None
    
    def hoverMoveEvent(self, event):
        """Handle hover move events for port highlighting"""
        port = self.find_port_at_position(event.pos())
        if port != self.highlight_port:
            self.highlight_port = port
            self.update()
            
            # Show tooltip with full port name and width if hovering over a port
            if port:
                width_text = f" [{self.port_widths[port]}]" if self.port_widths.get(port, "") else ""
                port_type = "Input" if port in self.ports["inputs"] else "Output"
                tooltip = f"{port_type}: {port}{width_text}"
                QToolTip.showText(event.screenPos(), tooltip)
            
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave events"""
        if self.highlight_port:
            self.highlight_port = None
            self.update()
        super().hoverLeaveEvent(event)


class WireItem(QGraphicsItem):
    """Represents a wire connecting two module ports"""
    
    def __init__(self, start_module, end_module, start_port, end_port, start_pos, end_pos):
        super().__init__()
        self.start_module = start_module
        self.end_module = end_module
        self.start_port = start_port
        self.end_port = end_port
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.setAcceptHoverEvents(True)  # Enable hover events for tooltips
        self.hover = False
        
    def boundingRect(self):
        """Create a bounding rectangle that dynamically encompasses the wire"""
        # Use current positions rather than stored positions
        start_pos = self.start_module.mapToScene(self.start_module.port_positions[self.start_port])
        end_pos = self.end_module.mapToScene(self.end_module.port_positions[self.end_port])
        
        x = min(start_pos.x(), end_pos.x())
        y = min(start_pos.y(), end_pos.y())
        width = abs(end_pos.x() - start_pos.x())
        height = abs(end_pos.y() - start_pos.y())
        return QRectF(x, y, width, height).adjusted(-5, -5, 5, 5)
    
    def paint(self, painter, option, widget):
        """Paint the wire using current module positions"""
        # Get current positions from modules
        start_pos = self.start_module.mapToScene(self.start_module.port_positions[self.start_port])
        end_pos = self.end_module.mapToScene(self.end_module.port_positions[self.end_port])
        
        # Update stored positions
        self.start_pos = start_pos
        self.end_pos = end_pos
        
        if self.hover:
            # Highlight wire when hovered
            painter.setPen(QPen(Qt.red, 3))
        else:
            painter.setPen(QPen(Qt.black, 2))
        
        painter.drawLine(start_pos, end_pos)

    def hoverEnterEvent(self, event):
        """Handle hover enter events"""
        self.hover = True
        self.update()
        tooltip = f"{self.start_module.name}.{self.start_port} → {self.end_module.name}.{self.end_port}"
        QToolTip.showText(event.screenPos(), tooltip)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave events"""
        self.hover = False
        self.update()
        super().hoverLeaveEvent(event)


class DesignCanvas(QGraphicsScene):
    """The main canvas where modules and wires are placed and manipulated"""
    
    def __init__(self):
        super().__init__()
        self.modules = {}  # Store module objects by name
        self.wires = []    # Store wire connections
        self.drawing_wire = False
        self.start_module = None
        self.start_port = None
        self.start_pos = None
        self.temp_line = None
        self.setSceneRect(-5000, -5000, 10000, 10000)  # Large canvas area
    
    def get_module_type(self, module_name):
        """Get the original module type from the instance name"""
        if '_' in module_name and module_name.split('_')[-1].isdigit():
            return '_'.join(module_name.split('_')[:-1])
        return module_name
    
    def contextMenuEvent(self, event):
        """Show context menu"""
        menu = QMenu()
        
        # Add global actions
        add_module_action = menu.addAction("Add Module")
        delete_action = None
        
        # Add actions for selected items
        selected_items = self.selectedItems()
        if selected_items:
            delete_action = menu.addAction("Delete Selected")
        
        action = menu.exec_(event.screenPos())
        
        # Handle menu actions
        if action == add_module_action:
            # Signal main window to show add module dialog
            main_window = self.views()[0].window()
            main_window.add_module_manually()
        
        elif action == delete_action:
            self.delete_selected_items()
    
    def delete_selected_items(self):
        """Delete selected items"""
        selected_items = self.selectedItems()
        
        for item in selected_items:
            # If it's a module
            if isinstance(item, ModuleItem):
                # Remove all wires connected to this module
                wires_to_remove = []
                for wire in self.wires:
                    if wire.start_module == item or wire.end_module == item:
                        wires_to_remove.append(wire)
                
                for wire in wires_to_remove:
                    self.wires.remove(wire)
                    self.removeItem(wire)
                
                # Remove module from dictionary and scene
                del self.modules[item.name]
                self.removeItem(item)
            
            # If it's a wire
            elif isinstance(item, WireItem):
                self.wires.remove(item)
                self.removeItem(item)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for wire creation"""
        # First, check if we're clicking on a port
        port_clicked = False
        
        if event.button() == Qt.LeftButton:
            # Check if user clicked on a port
            for module in self.modules.values():
                port = module.find_port_at_position(module.mapFromScene(event.scenePos()))
                if port:
                    self.drawing_wire = True
                    self.start_module = module
                    self.start_port = port
                    self.start_pos = module.mapToScene(module.port_positions[port])
                    self.temp_line = self.addLine(
                        self.start_pos.x(), self.start_pos.y(),
                        event.scenePos().x(), event.scenePos().y(),
                        QPen(Qt.DashLine)
                    )
                    port_clicked = True
                    break
        
        # Only if we didn't click on a port, pass the event to the base class
        if not port_clicked:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Update temporary wire during drawing"""
        super().mouseMoveEvent(event)
        
        if self.drawing_wire and self.temp_line:
            self.temp_line.setLine(
                self.start_pos.x(), self.start_pos.y(),
                event.scenePos().x(), event.scenePos().y()
            )
    
    def mouseReleaseEvent(self, event):
        """Finalize wire creation"""
        super().mouseReleaseEvent(event)
        
        if self.drawing_wire and event.button() == Qt.LeftButton:
            valid_connection = False
            
            # Check if mouse was released on another port
            for module in self.modules.values():
                if module == self.start_module:
                    continue  # Skip self-connections
                    
                for port, pos in module.port_positions.items():
                    global_pos = module.mapToScene(pos)
                    if (global_pos - event.scenePos()).manhattanLength() < 10:
                        # Check if it's a valid connection (output -> input)
                        if (self.start_port in self.start_module.ports["outputs"] and 
                            port in module.ports["inputs"]):
                            # Valid connection: output -> input
                            valid_connection = True
                        elif (self.start_port in self.start_module.ports["inputs"] and 
                              port in module.ports["outputs"]):
                            # Valid connection: input <- output (reverse connection)
                            valid_connection = True
                            # Swap start and end for correct direction
                            self.start_module, module = module, self.start_module
                            self.start_port, port = port, self.start_port
                            self.start_pos = global_pos
                        
                        if valid_connection:
                            # Check if the input port is already connected
                            # Note: we allow multiple connections to the same output
                            input_already_connected = False
                            
                            # If we're connecting to an input port, check if it's already connected
                            if port in module.ports["inputs"]:
                                for wire in self.wires:
                                    if wire.end_module == module and wire.end_port == port:
                                        input_already_connected = True
                                        break
                            
                            if not input_already_connected:
                                # Create permanent wire
                                wire = WireItem(
                                    self.start_module,
                                    module,
                                    self.start_port,
                                    port,
                                    self.start_pos,
                                    global_pos
                                )
                                self.addItem(wire)
                                self.wires.append(wire)
                            else:
                                QMessageBox.warning(None, "Connection Error", 
                                                  "Input port already connected! Each input can only connect to one output.")
                        else:
                            QMessageBox.warning(None, "Connection Error", 
                                              "Invalid connection! Connect output to input.")
                        break
            
            # Remove temporary line
            if self.temp_line:
                self.removeItem(self.temp_line)
                self.temp_line = None
            
            self.drawing_wire = False
            self.start_module = None
            self.start_port = None


class ModuleLibraryWidget(QListWidget):
    """Widget to display available SystemVerilog modules"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.modules = {}  # Module definitions
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def add_module_definition(self, name, inputs, outputs):
        """Add a module definition to the library"""
        self.modules[name] = {
            "inputs": inputs,
            "outputs": outputs
        }
        self.addItem(name)
    
    def load_module_file(self, filename):
        """Load module definitions from a SystemVerilog file"""
        modules = SystemVerilogParser.parse_file(filename)
        
        for name, ports in modules.items():
            self.add_module_definition(name, ports["inputs"], ports["outputs"])
            
        return len(modules) > 0
    
    def show_context_menu(self, position):
        """Show context menu for modules in library"""
        menu = QMenu()
        
        item = self.itemAt(position)
        if item:
            module_name = item.text()
            view_action = menu.addAction(f"View {module_name} Details")
            delete_action = menu.addAction(f"Remove {module_name}")
            
            action = menu.exec_(self.mapToGlobal(position))
            
            if action == view_action:
                self.show_module_details(module_name)
            elif action == delete_action:
                self.delete_module(module_name)
    
    def show_module_details(self, module_name):
        """Show module details in a message box"""
        if module_name in self.modules:
            module = self.modules[module_name]
            inputs = ", ".join(module["inputs"])
            outputs = ", ".join(module["outputs"])
            
            details = f"Module: {module_name}\n\n"
            details += f"Inputs ({len(module['inputs'])}):\n{inputs}\n\n"
            details += f"Outputs ({len(module['outputs'])}):\n{outputs}"
            
            QMessageBox.information(self, f"Module Details - {module_name}", details)
    
    def delete_module(self, module_name):
        """Remove a module from the library"""
        if module_name in self.modules:
            reply = QMessageBox.question(self, "Confirm Deletion", 
                                       f"Are you sure you want to remove {module_name}?",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                del self.modules[module_name]
                items = self.findItems(module_name, Qt.MatchExactly)
                for item in items:
                    self.takeItem(self.row(item))


class SystemVerilogDesigner(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SystemVerilog Module Designer")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create the graphics view and scene
        self.canvas = DesignCanvas()
        self.view = QGraphicsView(self.canvas)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)  # Enable selection rectangle
        self.setCentralWidget(self.view)
        
        # Create module library panel
        self.create_module_library()
        
        # Create display control toolbar
        self.create_display_controls()
        
        # Create menus
        self.create_menus()
    
    def create_module_library(self):
        """Create the module library panel"""
        self.module_library = ModuleLibraryWidget()
        self.module_library.itemDoubleClicked.connect(self.add_module_from_library)
        
        dock = QDockWidget("Module Library", self)
        dock.setWidget(self.module_library)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
    
    def create_display_controls(self):
        """Create toolbar with display controls"""
        display_toolbar = QToolBar("Display Controls")
        self.addToolBar(display_toolbar)
        
        # Module text length control
        display_toolbar.addWidget(QLabel("Port Text Length:"))
        
        self.text_length_slider = QSlider(Qt.Horizontal)
        self.text_length_slider.setRange(5, 50)
        self.text_length_slider.setValue(15)
        self.text_length_slider.setFixedWidth(150)
        self.text_length_slider.valueChanged.connect(self.update_text_length)
        display_toolbar.addWidget(self.text_length_slider)
        
        self.text_length_spinner = QSpinBox()
        self.text_length_spinner.setRange(5, 50)
        self.text_length_spinner.setValue(15)
        self.text_length_spinner.valueChanged.connect(self.text_length_slider.setValue)
        display_toolbar.addWidget(self.text_length_spinner)
        
        self.text_length_slider.valueChanged.connect(self.text_length_spinner.setValue)
        
        # Add spacing
        display_toolbar.addSeparator()
        
        # Port spacing control
        display_toolbar.addWidget(QLabel("Port Spacing:"))
        
        self.port_spacing_slider = QSlider(Qt.Horizontal)
        self.port_spacing_slider.setRange(10, 30)
        self.port_spacing_slider.setValue(15)
        self.port_spacing_slider.setFixedWidth(150)
        self.port_spacing_slider.valueChanged.connect(self.update_port_spacing)
        display_toolbar.addWidget(self.port_spacing_slider)
        
        self.port_spacing_spinner = QSpinBox()
        self.port_spacing_spinner.setRange(10, 30)
        self.port_spacing_spinner.setValue(15)
        self.port_spacing_spinner.valueChanged.connect(self.port_spacing_slider.setValue)
        display_toolbar.addWidget(self.port_spacing_spinner)
        
        self.port_spacing_slider.valueChanged.connect(self.port_spacing_spinner.setValue)
        
        # Add spacing
        display_toolbar.addSeparator()
        
        # Add zoom controls
        display_toolbar.addWidget(QLabel("Zoom:"))
        
        zoom_in_button = QPushButton("+")
        zoom_in_button.clicked.connect(self.zoom_in)
        display_toolbar.addWidget(zoom_in_button)
        
        zoom_out_button = QPushButton("-")
        zoom_out_button.clicked.connect(self.zoom_out)
        display_toolbar.addWidget(zoom_out_button)
        
        zoom_reset_button = QPushButton("Reset")
        zoom_reset_button.clicked.connect(self.zoom_reset)
        display_toolbar.addWidget(zoom_reset_button)
        
        # Add fit view button
        fit_button = QPushButton("Fit View")
        fit_button.clicked.connect(self.fit_view)
        display_toolbar.addWidget(fit_button)
    
    def create_menus(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_design)
        file_menu.addAction(new_action)
        
        load_module_action = QAction("Load Module", self)
        load_module_action.setShortcut("Ctrl+L")
        load_module_action.triggered.connect(self.load_module)
        file_menu.addAction(load_module_action)
        
        save_action = QAction("Save SystemVerilog", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.generate_systemverilog)
        file_menu.addAction(save_action)
        
        export_image_action = QAction("Export as Image", self)
        export_image_action.triggered.connect(self.export_as_image)
        file_menu.addAction(export_image_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Module menu
        module_menu = menubar.addMenu("Module")
        
        add_action = QAction("Add Module", self)
        add_action.setShortcut("Ctrl+A")
        add_action.triggered.connect(self.add_module_manually)
        module_menu.addAction(add_action)
        
        delete_action = QAction("Delete Selected", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected)
        module_menu.addAction(delete_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        zoom_reset_action = QAction("Reset Zoom", self)
        zoom_reset_action.setShortcut("Ctrl+0")
        zoom_reset_action.triggered.connect(self.zoom_reset)
        view_menu.addAction(zoom_reset_action)
        
        fit_view_action = QAction("Fit to View", self)
        fit_view_action.setShortcut("Ctrl+F")
        fit_view_action.triggered.connect(self.fit_view)
        view_menu.addAction(fit_view_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def update_text_length(self, value):
        """Update text length for all modules"""
        for module in self.canvas.modules.values():
            module.set_max_text_length(value)
        self.canvas.update()
    
    def update_port_spacing(self, value):
        """Update port spacing for all modules"""
        for module in self.canvas.modules.values():
            module.set_port_spacing(value)
        self.canvas.update()
    
    def zoom_in(self):
        """Zoom in the view"""
        self.view.scale(1.2, 1.2)
    
    def zoom_out(self):
        """Zoom out the view"""
        self.view.scale(1/1.2, 1/1.2)
    
    def zoom_reset(self):
        """Reset zoom level"""
        self.view.resetTransform()
    
    def fit_view(self):
        """Fit all content in the view"""
        if not self.canvas.modules:
            return
        
        self.view.fitInView(self.canvas.itemsBoundingRect(), Qt.KeepAspectRatio)
    
    def new_design(self):
        """Clear the current design"""
        reply = QMessageBox.question(self, "New Design", 
                                   "Are you sure you want to create a new design? Any unsaved changes will be lost.",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.canvas.clear()
            self.canvas.modules = {}
            self.canvas.wires = []
    
    def load_module(self):
        """Load a SystemVerilog module from file"""
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Open SystemVerilog Files", "", "SystemVerilog Files (*.sv);;Verilog Files (*.v)"
        )
        
        modules_added = 0
        for filename in filenames:
            if self.module_library.load_module_file(filename):
                modules_added += 1
        
        if modules_added > 0:
            QMessageBox.information(self, "Modules Loaded", 
                                  f"Loaded {modules_added} modules from {len(filenames)} files")
        else:
            QMessageBox.warning(self, "No Modules Found", 
                              "No modules found in the selected files")
    
    def add_module_from_library(self, item):
        """Add a module from the library to the canvas"""
        module_name = item.text()
        if module_name in self.module_library.modules:
            ports = self.module_library.modules[module_name]
            
            # Create a unique instance name
            instance_name = module_name
            count = 1
            while instance_name in self.canvas.modules:
                instance_name = f"{module_name}_{count}"
                count += 1
            
            module = ModuleItem(instance_name, ports)
            self.canvas.addItem(module)
            self.canvas.modules[instance_name] = module
            
            # Position module in center of view
            module.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
    
    def add_module_manually(self):
        """Add a new module to the canvas manually"""
        module_name, ok = QInputDialog.getText(self, "Add Module", "Module name:")
        if ok and module_name:
            # Check if it's in the library
            if module_name in self.module_library.modules:
                # Use the module from the library
                ports = self.module_library.modules[module_name]
                self.add_module_to_canvas(module_name, ports)
            else:
                # Create new module
                input_ports, ok = QInputDialog.getText(self, "Input Ports", 
                                                  "Input port names (comma-separated):")
                if not ok:
                    input_ports = ""
                    
                output_ports, ok = QInputDialog.getText(self, "Output Ports", 
                                                   "Output port names (comma-separated):")
                if not ok:
                    output_ports = ""
                
                ports = {
                    "inputs": [p.strip() for p in input_ports.split(",") if p.strip()],
                    "outputs": [p.strip() for p in output_ports.split(",") if p.strip()]
                }
                
                # Add to library
                self.module_library.add_module_definition(module_name, ports["inputs"], ports["outputs"])
                
                # Add to canvas
                self.add_module_to_canvas(module_name, ports)
    
    def add_module_to_canvas(self, module_name, ports):
        """Add a module to the canvas with a unique instance name"""
        instance_name = module_name
        count = 1
        while instance_name in self.canvas.modules:
            instance_name = f"{module_name}_{count}"
            count += 1
        
        module = ModuleItem(instance_name, ports)
        self.canvas.addItem(module)
        self.canvas.modules[instance_name] = module
        
        # Position module in center of view
        module.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
    
    def delete_selected(self):
        """Delete selected items"""
        self.canvas.delete_selected_items()
    
    def export_as_image(self):
        """Export the design as an image"""
        if not self.canvas.modules:
            QMessageBox.warning(self, "Empty Design", "There is nothing to export")
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, "Export Image", "", 
                                                "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)")
        if not filename:
            return
        
        # Create an image of the scene
        rect = self.canvas.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        image = QImage(rect.size().toSize(), QImage.Format_ARGB32)
        image.fill(Qt.white)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.canvas.render(painter, QRectF(image.rect()), rect)
        painter.end()
        
        # Save the image
        if image.save(filename):
            QMessageBox.information(self, "Export Successful", f"Design exported to {filename}")
        else:
            QMessageBox.warning(self, "Export Failed", "Failed to save the image")
    
    def generate_systemverilog(self):
        """Generate SystemVerilog code from the design and save to file"""
        if not self.canvas.modules:
            QMessageBox.warning(self, "Empty Design", "There are no modules to generate code from")
            return
        
        # Get output filename
        filename, _ = QFileDialog.getSaveFileName(self, "Save SystemVerilog File", "", 
                                                 "SystemVerilog Files (*.sv)")
        if not filename:
            return
        
        # Create top module
        top_name, ok = QInputDialog.getText(self, "Top Module", "Top module name:")
        if not ok or not top_name:
            top_name = "top"
        
        # Generate SystemVerilog code directly
        sv_code = []
        
        # Module header
        sv_code.append(f"module {top_name} (")
        
        # Collect external ports
        external_inputs = []
        external_outputs = []
        
        for module in self.canvas.modules.values():
            for port in module.ports["inputs"]:
                # Check if this port has a connection
                has_connection = False
                for wire in self.canvas.wires:
                    if wire.end_module == module and wire.end_port == port:
                        has_connection = True
                        break
                
                if not has_connection:
                    width = f"[{module.port_widths[port]}]" if module.port_widths.get(port, "") else ""
                    external_inputs.append((f"{module.name}_{port}", width))
            
            for port in module.ports["outputs"]:
                has_connection = False
                for wire in self.canvas.wires:
                    if wire.start_module == module and wire.start_port == port:
                        has_connection = True
                        break
                
                if not has_connection:
                    width = f"[{module.port_widths[port]}]" if module.port_widths.get(port, "") else ""
                    external_outputs.append((f"{module.name}_{port}", width))
        
        # Add port declarations
        ports = []
        for port, width in external_inputs:
            ports.append(f"  input wire {width}{port}")
        
        for port, width in external_outputs:
            ports.append(f"  output wire {width}{port}")
        
        if ports:
            sv_code.append(",\n".join(ports))
        else:
            # No external ports - create a dummy port to make the code valid
            sv_code.append("  // No external connections")
        
        sv_code.append(");")
        
        # Internal wire declarations
        wire_names = {}
        
        for wire in self.canvas.wires:
            start_qualname = f"{wire.start_module.name}_{wire.start_port}"
            end_qualname = f"{wire.end_module.name}_{wire.end_port}"
            wire_name = f"w_{start_qualname}_to_{end_qualname}"
            wire_names[(wire.start_module, wire.start_port, wire.end_module, wire.end_port)] = wire_name
            
            # Add width information if available
            width = f"[{wire.start_module.port_widths[wire.start_port]}]" if wire.start_module.port_widths.get(wire.start_port, "") else ""
            sv_code.append(f"  wire {width}{wire_name};")
        
        # Add newline after wire declarations
        if self.canvas.wires:
            sv_code.append("")
        
        # Module instantiations
        for module_name, module in self.canvas.modules.items():
            # Get module type from the module_name (remove instance numbers)
            module_type = self.canvas.get_module_type(module_name)
            
            sv_code.append(f"  {module_type} {module_name} (")
            
            # Add port connections
            connections = []
            
            for port in module.ports["inputs"] + module.ports["outputs"]:
                connected = False
                
                if port in module.ports["inputs"]:
                    # Find wire coming into this input
                    for wire in self.canvas.wires:
                        if wire.end_module == module and wire.end_port == port:
                            connected = True
                            wire_name = wire_names[(wire.start_module, wire.start_port, wire.end_module, wire.end_port)]
                            connections.append(f"    .{port}({wire_name})")
                            break
                
                elif port in module.ports["outputs"]:
                    # Find wire going from this output
                    for wire in self.canvas.wires:
                        if wire.start_module == module and wire.start_port == port:
                            connected = True
                            wire_name = wire_names[(wire.start_module, wire.start_port, wire.end_module, wire.end_port)]
                            connections.append(f"    .{port}({wire_name})")
                            break
                
                if not connected:
                    # Connect to external port
                    external_name = f"{module.name}_{port}"
                    connections.append(f"    .{port}({external_name})")
            
            if connections:
                sv_code.append(",\n".join(connections))
            else:
                sv_code.append("    // No connections")
            
            sv_code.append("  );")
            sv_code.append("")  # Add newline after each module
        
        # End module
        sv_code.append("endmodule")
        
        # Add a comment header with metadata
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        header = [
            "//=============================================================================",
            f"// File: {os.path.basename(filename)}",
            f"// Date: {timestamp}",
            f"// Description: Top level SystemVerilog module '{top_name}' generated by SystemVerilog Designer",
            "// Contains the following module instances:",
        ]
        
        for module_name in self.canvas.modules:
            header.append(f"//   - {module_name}")
        
        header.append("//=============================================================================")
        header.append("")  # Empty line after header
        
        # Insert header at the beginning
        sv_code = header + sv_code
        
        # Write to file
        try:
            with open(filename, "w") as f:
                f.write("\n".join(sv_code))
            
            QMessageBox.information(self, "Code Generated", 
                                  f"SystemVerilog code generated and saved to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        <h1>SystemVerilog Module Designer</h1>
        <p>A tool for designing SystemVerilog module connections graphically.</p>
        <p>Features:</p>
        <ul>
            <li>Load existing SystemVerilog modules</li>
            <li>Create connections with drag and drop</li>
            <li>Generate top-level SystemVerilog file</li>
            <li>Export design as image</li>
        </ul>
        <p>Version: 1.0</p>
        """
        
        QMessageBox.about(self, "About SystemVerilog Module Designer", about_text)
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.canvas.modules:
            reply = QMessageBox.question(self, "Exit", 
                                       "Are you sure you want to exit? Any unsaved changes will be lost.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Arial", 9)
    app.setFont(font)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    designer = SystemVerilogDesigner()
    designer.show()
    
    # Start event loop
    sys.exit(app.exec_())