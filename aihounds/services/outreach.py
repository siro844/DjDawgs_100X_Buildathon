import requests
from bs4 import BeautifulSoup
# from aihounds.constants.hound import openai_llm
from langchain.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import re
load_dotenv()
from langchain_core.messages import HumanMessage,BaseMessage
from langchain_openai import ChatOpenAI
import os 
from aihounds.constants.prompt import prompt_template,generate_message_prompt
from aihounds.constants.hound import openai_llm,mongo_client

class LinkedinOutreach:
    def __init__(self):
        self.api_key = os.getenv("UNIPILE_API_KEY")
        self.url = "https://api10.unipile.com:14044/api/v1"
        self.mongoose_client=mongo_client


    def get_text(self, url):
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            texts = soup.stripped_strings
            chain = prompt_template | openai_llm
            data=' '.join(texts)
            try:
                persona = chain.invoke({"texts": data})
            except Exception as e:
                print(e)
            print(persona.content)
            return persona.content
        except Exception as e:
            return str(e)

    def extract_profile_identifier(self, linkedin_url):
        regex = r'linkedin\.com\/in\/([a-zA-Z0-9-]+)'
        match = re.search(regex, linkedin_url)
        if match:
            return match.group(1)
        else:
            return None

    def get_provider_id(self, account_id, profile_identifier):
        base_url = f"{self.url}/users"
        url = f"{base_url}/{profile_identifier}?account_id={account_id}"
        headers = {
            "accept": "application/json",
            "X-API-KEY": self.api_key
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            print(data.get('provider_id', "NOT found"))
            return data.get("provider_id", ""), data.get("headline", "")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None
        
    def send_message(self,account_id,provider_id,message):
        try:
            url = f"{self.url}/chats"
            payload = {
                'attendees_ids': (None, provider_id),
                'account_id': (None, account_id),
                'text': (None, message)
            }
            headers = {
                "accept": "application/json",
                "X-API-KEY": self.api_key
            }
            response = requests.post(url, files=payload, headers=headers)
            response.raise_for_status()
            api_data = response.json()
            return api_data
        except Exception as e:
            print(e)
            return None
        
    def generate_and_send_message(self,account_id,user_id,domain,linkedin_url):
        user=self.mongoose_client.read("user",user_id)
        companyId=user.get("companyId")
        company=self.mongoose_client.read("company",companyId)

        persona=self.get_text(domain)
        chain=generate_message_prompt | openai_llm
        message=chain.invoke({"props":company.get('props'),"persona":persona})
        message=message.content
        profile_identifier=self.extract_profile_identifier(linkedin_url)
        provider_id,headline=self.get_provider_id(account_id,profile_identifier)
        print(message)
        return self.send_message(account_id,provider_id,message)
    
    def send_message_to_all(self,account_id,user_id,domain,linkedin_urls):
        try:
            for url in linkedin_urls:
                self.generate_and_send_message(account_id,user_id,domain,url)
            return "Messages sent successfully"
        except Exception as e:
            return e