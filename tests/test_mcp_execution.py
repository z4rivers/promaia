import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import Mock, MagicMock
from promaia.mcp.execution import McpToolExecutor
from promaia.mcp.client import McpClient

class TestMcpExecution(unittest.TestCase):
    def setUp(self):
        self.mock_mcp_client = MagicMock(spec=McpClient)
        self.executor = McpToolExecutor(self.mock_mcp_client)

    def test_has_tool_calls_detects_invoke_tags(self):
        ai_response = """
        Some text...
        <invoke name="API-post-search">
            <parameter name="query">journal</parameter>
        </invoke>
        Some more text...
        """
        self.assertTrue(self.executor.has_tool_calls(ai_response))

    def test_has_tool_calls_detects_tool_code_tags(self):
        ai_response = """
        Some text...
        <tool_code>search.web_search(query="Test Query")</tool_code>
        Some more text...
        """
        self.assertTrue(self.executor.has_tool_calls(ai_response))

    def test_has_tool_calls_false_for_no_tags(self):
        ai_response = "This is a response without any tool calls."
        self.assertFalse(self.executor.has_tool_calls(ai_response))

    def test_parse_tool_calls_parses_invoke_tags_with_dynamic_server(self):
        self.mock_mcp_client.get_connected_servers.return_value = ['notion_server']
        # Mock the _determine_server_for_tool method
        self.executor._determine_server_for_tool = lambda tool_name: 'notion_server'
        ai_response = """
        <invoke name="API-post-page">
            <parameter name="parent">{"database_id": "12345"}</parameter>
        </invoke>
        """
        tool_calls = self.executor.parse_tool_calls(ai_response)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]['server'], 'notion_server')
        self.assertEqual(tool_calls[0]['tool'], 'API-post-page')

    def test_parse_tool_calls_parses_tool_code_tags(self):
        self.mock_mcp_client.get_connected_servers.return_value = ['search']
        ai_response = """
        <tool_code>search.web_search(query="Koii Benvenutto")</tool_code>
        """
        tool_calls = self.executor.parse_tool_calls(ai_response)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]['server'], 'search')
        self.assertEqual(tool_calls[0]['tool'], 'web_search')
        self.assertEqual(tool_calls[0]['arguments'], {'query': 'Koii Benvenutto'})


if __name__ == '__main__':
    unittest.main()
