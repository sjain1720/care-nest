"""Upload file types and general-vs-own-cover question routing (pure Python)."""
import unittest

from app.services.file_types import detect_mime, is_image
from app.services.intents import keyword_about


class FileTypeTests(unittest.TestCase):
    def test_detects_pdf_and_photos(self):
        self.assertEqual(detect_mime(b"%PDF-1.7 ..."), "application/pdf")
        self.assertEqual(detect_mime(b"\xff\xd8\xff\xe0 JFIF"), "image/jpeg")
        self.assertEqual(detect_mime(b"\x89PNG\r\n\x1a\n...."), "image/png")
        self.assertEqual(detect_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 "), "image/webp")

    def test_rejects_everything_else(self):
        for data in (b"", b"GIF89a", b"PK\x03\x04 docx", b"<html>", b"RIFF\x00\x00\x00\x00WAVE"):
            self.assertIsNone(detect_mime(data), data)

    def test_is_image(self):
        self.assertTrue(is_image("image/png"))
        self.assertFalse(is_image("application/pdf"))


class AboutTests(unittest.TestCase):
    def test_general_questions(self):
        for q in ("What is a waiting period?", "How does co-pay work?", "What does sum insured mean", "Is maternity usually covered?"):
            self.assertEqual(keyword_about(q), "general", q)

    def test_own_cover_questions(self):
        for q in ("Does my policy cover maternity?", "Am I covered for cataract?", "Can I claim this bill?",
                  "How much cover do we have left?", "मेरी पॉलिसी में क्या शामिल है?"):
            self.assertEqual(keyword_about(q), "mine", q)


if __name__ == "__main__":
    unittest.main()
