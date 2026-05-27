from django.apps import AppConfig


class ManufacturingConfig(AppConfig):
    name = 'manufacturing'

    def ready(self):
        from .views import _init_schema
        _init_schema()
