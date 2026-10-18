import unittest
from unittest.mock import patch

from app.services.greetings import is_greeting
from app.services.conversation import prepare
from app.services.copilot import answer


class GreetingTests(unittest.TestCase):
    def test_pure_greetings_skip_context_and_model_even_in_existing_thread(self):
        with patch('app.services.conversation.scope_key', side_effect=AssertionError('Firestore access')), \
             patch('app.services.copilot.route', side_effect=AssertionError('Model routing')):
            for question in ('Hi', ' hello! ', 'Hey Nessi', 'Good morning', 'नमस्ते'):
                resolved, context = prepare(question, 'existing-thread')
                self.assertIsNone(context)
                result = answer(resolved)
                self.assertEqual(result.steps, [])
                self.assertEqual(result.answer.citations, [])
                self.assertTrue(result.answer.general)
            self.assertIn('नमस्ते', answer('hello', language='hi').answer.headline)

    def test_greeting_prefix_does_not_hide_actual_questions(self):
        for question in ('Hi, why was 38000 deducted?', 'Hello is maternity covered?',
                         'Hi my surgery is tomorrow', 'नमस्ते मेरी पॉलिसी क्या कवर करती है?'):
            self.assertFalse(is_greeting(question), question)
