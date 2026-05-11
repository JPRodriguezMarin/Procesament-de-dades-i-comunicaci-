"""
Listing 8.7 - Utilidades de terminal con secuencias de escape ANSI

Objetivo:
    Proveer funciones para controlar el cursor del terminal mediante secuencias
    ANSI. Permiten al cliente de chat dividir la pantalla en dos zonas:
    mensajes entrantes arriba, campo de input abajo. Son síncronas porque las
    secuencias ANSI se procesan de forma inmediata por el emulador de terminal.

Secuencias usadas:
    \\0337        -> Guarda posición del cursor
    \\0338        -> Restaura posición del cursor
    \\033[H       -> Mueve cursor a fila 1, columna 1
    \\033[2K      -> Borra toda la línea actual
    \\033[n;0H    -> Mueve cursor a fila n, columna 0
"""
import shutil
import sys


def save_cursor_position():
    """Guarda la posición actual del cursor."""
    sys.stdout.write('\0337')
    sys.stdout.flush()


def restore_cursor_position():
    """Restaura el cursor a la posición guardada con save_cursor_position."""
    sys.stdout.write('\0338')
    sys.stdout.flush()


def move_to_top_of_screen():
    """Mueve el cursor a la esquina superior izquierda (fila 1, columna 1)."""
    sys.stdout.write('\033[H')
    sys.stdout.flush()


def delete_line():
    """Borra la línea actual y posiciona el cursor al inicio de la línea."""
    sys.stdout.write('\033[2K\r')
    sys.stdout.flush()


def move_to_bottom_of_screen() -> int:
    """Mueve el cursor a la última fila del terminal. Devuelve número de filas."""
    rows, _ = shutil.get_terminal_size()
    sys.stdout.write(f'\033[{rows};0H')
    sys.stdout.flush()
    return rows
