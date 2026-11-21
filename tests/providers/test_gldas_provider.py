"""Diagnóstico Earthdata con respuestas simuladas; no son observaciones GLDAS."""

import json
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from services.api_service import ServiceError
from services.geography.cities import get_city
from services.providers.gldas import GldasProvider, PRODUCT, VERSION, public_diagnostic, environment_token
from services.science.scientific import ScientificStore
from scripts.data.fetch_science import main as fetch_science


class GldasTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.store=ScientificStore(Path(temporary.name))
        self.provider=GldasProvider(self.store)

    def responses(self, status):
        collection=Mock();collection.json.return_value={'feed':{'entry':[{
            'short_name':PRODUCT,'version_id':VERSION,'id':'synthetic-collection'}]}}
        granule=Mock();granule.json.return_value={'feed':{'entry':[{'links':[{
            'href':'https://opendap.earthdata.nasa.gov/collections/synthetic/granules/software-test'}]}]}}
        data=Mock();data.status_code=status;data.text='Dataset { software_test_only; }' if status==200 else 'Unauthorized'
        data.url='https://opendap.earthdata.nasa.gov/synthetic.dds'
        return [collection,granule,data]

    def test_unauthenticated_probe_never_enables_variables(self):
        with patch.dict(os.environ,{},clear=True), patch('services.providers.gldas.requests.get',side_effect=self.responses(401)):
            result=self.provider.probe()
        self.assertEqual(result['http_status'],401)
        self.assertFalse(result['authenticated_metadata_access'])
        self.assertFalse(result['data_extraction_verified'])
        self.assertEqual(self.store.inventory(),[])

    def test_token_is_not_persisted_and_metadata_access_is_not_data_verification(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret-for-software-test'}), patch(
                'services.providers.gldas.requests.get',side_effect=self.responses(200)) as network:
            result=self.provider.probe()
        self.assertIn('Authorization',network.call_args.kwargs['headers'])
        self.assertTrue(result['authenticated_metadata_access'])
        self.assertFalse(result['data_extraction_verified'])
        self.assertNotIn('synthetic-secret',json.dumps(result))
        self.assertNotIn('synthetic-secret',(self.store.root/'discovery/gldas-access-latest.json').read_text())
        self.assertEqual(result['records'],0)
        self.assertEqual(self.store.inventory(),[])

    def test_fetch_requires_authentication_before_requests(self):
        with patch.dict(os.environ,{},clear=True),patch('requests.get') as network:
            with self.assertRaises(ServiceError) as failure:
                self.provider.fetch(get_city('mendoza'),['Evap_tavg'],{'start_year':2024,'end_year':2024})
        self.assertEqual(failure.exception.code,'provider_auth_required')
        network.assert_not_called()

    def test_dap2_bad_request_tries_dap4_metadata_without_marking_observations(self):
        responses=self.responses(400)
        responses[-1].text='DAP2 incompatible variable types'
        dmr=Mock();dmr.status_code=200;dmr.url='https://opendap.earthdata.nasa.gov/synthetic.dmr.xml'
        dmr.text='<Dataset xmlns="http://xml.opendap.org/ns/DAP/4.0#" name="software-test" />'
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic-secret'}),patch(
                'services.providers.gldas.requests.get',side_effect=responses+[dmr]):
            result=self.provider.probe()
        self.assertTrue(result['authenticated_metadata_access'])
        self.assertEqual(result['descriptor_format'],'.dmr.xml')
        self.assertEqual([row['http_status'] for row in result['attempts']],[400,200])
        self.assertFalse(result['data_extraction_verified'])
        self.assertEqual(result['records'],0)

    def test_remote_error_diagnostic_redacts_token_and_html_sessions(self):
        response=Mock();response.text='Error: synthetic-secret Bearer synthetic-secret'
        self.assertNotIn('synthetic-secret',public_diagnostic(response,'synthetic-secret'))
        response.text='<html><form>private-session</form></html>'
        self.assertNotIn('private-session',public_diagnostic(response,'synthetic-secret'))
        response.text='<html><title>400 Error</title><p>bad token synthetic-secret</p><form><p>private-session</p></form><script>private-script</script></html>'
        message=public_diagnostic(response,'synthetic-secret')
        self.assertIn('400 Error',message)
        self.assertIn('bad token',message)
        self.assertNotIn('synthetic-secret',message)
        self.assertNotIn('private-session',message)
        self.assertNotIn('private-script',message)

    def test_token_with_bearer_prefix_is_rejected_without_echoing_credential(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'Bearer synthetic-secret'}),patch(
                'services.providers.gldas.requests.get',side_effect=self.responses(200)):
            with self.assertRaises(ServiceError) as failure:
                self.provider.probe()
        self.assertNotIn('synthetic-secret',str(failure.exception))

    def test_invalid_bearer_characters_are_rejected_before_network(self):
        for token in ('synthetic secret','synthetic\tsecret','synthetic\x1bsecret','"synthetic-secret"','synthetic\nsecret','Bearer synthetic-secret'):
            with self.subTest(),patch.dict(os.environ,{'EARTHDATA_TOKEN':token}),patch('services.providers.gldas.requests.get') as network:
                with self.assertRaises(ServiceError):
                    self.provider.probe()
                network.assert_not_called()
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic.valid_bearer-token~+/='}):
            self.assertEqual(environment_token(),'synthetic.valid_bearer-token~+/=')

    def test_cli_reports_invalid_credential_without_network_or_secret_output(self):
        output=StringIO()
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'synthetic\x1bsecret'}),patch(
                'services.providers.gldas.requests.get') as network,redirect_stdout(output):
            status=fetch_science(['--provider','gldas','--probe','--cache-dir',str(self.store.root/'power')])
        result=json.loads(output.getvalue())
        self.assertEqual(status,1)
        self.assertFalse(result['details']['credential_format_valid'])
        self.assertNotIn('synthetic',output.getvalue())
        network.assert_not_called()

    def test_format_diagnostic_identifies_paste_markers_without_revealing_token(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'\x1b[200~synthetic-secret\x1b[201~'}):
            with self.assertRaises(ServiceError) as failure:
                environment_token()
        details=failure.exception.details
        self.assertTrue(details['has_paste_markers'])
        self.assertTrue(details['has_control_characters'])
        self.assertEqual(details['invalid_character_codes'],['U+001B','U+005B'])
        self.assertNotIn('synthetic',json.dumps(details))

    def test_format_diagnostic_distinguishes_prefix_quotes_and_whitespace(self):
        with patch.dict(os.environ,{'EARTHDATA_TOKEN':'Bearer "synthetic-secret"\n'}):
            with self.assertRaises(ServiceError) as failure:
                environment_token()
        details=failure.exception.details
        for field in ('has_bearer_prefix','has_quotes','has_whitespace','has_control_characters'):
            self.assertTrue(details[field])
        self.assertFalse(details['has_paste_markers'])
        self.assertNotIn('synthetic',json.dumps(details))


if __name__=='__main__':
    unittest.main()
