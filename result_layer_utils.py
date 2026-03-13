from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .operation_result import OperationResult


class ResultLayerUtils:
    def __init__(self, project, canvas, result_layer_name, target_epsg, result_fields, style_callback=None):
        self.project = project
        self.canvas = canvas
        self.result_layer_name = result_layer_name
        self.target_epsg = target_epsg
        self.result_fields = result_fields
        self.style_callback = style_callback

    def tr(self, message):
        return QCoreApplication.translate("ResultLayerUtils", message)

    def _field_def_map(self):
        return {name: (field_type, length, precision) for name, field_type, length, precision in self.result_fields}

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

    def _validate_result_layer(self, layer):
        if layer is None:
            raise RuntimeError(self.tr("Existing result layer is missing."))

        if not layer.isValid():
            raise RuntimeError(self.tr("Existing result layer is invalid."))

        provider = layer.dataProvider()
        if provider is None:
            raise RuntimeError(self.tr("Existing result layer provider is unavailable."))

        if provider.name() != "memory":
            raise RuntimeError(
                self.tr("Existing result layer is incompatible. Expected a memory layer.")
            )

        if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            raise RuntimeError(
                self.tr("Existing result layer is incompatible. Expected a polygon layer.")
            )

        layer_crs = layer.crs()
        expected_auth_id = f"EPSG:{self.target_epsg}"
        if not layer_crs.isValid() or layer_crs.authid() != expected_auth_id:
            raise RuntimeError(
                self.tr("Existing result layer is incompatible. Expected CRS EPSG:2180.")
            )

        field_map = {field.name(): field for field in layer.fields()}
        expected_fields = self._field_def_map()
        missing_fields = [field_name for field_name in expected_fields if field_name not in field_map]
        if missing_fields:
            raise RuntimeError(
                self.tr("Existing result layer is incompatible. Required fields are missing.")
            )

        invalid_field_types = [
            field_name
            for field_name, (expected_type, _length, _precision) in expected_fields.items()
            if field_map[field_name].type() != expected_type
        ]
        if invalid_field_types:
            raise RuntimeError(
                self.tr("Existing result layer is incompatible. Required field types are invalid.")
            )

        return layer

    def _find_existing_result_layers(self):
        return self.project.mapLayersByName(self.result_layer_name)

    def _create_result_layer(self):
        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:{0}".format(self.target_epsg),
            self.result_layer_name,
            "memory",
        )
        if not layer.isValid():
            raise RuntimeError(self.tr("Failed to create result layer."))

        provider = layer.dataProvider()
        if provider is None:
            raise RuntimeError(self.tr("Failed to access result layer provider."))

        if not provider.addAttributes(self._create_qgs_fields()):
            raise RuntimeError(self.tr("Failed to initialize result layer fields."))

        layer.updateFields()
        self.project.addMapLayer(layer)
        if self.style_callback is not None:
            self.style_callback(layer)
        return self._validate_result_layer(layer)

    def get_or_create_result_layer(self):
        layers = self._find_existing_result_layers()

        if len(layers) > 1:
            raise RuntimeError(
                self.tr("Multiple result layers named '{0}' were found. Keep only one.").format(
                    self.result_layer_name
                )
            )

        if len(layers) == 1:
            return self._validate_result_layer(layers[0])

        return self._create_result_layer()

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

    def _is_duplicate_feature(self, existing_feature, new_geometry, parcel_data):
        existing_geometry = existing_feature.geometry()
        if existing_geometry is None or existing_geometry.isNull() or existing_geometry.isEmpty():
            return False

        existing_teryt = str(existing_feature["teryt"]).strip()
        existing_parcel = str(existing_feature["parcel"]).strip()
        new_teryt = str(parcel_data.get("teryt", "")).strip()
        new_parcel = str(parcel_data.get("parcel", "")).strip()

        identifiers_match = bool(
            existing_teryt
            and existing_parcel
            and new_teryt
            and new_parcel
            and existing_teryt == new_teryt
            and existing_parcel == new_parcel
        )

        geometries_match = existing_geometry.equals(new_geometry)

        if identifiers_match and geometries_match:
            return True

        if not new_teryt and not new_parcel and geometries_match:
            return True

        return False

    def _find_duplicate_geometry(self, layer, geometry, parcel_data):
        for feature in layer.getFeatures():
            if self._is_duplicate_feature(feature, geometry, parcel_data):
                existing_geometry = feature.geometry()
                if (
                    existing_geometry is not None
                    and not existing_geometry.isNull()
                    and not existing_geometry.isEmpty()
                ):
                    return existing_geometry
                return geometry
        return None

    def _refresh_result_layer_views(self, layer):
        layer.updateExtents()
        layer.reload()
        layer.triggerRepaint()
        layer.dataChanged.emit()
        self.canvas.refresh()

    def add_parcel_to_layer(self, layer, parcel_data):
        layer = self._validate_result_layer(layer)
        geometry = self._validate_parcel_data(parcel_data)

        duplicate_geometry = self._find_duplicate_geometry(layer, geometry, parcel_data)
        if duplicate_geometry is not None:
            return OperationResult(
                geometry=duplicate_geometry,
                success=True,
                added=False,
                saved_to_file=False,
                added_to_project=False,
                message=self.tr("The selected parcel already exists in the result layer."),
            )

        provider = layer.dataProvider()
        if provider is None:
            raise RuntimeError(self.tr("Failed to access result layer provider."))

        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)

        attributes = self._build_attributes(parcel_data, geometry)
        for field_name, value in attributes.items():
            feature.setAttribute(field_name, value)

        if not provider.addFeature(feature):
            raise RuntimeError(self.tr("Failed to add parcel to result layer."))

        self._refresh_result_layer_views(layer)

        return OperationResult(
            geometry=geometry,
            success=True,
            added=True,
            saved_to_file=False,
            added_to_project=False,
            message=self.tr("Parcel downloaded successfully."),
        )

    def zoom_to_geometry(self, geometry):
        if geometry is None or geometry.isNull() or geometry.isEmpty():
            return

        source_crs = QgsCoordinateReferenceSystem.fromEpsgId(self.target_epsg)
        destination_crs = self.project.crs()

        if not source_crs.isValid() or not destination_crs.isValid():
            return

        zoom_geometry = QgsGeometry(geometry)

        if source_crs != destination_crs:
            transformer = QgsCoordinateTransform(source_crs, destination_crs, self.project)
            try:
                transform_result = zoom_geometry.transform(transformer)
                if transform_result != 0:
                    return
            except Exception:
                return

        extent = zoom_geometry.boundingBox()
        if extent.isEmpty():
            return

        extent.scale(1.10)
        self.canvas.setExtent(extent)
        self.canvas.refresh()
