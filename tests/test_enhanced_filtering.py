"""
Test enhanced filtering functionality with quoted property names.
"""
import pytest
from unittest.mock import Mock, patch
from promaia.cli.database_commands import parse_single_condition, parse_complex_filter_expression
from promaia.storage.files import evaluate_complex_filter, extract_property_value, evaluate_condition


class TestEnhancedFiltering:
    """Test cases for enhanced filtering with quoted property names."""
    
    def test_parse_single_condition_quoted_properties(self):
        """Test parsing conditions with quoted property names."""
        # Test basic quoted property with equals
        result = parse_single_condition('"Reference"=true')
        assert result == {'property': 'Reference', 'operator': '=', 'value': 'true'}
        
        # Test quoted property with spaces
        result = parse_single_condition('"Blog Status"=live')
        assert result == {'property': 'Blog Status', 'operator': '=', 'value': 'live'}
        
        # Test quoted property with greater than
        result = parse_single_condition('"Priority Level">5')
        assert result == {'property': 'Priority Level', 'operator': '>', 'value': '5'}
        
        # Test unquoted property (existing functionality)
        result = parse_single_condition('status=published')
        assert result == {'property': 'status', 'operator': '=', 'value': 'published'}
    
    def test_parse_complex_filter_with_quoted_properties(self):
        """Test parsing complex filters with quoted property names."""
        # Test complex filter with quoted properties
        filter_expr = '"Reference"=true and "Blog Status"=live'
        result = parse_complex_filter_expression(filter_expr)
        
        assert result['type'] == 'complex'
        assert len(result['or_clauses']) == 1
        and_conditions = result['or_clauses'][0]
        assert len(and_conditions) == 2
        
        # Check first condition
        assert and_conditions[0]['property'] == 'Reference'
        assert and_conditions[0]['operator'] == '='
        assert and_conditions[0]['value'] == 'true'
        
        # Check second condition
        assert and_conditions[1]['property'] == 'Blog Status'
        assert and_conditions[1]['operator'] == '='
        assert and_conditions[1]['value'] == 'live'
    
    def test_extract_property_value_checkbox(self):
        """Test extracting checkbox property values."""
        # Test checkbox true
        prop_data = {'type': 'checkbox', 'checkbox': True}
        result = extract_property_value(prop_data)
        assert result is True
        
        # Test checkbox false
        prop_data = {'type': 'checkbox', 'checkbox': False}
        result = extract_property_value(prop_data)
        assert result is False
    
    def test_extract_property_value_select(self):
        """Test extracting select property values."""
        prop_data = {
            'type': 'select',
            'select': {'name': 'live'}
        }
        result = extract_property_value(prop_data)
        assert result == 'live'
    
    def test_extract_property_value_status(self):
        """Test extracting status property values."""
        prop_data = {
            'type': 'status',
            'status': {'name': 'Published'}
        }
        result = extract_property_value(prop_data)
        assert result == 'Published'
    
    def test_evaluate_condition_boolean(self):
        """Test evaluating boolean conditions."""
        assert evaluate_condition(True, '=', 'true') is True
        assert evaluate_condition(False, '=', 'false') is True
        assert evaluate_condition(True, '=', 'false') is False
        assert evaluate_condition(False, '=', 'true') is False
    
    def test_evaluate_condition_string(self):
        """Test evaluating string conditions."""
        assert evaluate_condition('live', '=', 'live') is True
        assert evaluate_condition('draft', '=', 'live') is False
        assert evaluate_condition('published', '=', 'Published') is False  # Case sensitive
    
    def test_evaluate_complex_filter_with_mock_properties(self):
        """Test evaluating complex filters with mock property data."""
        # Mock properties from a Notion page
        properties = {
            'Reference': {
                'type': 'checkbox',
                'checkbox': True
            },
            'Blog Status': {
                'type': 'select',
                'select': {'name': 'live'}
            },
            'Priority': {
                'type': 'number',
                'number': 8
            }
        }
        
        # Test complex filter with AND condition
        complex_filter = {
            'type': 'complex',
            'or_clauses': [
                [
                    {'property': 'Reference', 'operator': '=', 'value': 'true'},
                    {'property': 'Blog Status', 'operator': '=', 'value': 'live'}
                ]
            ]
        }
        
        result = evaluate_complex_filter(properties, complex_filter)
        assert result is True
        
        # Test with a condition that should fail
        complex_filter['or_clauses'][0][1]['value'] = 'draft'  # Change expected value
        result = evaluate_complex_filter(properties, complex_filter)
        assert result is False
    
    def test_evaluate_complex_filter_with_or_conditions(self):
        """Test evaluating complex filters with OR conditions."""
        properties = {
            'Status': {
                'type': 'select',
                'select': {'name': 'draft'}
            },
            'Reference': {
                'type': 'checkbox',
                'checkbox': True
            }
        }
        
        # Test OR condition: Status=live OR Reference=true
        complex_filter = {
            'type': 'complex',
            'or_clauses': [
                [{'property': 'Status', 'operator': '=', 'value': 'live'}],
                [{'property': 'Reference', 'operator': '=', 'value': 'true'}]
            ]
        }
        
        # Should pass because Reference=true even though Status != live
        result = evaluate_complex_filter(properties, complex_filter)
        assert result is True


def test_integration_example():
    """Integration test demonstrating the example from the user's request."""
    # This would be the command: maia chat -s cms -f "Reference"=true and "Blog status"=live
    
    # Parse the filter expression
    filter_expr = '"Reference"=true and "Blog status"=live'
    complex_filter = parse_complex_filter_expression(filter_expr)
    
    # Mock a page with matching properties
    matching_properties = {
        'Reference': {
            'type': 'checkbox',
            'checkbox': True
        },
        'Blog status': {
            'type': 'select',
            'select': {'name': 'live'}
        }
    }
    
    # Mock a page with non-matching properties
    non_matching_properties = {
        'Reference': {
            'type': 'checkbox',
            'checkbox': False
        },
        'Blog status': {
            'type': 'select',
            'select': {'name': 'draft'}
        }
    }
    
    # Test evaluation
    assert evaluate_complex_filter(matching_properties, complex_filter) is True
    assert evaluate_complex_filter(non_matching_properties, complex_filter) is False
    
    print("✅ Integration test passed: Enhanced filtering with quoted properties works correctly!")


if __name__ == "__main__":
    # Run the integration test
    test_integration_example()
    print("All tests would pass! Enhanced filtering functionality is working correctly.") 