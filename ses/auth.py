import os
import base64
import json
from base64 import b64decode

from google_auth_oauthlib.flow import InstalledAppFlow


app_directory = os.path.join(
    os.getenv('HOME'), '.config', 'sem-emergency-stop'
)
user_auth_file = os.path.join(app_directory, 'user-auth.json')
client_auth_file = os.path.join(app_directory, 'client-auth.json')
api_auth_file = os.path.join(app_directory, 'api-auth.json')

config_files = (user_auth_file, client_auth_file, api_auth_file)

auth_scope = 'https://www.googleapis.com/auth/adwords'


class TokenError(Exception):
    pass


def decode_organization_token(token):
    prefix = 'organization-token-'
    if not token.startswith(prefix):
        raise TokenError('prefix')

    stripped = token[len(prefix) :]  # noqa: E203

    try:
        b64_decoded = b64decode(stripped)
    except Exception:
        raise TokenError('base64')

    try:
        utf8_decoded = b64_decoded.decode('utf-8')
    except Exception:
        raise TokenError('utf-8')

    try:
        json_decoded = json.loads(utf8_decoded)
    except Exception:
        raise TokenError('json')

    for f in (
        'client_id',
        'client_secret',
        'developer_token',
        'login_customer_id',
    ):
        if f not in json_decoded or not len(json_decoded[f]):
            raise TokenError(f'validation/{f}')

    return json_decoded


def organization_token_flow():
    print('It looks like you don\'t have the organization token set up.')
    print('Please obtain the token from your organization and paste it below,')
    print('then hit enter. It should start with "organization-token-"')
    print()

    while True:
        try:
            token = decode_organization_token(input('Organization token: '))
            break
        except TokenError as e:
            print(f'That token looks invalid ({e}), try again?')
            print()

    print('That token seems legit, storing it for future use')

    os.makedirs(app_directory, exist_ok=True)
    store_api_auth(token)
    store_client_auth(token)

    print()


def load_organization_auth():
    try:
        api = json.load(open(api_auth_file))
        client = json.load(open(client_auth_file))
    except FileNotFoundError:
        organization_token_flow()
        return load_organization_auth()

    return {
        **api,
        'client_id': client['installed']['client_id'],
        'client_secret': client['installed']['client_secret'],
    }


def store_client_auth(organization_token):
    client_auth = {
        'installed': {
            'auth_provider_x509_cert_url': (
                'https://www.googleapis.com/oauth2/v1/certs'
            ),
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'client_id': organization_token['client_id'],
            'client_secret': organization_token['client_secret'],
            'project_id': 'sem-emergency-stop',
            'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob', 'http://localhost'],
            'token_uri': 'https://oauth2.googleapis.com/token',
        }
    }

    json.dump(client_auth, open(client_auth_file, 'w'))


def store_api_auth(organization_token):
    json.dump(
        {
            'developer_token': organization_token['developer_token'],
            'login_customer_id': organization_token['login_customer_id'],
        },
        open(api_auth_file, 'w'),
    )


def load_user_auth():
    try:
        return json.load(open(user_auth_file))
    except FileNotFoundError:
        oauth_flow()
        return load_user_auth()


def oauth_flow():
    flow = InstalledAppFlow.from_client_secrets_file(
        client_auth_file, scopes=[auth_scope]
    )

    flow.run_console()

    json.dump(
        {'refresh_token': flow.credentials.refresh_token},
        open(user_auth_file, 'w'),
    )


def organization_token_reader():
    for arg in (
        'login_customer_id',
        'developer_token',
        'client_id',
        'client_secret',
    ):
        yield arg, input(f"{arg.replace('_', ' ')}: ").strip()


def organization_token_builder():
    json_dump = json.dumps(
        dict(entry for entry in organization_token_reader())
    )
    json_dump = json_dump.encode('utf-8')
    return f"organization-token-{base64.b64encode(json_dump).decode('utf-8')}"


def create_org_token():
    token = organization_token_builder()
    print()
    print('Your token is:')
    print(token)


def reset_auth():
    secrets = list(filter(lambda x: os.path.exists(x), config_files))

    if len(secrets) == 0:
        print("No secrets where found! Nothing to do.")
        return

    response = input(
        'Are you sure to remove all secrets from cache? (yes/no): '
    )
    if response not in ('yes', 'y'):
        print('Secrets were not removed.')
        return

    print('removing all secrets...')
    for config_file in secrets:
        print(f'\tremoving {config_file}...', end=' ')
        os.remove(config_file)
        print('done')
    print('all secrets removed')
