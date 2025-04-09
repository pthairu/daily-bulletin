import os
import requests
from dotenv import dotenv_values
from bs4 import BeautifulSoup


config = dotenv_values("../.env")
website = input("Website name: ")

page = requests.get(website)
soup = BeautifulSoup(page.content, "html.parser")







