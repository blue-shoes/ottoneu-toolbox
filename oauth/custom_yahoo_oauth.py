from yahoo_oauth import OAuth2
from yahoo_oauth.utils import get_data

import webbrowser
import time
import json


class Custom_OAuth2(OAuth2):
    """Custom implementation of the yahoo_oauth.OAuth2 library that doesn't require command-line input of verificaiton token."""

    def __init__(self, consumer_key, consumer_secret, **kwargs):
        super().__init__(consumer_key, consumer_secret, **kwargs)

    def handler(self):
        """* get request token if OAuth1
        * Get user authorization
        * Get access token
        """
        authorize_url = self.oauth.get_authorize_url(redirect_uri=self.callback_uri, response_type='code')

        # logger.debug("AUTHORIZATION URL : {0}".format(authorize_url))
        if self.browser_callback:
            # Open authorize_url
            webbrowser.open(authorize_url)
        self.access_token = ''
        return {}

    def store_token(self, token: str):
        self.verifier = token
        data = get_data(self.from_file)
        vars(self).update(data)

        self.token_time = time.time()

        credentials = {'token_time': self.token_time}

        # Building headers
        headers = self.generate_oauth2_headers()
        # Getting access token
        raw_access = self.oauth.get_raw_access_token(data={'code': self.verifier, 'redirect_uri': self.callback_uri, 'grant_type': 'authorization_code'}, headers=headers)
        #  parsed_access = parse_utf8_qsl(raw_access.content.decode('utf-8'))
        credentials.update(self.oauth2_access_parser(raw_access))

        data.update(credentials)

        with open('conf/token.json', 'w') as fp:
            json.dump(data, fp, indent=4, sort_keys=True, ensure_ascii=False)


def init_oauth() -> Custom_OAuth2:
    private_json_path = 'conf/private.json'
    # load credentials
    with open(private_json_path) as yahoo_app_credentials:
        auth_info = json.load(yahoo_app_credentials)

    token_file_path = 'conf/token.json'
    with open(token_file_path, 'w') as yahoo_oauth_token:
        json.dump(auth_info, yahoo_oauth_token)
    return Custom_OAuth2(None, None, from_file=token_file_path)


def set_credentials(oauth: Custom_OAuth2, verifier: str):
    oauth.store_token(verifier)
