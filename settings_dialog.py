from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from .qgis_branding.branding_footer import BrandingFooter
except Exception:
    BrandingFooter = None


class MiniULDKSettingsDialog(QDialog):
    def __init__(self, initial_settings, parent=None):
        super().__init__(parent)
        self._initial_settings = dict(initial_settings or {})
        self.footer = None

        self.setWindowTitle(self.tr("MiniULDK Settings"))
        self.setModal(True)
        self.resize(520, 0)

        self.shp_enabled_checkbox = QCheckBox(
            self.tr("Save clicked parcels as SHP")
        )
        self.shp_folder_edit = QLineEdit()
        self.shp_browse_button = QPushButton(self.tr("Browse..."))
        self.shp_add_to_project_checkbox = QCheckBox(
            self.tr("Add downloaded parcels to the project")
        )

        self.gpkg_enabled_checkbox = QCheckBox(
            self.tr("Save clicked parcels to GPKG")
        )
        self.gpkg_path_edit = QLineEdit()
        self.gpkg_browse_button = QPushButton(self.tr("Browse..."))
        self.gpkg_add_to_project_checkbox = QCheckBox(
            self.tr("Add downloaded parcels to the project")
        )

        self.temporary_layer_info_label = QLabel(
            self.tr("If the option to add SHP and GPKG layers to the project is disabled, parcels are added to a temporary layer.")
        )
        self.temporary_layer_info_label.setWordWrap(True)
        self.project_settings_info_label = QLabel(
            self.tr("Settings are stored with the saved project.")
        )
        self.project_settings_info_label.setWordWrap(True)

        self.zoom_checkbox = QCheckBox(self.tr("Zoom to the clicked parcel"))

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        self._build_ui()
        self._connect_signals()
        self._apply_initial_settings()
        self._update_enabled_states()

    def tr(self, message):
        return QCoreApplication.translate("MiniULDKSettingsDialog", message)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        shp_group = QGroupBox(self.tr("SHP file save settings"))
        shp_layout = QVBoxLayout(shp_group)
        shp_layout.addWidget(self.shp_enabled_checkbox)
        shp_layout.addWidget(QLabel(self.tr("Target folder path:")))
        shp_layout.addWidget(self._build_path_row(self.shp_folder_edit, self.shp_browse_button))
        shp_info_label = QLabel(
            self.tr("Each downloaded parcel is saved as a new Shapefile in the selected folder.")
        )
        shp_info_label.setWordWrap(True)
        shp_layout.addWidget(shp_info_label)
        shp_layout.addWidget(self.shp_add_to_project_checkbox)

        gpkg_group = QGroupBox(self.tr("GPKG file save settings"))
        gpkg_layout = QVBoxLayout(gpkg_group)
        gpkg_layout.addWidget(self.gpkg_enabled_checkbox)
        gpkg_layout.addWidget(QLabel(self.tr("File save path:")))
        gpkg_layout.addWidget(self._build_path_row(self.gpkg_path_edit, self.gpkg_browse_button))
        gpkg_info_label = QLabel(
            self.tr("Each downloaded parcel is saved as a new layer in the selected GeoPackage file.")
        )
        gpkg_info_label.setWordWrap(True)
        gpkg_layout.addWidget(gpkg_info_label)
        gpkg_layout.addWidget(self.gpkg_add_to_project_checkbox)

        zoom_group = QGroupBox(self.tr("View"))
        zoom_layout = QVBoxLayout(zoom_group)
        zoom_layout.addWidget(self.zoom_checkbox)

        main_layout.addWidget(shp_group)
        main_layout.addWidget(gpkg_group)
        main_layout.addWidget(self.temporary_layer_info_label)
        main_layout.addWidget(self.project_settings_info_label)
        main_layout.addWidget(zoom_group)

        if BrandingFooter is not None:
            self.footer = BrandingFooter()
            footer_wrap = QWidget(self)
            footer_layout = QVBoxLayout(footer_wrap)
            footer_layout.setContentsMargins(6, 6, 6, 6)
            footer_layout.setSpacing(0)
            footer_layout.addWidget(self.footer)
            main_layout.addWidget(footer_wrap, 0, Qt.AlignBottom)

        main_layout.addWidget(self.button_box)

    def _build_path_row(self, line_edit, button):
        row_widget = QHBoxLayout()
        row_widget.setContentsMargins(0, 0, 0, 0)
        row_widget.addWidget(line_edit, 1)
        row_widget.addWidget(button)

        container = QWidget(self)
        container.setLayout(row_widget)
        return container

    def _connect_signals(self):
        self.shp_enabled_checkbox.toggled.connect(self._on_shp_toggled)
        self.gpkg_enabled_checkbox.toggled.connect(self._on_gpkg_toggled)
        self.shp_browse_button.clicked.connect(self._browse_shp_folder)
        self.gpkg_browse_button.clicked.connect(self._browse_gpkg_path)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _apply_initial_settings(self):
        self.shp_enabled_checkbox.setChecked(bool(self._initial_settings.get("save_to_shp", False)))
        self.shp_folder_edit.setText(str(self._initial_settings.get("shp_folder", "") or ""))
        self.shp_add_to_project_checkbox.setChecked(
            bool(self._initial_settings.get("shp_add_to_project", False))
        )

        self.gpkg_enabled_checkbox.setChecked(bool(self._initial_settings.get("save_to_gpkg", False)))
        self.gpkg_path_edit.setText(str(self._initial_settings.get("gpkg_path", "") or ""))
        self.gpkg_add_to_project_checkbox.setChecked(
            bool(self._initial_settings.get("gpkg_add_to_project", False))
        )

        self.zoom_checkbox.setChecked(bool(self._initial_settings.get("zoom_to_parcel", False)))

    def _normalize_path(self, value):
        raw_value = str(value or "").strip()
        if not raw_value:
            return ""
        try:
            return str(Path(raw_value).expanduser())
        except Exception:
            return raw_value

    def _on_shp_toggled(self, checked):
        if checked and self.gpkg_enabled_checkbox.isChecked():
            self.gpkg_enabled_checkbox.blockSignals(True)
            self.gpkg_enabled_checkbox.setChecked(False)
            self.gpkg_enabled_checkbox.blockSignals(False)
        self._update_enabled_states()

    def _on_gpkg_toggled(self, checked):
        if checked and self.shp_enabled_checkbox.isChecked():
            self.shp_enabled_checkbox.blockSignals(True)
            self.shp_enabled_checkbox.setChecked(False)
            self.shp_enabled_checkbox.blockSignals(False)
        self._update_enabled_states()

    def _update_enabled_states(self):
        shp_enabled = self.shp_enabled_checkbox.isChecked()
        gpkg_enabled = self.gpkg_enabled_checkbox.isChecked()

        self.shp_folder_edit.setEnabled(shp_enabled)
        self.shp_browse_button.setEnabled(shp_enabled)
        self.shp_add_to_project_checkbox.setEnabled(shp_enabled)

        self.gpkg_path_edit.setEnabled(gpkg_enabled)
        self.gpkg_browse_button.setEnabled(gpkg_enabled)
        self.gpkg_add_to_project_checkbox.setEnabled(gpkg_enabled)

    def _browse_shp_folder(self):
        selected_path = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select SHP target folder"),
            self._normalize_path(self.shp_folder_edit.text()),
        )
        if selected_path:
            self.shp_folder_edit.setText(self._normalize_path(selected_path))

    def _browse_gpkg_path(self):
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Select GPKG file"),
            self._normalize_path(self.gpkg_path_edit.text()),
            self.tr("GeoPackage (*.gpkg)"),
        )
        if selected_path:
            normalized_path = self._normalize_path(selected_path)
            if normalized_path and not normalized_path.lower().endswith(".gpkg"):
                normalized_path = f"{normalized_path}.gpkg"
            self.gpkg_path_edit.setText(normalized_path)

    def _show_validation_error(self, message):
        QMessageBox.warning(self, self.tr("Invalid settings"), message)

    def _validate_shp_settings(self):
        shp_folder = self._normalize_path(self.shp_folder_edit.text())
        self.shp_folder_edit.setText(shp_folder)

        if not shp_folder:
            self._show_validation_error(self.tr("Select a target folder for SHP export."))
            return False

        shp_path = Path(shp_folder)
        if not shp_path.exists() or not shp_path.is_dir():
            self._show_validation_error(self.tr("Selected SHP folder does not exist."))
            return False

        return True

    def _validate_gpkg_settings(self):
        gpkg_path = self._normalize_path(self.gpkg_path_edit.text())
        if gpkg_path and not gpkg_path.lower().endswith(".gpkg"):
            gpkg_path = f"{gpkg_path}.gpkg"
        self.gpkg_path_edit.setText(gpkg_path)

        if not gpkg_path:
            self._show_validation_error(self.tr("Select a target GPKG file."))
            return False

        gpkg_file = Path(gpkg_path)
        parent_dir = gpkg_file.parent
        if not str(parent_dir) or not parent_dir.exists() or not parent_dir.is_dir():
            self._show_validation_error(self.tr("Selected GPKG folder does not exist."))
            return False

        return True

    def accept(self):
        if self.shp_enabled_checkbox.isChecked() and not self._validate_shp_settings():
            return

        if self.gpkg_enabled_checkbox.isChecked() and not self._validate_gpkg_settings():
            return

        super().accept()

    def get_settings(self):
        return {
            "save_to_shp": self.shp_enabled_checkbox.isChecked(),
            "shp_folder": self._normalize_path(self.shp_folder_edit.text()),
            "shp_add_to_project": self.shp_add_to_project_checkbox.isChecked(),
            "save_to_gpkg": self.gpkg_enabled_checkbox.isChecked(),
            "gpkg_path": self._normalize_path(self.gpkg_path_edit.text()),
            "gpkg_add_to_project": self.gpkg_add_to_project_checkbox.isChecked(),
            "zoom_to_parcel": self.zoom_checkbox.isChecked(),
        }
