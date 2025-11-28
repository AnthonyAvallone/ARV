from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for Go High Level webhook

# RentCast API Configuration
RENTCAST_API_KEY = os.getenv('RENTCAST_API_KEY')
RENTCAST_BASE_URL = 'https://api.rentcast.io/v1'

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Server is running'}), 200

@app.route('/get-arv', methods=['POST'])
@app.route('/get-arv', methods=['POST'])
def get_after_repair_value():
    """
    Endpoint to receive property data from Go High Level
    and return the After Repair Value from RentCast API
    """
    try:
        # Get data from Go High Level webhook
        data = request.json
        
        # Log incoming data for debugging
        print(f"Received data: {data}")
        
        # Handle both standard webhook and custom webhook formats
        contact_data = data.get('contact', {})
        custom_data = data.get('customData', {})
        
        # Extract property details (check root level FIRST, then nested locations)
        address = (
            data.get('address') or  # Check root level first
            custom_data.get('address') or 
            contact_data.get('address1') or 
            data.get('address1')
        )
        
        city = (
            data.get('city') or  # Check root level first
            custom_data.get('city') or 
            contact_data.get('city')
        )
        
        state = (
            data.get('state') or  # Check root level first
            custom_data.get('state') or 
            contact_data.get('state')
        )
        
        zip_code = (
            data.get('zipCode') or  # Check root level first
            data.get('postal_code') or  # Also check postal_code variant
            custom_data.get('zipCode') or 
            contact_data.get('postal_code')
        )

        # Validate required fields
        if not all([address, city, state, zip_code]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: address, city, state, zipCode',
                'receivedData': data,
                'extracted': {
                    'address': address,
                    'city': city,
                    'state': state,
                    'zipCode': zip_code
                }
            }), 400

        
        # Prepare RentCast API request
        rentcast_params = {
            'address': address,
            'city': city,
            'state': state,
            'zipCode': zip_code
        }
        
        headers = {
            'X-Api-Key': RENTCAST_API_KEY
        }
        
        # Call RentCast API to get property value
        rentcast_response = requests.get(
            f'{RENTCAST_BASE_URL}/avm/value',
            params=rentcast_params,
            headers=headers,
            timeout=10
        )
        
        # Check if RentCast API call was successful
        if rentcast_response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'RentCast API error: {rentcast_response.text}'
            }), rentcast_response.status_code
        
        # Parse RentCast response
        rentcast_data = rentcast_response.json()
        
        # Extract the after-repair value
        arv = rentcast_data.get('price', 0)
        confidence_score = rentcast_data.get('confidence', 0)
        
        # Prepare response for Go High Level
        response_data = {
            'success': True,
            'property': {
                'address': address,
                'city': city,
                'state': state,
                'zipCode': zip_code
            },
            'afterRepairValue': arv,
            'confidenceScore': confidence_score,
            'fullData': rentcast_data
        }
        
        print(f"Sending response: {response_data}")
        
        return jsonify(response_data), 200
        
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'RentCast API request timed out'
        }), 504
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Error calling RentCast API: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/test-rentcast', methods=['GET'])
def test_rentcast():
    """Test endpoint to verify RentCast API connection"""
    try:
        headers = {
            'X-Api-Key': RENTCAST_API_KEY
        }
        
        # Test with a sample address
        params = {
            'address': '5500 Grand Lake Drive',
            'city': 'San Antonio',
            'state': 'TX',
            'zipCode': '78244'
        }
        
        response = requests.get(
            f'{RENTCAST_BASE_URL}/avm/value',
            params=params,
            headers=headers,
            timeout=10
        )
        
        return jsonify({
            'success': response.status_code == 200,
            'statusCode': response.status_code,
            'data': response.json() if response.status_code == 200 else response.text
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Check if API key is set
    if not RENTCAST_API_KEY:
        print("WARNING: RENTCAST_API_KEY not found in environment variables!")
    
    # Run the server
    app.run(host='0.0.0.0', port=5000, debug=True)