import os
import streamlit as st
import sys
import requests
from PIL import Image

# 確保可以導入後端模組
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'app')))

from services.api import upload_fhir_ecg_to_ai
# streamlit run app.py

def login(username, password):
    """
    使用 OAuth 2.0 進行登入驗證
    """
    try:
        # 發送登入請求到您的 token 端點
        token_url = "http://127.0.0.1:8000/api/v1/SMART-ECG/token"
        response = requests.post(
            token_url, 
            data={
                "username": username, 
                "password": password,
                "grant_type": "password"
            }
        )
        
        # 檢查登入是否成功
        if response.status_code == 200:
            token_data = response.json()
            return {
                "success": True, 
                "access_token": token_data['access_token'],
                "token_type": token_data['token_type']
            }
        else:
            return {
                "success": False, 
                "message": "Invalid credentials"
            }
    except Exception as e:
        return {
            "success": False, 
            "message": str(e)
        }

def main():
    st.title("Tri-Service General Hospital AI ECG Analyzer")

    # 檢查是否已經登入
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # 登入邏輯
    if not st.session_state.logged_in:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            login_result = login(username, password)
            
            if login_result['success']:
                st.session_state.logged_in = True
                st.session_state.access_token = login_result['access_token']
                st.session_state.token_type = login_result['token_type']
                st.session_state.username = username  # 儲存登入的 username
                st.rerun()
            else:
                st.error(login_result['message'])
    
    # 登入後的主介面
    if st.session_state.logged_in:
        # 顯示登入的 username
        st.sidebar.header(f"Welcome, {st.session_state.username}")
        
        # 添加登出按鈕
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.access_token = None
            st.session_state.token_type = None
            st.session_state.username = None  # 清除登入的 username
            st.rerun()

        st.sidebar.header("Operation options")
        file_uploaded = st.sidebar.file_uploader("Upload FHIR file (JSON format)", type=["json"])
        submit_button = st.sidebar.button("Submit")

        # 創建一個佔位符來動態更新內容
        result_placeholder = st.empty()

        if submit_button:
            if file_uploaded is None:
                result_placeholder.error("Please upload the file first!")
            else:
                # 使用更安全的臨時文件路徑
                temp_dir = "temp"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, file_uploaded.name)
                
                try:
                    # 保存文件
                    with open(temp_path, "wb") as f:
                        f.write(file_uploaded.getbuffer())

                    # 清空之前的內容並顯示處理中消息
                    result_placeholder.info("Processing file, please wait...")

                    # 調用 API，傳遞 access token
                    headers = {
                        "Authorization": f"{st.session_state.token_type} {st.session_state.access_token}"
                    }
                    
                    # 修改您的 upload_fhir_ecg_to_ai 函數以支持傳遞 headers
                    result = upload_fhir_ecg_to_ai(temp_path, headers=headers)

                    if not result.get("success", False):
                        # 處理失敗
                        result_placeholder.error(f"File processing failed: {result.get('message', 'Unknown error')}")
                    else:
                        # 清空所有內容並重新渲染
                        result_placeholder.empty()
                        
                        # 重新創建結果顯示
                        st.success("File processing successful!")
                        
                        # 顯示 AI 預測結果
                        st.subheader("AI ECG Prediction Results")
                        st.write(result.get("file_name", "No file name provided"))
                        st.json(result.get("result", {}))

                        # 顯示圖像
                        image_path = result.get("fig_path")
                        if image_path and os.path.exists(image_path):
                            image = Image.open(image_path)
                            st.image(image, caption="ECG Plot", use_container_width =True)
                        else:
                            st.warning("No image results found")
                
                except Exception as e:
                    result_placeholder.error(f"An error occurred: {str(e)}")
                
                finally:
                    # 可選：處理完成後刪除臨時文件
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

if __name__ == "__main__":
    main()
