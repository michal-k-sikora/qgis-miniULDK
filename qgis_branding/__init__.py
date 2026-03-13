"""Shared QGIS branding package.

Importing this package should register bundled Qt resources so widgets can use
the ``:/branding/...`` paths without extra setup in each plugin.
"""

QRC_REGISTERED = False
QRC_MODULE = None


def _register_resources():
    global QRC_REGISTERED, QRC_MODULE

    for module_name in ("resources_rc", "branding_rc"):
        try:
            module = __import__(f"{__name__}.{module_name}", fromlist=[module_name])
        except Exception:
            continue

        QRC_REGISTERED = True
        QRC_MODULE = module
        return


_register_resources()
