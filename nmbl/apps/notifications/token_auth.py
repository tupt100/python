from channels.auth import AuthMiddlewareStack
from customers.models import Domain
from django.contrib.auth.models import AnonymousUser
from django_tenants.utils import schema_context
from rest_framework.authtoken.models import Token


def set_user(scope, domain, token_key):
    schema = Domain.objects.get(
        domain=domain).tenant.schema_name
    with schema_context(schema):
        token = Token.objects.get(key=token_key)
        scope['user'] = token.user


class TokenAuthMiddleware:
    """
    Token authorization middleware for Django Channels 2
    """

    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope, receive, send):
        headers = dict(scope['headers'])
        if scope.get('query_string'):
            query_string = scope['query_string']
            all_params = query_string.decode().split('&')
            for param in all_params:
                if 'token' in param.lower():
                    token_name, token_key = param.split('=')
                    try:
                        if token_name.lower() == 'token':
                            domain = headers[b'host'].decode().split()[0]
                            domain = domain.split(":")[0]
                            set_user(scope, domain, token_key)
                    except Exception as e:
                        print('Error: TokenAuthMiddleware: ', e)
                    break
        elif b'authorization' in headers:
            try:
                token_name, token_key = \
                    headers[b'authorization'].decode().split()
                if token_name == 'Token':
                    domain = headers[b'host'].decode().split()[0]
                    domain = domain.split(":")[0]
                    set_user(scope, domain, token_key)
            except Token.DoesNotExist:
                scope['user'] = AnonymousUser()
        return self.inner(scope, receive, send)


TokenAuthMiddlewareStack = lambda inner: \
    TokenAuthMiddleware(AuthMiddlewareStack(inner))
