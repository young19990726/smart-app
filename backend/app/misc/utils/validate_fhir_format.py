import os
import sys

from dotenv import load_dotenv
from requests import post, RequestException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.middleware.exception import exception_message


env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..', 'configs', '.env'))
load_dotenv(dotenv_path=env_path)


def get_validate_token():

    # get validate token from FHIR server (example url)
    url = "http://172.18.0.58:8080/realms/mitw/protocol/openid-connect/token"

    # example payload
    payload = {
        'grant_type': 'client_credentials',
        'client_id': os.environ.get('client_id'),
        'client_secret': os.environ.get('client_secret')
    }
    
    try:
        response = post(url, data=payload, timeout=30)
        response.raise_for_status()
        token_data = response.json()

        if 'access_token' in token_data:
            return token_data['access_token']
        else:
            raise ValueError("Response does not contain 'access_token'")
    
    except RequestException as e:
        raise RuntimeError(f"Failed to get validate token: {exception_message(e)}") 
    
    except ValueError as e:
        raise RuntimeError(f"Invalid token response: {exception_message(e)}") 

def validate_fhir_format(file_data):
    
    # validate observation format by FHIR server (example url)
    url = "http://172.18.0.53:10004/fhir/Observation"

    try:
        # get validate token
        sJWT = get_validate_token()
        if not sJWT:
            raise RuntimeError("Failed to obtain a valid JWT token.")

        headers = {
            "Content-Type": "application/fhir+json",
            "Authorization": f"Bearer {sJWT}"
        }

        response = post(url, json=file_data, headers=headers)
        if response.status_code == 201:
            print("Observation sent successfully")
            return True
        else:
            print("Validation failed:", response.text)
            return False
    
    except RequestException as e:
        print(f"Request failed: {exception_message(e)}")
        return False
    
    except RuntimeError as e:
        print(f"Runtime error: {exception_message(e)}")
        return False
    
    except ValueError as e:
        print(f"Error parsing JSON response: {exception_message(e)}")
        return False

if __name__ == "__main__":
    pass