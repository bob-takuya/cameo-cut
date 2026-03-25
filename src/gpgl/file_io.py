"""
GPGL File I/O - Save and load GPGL command files

GPGL files are similar to G-code files but for Silhouette/Graphtec plotters.
They contain ASCII text commands that can be sent directly to the device.
"""

import os
import logging
from typing import Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class GPGLFile:
    """Represents a GPGL command file"""

    # File extension
    EXTENSION = ".gpgl"

    def __init__(self):
        self.commands: List[bytes] = []
        self.metadata: dict = {
            "created": None,
            "source_file": None,
            "width_mm": 0,
            "height_mm": 0,
            "entity_count": 0,
        }

    def add_command(self, command: bytes):
        """Add a command to the file"""
        self.commands.append(command)

    def add_commands(self, commands: bytes):
        """Add multiple commands from a byte string (split by ETX)"""
        # Split by ETX (0x03) and add each command
        parts = commands.split(b'\x03')
        for part in parts:
            if part.strip():
                self.commands.append(part + b'\x03')

    def get_raw_commands(self) -> bytes:
        """Get all commands as a single byte string"""
        return b''.join(self.commands)

    def save(self, filepath: str) -> bool:
        """Save commands to a .gpgl file

        The file format is:
        - Header comments starting with ';'
        - Raw GPGL commands (ASCII)

        Args:
            filepath: Path to save the file

        Returns:
            True if successful
        """
        try:
            # Ensure .gpgl extension
            if not filepath.lower().endswith(self.EXTENSION):
                filepath += self.EXTENSION

            with open(filepath, 'wb') as f:
                # Write header
                header = f"; GPGL Command File\n"
                header += f"; Created: {datetime.now().isoformat()}\n"

                if self.metadata.get("source_file"):
                    header += f"; Source: {self.metadata['source_file']}\n"
                if self.metadata.get("width_mm"):
                    header += f"; Size: {self.metadata['width_mm']:.1f} x {self.metadata['height_mm']:.1f} mm\n"
                if self.metadata.get("entity_count"):
                    header += f"; Entities: {self.metadata['entity_count']}\n"

                header += ";\n"
                header += "; Commands:\n"
                f.write(header.encode('ascii'))

                # Write commands
                for cmd in self.commands:
                    # Convert to readable format with newlines
                    cmd_str = cmd.decode('ascii', errors='replace')
                    # Replace ETX with newline for readability
                    cmd_str = cmd_str.replace('\x03', '\n')
                    f.write(cmd_str.encode('ascii'))

            logger.info(f"Saved GPGL file: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save GPGL file: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> Optional['GPGLFile']:
        """Load commands from a .gpgl file

        Args:
            filepath: Path to the file

        Returns:
            GPGLFile object or None if failed
        """
        try:
            gpgl = cls()

            with open(filepath, 'rb') as f:
                content = f.read()

            # Parse content
            lines = content.decode('ascii', errors='replace').split('\n')

            for line in lines:
                line = line.strip()

                # Skip comments
                if line.startswith(';') or not line:
                    # Parse metadata from comments
                    if line.startswith('; Source:'):
                        gpgl.metadata["source_file"] = line.split(':', 1)[1].strip()
                    elif line.startswith('; Size:'):
                        try:
                            size_str = line.split(':', 1)[1].strip()
                            w, h = size_str.replace('mm', '').split('x')
                            gpgl.metadata["width_mm"] = float(w.strip())
                            gpgl.metadata["height_mm"] = float(h.strip())
                        except:
                            pass
                    continue

                # Add command with ETX terminator
                cmd = line.encode('ascii')
                if not cmd.endswith(b'\x03'):
                    cmd += b'\x03'
                gpgl.commands.append(cmd)

            logger.info(f"Loaded GPGL file: {filepath} ({len(gpgl.commands)} commands)")
            return gpgl

        except Exception as e:
            logger.error(f"Failed to load GPGL file: {e}")
            return None

    def get_human_readable(self) -> str:
        """Get commands in human-readable format"""
        lines = []
        for cmd in self.commands:
            cmd_str = cmd.decode('ascii', errors='replace').replace('\x03', '')
            lines.append(cmd_str)
        return '\n'.join(lines)

    def __len__(self) -> int:
        return len(self.commands)

    def __repr__(self) -> str:
        return f"GPGLFile({len(self.commands)} commands)"


def save_gpgl(commands: bytes, filepath: str, metadata: dict = None) -> bool:
    """Convenience function to save GPGL commands to a file

    Args:
        commands: Raw GPGL command bytes
        filepath: Output file path
        metadata: Optional metadata dict

    Returns:
        True if successful
    """
    gpgl = GPGLFile()
    gpgl.add_commands(commands)
    if metadata:
        gpgl.metadata.update(metadata)
    return gpgl.save(filepath)


def load_gpgl(filepath: str) -> Optional[bytes]:
    """Convenience function to load GPGL commands from a file

    Args:
        filepath: Input file path

    Returns:
        Raw GPGL command bytes or None if failed
    """
    gpgl = GPGLFile.load(filepath)
    if gpgl:
        return gpgl.get_raw_commands()
    return None
