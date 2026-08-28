"""Tests for manufacturing/api_openapi_core.py — the hand-curated OpenAPI
spec for the mobile REST API. Pure Python, no DB, no Django request needed."""

from manufacturing.api_openapi_core import build_openapi_spec, ENDPOINTS


def test_spec_has_required_top_level_keys():
    spec = build_openapi_spec()
    assert spec['openapi'] == '3.0.3'
    assert 'info' in spec
    assert 'paths' in spec
    assert 'components' in spec


def test_spec_includes_every_declared_endpoint():
    spec = build_openapi_spec()
    for path, methods, _summary, _auth in ENDPOINTS:
        assert path in spec['paths'], f'{path} missing from spec'
        for method in methods:
            assert method in spec['paths'][path], f'{method} {path} missing'


def test_login_endpoint_has_no_security_requirement():
    spec = build_openapi_spec()
    op = spec['paths']['/auth/login/']['post']
    assert op['security'] == []


def test_authenticated_endpoint_requires_bearer_auth():
    spec = build_openapi_spec()
    op = spec['paths']['/auth/profile/']['get']
    assert op['security'] == [{'bearerAuth': []}]


def test_authenticated_endpoint_documents_401_and_429():
    spec = build_openapi_spec()
    op = spec['paths']['/auth/profile/']['get']
    assert '401' in op['responses']
    assert '429' in op['responses']


def test_login_endpoint_does_not_document_401_or_429_from_bearer_auth():
    # Login itself can still 401 on bad credentials, but not via the
    # bearer-token-required path — this spec only adds 401/429 to
    # endpoints that go through api_required.
    spec = build_openapi_spec()
    op = spec['paths']['/auth/login/']['post']
    assert '429' not in op['responses']


def test_path_parameters_are_declared():
    spec = build_openapi_spec()
    op = spec['paths']['/wo/{wo_id}/']['get']
    param_names = [p['name'] for p in op['parameters']]
    assert param_names == ['wo_id']


def test_multi_param_path_declares_both_parameters():
    spec = build_openapi_spec()
    op = spec['paths']['/wo/{wo_id}/operations/{seq}/complete/']['post']
    param_names = {p['name'] for p in op['parameters']}
    assert param_names == {'wo_id', 'seq'}


def test_server_url_includes_base_url_when_given():
    spec = build_openapi_spec(base_url='https://erp.example.com')
    assert spec['servers'][0]['url'] == 'https://erp.example.com/api/v1'


def test_server_url_defaults_to_relative_when_no_base_url():
    spec = build_openapi_spec()
    assert spec['servers'][0]['url'] == '/api/v1'


def test_bearer_auth_security_scheme_declared():
    spec = build_openapi_spec()
    scheme = spec['components']['securitySchemes']['bearerAuth']
    assert scheme['type'] == 'http'
    assert scheme['scheme'] == 'bearer'


def test_endpoints_list_has_no_duplicate_path_method_pairs():
    seen = set()
    for path, methods, _summary, _auth in ENDPOINTS:
        for method in methods:
            key = (path, method)
            assert key not in seen, f'duplicate {method.upper()} {path}'
            seen.add(key)
