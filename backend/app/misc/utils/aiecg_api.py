import json

from requests import post

def ecg_ai_model(matrix_data):
    
    url = "http://192.192.91.111:18392"

    ecg_data = {"data" : json.dumps(matrix_data.tolist())}  

    response = post(url+ "/api/v1/standard/inference", json=ecg_data)

    return response.json()

if __name__ == "__main__":

    pass