import importlib

from django.apps import apps as global_apps
from django.contrib.contenttypes.management import create_contenttypes
from django.db import DEFAULT_DB_ALIAS, router, connection


def create_feature_permission_for_client(app_config, verbosity=2, interactive=True, using=DEFAULT_DB_ALIAS,
                                         apps=global_apps, **kwargs):
    if connection.schema_name != 'public' or not app_config.models_module or app_config.label != 'customers':
        return
    package_name = app_config.name
    create_contenttypes(app_config, verbosity=verbosity, interactive=interactive, using=using, apps=apps, **kwargs)

    app_label = app_config.label
    try:
        app_config = apps.get_app_config(app_label)
        ContentType = apps.get_model('contenttypes', 'ContentType')
        Feature = apps.get_model('customers', 'Feature')
        Client = apps.get_model('customers', 'Client')
        FeatureName = _import_class(f'{package_name}.features.models.FeatureName')
    except LookupError:
        return

    if not router.allow_migrate_model(using, Feature):
        return

    items = []
    for f in FeatureName.values:
        items += [
            Feature(key=f, client=c)
            for c in Client.objects.exclude(pk__in=Feature.objects.filter(key=f).values_list('client_id', flat=True))
        ]

    per_items = Feature.objects.bulk_create(items)

    if verbosity >= 2:
        for per in per_items:
            print("Adding feature item setting '%s'" % per)


def _import_class(alias_path):
    package, attr = alias_path.rsplit('.', 1)
    return _import_attribute(package, attr)


def _import_attribute(package, attribute, related_name=None):
    module = _find_related_module(package, related_name)
    i_m = importlib.import_module(module.__name__)
    try:
        attr = getattr(i_m, attribute)
        return attr
    except AttributeError as e:
        pass
    return None


def _find_related_module(package, related_name):
    """Find module in package."""
    # Django 1.7 allows for speciying a class name in INSTALLED_APPS.
    # (Issue #2248).
    try:
        module = importlib.import_module(package)
        if not related_name and module:
            return module
    except ImportError:
        package, _, _ = package.rpartition('.')
        if not package:
            raise

    module_name = '{0}.{1}'.format(package, related_name)

    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        import_exc_name = getattr(e, 'name', module_name)
        if import_exc_name is not None and import_exc_name != module_name:
            raise e
        return
