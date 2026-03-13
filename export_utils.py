import os
import re
import sqlite3
import time
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .operation_result import OperationResult


class ExportUtils:
    SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
    MAX_BASE_NAME_LENGTH = 48
    FALLBACK_NAME_PREFIX = "miniuldk_parcel"
    TERYT_PREFIX_LENGTH = 9

    def __init__(self, project, target_epsg, result_fields, style_callback=None):
        self.project = project
        self.target_epsg = target_epsg
        self.result_fields = result_fields
        self.style_callback = style_callback

    def tr(self, message):
        return QCoreApplication.translate("ExportUtils", message)

    def _field_names(self):
        return [name for name, _field_type, _length, _precision in self.result_fields]

    def _create_qgs_fields(self):
        fields = []
        for name, field_type, length, precision in self.result_fields:
            if field_type == QVariant.Double:
                fields.append(QgsField(name, field_type, "double", length, precision))
            else:
                fields.append(QgsField(name, field_type))
        return fields

    def _calculate_area_values(self, geometry):
        area_m2 = round(float(geometry.area()), 2)
        area_ha = round(area_m2 / 10000.0, 4)
        return area_m2, area_ha

    def _build_attributes(self, parcel_data, geometry):
        area_m2, area_ha = self._calculate_area_values(geometry)
        attributes = {}
        for field_name in self._field_names():
            if field_name == "POW_GEOM_M2":
                attributes[field_name] = area_m2
            elif field_name == "POW_GEOM_HA":
                attributes[field_name] = area_ha
            else:
                value = parcel_data.get(field_name, "")
                attributes[field_name] = "" if value is None else str(value)
        return attributes

    def _validate_parcel_data(self, parcel_data):
        if not isinstance(parcel_data, dict):
            raise RuntimeError(self.tr("Invalid response from ULDK."))

        geometry = parcel_data.get("_geometry")
        if isinstance(geometry, QgsGeometry):
            if geometry.isNull() or geometry.isEmpty():
                raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))
            if QgsWkbTypes.geometryType(geometry.wkbType()) != QgsWkbTypes.PolygonGeometry:
                raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))
            return QgsGeometry(geometry)

        wkt = str(parcel_data.get("wkt", "")).strip()
        if not wkt:
            raise ValueError(self.tr("No parcel geometry returned by ULDK."))

        geometry = QgsGeometry.fromWkt(wkt)
        if geometry.isNull() or geometry.isEmpty():
            raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))

        if QgsWkbTypes.geometryType(geometry.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))

        return geometry

    def _sanitize_name(self, value, fallback):
        raw_value = str(value or "").strip()
        safe_value = self.SAFE_NAME_PATTERN.sub("_", raw_value)
        safe_value = re.sub(r"_+", "_", safe_value).strip("._")

        if not safe_value:
            safe_value = fallback

        if len(safe_value) > self.MAX_BASE_NAME_LENGTH:
            safe_value = safe_value[: self.MAX_BASE_NAME_LENGTH].rstrip("._")

        return safe_value or fallback

    def _fallback_name(self):
        return f"{self.FALLBACK_NAME_PREFIX}_{int(time.time() * 1000)}"

    def _build_base_name(self, parcel_data):
        fallback_name = self._fallback_name()
        raw_teryt = str(parcel_data.get("teryt", "") or "").strip()

        if len(raw_teryt) > self.TERYT_PREFIX_LENGTH:
            trimmed_teryt = raw_teryt[self.TERYT_PREFIX_LENGTH :]
            safe_trimmed_teryt = self._sanitize_name(trimmed_teryt, "")
            if safe_trimmed_teryt:
                return safe_trimmed_teryt

        return fallback_name

    def _generate_unique_file_path(self, folder_path, base_name, extension):
        folder = Path(folder_path)
        candidate_path = folder / f"{base_name}.{extension}"
        counter = 2

        while candidate_path.exists():
            candidate_path = folder / f"{base_name}_{counter}.{extension}"
            counter += 1

        return str(candidate_path)

    def _existing_gpkg_layer_names(self, gpkg_path):
        gpkg_file = Path(gpkg_path)
        if not gpkg_file.exists():
            return set()

        layer_names = set()
        try:
            with sqlite3.connect(str(gpkg_file)) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT table_name FROM gpkg_contents")
                for row in cursor.fetchall():
                    if row and row[0]:
                        layer_names.add(str(row[0]))
        except sqlite3.Error:
            return set()
        return layer_names

    def _generate_unique_layer_name(self, gpkg_path, parcel_data):
        base_name = self._build_base_name(parcel_data)
        existing_names = self._existing_gpkg_layer_names(gpkg_path)
        layer_name = base_name
        counter = 2

        while layer_name in existing_names:
            suffix = f"_{counter}"
            trimmed_base = base_name[: max(1, self.MAX_BASE_NAME_LENGTH - len(suffix))]
            layer_name = f"{trimmed_base}{suffix}"
            counter += 1

        return layer_name

    def _create_single_parcel_layer(self, parcel_data, layer_name):
        geometry = self._validate_parcel_data(parcel_data)
        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:{0}".format(self.target_epsg),
            layer_name,
            "memory",
        )
        if not layer.isValid():
            raise RuntimeError(self.tr("Failed to create parcel export layer."))

        provider = layer.dataProvider()
        if provider is None:
            raise RuntimeError(self.tr("Failed to access parcel export layer provider."))

        if not provider.addAttributes(self._create_qgs_fields()):
            raise RuntimeError(self.tr("Failed to initialize parcel export layer fields."))

        layer.updateFields()

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)

        attributes = self._build_attributes(parcel_data, geometry)
        for field_name, value in attributes.items():
            feature.setAttribute(field_name, value)

        if not provider.addFeature(feature):
            raise RuntimeError(self.tr("Failed to add parcel to export layer."))

        layer.updateExtents()
        return layer, geometry

    def _write_vector_layer(self, source_layer, destination_path, driver_name, layer_name):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver_name
        options.fileEncoding = "UTF-8"
        options.layerName = layer_name

        if driver_name == "GPKG":
            if os.path.exists(destination_path):
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            source_layer,
            destination_path,
            self.project.transformContext(),
            options,
        )

        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""
        if error_code != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                self.tr("Failed to save parcel layer: {0}").format(error_message or destination_path)
            )

        if driver_name == "ESRI Shapefile":
            if not Path(destination_path).exists():
                raise RuntimeError(self.tr("SHP export did not create the expected file."))
        elif driver_name == "GPKG":
            if not Path(destination_path).exists():
                raise RuntimeError(self.tr("GPKG export did not create the expected file."))

    def _load_exported_layer(self, layer_source, layer_name):
        layer = QgsVectorLayer(layer_source, layer_name, "ogr")
        if not layer.isValid():
            raise RuntimeError(self.tr("Parcel was saved, but loading it into the project failed."))
        self.project.addMapLayer(layer)
        if self.style_callback is not None:
            self.style_callback(layer)
        return layer

    def export_parcel_to_shp(self, parcel_data, folder_path, add_to_project):
        folder_path = str(folder_path or "").strip()
        if not folder_path:
            raise ValueError(self.tr("Select a target folder for SHP export."))

        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(self.tr("Selected SHP folder does not exist."))

        base_name = self._build_base_name(parcel_data)
        destination_path = self._generate_unique_file_path(str(folder), base_name, "shp")
        layer_name = Path(destination_path).stem
        export_layer, geometry = self._create_single_parcel_layer(parcel_data, layer_name)

        try:
            self._write_vector_layer(export_layer, destination_path, "ESRI Shapefile", layer_name)
            if add_to_project:
                self._load_exported_layer(destination_path, layer_name)
        except Exception as exc:
            raise RuntimeError(
                self.tr("SHP export failed for '{0}': {1}").format(destination_path, str(exc))
            ) from exc

        return OperationResult(
            geometry=geometry,
            success=True,
            added=True,
            saved_to_file=True,
            added_to_project=bool(add_to_project),
            message=self.tr("Parcel downloaded and saved to SHP successfully."),
        )

    def export_parcel_to_gpkg(self, parcel_data, gpkg_path, add_to_project):
        gpkg_path = str(gpkg_path or "").strip()
        if not gpkg_path:
            raise ValueError(self.tr("Select a target GPKG file."))

        gpkg_file = Path(gpkg_path)
        if gpkg_file.suffix.lower() != ".gpkg":
            gpkg_file = gpkg_file.with_suffix(".gpkg")

        parent_dir = gpkg_file.parent
        if not str(parent_dir) or not parent_dir.exists() or not parent_dir.is_dir():
            raise ValueError(self.tr("Selected GPKG folder does not exist."))

        layer_name = self._generate_unique_layer_name(str(gpkg_file), parcel_data)
        export_layer, geometry = self._create_single_parcel_layer(parcel_data, layer_name)

        try:
            self._write_vector_layer(export_layer, str(gpkg_file), "GPKG", layer_name)
            if add_to_project:
                self._load_exported_layer(f"{gpkg_file}|layername={layer_name}", layer_name)
        except Exception as exc:
            raise RuntimeError(
                self.tr("GPKG export failed for '{0}' (layer '{1}'): {2}").format(
                    str(gpkg_file), layer_name, str(exc)
                )
            ) from exc

        return OperationResult(
            geometry=geometry,
            success=True,
            added=True,
            saved_to_file=True,
            added_to_project=bool(add_to_project),
            message=self.tr("Parcel downloaded and saved to GPKG successfully."),
        )
