import base64
import os
import sys

from requests import post, exceptions

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from middleware.exception import exception_message


def upload_fhir_ecg_to_ai(file_path: str, headers: dict = None) -> dict:
    try:
        url = "http://127.0.0.1:8000/api/v1/SMART-ECG"
        # url = "http://0.0.0.0:5433/api/v1/SMART-ECG"

        # 預設 headers
        default_headers = {}
        
        # 如果傳入了 headers，則更新預設 headers
        if headers:
            default_headers.update(headers)

        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/json')}

            response = post(url, files=files, headers=default_headers)
            
            if response.status_code == 200 and response.headers.get("Content-Type") == "application/json":
                print("Upload FHIR ECG file successfully")
                response_data = response.json()
                return { 
                    "success": True,
                    "file_name": response_data.get('file_name'),
                    "file_path": response_data.get('file_path'),
                    "fig_path": response_data.get('fig_path'),
                    # "result": response_data.get('result'),  
                }
            else:
                print("Failed to upload FHIR ECG file")
                return {
                    "success": False,
                    "error": f"API response is not json format: {response.text}"
                }
    except RequestException as e:
        return {
            "success": False,
            "error": f"API call failed: {exception_message(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"An error occurred while processing the FHIR file: {exception_message(e)}"
        }
    
# def upload_fhir_ecg_to_ai(file_path: str) -> dict:
#     try:
#         url = "http://127.0.0.1:8000/api/v1/SMART-ECG"
#         # url = "http://0.0.0.0:5433/api/v1/SMART-ECG"

#         with open(file_path, 'rb') as f:
#             files = {'file': (os.path.basename(file_path), f, 'application/json')}

#             response = post(url, files=files)
#             if response.status_code == 200 and response.headers.get("Content-Type") == "application/json":
#                 print("Upload FHIR ECG file successfully")
#                 response_data = response.json()
#                 return { 
#                     "success": True,
#                     "file_name": response_data.get('file_name'),
#                     "file_path": response_data.get('file_path'),
#                     "fig_path": response_data.get('fig_path'),
#                     # "result": response_data.get('result'),  
#                 }
#             else:
#                 print("Failed to upload FHIR ECG file")
#                 return {
#                     "success": False,
#                     "error": f"API response is not json format: {response.text}"
#                 }
#     except RequestException as e:
#         return {
#             "success": False,
#             "error": f"API call failed: {exception_message(e)}"
#         }
#     except Exception as e:
#         return {
#             "success": False,
#             "error": f"An error occurred while processing the FHIR file: {exception_message(e)}"
#         }

if __name__ == "__main__":

    response = upload_fhir_ecg_to_ai("/home/young19990726/Project/smart-app/backend/app/misc/utils/file/test.json")
    print(response)
    pass