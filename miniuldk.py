import os
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, QSettings, QSize, Qt, QTranslator, QVariant, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QHBoxLayout, QMenu, QToolBar, QToolButton, QWidget
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
)
from qgis.gui import QgsMapToolEmitPoint

from . import resources_rc
from .export_utils import ExportUtils
from .result_layer_utils import ResultLayerUtils
from .settings_dialog import MiniULDKSettingsDialog
from .uldk_client import UldkClient

TOOLBAR_TITLE = "OnGeo"
MENU_ROOT = "OnGeo"
ONGEO_TOOLBAR_OBJECT_NAME = "OnGeoToolbar"


def _get_or_create_toolbar(iface, title, object_name):
    mw = iface.mainWindow()
    for tb in mw.findChildren(QToolBar):
        if tb.objectName() == object_name:
            tb.setWindowTitle(title)
            tb.setToolTip(title)
            if tb.toggleViewAction():
                tb.toggleViewAction().setText(title)
            return tb

    tb = iface.addToolBar(title)
    tb.setObjectName(object_name)
    tb.setWindowTitle(title)
    tb.setToolTip(title)
    tb.setMovable(True)
    if tb.toggleViewAction():
        tb.toggleViewAction().setText(title)
    return tb


class MiniULDKMapTool(QgsMapToolEmitPoint):
    cancelRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class MiniULDK:
    PLUGIN_NAME = "MiniULDK"
    RESULT_LAYER_NAME = "MiniULDK - pobrane działki"
    ULDK_BASE_URL = "https://uldk.gugik.gov.pl/"
    TARGET_EPSG = 2180
    TOOLBAR_ICON_PATH = ":/plugins/miniuldk/icons/button.svg"
    SETTINGS_ICON_PATH = ":/plugins/miniuldk/icons/button_2.svg"
    PROJECT_SETTINGS_SCOPE = "MiniULDK"
    RESULT_FIELDS = (
        ("teryt", QVariant.String, 0, 0),
        ("parcel", QVariant.String, 0, 0),
        ("region", QVariant.String, 0, 0),
        ("commune", QVariant.String, 0, 0),
        ("county", QVariant.String, 0, 0),
        ("voivodeship", QVariant.String, 0, 0),
        ("POW_GEOM_M2", QVariant.Double, 20, 2),
        ("POW_GEOM_HA", QVariant.Double, 20, 4),
    )

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.project = QgsProject.instance()
        self.action = None
        self.settings_action = None
        self.toolbar = None
        self.toolbar_widget = None
        self.toolbar_widget_action = None
        self.toolbar_menu = None
        self.main_tool_button = None
        self.menu_tool_button = None
        self.map_tool = None
        self.translator = None
        self.request_in_progress = False

        locale = QSettings().value("locale/userLocale", "en")
        if locale:
            locale = str(locale)[0:2]
        else:
            locale = "en"

        plugin_dir = os.path.dirname(__file__)
        translation_path = os.path.join(plugin_dir, "i18n", f"miniuldk_{locale}.qm")

        if os.path.exists(translation_path):
            self.translator = QTranslator()
            if self.translator.load(translation_path):
                QCoreApplication.installTranslator(self.translator)
            else:
                self.translator = None

        self.uldk_client = UldkClient(
            base_url=self.ULDK_BASE_URL,
            target_epsg=self.TARGET_EPSG,
        )
        self.result_layer_utils = ResultLayerUtils(
            project=self.project,
            canvas=self.canvas,
            result_layer_name=self.RESULT_LAYER_NAME,
            target_epsg=self.TARGET_EPSG,
            result_fields=self.RESULT_FIELDS,
            style_callback=self._apply_default_layer_style,
        )
        self.export_utils = ExportUtils(
            project=self.project,
            target_epsg=self.TARGET_EPSG,
            result_fields=self.RESULT_FIELDS,
            style_callback=self._apply_default_layer_style,
        )

    def tr(self, message):
        return QCoreApplication.translate(self.PLUGIN_NAME, message)

    def initGui(self):
        self.toolbar = _get_or_create_toolbar(self.iface, TOOLBAR_TITLE, ONGEO_TOOLBAR_OBJECT_NAME)

        icon = QIcon(self.TOOLBAR_ICON_PATH)
        self.action = QAction(icon, self.tr("MiniULDK"), self.iface.mainWindow())
        self.action.setObjectName("MiniULDKAction")
        self.action.setToolTip(self.tr("MiniULDK"))
        self.action.setCheckable(True)
        self.action.triggered.connect(self.activate_map_tool)
        self.iface.addPluginToMenu(MENU_ROOT, self.action)

        settings_icon = QIcon(self.SETTINGS_ICON_PATH)
        self.settings_action = QAction(
            settings_icon,
            self.tr("MiniULDK Settings"),
            self.iface.mainWindow(),
        )
        self.settings_action.setObjectName("MiniULDKSettingsAction")
        self.settings_action.setToolTip(self.tr("MiniULDK Settings"))
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.iface.addPluginToMenu(MENU_ROOT, self.settings_action)

        if self._create_toolbar_widget():
            self.toolbar.iconSizeChanged.connect(self._on_toolbar_icon_size_changed)
        else:
            self.toolbar.addAction(self.action)

        self.canvas.mapToolSet.connect(self.on_map_tool_changed)

    def unload(self):
        self.uldk_client.cancel_active_request()

        try:
            self.canvas.mapToolSet.disconnect(self.on_map_tool_changed)
        except Exception:
            pass

        if self.toolbar is not None:
            try:
                self.toolbar.iconSizeChanged.disconnect(self._on_toolbar_icon_size_changed)
            except Exception:
                pass

        if self.map_tool is not None and self.canvas.mapTool() == self.map_tool:
            self.canvas.unsetMapTool(self.map_tool)

        if self.toolbar_widget_action is not None:
            try:
                if self.toolbar:
                    self.toolbar.removeAction(self.toolbar_widget_action)
            except Exception:
                pass
            self.toolbar_widget_action = None

        if self.toolbar_widget is not None:
            self.toolbar_widget.deleteLater()
            self.toolbar_widget = None

        self.toolbar_menu = None
        self.main_tool_button = None
        self.menu_tool_button = None

        if self.action is not None:
            try:
                if self.toolbar:
                    self.toolbar.removeAction(self.action)
            except Exception:
                pass
            try:
                self.iface.removePluginMenu(MENU_ROOT, self.action)
            except Exception:
                pass
            try:
                self.iface.removePluginMenu(self.tr("&MiniULDK"), self.action)
            except Exception:
                pass
            self.action.deleteLater()
            self.action = None

        if self.settings_action is not None:
            try:
                if self.toolbar:
                    self.toolbar.removeAction(self.settings_action)
            except Exception:
                pass
            try:
                self.iface.removePluginMenu(MENU_ROOT, self.settings_action)
            except Exception:
                pass
            try:
                self.iface.removePluginMenu(self.tr("&MiniULDK"), self.settings_action)
            except Exception:
                pass
            self.settings_action.deleteLater()
            self.settings_action = None

        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)
            self.translator = None

        self.toolbar = None
        self.map_tool = None
        self.request_in_progress = False

    def _create_toolbar_widget(self):
        if self.toolbar is None or self.action is None or self.settings_action is None:
            return False

        try:
            container = QWidget(self.toolbar)
            container.setObjectName("MiniULDKToolbarWidget")
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            main_button = QToolButton(container)
            main_button.setObjectName("MiniULDKMainToolButton")
            main_button.setDefaultAction(self.action)
            main_button.setAutoRaise(True)
            main_button.setToolButtonStyle(Qt.ToolButtonIconOnly)

            menu = QMenu(container)
            menu.addAction(self.settings_action)

            arrow_button = QToolButton(container)
            arrow_button.setObjectName("MiniULDKMenuToolButton")
            arrow_button.setToolTip(self.tr("MiniULDK Settings"))
            arrow_button.setAutoRaise(True)
            arrow_button.setPopupMode(QToolButton.InstantPopup)
            arrow_button.setMenu(menu)
            arrow_button.setArrowType(Qt.DownArrow)
            arrow_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            arrow_button.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0px; }")

            layout.addWidget(main_button)
            layout.addWidget(arrow_button)

            self.toolbar_widget_action = self.toolbar.addWidget(container)
            self.toolbar_widget = container
            self.toolbar_menu = menu
            self.main_tool_button = main_button
            self.menu_tool_button = arrow_button
            self._update_toolbar_widget_sizes()
            return True
        except Exception as exc:
            self.log_technical_error("Failed to create toolbar widget", exc, Qgis.Warning)
            if self.toolbar_widget is not None:
                self.toolbar_widget.deleteLater()
                self.toolbar_widget = None
            self.toolbar_widget_action = None
            self.toolbar_menu = None
            self.main_tool_button = None
            self.menu_tool_button = None
            return False

    def _update_toolbar_widget_sizes(self, toolbar_icon_size=None):
        if (
            self.toolbar_widget is None
            or self.main_tool_button is None
            or self.menu_tool_button is None
            or self.toolbar is None
        ):
            return

        if toolbar_icon_size is None:
            toolbar_icon_size = self.toolbar.iconSize()

        if not toolbar_icon_size.isValid() or toolbar_icon_size.isEmpty():
            toolbar_icon_size = QSize(24, 24)

        button_extent = max(toolbar_icon_size.width(), toolbar_icon_size.height()) + 8
        arrow_width = max(10, min(14, toolbar_icon_size.width() // 2 + 2))

        self.toolbar_widget.setFixedHeight(button_extent)
        self.main_tool_button.setIconSize(toolbar_icon_size)
        self.main_tool_button.setFixedSize(button_extent, button_extent)
        self.menu_tool_button.setFixedSize(arrow_width, button_extent)

    def _on_toolbar_icon_size_changed(self, toolbar_icon_size):
        self._update_toolbar_widget_sizes(toolbar_icon_size)

    def activate_map_tool(self, checked=False):
        del checked

        if not self.is_project_crs_valid():
            self._set_main_action_checked(False)
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("Project CRS is not set correctly. Set a valid CRS before using MiniULDK."),
                Qgis.Warning,
            )
            return

        if self.map_tool is None:
            self.map_tool = MiniULDKMapTool(self.canvas)
            self.map_tool.canvasClicked.connect(self.handle_canvas_click)
            self.map_tool.cancelRequested.connect(self.cancel_map_tool)

        if self.canvas.mapTool() == self.map_tool:
            self._set_main_action_checked(True)
            return

        self.canvas.setMapTool(self.map_tool)
        self._set_main_action_checked(True)
        self.show_message(
            self.tr("MiniULDK"),
            self.tr("Click a point on the map to download a parcel. Press ESC to cancel."),
            Qgis.Info,
        )

    def cancel_map_tool(self):
        if self.map_tool is not None and self.canvas.mapTool() == self.map_tool:
            self.canvas.unsetMapTool(self.map_tool)
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("MiniULDK tool canceled."),
                Qgis.Info,
            )
        else:
            self._set_main_action_checked(False)

    def on_map_tool_changed(self, new_tool, old_tool):
        del old_tool
        is_active = new_tool == self.map_tool and self.map_tool is not None
        self._set_main_action_checked(is_active)

    def _set_main_action_checked(self, checked):
        if self.action is not None and self.action.isChecked() != checked:
            self.action.blockSignals(True)
            self.action.setChecked(checked)
            self.action.blockSignals(False)

    def is_project_crs_valid(self):
        crs = self.project.crs()
        return bool(crs and crs.isValid() and crs.authid())

    def handle_canvas_click(self, point, button=None):
        del button

        if not self.is_project_crs_valid():
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("Project CRS is not set correctly. Set a valid CRS before using MiniULDK."),
                Qgis.Warning,
            )
            return

        if self.request_in_progress:
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("Parcel request is already in progress."),
                Qgis.Info,
            )
            return

        try:
            settings = self.read_project_settings()
            point_2180 = self.transform_point_to_2180(point)
        except ValueError as exc:
            self.show_message(self.tr("MiniULDK"), str(exc), Qgis.Warning)
            return
        except RuntimeError as exc:
            self.log_technical_error("RuntimeError before parcel request", exc, Qgis.Critical)
            self.show_message(self.tr("MiniULDK"), str(exc), Qgis.Critical)
            return
        except Exception as exc:
            self.log_technical_error("Unexpected error before parcel request", exc, Qgis.Critical)
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("Request failed. See QGIS Message Log for details."),
                Qgis.Critical,
            )
            return

        self.request_in_progress = True
        self.uldk_client.fetch_parcel_async(
            point_2180=point_2180,
            on_success=lambda raw_response, current_settings=settings: self.handle_parcel_response(
                raw_response,
                current_settings,
            ),
            on_error=self.handle_parcel_request_error,
        )

    def handle_parcel_response(self, raw_response, settings):
        try:
            parcel_data = self.uldk_client.parse_uldk_response(raw_response)
            operation_result = self.process_parcel_result(parcel_data, settings)
        except ValueError as exc:
            self.show_message(self.tr("MiniULDK"), str(exc), Qgis.Warning)
        except RuntimeError as exc:
            self.log_technical_error("RuntimeError during parcel download", exc, Qgis.Critical)
            self.show_message(self.tr("MiniULDK"), str(exc), Qgis.Critical)
        except Exception as exc:
            self.log_technical_error("Unexpected error during parcel download", exc, Qgis.Critical)
            self.show_message(
                self.tr("MiniULDK"),
                self.tr("Request failed. See QGIS Message Log for details."),
                Qgis.Critical,
            )
        else:
            if settings["zoom_to_parcel"]:
                self.result_layer_utils.zoom_to_geometry(operation_result.geometry)

            if operation_result.success and operation_result.added:
                self.show_message(
                    self.tr("MiniULDK"),
                    operation_result.message,
                    Qgis.Success,
                )
            elif operation_result.success:
                self.show_message(
                    self.tr("MiniULDK"),
                    operation_result.message,
                    Qgis.Info,
                )
            else:
                self.show_message(
                    self.tr("MiniULDK"),
                    operation_result.message,
                    Qgis.Warning,
                )
        finally:
            self.request_in_progress = False

    def handle_parcel_request_error(self, user_message, technical_message=None):
        if technical_message:
            self.log_technical_error("ULDK request failed", technical_message, Qgis.Critical)
        self.show_message(
            self.tr("MiniULDK"),
            user_message,
            Qgis.Critical,
        )
        self.request_in_progress = False

    def open_settings_dialog(self):
        dialog = MiniULDKSettingsDialog(
            initial_settings=self.read_project_settings(),
            parent=self.iface.mainWindow(),
        )
        if dialog.exec_():
            self.write_project_settings(dialog.get_settings())

    def default_settings(self):
        return {
            "save_to_shp": False,
            "shp_folder": "",
            "shp_add_to_project": False,
            "save_to_gpkg": False,
            "gpkg_path": "",
            "gpkg_add_to_project": False,
            "zoom_to_parcel": False,
        }

    def _normalize_path_value(self, value):
        raw_value = str(value or "").strip()
        if not raw_value:
            return ""
        try:
            return str(Path(raw_value).expanduser())
        except Exception:
            return raw_value

    def normalize_settings(self, settings):
        normalized = self.default_settings()
        normalized.update(settings or {})

        normalized["save_to_shp"] = bool(normalized["save_to_shp"])
        normalized["save_to_gpkg"] = bool(normalized["save_to_gpkg"])
        normalized["shp_add_to_project"] = bool(normalized["shp_add_to_project"])
        normalized["gpkg_add_to_project"] = bool(normalized["gpkg_add_to_project"])
        normalized["zoom_to_parcel"] = bool(normalized["zoom_to_parcel"])
        normalized["shp_folder"] = self._normalize_path_value(normalized["shp_folder"])
        normalized["gpkg_path"] = self._normalize_path_value(normalized["gpkg_path"])

        if normalized["save_to_shp"] and normalized["save_to_gpkg"]:
            normalized["save_to_gpkg"] = False

        return normalized

    def _validate_settings_for_runtime(self, settings):
        validated = dict(settings)
        warnings = []

        if validated["save_to_shp"]:
            shp_folder = validated["shp_folder"]
            if not shp_folder:
                validated["save_to_shp"] = False
                validated["shp_add_to_project"] = False
                warnings.append(self.tr("Invalid SHP settings detected in project. SHP export was disabled."))
            else:
                shp_path = Path(shp_folder)
                if not shp_path.exists() or not shp_path.is_dir():
                    validated["save_to_shp"] = False
                    validated["shp_add_to_project"] = False
                    warnings.append(self.tr("Saved SHP folder is unavailable. SHP export was disabled."))

        if validated["save_to_gpkg"]:
            gpkg_path_value = validated["gpkg_path"]
            if not gpkg_path_value:
                validated["save_to_gpkg"] = False
                validated["gpkg_add_to_project"] = False
                warnings.append(self.tr("Invalid GPKG settings detected in project. GPKG export was disabled."))
            else:
                gpkg_path = Path(gpkg_path_value)
                if gpkg_path.suffix.lower() != ".gpkg":
                    gpkg_path = gpkg_path.with_suffix(".gpkg")
                    validated["gpkg_path"] = str(gpkg_path)
                    warnings.append(self.tr("Saved GPKG path was normalized to use the .gpkg extension."))

                parent_dir = gpkg_path.parent
                if not str(parent_dir) or not parent_dir.exists() or not parent_dir.is_dir():
                    validated["save_to_gpkg"] = False
                    validated["gpkg_add_to_project"] = False
                    warnings.append(self.tr("Saved GPKG folder is unavailable. GPKG export was disabled."))

        if validated["save_to_shp"] and validated["save_to_gpkg"]:
            validated["save_to_gpkg"] = False
            warnings.append(self.tr("Conflicting export settings were detected. GPKG export was disabled."))

        return validated, warnings

    def read_project_settings(self):
        defaults = self.default_settings()
        project = self.project
        raw_settings = dict(defaults)

        raw_settings["save_to_shp"] = project.readBoolEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "save_to_shp",
            defaults["save_to_shp"],
        )[0]
        raw_settings["shp_folder"] = project.readEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "shp_folder",
            defaults["shp_folder"],
        )[0]
        raw_settings["shp_add_to_project"] = project.readBoolEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "shp_add_to_project",
            defaults["shp_add_to_project"],
        )[0]
        raw_settings["save_to_gpkg"] = project.readBoolEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "save_to_gpkg",
            defaults["save_to_gpkg"],
        )[0]
        raw_settings["gpkg_path"] = project.readEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "gpkg_path",
            defaults["gpkg_path"],
        )[0]
        raw_settings["gpkg_add_to_project"] = project.readBoolEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "gpkg_add_to_project",
            defaults["gpkg_add_to_project"],
        )[0]
        raw_settings["zoom_to_parcel"] = project.readBoolEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "zoom_to_parcel",
            defaults["zoom_to_parcel"],
        )[0]

        normalized = self.normalize_settings(raw_settings)
        validated, warnings = self._validate_settings_for_runtime(normalized)

        for warning_message in warnings:
            self.log_technical_error("Project settings normalization", warning_message, Qgis.Warning)

        return validated

    def write_project_settings(self, settings):
        normalized = self.normalize_settings(settings)
        validated, warnings = self._validate_settings_for_runtime(normalized)

        for warning_message in warnings:
            self.log_technical_error("Project settings validation", warning_message, Qgis.Warning)

        project = self.project

        project.writeEntryBool(
            self.PROJECT_SETTINGS_SCOPE,
            "save_to_shp",
            validated["save_to_shp"],
        )
        project.writeEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "shp_folder",
            validated["shp_folder"],
        )
        project.writeEntryBool(
            self.PROJECT_SETTINGS_SCOPE,
            "shp_add_to_project",
            validated["shp_add_to_project"],
        )
        project.writeEntryBool(
            self.PROJECT_SETTINGS_SCOPE,
            "save_to_gpkg",
            validated["save_to_gpkg"],
        )
        project.writeEntry(
            self.PROJECT_SETTINGS_SCOPE,
            "gpkg_path",
            validated["gpkg_path"],
        )
        project.writeEntryBool(
            self.PROJECT_SETTINGS_SCOPE,
            "gpkg_add_to_project",
            validated["gpkg_add_to_project"],
        )
        project.writeEntryBool(
            self.PROJECT_SETTINGS_SCOPE,
            "zoom_to_parcel",
            validated["zoom_to_parcel"],
        )

    def process_parcel_result(self, parcel_data, settings):
        settings = self.normalize_settings(settings)

        if settings["save_to_gpkg"]:
            return self.export_utils.export_parcel_to_gpkg(
                parcel_data,
                settings["gpkg_path"],
                settings["gpkg_add_to_project"],
            )

        if settings["save_to_shp"]:
            shp_result = self.export_utils.export_parcel_to_shp(
                parcel_data,
                settings["shp_folder"],
                settings["shp_add_to_project"],
            )
            if settings["shp_add_to_project"]:
                return shp_result

        layer = self.result_layer_utils.get_or_create_result_layer()
        return self.result_layer_utils.add_parcel_to_layer(layer, parcel_data)

    def _apply_default_layer_style(self, layer):
        if layer is None or not layer.isValid():
            return

        style_path = Path(__file__).resolve().parent / "styles" / "dzew_styl.qml"
        if not style_path.exists():
            self.log_technical_error("Layer styling skipped", f"Missing style file: {style_path}", Qgis.Warning)
            return

        try:
            load_result = layer.loadNamedStyle(str(style_path))
            if isinstance(load_result, tuple):
                style_loaded = bool(load_result[0])
                error_message = str(load_result[1]) if len(load_result) > 1 else ""
            else:
                style_loaded = bool(load_result)
                error_message = ""

            if not style_loaded:
                self.log_technical_error(
                    "Layer styling skipped",
                    error_message or f"Could not load style: {style_path}",
                    Qgis.Warning,
                )
                return

            layer.triggerRepaint()
        except Exception as exc:
            self.log_technical_error("Failed to apply layer style", exc, Qgis.Warning)

    def transform_point_to_2180(self, point):
        source_crs = self.project.crs()
        target_crs = QgsCoordinateReferenceSystem.fromEpsgId(self.TARGET_EPSG)

        if not source_crs.isValid():
            raise ValueError(
                self.tr("Project CRS is not set correctly. Set a valid CRS before using MiniULDK.")
            )

        if source_crs == target_crs:
            return point

        transformer = QgsCoordinateTransform(source_crs, target_crs, self.project)
        try:
            return transformer.transform(point)
        except Exception as exc:
            raise RuntimeError(
                self.tr("Failed to transform clicked point to EPSG:2180.")
            ) from exc

    def log_technical_error(self, context_message, exception, level=Qgis.Warning):
        message = "{0}: {1}".format(context_message, str(exception))
        QgsMessageLog.logMessage(message, self.PLUGIN_NAME, level)

    def show_message(self, title, message, level=Qgis.Info, duration=5):
        self.iface.messageBar().pushMessage(title, message, level=level, duration=duration)
