#!/usr/bin/env python3
"""
AWS Lambda handler for EU CTIS harvester.
"""

import json
import asyncio
import os
from datetime import datetime
from ctis_harvester import run

def lambda_handler(event, context):
    """
    AWS Lambda entry point for CTIS harvester.
    
    Args:
        event: Lambda event data (może zawierać parametry)
        context: Lambda context object
    
    Returns:
        dict: Response z statusem i informacjami o wykonaniu
    """
    
    print(f"🚀 CTIS Harvester Lambda started at {datetime.utcnow()}")
    print(f"Event: {json.dumps(event, default=str)}")
    
    try:
        # Uruchom harvester asynchronicznie
        result = asyncio.run(run())
        
        response = {
            'statusCode': 200,
            'body': {
                'message': 'CTIS harvester completed successfully',
                'timestamp': datetime.utcnow().isoformat(),
                'presigned_url': result,
                'event': event
            }
        }
        
        print(f"✅ Success: {response}")
        return response
        
    except Exception as e:
        error_response = {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'CTIS harvester failed',
                'timestamp': datetime.utcnow().isoformat(),
                'event': event
            }
        }
        
        print(f"❌ Error: {error_response}")
        return error_response

# Test local execution
if __name__ == "__main__":
    # Test event dla lokalnego testowania
    test_event = {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "detail": {}
    }
    
    test_context = type('Context', (), {
        'function_name': 'ctis-harvester-test',
        'function_version': '$LATEST',
        'memory_limit_in_mb': '512'
    })()
    
    result = lambda_handler(test_event, test_context)
    print(f"Local test result: {json.dumps(result, indent=2)}")
