import unittest
from hashlib import sha256
from unittest.mock import Mock, patch
from app.services.demo_extraction_cache import reuse_demo_extraction
from app.services.doc_extract import BillOut


class DemoExtractionCacheTests(unittest.TestCase):
    def test_only_exact_allowlisted_content_is_shared_and_results_are_copied(self):
        synthetic = b'fictional fixture'
        underlying = Mock(return_value=BillOut())
        read = reuse_demo_extraction(underlying)
        with patch('app.services.demo_extraction_cache._SYNTHETIC_DIGESTS', {sha256(synthetic).hexdigest()}):
            first = read(synthetic)
            first.hospital = 'Changed by a guest'
            self.assertIsNone(read(synthetic).hospital)
            self.assertEqual(underlying.call_count, 1)
            read(b'private bill')
            read(b'private bill')
            read(synthetic + b' modified')
            read(synthetic, 'image/jpeg')
            self.assertEqual(underlying.call_count, 5)
