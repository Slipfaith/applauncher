"""Custom layouts for the launcher."""
from PySide6.QtWidgets import QLayout
from PySide6.QtCore import Qt, QRect, QSize, QPoint


class FlowLayout(QLayout):
    """
    A layout that arranges child widgets from left to right,
    wrapping to the next line when space runs out.
    """

    def __init__(self, parent=None, margin=-1, h_spacing=-1, v_spacing=-1):
        super().__init__(parent)
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def horizontalSpacing(self):
        if self._h_spacing >= 0:
            return self._h_spacing
        return self.spacing()

    def verticalSpacing(self):
        if self._v_spacing >= 0:
            return self._v_spacing
        return self.spacing()

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _resolve_columns(self, available_width: int, min_spacing_x: int, max_item_width: int) -> int:
        if available_width <= 0 or max_item_width <= 0:
            return 1
        columns = (available_width + min_spacing_x) // (max_item_width + min_spacing_x)
        return max(1, int(columns))

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(+left, +top, -right, -bottom)
        items = self._item_list
        if not items:
            return top + bottom

        min_spacing_x = max(0, self.horizontalSpacing())
        spacing_y = max(0, self.verticalSpacing())
        hints = [item.sizeHint() for item in items]
        max_item_width = max(hint.width() for hint in hints)
        available_width = max(0, effective_rect.width())
        max_columns = self._resolve_columns(available_width, min_spacing_x, max_item_width)

        if max_columns > 1:
            full_row_width = max_item_width * max_columns
            remaining = max(0, available_width - full_row_width)
            grid_spacing_x = max(float(min_spacing_x), remaining / float(max_columns - 1))
        else:
            grid_spacing_x = 0.0

        y = effective_rect.y()
        index = 0
        while index < len(items):
            row_items = items[index : index + max_columns]
            row_hints = hints[index : index + max_columns]
            row_height = max(hint.height() for hint in row_hints)

            x = float(effective_rect.x())
            for item, hint in zip(row_items, row_hints):
                if not test_only:
                    item.setGeometry(QRect(QPoint(int(round(x)), y), hint))
                x += hint.width() + grid_spacing_x

            y += row_height + spacing_y
            index += len(row_items)

        return y - effective_rect.y() - spacing_y + top + bottom
