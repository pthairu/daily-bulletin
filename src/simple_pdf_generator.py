import os
import sys
import re
import requests
import tempfile
import uuid
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from readability import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from PIL import Image as PILImage
from io import BytesIO

# Check if we have the required lxml_html_clean package
try:
    import lxml_html_clean
except ImportError:
    print("Warning: lxml_html_clean package not found. Installing it now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lxml_html_clean"])
    print("lxml_html_clean package installed successfully.")

def download_image(img_url, base_url):
    """Download an image and return a PIL Image object"""
    try:
        # Handle relative URLs
        if not bool(urlparse(img_url).netloc):
            img_url = urljoin(base_url, img_url)
        
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            return PILImage.open(BytesIO(response.content))
        return None
    except Exception as e:
        print(f"Error downloading image {img_url}: {e}")
        return None

def extract_article_content(url):
    """Extract the main article content from a URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Get the original HTML to extract images and content
        original_soup = BeautifulSoup(response.text, 'html.parser')
        original_images = []
        
        # Find all images in the original HTML
        for img in original_soup.find_all('img'):
            if img.get('src'):
                # Filter out tiny images, icons, and tracking pixels
                if img.get('width') and img.get('height'):
                    try:
                        width = int(img['width'])
                        height = int(img['height'])
                        if width < 50 or height < 50:
                            continue
                    except (ValueError, TypeError):
                        pass
                
                # Store the image URL
                img_url = img.get('src')
                if img_url and not img_url.startswith('data:'):  # Skip data URLs
                    original_images.append(img_url)
        
        # Use readability to extract the main content
        doc = Document(response.text)
        title = doc.title()
        content = doc.summary()
        
        # Parse the extracted content with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove unwanted elements that might have been kept
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Check if the extracted content seems incomplete
        # If the content is too short, try to extract it directly from the original HTML
        if len(soup.get_text().strip()) < 500:  # Arbitrary threshold for "too short"
            print("Readability extraction seems incomplete. Trying alternative extraction...")
            
            # Try to find the article content in the original HTML
            # Look for common article container elements
            article_containers = original_soup.select('article, .article, .post, .content, .post-content, [role="main"]')
            
            if article_containers:
                # Use the first container found
                article_container = article_containers[0]
                
                # Remove unwanted elements from the container
                for tag in article_container.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', '.ad', '.advertisement', '.social-share', '.related-posts']):
                    tag.decompose()
                
                # Replace the soup with the article container
                soup = BeautifulSoup(str(article_container), 'html.parser')
                print("Alternative extraction successful.")
            else:
                print("Could not find article container. Using original extraction.")
        
        # Process images - collect them for later download
        images = []
        
        # First, process images found in the extracted content
        for img in soup.find_all('img'):
            if img.get('src'):
                # Store image source and its position in the document
                img_id = str(uuid.uuid4())
                img['data-img-id'] = img_id
                images.append({
                    'id': img_id,
                    'src': img.get('src'),
                    'alt': img.get('alt', '')
                })
        
        # If we didn't find any images, try to add the original images
        if not images and original_images:
            print(f"No images found in extracted content. Adding {len(original_images)} images from original HTML.")
            
            # Create image elements and add them to the soup at appropriate positions
            paragraphs = soup.find_all('p')
            if paragraphs:
                # Add an image after every few paragraphs
                img_index = 0
                for i, p in enumerate(paragraphs):
                    if i > 0 and i % 3 == 0 and img_index < len(original_images):
                        img_id = str(uuid.uuid4())
                        img_tag = soup.new_tag('img')
                        img_tag['src'] = original_images[img_index]
                        img_tag['data-img-id'] = img_id
                        p.insert_after(img_tag)
                        
                        images.append({
                            'id': img_id,
                            'src': original_images[img_index],
                            'alt': ''
                        })
                        
                        img_index += 1
        
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

def create_pdf(article_data, output_path):
    """Create a PDF from the article data without using AI for cleaning"""
    try:
        if not article_data:
            return False
            
        # Create a temporary directory for downloaded images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download images
            image_files = {}
            for img in article_data['images']:
                img_obj = download_image(img['src'], article_data['base_url'])
                if img_obj:
                    # Convert RGBA images to RGB for JPEG compatibility
                    if img_obj.mode == 'RGBA':
                        rgb_img = PILImage.new('RGB', img_obj.size, (255, 255, 255))
                        rgb_img.paste(img_obj, mask=img_obj.split()[3])  # Use alpha channel as mask
                        img_obj = rgb_img
                    elif img_obj.mode != 'RGB':
                        img_obj = img_obj.convert('RGB')
                        
                    img_path = os.path.join(temp_dir, f"{img['id']}.jpg")
                    img_obj.save(img_path)
                    image_files[img['id']] = img_path
            
            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=letter,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=72)
            
            # Define styles
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading1_style = styles['Heading1']
            heading2_style = styles['Heading2']
            heading3_style = styles['Heading3']
            normal_style = styles['Normal']
            code_style = ParagraphStyle(
                'Code',
                parent=styles['Normal'],
                fontName='Courier',
                fontSize=9,
                leading=11,
                leftIndent=20,
                rightIndent=20
            )
            
            # Create content elements
            elements = []
            
            # Add title
            elements.append(Paragraph(article_data['title'], title_style))
            elements.append(Spacer(1, 0.25 * inch))
            
            # Parse the content
            soup = BeautifulSoup(article_data['content'], 'html.parser')
            
            # Process all elements recursively
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'img', 'pre', 'code', 'ul', 'ol', 'li', 'div']):
                if element.name in ['h1']:
                    elements.append(Paragraph(element.get_text().strip(), title_style))
                    elements.append(Spacer(1, 0.25 * inch))
                elif element.name in ['h2']:
                    elements.append(Paragraph(element.get_text().strip(), heading1_style))
                    elements.append(Spacer(1, 0.15 * inch))
                elif element.name in ['h3', 'h4', 'h5', 'h6']:
                    elements.append(Paragraph(element.get_text().strip(), heading2_style))
                    elements.append(Spacer(1, 0.1 * inch))
                elif element.name == 'p':
                    text = element.get_text().strip()
                    if text:  # Only add non-empty paragraphs
                        elements.append(Paragraph(text, normal_style))
                        elements.append(Spacer(1, 0.1 * inch))
                elif element.name == 'pre' or element.name == 'code':
                    text = element.get_text().strip()
                    if text:
                        elements.append(Paragraph(text, code_style))
                        elements.append(Spacer(1, 0.1 * inch))
                elif element.name == 'ul' or element.name == 'ol':
                    # Skip lists that will be processed through their list items
                    continue
                elif element.name == 'li':
                    text = element.get_text().strip()
                    if text:
                        elements.append(Paragraph(f"• {text}", normal_style))
                        elements.append(Spacer(1, 0.05 * inch))
                elif element.name == 'div':
                    # Only process divs that have direct text content
                    if element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'img', 'pre', 'code', 'ul', 'ol', 'li']):
                        # Skip divs that contain other elements we're already processing
                        continue
                    
                    text = element.get_text().strip()
                    if text:
                        elements.append(Paragraph(text, normal_style))
                        elements.append(Spacer(1, 0.1 * inch))
                elif element.name == 'img':
                    img_id = element.get('data-img-id')
                    if img_id and img_id in image_files:
                        img = Image(image_files[img_id])
                        # Scale image to fit page width
                        max_width = 6 * inch  # 6 inches max width
                        if img.drawWidth > max_width:
                            ratio = max_width / img.drawWidth
                            img.drawWidth = max_width
                            img.drawHeight *= ratio
                        elements.append(img)
                        elements.append(Spacer(1, 0.1 * inch))
            
            # Build the PDF
            doc.build(elements)
            
            return True
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return False

def main():
    """Main function to run the simple PDF generator"""
    print("Daily Bulletin - Simple PDF Generator")
    print("------------------------------------")
    
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
    
    print(f"Article found: {article_data['title']}")
    print(f"Found {len(article_data['images'])} images in the article")
    
    # Generate output filename from article title
    title_slug = re.sub(r'[^\w\s-]', '', article_data['title']).strip().lower()
    title_slug = re.sub(r'[-\s]+', '-', title_slug)
    output_file = f"{title_slug}.pdf"
    
    # Create PDF
    print(f"\nGenerating PDF: {output_file}")
    success = create_pdf(article_data, output_file)
    
    if success:
        print(f"\nSuccess! PDF created: {output_file}")
        print(f"Full path: {os.path.abspath(output_file)}")
    else:
        print("\nFailed to create PDF. Please check the errors above.")

if __name__ == "__main__":
    main()
