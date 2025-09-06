#!/usr/bin/env python3
"""
Quick test of the model switching functionality
"""

import sys
sys.path.append('/Users/kb20250422/Documents/dev/promaia')

from promaia.chat.interface import get_current_model_name, switch_model

def test_model_switch():
    print("=== Model Switch Test ===")
    print(f"Current model: {get_current_model_name()}")
    
    print("\nTesting model switch with target model 'gemini'...")
    result = switch_model('gemini')
    if result:
        print(f"After switch: {get_current_model_name()}")
    else:
        print("Switch failed or model not available")
    
    print("\n=== Available Model Commands ===")
    print("/model                 - Interactive model selection menu")
    print("/model claude         - Switch to Claude")  
    print("/model gpt            - Switch to GPT-4o")
    print("/model gemini         - Switch to Gemini")
    print("/model llama          - Switch to Local Llama")

if __name__ == "__main__":
    test_model_switch()