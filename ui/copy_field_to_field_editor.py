from contextlib import suppress

# noinspection PyUnresolvedReferences
from aqt import mw
# noinspection PyUnresolvedReferences
from aqt.qt import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QLabel,
    QDialog,
    QComboBox,
    QFormLayout,
    QPushButton,
    QGridLayout,
    QCheckBox,
    Qt,
    qtmajor,
)

if qtmajor > 5:
    QFrameStyledPanel = QFrame.Shape.StyledPanel
    QFrameShadowRaised = QFrame.Shadow.Raised
else:
    QFrameStyledPanel = QFrame.StyledPanel
    QFrameShadowRaised = QFrame.Raised

from ..configuration import COPY_MODE_WITHIN_NOTE
from .grouped_combo_box import GroupedComboBox
from .edit_extra_processing_dialog import EditExtraProcessingWidget


class CopyFieldToFieldEditor(QWidget):
    """
    Class for editing the list of fields to copy from and fields to copy into.
    Shows the list of current field-to-field definitions. Add button for adding new definitions is at the bottom.
    Remove button for removing definitions is at the top-right of each definition.
    """

    def __init__(self, parent, copy_definition, copy_mode):
        super().__init__(parent)
        self.field_to_field_defs = copy_definition.get("field_to_field_defs", [])
        self.copy_mode = copy_mode

        self.copy_definition = copy_definition
        self.selected_copy_into_model_name = copy_definition.get("copy_into_note_type")

        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)

        self.middle_grid = QGridLayout()
        self.middle_grid.setColumnMinimumWidth(0, 400)
        self.middle_grid.setColumnMinimumWidth(1, 50)
        self.vbox.addLayout(self.middle_grid)

        self.bottom_form = QFormLayout()
        self.vbox.addLayout(self.bottom_form)

        self.add_new_button = QPushButton("Add another field-to-field definition")
        self.bottom_form.addRow("", self.add_new_button)
        self.add_new_button.clicked.connect(self.add_new_definition)

        self.copy_field_inputs = []

        # There has to be at least one definition so initialize with one
        if len(self.field_to_field_defs) == 0:
            self.add_new_definition()
        else:
            for index, copy_field_to_field_definition in enumerate(self.field_to_field_defs):
                self.add_copy_field_row(index, copy_field_to_field_definition)

    def add_new_definition(self):
        new_definition = {
            "copy_into_note_field": "",
            "copy_from_field": "",
            "copy_if_empty": False
        }
        self.field_to_field_defs.append(new_definition)
        self.add_copy_field_row(len(self.field_to_field_defs) - 1, new_definition)

    def add_copy_field_row(self, index, copy_field_to_field_definition):
        # Create a QFrame
        frame = QFrame(self)
        frame.setFrameShape(QFrameStyledPanel)
        frame.setFrameShadow(QFrameShadowRaised)

        # Create a layout for the frame
        frame_layout = QVBoxLayout(frame)

        # Add the frame to the main layout
        self.middle_grid.addWidget(frame, index, 0)
        row_form = QFormLayout()
        frame_layout.addLayout(row_form)

        copy_field_inputs_dict = {}

        # Copy into field
        field_target_cbox = QComboBox()
        copy_field_inputs_dict["copy_into_note_field"] = field_target_cbox
        row_form.addRow("Note field to copy into", field_target_cbox)
        self.update_field_target_options(field_target_cbox)
        with suppress(KeyError):
            field_target_cbox.setCurrentText(copy_field_to_field_definition["copy_into_note_field"])

        # Copy from field
        copy_from_field_cbox = GroupedComboBox()
        copy_field_inputs_dict["copy_from_field"] = copy_from_field_cbox
        row_form.addRow("What field to copy from", copy_from_field_cbox)
        self.update_copy_from_options(copy_from_field_cbox)
        with suppress(KeyError):
            copy_from_field_cbox.setCurrentText(copy_field_to_field_definition["copy_from_field"])

        copy_if_empty = QCheckBox("Only copy into field, if it's empty")
        copy_field_inputs_dict["copy_if_empty"] = copy_if_empty
        row_form.addRow("", copy_if_empty)
        with suppress(KeyError):
            copy_if_empty.setChecked(copy_field_to_field_definition["copy_if_empty"])

        process_chain_widget = EditExtraProcessingWidget(
            self,
            self.copy_definition,
            copy_field_to_field_definition,
        )
        copy_field_inputs_dict["process_chain"] = process_chain_widget
        row_form.addRow("Extra processing", process_chain_widget)

        # Remove
        remove_button = QPushButton("Delete")

        self.copy_field_inputs.append(copy_field_inputs_dict)

        def remove_row():
            for widget in [
                field_target_cbox,
                copy_from_field_cbox,
                copy_if_empty,
                remove_button,
                process_chain_widget,
            ]:
                widget.deleteLater()
                row_form.removeWidget(widget)
                widget = None
            self.middle_grid.removeWidget(frame)
            self.remove_definition(copy_field_to_field_definition, copy_field_inputs_dict)

        remove_button.clicked.connect(remove_row)
        row_form.addRow("", remove_button)

    def remove_definition(self, definition, inputs_dict):
        """
        Removes the selected field-to-field definition and input dict.
        """
        self.field_to_field_defs.remove(definition)
        self.copy_field_inputs.remove(inputs_dict)

    def get_field_to_field_defs(self):
        """
        Returns the list of field-to-field definitions from the current state of the editor.
        """
        field_to_field_defs = []
        for copy_field_inputs in self.copy_field_inputs:
            copy_field_definition = {
                "copy_into_note_field": copy_field_inputs["copy_into_note_field"].currentText(),
                "copy_from_field": copy_field_inputs["copy_from_field"].currentText().strip(),
                "copy_if_empty": copy_field_inputs["copy_if_empty"].isChecked(),
                "process_chain": copy_field_inputs["process_chain"].get_process_chain(),
            }
            field_to_field_defs.append(copy_field_definition)
        return field_to_field_defs

    def set_selected_copy_into_model(self, model_name):
        self.selected_copy_into_model_name = model_name
        for copy_field_inputs in self.copy_field_inputs:
            self.update_field_target_options(copy_field_inputs["copy_into_note_field"])
            if self.copy_mode == COPY_MODE_WITHIN_NOTE:
                self.update_copy_from_options(copy_field_inputs["copy_from_field"])

    def update_field_target_options(self, field_target_cbox):
        """
        Updates the options in the "Note field to copy into" dropdown box.
        """
        model = mw.col.models.by_name(self.selected_copy_into_model_name)
        if model is None:
            return

        previous_text = field_target_cbox.currentText()
        previous_text_in_new_options = False
        # Clear will unset the current selected text
        field_target_cbox.clear()
        field_target_cbox.addItem("-")
        for field_name in mw.col.models.field_names(model):
            if field_name == previous_text:
                previous_text_in_new_options = True
            field_target_cbox.addItem(field_name)

        # Reset the selected text, if the new options still include it
        if previous_text_in_new_options:
            field_target_cbox.setCurrentText(previous_text)

    def update_copy_from_options(self, copy_from_field_cbox):
        """
        Updates the options in the "What field to copy from" dropdown box.
        """
        previous_text = copy_from_field_cbox.currentText().strip()
        previous_text_in_new_options = False

        def add_model_option(model_name, model_id):
            nonlocal previous_text_in_new_options
            copy_from_field_cbox.addGroup(model_name)
            for field_name in mw.col.models.field_names(mw.col.models.get(model_id)):
                copy_from_field_cbox.addItemToGroup(model_name, field_name)
                if field_name == previous_text:
                    previous_text_in_new_options = True

        copy_from_field_cbox.clear()
        copy_from_field_cbox.addItem("-")

        if self.copy_mode == COPY_MODE_WITHIN_NOTE:
            # If we're in within note copy mode, only add the single model as the target
            model = mw.col.models.by_name(self.selected_copy_into_model_name)
            if model is None:
                return
            add_model_option(model["name"], model["id"])
        else:
            # Otherwise, add fields from all models
            models = mw.col.models.all_names_and_ids()
            for model in models:
                add_model_option(model.name, model.id)

        if previous_text_in_new_options:
            copy_from_field_cbox.setCurrentText(previous_text)
