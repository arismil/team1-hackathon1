import os

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()

model = AzureChatOpenAI(
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
)
