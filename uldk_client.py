from urllib.parse import urlencode

from qgis.PyQt.QtCore import QCoreApplication, QTimer, QUrl
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qgis.core import QgsGeometry, QgsWkbTypes


class UldkClient:
    REQUEST_TIMEOUT_MS = 15000
    MIN_EXPECTED_FIELDS = 7

    def __init__(self, base_url, target_epsg):
        self.base_url = base_url
        self.target_epsg = target_epsg
        self.network_manager = QNetworkAccessManager()
        self.active_reply = None

    def tr(self, message):
        return QCoreApplication.translate("UldkClient", message)

    def build_uldk_url(self, point_2180):
        params = {
            "request": "GetParcelByXY",
            "xy": f"{point_2180.x()},{point_2180.y()}",
            "result": "geom_wkt,teryt,parcel,region,commune,county,voivodeship",
            "srid": str(self.target_epsg),
        }
        return "{0}?{1}".format(self.base_url, urlencode(params))

    def fetch_parcel_async(self, point_2180, on_success, on_error):
        if self.active_reply is not None:
            on_error(
                self.tr("Parcel request is already in progress."),
                self.tr("ULDK request rejected because another request is already active."),
            )
            return

        url = self.build_uldk_url(point_2180)
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.UserAgentHeader, "MiniULDK/QGIS")

        reply = self.network_manager.get(request)
        self.active_reply = reply

        timeout_timer = QTimer(reply)
        timeout_timer.setSingleShot(True)

        def handle_timeout():
            if reply.isRunning():
                reply.setProperty("miniuldk_timed_out", True)
                reply.abort()

        def handle_finished():
            try:
                if reply.property("miniuldk_timed_out"):
                    on_error(
                        self.tr("Request timed out while contacting ULDK."),
                        self.tr("ULDK request timed out after {0} ms.").format(self.REQUEST_TIMEOUT_MS),
                    )
                    return

                if reply.property("miniuldk_canceled"):
                    on_error(
                        self.tr("Request failed: unable to reach ULDK."),
                        self.tr("ULDK request was canceled before completion."),
                    )
                    return

                if reply.error() != QNetworkReply.NoError:
                    status_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
                    status_text = reply.errorString() or self.tr("Unknown network error.")
                    if status_code is not None:
                        user_message = self.tr("Request failed with HTTP status {0}.").format(status_code)
                        technical_message = self.tr("HTTP status {0}: {1}").format(status_code, status_text)
                    else:
                        user_message = self.tr("Request failed: unable to reach ULDK.")
                        technical_message = status_text
                    on_error(user_message, technical_message)
                    return

                payload = bytes(reply.readAll()).decode("utf-8", errors="replace").strip()
                if not payload:
                    on_error(
                        self.tr("No parcel found for clicked location."),
                        self.tr("ULDK returned an empty response body."),
                    )
                    return

                on_success(payload)
            finally:
                timeout_timer.stop()
                reply.deleteLater()
                if self.active_reply is reply:
                    self.active_reply = None

        timeout_timer.timeout.connect(handle_timeout)
        reply.finished.connect(handle_finished)
        timeout_timer.start(self.REQUEST_TIMEOUT_MS)

    def cancel_active_request(self):
        if self.active_reply is not None and self.active_reply.isRunning():
            self.active_reply.setProperty("miniuldk_canceled", True)
            self.active_reply.abort()

    def _extract_candidate_response_line(self, line):
        candidate = line
        if ";" in candidate:
            # ULDK sometimes returns a technical prefix before the actual payload.
            # Prefer the fragment that contains the structured "|" payload.
            prefix, suffix = candidate.split(";", 1)
            prefix = prefix.strip()
            suffix = suffix.strip()
            if suffix and "|" in suffix:
                candidate = suffix
            elif prefix and "|" in prefix:
                candidate = prefix
            else:
                # If neither fragment contains "|", keep the more specific trailing fragment.
                candidate = suffix or prefix
        return candidate.strip()

    def _classify_response_line(self, line):
        lowered = line.lower()

        # Explicit "no result" style responses should map to a non-technical, user-facing miss.
        if line.startswith("-1") or "brak wynik" in lowered or "no result" in lowered:
            return "no_result"

        # HTML or XML-like responses mean the service returned something other than the expected text payload.
        if line.startswith("<?xml") or line.startswith("<") or "<html" in lowered:
            return "structured_error"

        # Textual error markers indicate a service-side or protocol-level problem.
        if "<error" in lowered or "</error>" in lowered:
            return "service_error"
        if "blad" in lowered or "błąd" in lowered or "error" in lowered:
            return "service_error"

        return "data_or_other"

    def _validate_geometry_from_wkt(self, wkt):
        if not wkt:
            raise ValueError(self.tr("No parcel geometry returned by ULDK."))

        geometry = QgsGeometry.fromWkt(wkt)
        if geometry.isNull() or geometry.isEmpty():
            raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))

        geometry_type = QgsWkbTypes.geometryType(geometry.wkbType())
        if geometry_type != QgsWkbTypes.PolygonGeometry:
            raise RuntimeError(self.tr("Invalid parcel geometry returned by ULDK."))

        return geometry

    def _build_parcel_data(self, parts, geometry):
        return {
            "wkt": parts[0],
            "teryt": parts[1] if len(parts) > 1 else "",
            "parcel": parts[2] if len(parts) > 2 else "",
            "region": parts[3] if len(parts) > 3 else "",
            "commune": parts[4] if len(parts) > 4 else "",
            "county": parts[5] if len(parts) > 5 else "",
            "voivodeship": parts[6] if len(parts) > 6 else "",
            "_geometry": geometry,
        }

    def parse_uldk_response(self, raw_response):
        if raw_response is None:
            raise RuntimeError(self.tr("Invalid response from ULDK."))

        response_text = str(raw_response).strip()
        if not response_text:
            raise ValueError(self.tr("No parcel found for clicked location."))

        found_candidate_line = False

        for raw_line in response_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            response_kind = self._classify_response_line(line)
            if response_kind == "no_result":
                raise ValueError(self.tr("No parcel found for clicked location."))
            if response_kind in ("structured_error", "service_error"):
                raise RuntimeError(self.tr("Invalid response from ULDK."))

            candidate = self._extract_candidate_response_line(line)
            if not candidate or "|" not in candidate:
                continue

            found_candidate_line = True
            parts = [part.strip() for part in candidate.split("|")]

            if len(parts) < self.MIN_EXPECTED_FIELDS:
                raise RuntimeError(self.tr("Invalid response from ULDK."))

            geometry = self._validate_geometry_from_wkt(parts[0])
            return self._build_parcel_data(parts, geometry)

        if found_candidate_line:
            raise RuntimeError(self.tr("Invalid response from ULDK."))

        raise ValueError(self.tr("No parcel found for clicked location."))
