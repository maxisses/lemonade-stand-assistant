"""Test detector failure handling without loading or downloading language models."""
import ast
import asyncio
import logging
from pathlib import Path
import re
from types import SimpleNamespace
from typing import List
import unittest
from fastapi import HTTPException

source = Path(__file__).resolve().parents[1] / 'chart/files/lingua-app.py'
tree = ast.parse(source.read_text())
functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in {'detect_language', 'analyze_contents'}]
for function in functions:
    function.decorator_list = []

class BrokenDetector:
    def detect_language_of(self, text):
        raise RuntimeError('Simulated detector outage')

namespace = {'List':List, 'ContentAnalysisResponse':object, 'ContentAnalysisHttpRequest':object,
             'asyncio':asyncio, 'logger':logging.getLogger('test_language'), 're':re,
             'detector':BrokenDetector(), 'HTTPException':HTTPException}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)

class LanguageFailureTests(unittest.IsolatedAsyncioTestCase):
    def test_detector_exception_is_not_an_empty_detection(self):
        with self.assertRaises(RuntimeError):
            namespace['detect_language']('Hello there')

    async def test_handler_returns_unavailable_on_detector_failure(self):
        with self.assertRaises(HTTPException) as error:
            await namespace['analyze_contents'](SimpleNamespace(contents=['Hello there']))
        self.assertEqual(error.exception.status_code, 503)

if __name__ == '__main__': unittest.main()
