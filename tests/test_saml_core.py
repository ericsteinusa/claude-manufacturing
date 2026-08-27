"""Tests for saml_core.py — Qt-free, no live network, no live database.

The security-critical XML signature verification itself lives entirely
inside python3-saml/xmlsec (an audited library, not hand-rolled code in
this app — see saml_core.py's module docstring), so unit tests here focus
on what this module actually wrote: provider config parsing/validation
and the settings dict this app builds for the library. A genuine signed
end-to-end round trip (real X.509 cert, real xmlsec signing) is verified
separately, live, against the running dev server.

Same DJANGO_SETTINGS_MODULE-without-django.setup() pattern as
test_sso_core.py, for the same reason (avoid AppConfig.ready() opening a
real DB connection).
"""
import json
import os
from unittest.mock import MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacture.settings')

import pytest  # noqa: E402
from django.conf import settings as django_settings  # noqa: E402

from manufacturing import saml_core  # noqa: E402

IDP_ENTITY_ID = 'https://idp.example.com/saml'
IDP_SSO_URL = 'https://idp.example.com/saml/sso'
IDP_CERT = 'MIIDpDCCAoygAwIBAgIfake=='


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', '')
    yield


@pytest.fixture
def provider():
    return {
        'key': 'okta', 'label': 'Okta',
        'idp_entity_id': IDP_ENTITY_ID, 'idp_sso_url': IDP_SSO_URL,
        'idp_x509_cert': IDP_CERT,
        'auto_provision': False, 'default_dept_key': '',
    }


# ---------------------------------------------------------------------------
# get_providers / get_provider / is_configured
# ---------------------------------------------------------------------------

def test_get_providers_empty_by_default():
    assert saml_core.get_providers() == []


def test_is_configured_false_by_default():
    assert saml_core.is_configured() is False


def test_get_providers_parses_valid_config(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT},
    ]))
    providers = saml_core.get_providers()
    assert len(providers) == 1
    assert providers[0]['key'] == 'okta'
    assert providers[0]['idp_entity_id'] == IDP_ENTITY_ID
    assert saml_core.is_configured() is True


def test_get_providers_supports_multiple(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT},
        {'key': 'adfs', 'label': 'ADFS', 'idp_entity_id': 'https://adfs.example.com',
         'idp_sso_url': 'https://adfs.example.com/sso', 'idp_x509_cert': IDP_CERT},
    ]))
    providers = saml_core.get_providers()
    assert [p['key'] for p in providers] == ['okta', 'adfs']


def test_invalid_json_disables_saml_without_crashing(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', 'not valid json')
    assert saml_core.get_providers() == []


def test_entry_missing_required_field_is_skipped(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'broken', 'label': 'Broken'},  # missing idp_* fields
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT},
    ]))
    providers = saml_core.get_providers()
    assert [p['key'] for p in providers] == ['okta']


def test_defaults_to_no_auto_provision(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT},
    ]))
    providers = saml_core.get_providers()
    assert providers[0]['auto_provision'] is False
    assert providers[0]['default_dept_key'] == ''


def test_auto_provision_without_default_dept_key_is_disabled(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT,
         'auto_provision': True},
    ]))
    providers = saml_core.get_providers()
    assert providers[0]['auto_provision'] is False


def test_auto_provision_with_default_dept_key_enabled(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT,
         'auto_provision': True, 'default_dept_key': 'sales'},
    ]))
    providers = saml_core.get_providers()
    assert providers[0]['auto_provision'] is True
    assert providers[0]['default_dept_key'] == 'sales'


def test_get_provider_returns_none_for_unknown_key(monkeypatch):
    monkeypatch.setattr(django_settings, 'SAML_PROVIDERS', json.dumps([
        {'key': 'okta', 'label': 'Okta', 'idp_entity_id': IDP_ENTITY_ID,
         'idp_sso_url': IDP_SSO_URL, 'idp_x509_cert': IDP_CERT},
    ]))
    assert saml_core.get_provider('adfs') is None
    assert saml_core.get_provider('okta')['idp_entity_id'] == IDP_ENTITY_ID


# ---------------------------------------------------------------------------
# build_settings
# ---------------------------------------------------------------------------

def test_build_settings_uses_this_providers_idp_config(provider):
    result = saml_core.build_settings(
        provider, 'https://app.local/sso/saml/login/okta/',
        'https://app.local/sso/saml/acs/okta/')
    assert result['idp']['entityId'] == IDP_ENTITY_ID
    assert result['idp']['singleSignOnService']['url'] == IDP_SSO_URL
    assert result['idp']['x509cert'] == IDP_CERT
    assert result['sp']['entityId'] == 'https://app.local/sso/saml/login/okta/'
    assert result['sp']['assertionConsumerService']['url'] == 'https://app.local/sso/saml/acs/okta/'


def test_build_settings_requires_signed_assertions(provider):
    result = saml_core.build_settings(provider, 'sp-id', 'https://app.local/acs')
    assert result['security']['wantAssertionsSigned'] is True


def test_build_settings_is_strict(provider):
    result = saml_core.build_settings(provider, 'sp-id', 'https://app.local/acs')
    assert result['strict'] is True


# ---------------------------------------------------------------------------
# prepare_request_data
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, secure, host, path, get=None, post=None):
        self._secure = secure
        self.META = {'HTTP_HOST': host}
        self.path = path
        self.GET = get or {}
        self.POST = post or {}

    def is_secure(self):
        return self._secure

    def copy(self):
        return dict(self)


def test_prepare_request_data_https_on():
    req = _FakeRequest(True, 'app.local', '/sso/saml/acs/okta/')
    req.GET = type('QD', (), {'copy': lambda self: {}})()
    req.POST = type('QD', (), {'copy': lambda self: {}})()
    data = saml_core.prepare_request_data(req)
    assert data['https'] == 'on'
    assert data['http_host'] == 'app.local'
    assert data['script_name'] == '/sso/saml/acs/okta/'


def test_prepare_request_data_https_off():
    req = _FakeRequest(False, 'app.local', '/sso/saml/login/okta/')
    req.GET = type('QD', (), {'copy': lambda self: {}})()
    req.POST = type('QD', (), {'copy': lambda self: {}})()
    data = saml_core.prepare_request_data(req)
    assert data['https'] == 'off'


# ---------------------------------------------------------------------------
# consume_assertion_once — replay protection
# ---------------------------------------------------------------------------

def test_first_use_of_an_assertion_id_is_allowed():
    conn = MagicMock()
    conn.execute.return_value.rowcount = 1
    assert saml_core.consume_assertion_once(conn, 'assertion-123') is True
    conn.commit.assert_called_once()


def test_replayed_assertion_id_is_denied():
    conn = MagicMock()
    conn.execute.return_value.rowcount = 0
    assert saml_core.consume_assertion_once(conn, 'assertion-123') is False


def test_empty_assertion_id_is_denied_without_touching_db():
    conn = MagicMock()
    assert saml_core.consume_assertion_once(conn, '') is False
    conn.execute.assert_not_called()


def test_consume_assertion_uses_on_conflict_do_nothing():
    conn = MagicMock()
    conn.execute.return_value.rowcount = 1
    saml_core.consume_assertion_once(conn, 'assertion-123')
    insert_sql = [c for c in conn.execute.call_args_list if 'INSERT' in c[0][0]][0][0][0]
    assert 'ON CONFLICT (assertion_id) DO NOTHING' in insert_sql
