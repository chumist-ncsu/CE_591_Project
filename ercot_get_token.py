import requests
import json


with open('ercot_credentials.json', 'r') as f:
    credentials = json.load(f)
    USERNAME = credentials['ERCOT_USERNAME']
    PASSWORD = credentials['ERCOT_PASSWORD']
    SUBSCRIPTION_KEY = credentials['ERCOT_API_KEY']

# Authorization URL for signing into ERCOT Public API account
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token\
?username={username}\
&password={password}\
&grant_type=password\
&scope=openid+fec253ea-0d06-4272-a5e6-b478baeecd70+offline_access\
&client_id=fec253ea-0d06-4272-a5e6-b478baeecd70\
&response_type=id_token"

# Sign In/Authenticate
auth_response = requests.post(AUTH_URL.format(username = USERNAME, password=PASSWORD))



with open('auth_response.json', 'w') as f:
    print("Saving auth response to auth_response.json")
    json.dump(auth_response.json(), f)