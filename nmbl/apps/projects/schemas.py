# -*- coding: utf-8 -*-
from collections import OrderedDict, Counter

import coreapi
from django.contrib.auth import login
from rest_framework import exceptions
from rest_framework.authentication import SessionAuthentication
from rest_framework.authentication import (
    TokenAuthentication,
    BasicAuthentication
)
from rest_framework.permissions import AllowAny
from rest_framework.renderers import CoreJSONRenderer
from rest_framework.response import Response
from rest_framework.schemas import SchemaGenerator
from rest_framework.views import APIView
from rest_framework_swagger import renderers

INSERT_INTO_COLLISION_FMT = """
Schema Naming Collision.

coreapi.Link for URL path {value_url} cannot be inserted into schema.
Position conflicts with coreapi.Link for URL path {target_url}.

Attemped to insert link with keys: {keys}.

Adjust URLs to avoid naming collision or override `SchemaGenerator.get_keys()`
to customise schema structure.
"""


class CsrfExemptSessionAuthentication(SessionAuthentication):

    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening


def insert_into(target, keys, value):
    """
    Nested dictionary insertion.
    >>> example = {}
    >>> insert_into(example, ['a', 'b', 'c'], 123)
    >>> example
    {'a': {'b': {'c': 123}}}
    """
    for key in keys[:-1]:
        if key not in target:
            target[key] = LinkNode()
        target = target[key]

    try:
        target.links.append((keys[-1], value))
    except TypeError:
        msg = INSERT_INTO_COLLISION_FMT.format(
            value_url=value.url,
            target_url=target.url,
            keys=keys
        )
        raise ValueError(msg)


class LinkNode(OrderedDict):

    def __init__(self):
        self.links = []
        self.methods_counter = Counter()
        super(LinkNode, self).__init__()

    def get_available_key(self, preferred_key):
        if preferred_key not in self:
            return preferred_key

        while True:
            current_val = self.methods_counter[preferred_key]
            self.methods_counter[preferred_key] += 1

            key = '{}_{}'.format(preferred_key, current_val)
            if key not in self:
                return key


class ParamsSchemaGenerator(SchemaGenerator):

    def get_link(self, path, method, view, url):
        header_fields = (coreapi.Field(
            name='Authorization',
            location='header',
            required=False,
            description='Authorization',
            type='string'
        ),)
        link = view.schema.get_link(path, method, base_url=url)
        replace_old, fields = self.get_core_fields(view)

        if replace_old:
            link._fields = header_fields + fields
        else:
            link._fields = header_fields + link._fields + fields
        return link

    def get_links(self, request=None):
        """
        Return a dictionary containing all the links that should be
        included in the API schema.
        """
        links = LinkNode()

        # Generate (path, method, view) given (path, method, callback).
        paths = []
        view_endpoints = []
        for path, method, callback in self.endpoints:
            view = self.create_view(callback, method, request)
            if getattr(view, 'exclude_from_schema', False):
                continue
            path = self.coerce_path(path, method, view)
            paths.append(path)
            view_endpoints.append((path, method, view))

        # Only generate the path prefix for paths that will be included
        if not paths:
            return None
        prefix = self.determine_path_prefix(paths)

        for path, method, view in view_endpoints:
            # To allow all apis displayed in swagger regardless auth
            if not self.has_view_permissions(path, method, view):
                continue

            # if not self.url:
            #     continue
            link = self.get_link(path, method, view, self.url)
            subpath = path[len(prefix):]
            keys = self.get_keys(subpath, method, view)
            insert_into(links, keys, link)
        return links

    # def get_links(self, request=None):
    #     """
    #     Return a dictionary containing all the links that should be
    #     included in the API schema.
    #     """
    #     """
    #     Return a dictionary containing all the links that should be
    #     included in the API schema.
    #     """
    #     links = LinkNode()

    #     # Generate (path, method, view) given (path, method, callback).
    #     paths = []
    #     view_endpoints = []
    #     for path, method, callback in self.endpoints:
    #         view = self.create_view(callback, method, request)
    #         path = self.coerce_path(path, method, view)
    #         paths.append(path)
    #         view_endpoints.append((path, method, view))

    #     # Only generate the path prefix for paths that will be included
    #     if not paths:
    #         return None
    #     prefix = self.determine_path_prefix(paths)

    #     for path, method, view in view_endpoints:
    #         print("path: ", path)
    #         print("method: ", method)
    #         # print("view: ", view.get_serializer())
    #         # if not self.has_view_permissions(path, method, view):
    #         #     continue
    #         # link = view.schema.get_link(path, method, base_url=self.url)
    #         link = self.get_link(path, method, view, self.url)
    #         subpath = path[len(prefix):]
    #         keys = self.get_keys(subpath, method, view)
    #         insert_into(links, keys, link)
    #     return links

    def get_core_fields(self, view):
        existing_fields = getattr(view, 'coreapi_fields', ())
        # print(existing_fields)
        # existing_fields += coreapi.Field(
        #     name='Authorization',
        #     location='header',
        #     required=False,
        #     description='Authorization',
        #     type='string'
        # )

        if getattr(view, 'custom_route_swagger', {}):
            custom_dict = getattr(view, 'custom_route_swagger', {})
            if view.action in custom_dict:
                return True, existing_fields + custom_dict[view.action]
            else:
                # getattr(view, 'coreapi_fields', ())
                return False, existing_fields
        else:
            # getattr(view, 'coreapi_fields', ())
            return False, existing_fields


def get_params_swagger_view(title=None, url=None):
    """
    Returns schema view which renders Swagger/OpenAPI.

    (Replace with DRF get_schema_view shortcut in 3.5)
    """

    class SwaggerSchemaView(APIView):
        _ignore_model_permissions = True
        exclude_from_schema = False
        permission_classes = [AllowAny]
        renderer_classes = [
            CoreJSONRenderer,
            renderers.OpenAPIRenderer,
            renderers.SwaggerUIRenderer
        ]
        authentication_classes = (
            TokenAuthentication,
            CsrfExemptSessionAuthentication,
            BasicAuthentication,
        )

        def get(self, request):
            if request.user.is_authenticated:
                login(request, request.user)

            generator = ParamsSchemaGenerator(title=title, url=url)
            schema = generator.get_schema(request=request)
            if not schema:
                raise exceptions.ValidationError(
                    'The schema generator did not return a schema Document'
                )

            return Response(schema)

    return SwaggerSchemaView.as_view()
