#!/usr/bin/env python3
"""
Test lokalny Lambda handler przed deployment.
"""

import json
from lambda_handler import lambda_handler

def test_lambda_locally():
    """Test funkcji Lambda lokalnie."""
    
    print("🧪 Test Lambda handler lokalnie...")
    
    # Symulacja EventBridge event
    test_event = {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2025-08-06T04:00:00Z",
        "region": "eu-west-1",
        "detail": {}
    }
    
    # Symulacja Lambda context
    class MockContext:
        def __init__(self):
            self.function_name = "ctis-harvester"
            self.function_version = "$LATEST"
            self.invoked_function_arn = "arn:aws:lambda:eu-west-1:123456789012:function:ctis-harvester"
            self.memory_limit_in_mb = "512"
            self.log_group_name = "/aws/lambda/ctis-harvester"
            self.log_stream_name = "2025/08/06/[$LATEST]test"
            self.aws_request_id = "test-request-id"
    
    context = MockContext()
    
    try:
        result = lambda_handler(test_event, context)
        
        print("\n" + "="*50)
        print("📊 REZULTAT TESTU:")
        print("="*50)
        print(json.dumps(result, indent=2, default=str))
        print("="*50)
        
        if result['statusCode'] == 200:
            print("✅ Test zakończony sukcesem!")
        else:
            print("❌ Test zakończony błędem!")
            
    except Exception as e:
        print(f"💥 Błąd podczas testu: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_lambda_locally()
