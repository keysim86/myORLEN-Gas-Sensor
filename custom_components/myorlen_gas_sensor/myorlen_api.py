import string
import logging

import requests


from .invoices import invoices_from_dict, Invoices
from .pgp_list import (PpgList, ppg_list_from_dict)
from .ppg_reading_for_meter import PpgReadingForMeter, ppg_reading_for_meter_from_dict

login_url = "https://ebok.myorlen.pl/auth/login?api-version=3.0"
devices_list_url = "https://ebok.myorlen.pl/crm/get-ppg-list?api-version=3.0"
readings_url = "https://ebok.myorlen.pl/crm/get-all-ppg-readings-for-meter?pageSize=10&pageNumber=1&api-version=3.0&idPpg="
invoices_url = "https://ebok.myorlen.pl/crm/get-invoices-v2?pageNumber=1&pageSize=12&api-version=3.0"
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
}

_LOGGER = logging.getLogger(__name__)

AUTH_METHOD_ORLEN_ID = "orlen_id"
AUTH_METHOD_EBOK = "login_ebok"


class myORLENApi:

    def __init__(self, username, password, auth_method=AUTH_METHOD_ORLEN_ID) -> None:
        self.username = username
        self.password = password
        self.auth_method = auth_method

    def meterList(self) -> PpgList:
        token = self.login()
        if not token:
            raise Exception("Login failed: No token received")

        response = requests.get(devices_list_url, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'AuthToken': token
        })
        data = response.json()
        if data is None or "PpgList" not in data:
            raise Exception("Invalid API response: PpgList missing")
        return ppg_list_from_dict(data)

    def readingForMeter(self, meter_id) -> PpgReadingForMeter:
        return ppg_reading_for_meter_from_dict(requests.get(readings_url + meter_id, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'AuthToken': (self.login())
        }).json())

    def invoices(self) -> Invoices:
        return invoices_from_dict(requests.get(invoices_url, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'AuthToken': (self.login())
        }).json())

    def login(self) -> string:
        if self.auth_method == AUTH_METHOD_EBOK:
            payload = {
                "identificator": self.username,
                "accessPin": self.password,
                "rememberLogin": "false",
                "DeviceId": "a908313085dd4f16deaa4c15897e755e",
                "DeviceType": "Web",
                "DeviceName": "HomeAssistant"
            }
            response = requests.post(login_url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json().get('Token')
            _LOGGER.error("eBOK Login failed. Status: %s, Response: %s", response.status_code, response.text)
            return ""

        init_url = 'https://ebok.myorlen.pl/auth/oid/init-login?api-version=3.0'

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        })
        init_data = {
            "DeviceId": "a908313085dd4f16deaa4c15897e755e",
            "DeviceType": "Web",
            "DeviceName": "HomeAssistant wersja: 0.1",
            "LightweightRedirectUrl": "https://ebok.myorlen.pl/?show=modal",
            "FinalizeRegistrationRedirectUrl": "https://ebok.myorlen.pl/aktywuj-oid/"
        }

        response_init = session.post(init_url, json=init_data)
        redirect_url = response_init.json().get('RedirectUrl')
        response_page = session.get(redirect_url)
        match = re.search(r'action="([^"]+)"', response_page.text)

        if match:
            post_url = match.group(1).replace('&amp;', '&')
            payload = {
                'username': self.username,
                'password': self.password,
                'credentialId': ''
            }
            final_response = session.post(post_url, data=payload)

            if "https://ebok.myorlen.pl/home" in final_response.url:
                auth_token_url = f'https://ebok.myorlen.pl/auth/get-auth-token?deviceId={init_data["DeviceId"]}&api-version=3.0'
                session.headers.update({'Referer': 'https://ebok.myorlen.pl/'})
                res_auth = session.get(auth_token_url)
                if res_auth.status_code == 200:
                    return res_auth.json().get('Token')
        else:
            _LOGGER.error("Failed to find action URL in response page")
        return ""