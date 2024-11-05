from projects.api.serializers.templates import *  # noqa
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404


def validate_custom_fields_value(model, model_template, template_id, data):
    template = None
    if template_id:
        template = get_object_or_404(model_template.objects.active(), pk=template_id)
    data = model.prepare_custom_fields_value(template, data)
    custom_fields_errors_list = model.clean_custom_fields_value(template, data, raise_error=False)
    if custom_fields_errors_list and len(custom_fields_errors_list) > 0:
        custom_fields_errors_list = {k: v.messages for d in custom_fields_errors_list for k, v in d.items()}
        raise ValidationError({'custom_fields_value': custom_fields_errors_list})
    return data
