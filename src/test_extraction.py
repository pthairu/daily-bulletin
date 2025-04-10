import os
import sys
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from readability import Document

def extract_article_content(url):
    """Extract the main article content from a URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Use readability to extract the main content
        doc = Document(response.text)
        title = doc.title()
        content = doc.summary()
        
        # Parse the extracted content with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove unwanted elements that might have been kept
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
            
        # Process images - collect them for later download
        images = []
        for img in soup.find_all('img'):
            if img.get('src'):
                images.append({
                    'src': img.get('src'),
                    'alt': img.get('alt', '')
                })
        
        return {
            'title': title,
            'content': str(soup),
            'images': images,
            'base_url': url
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the article: {e}")
        return None
    except Exception as e:
        print(f"Error extracting article content: {e}")
        return None

def main():
    """Test the article extraction functionality"""
    print("Daily Bulletin - Article Extraction Test")
    print("---------------------------------------")
    
    # Get URL from user
    url = input("Enter article URL: ")
    if not url:
        print("No URL provided. Exiting.")
        return
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print(f"\nFetching article from: {url}")
    
    # Extract article content
    article_data = extract_article_content(url)
    if not article_data:
        print("Failed to extract article content. The page might be behind a paywall or not accessible.")
        return
    
    print(f"\nArticle found: {article_data['title']}")
    print(f"Found {len(article_data['images'])} images in the article")
    
    # Print a sample of the content
    soup = BeautifulSoup(article_data['content'], 'html.parser')
    paragraphs = soup.find_all('p')
    
    print("\nSample content:")
    print("--------------")
    for i, p in enumerate(paragraphs[:3]):  # Print first 3 paragraphs
        print(p.get_text().strip())
        print()
    
    if len(paragraphs) > 3:
        print("...")
    
    # Print image information
    if article_data['images']:
        print("\nImage sources:")
        print("-------------")
        for i, img in enumerate(article_data['images'][:5]):  # Print first 5 images
            print(f"{i+1}. {img['src']}")
        
        if len(article_data['images']) > 5:
            print(f"... and {len(article_data['images']) - 5} more")

if __name__ == "__main__":
    main()
