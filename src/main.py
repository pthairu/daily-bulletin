import os
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI

load_dotenv()

client = OpenAI()

website = input("Website name: ")

page = requests.get(website)
soup = BeautifulSoup(page.content, "html.parser")

removed_tags = soup.find_all(lambda tag: tag.name in ['style','script', 'img', 'path'])

for tag in removed_tags:
    tag.decompose()

text_only = soup.get_text()

response = client.responses.create(
    model="gpt-4o",
    instructions="I am going to pass you text from an articles website that I cleaned a little using beautiful soup. Return only the article content and title in a clean format, clean any remaining html or anything else that doesn't belong. If the article seems to be locked behind a login report that the content can't be accessed.",
    input=text_only
)

print(response.output_text)







