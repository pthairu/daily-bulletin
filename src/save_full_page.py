import os
import re
import sys
import time
import json
import base64
import requests
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def is_medium_url(url):
    """Check if the URL is from Medium"""
    parsed_url = urlparse(url)
    return 'medium.com' in parsed_url.netloc

def handle_medium_verification(driver):
    """Handle Medium's human verification if it appears"""
    try:
        # Check for the verification dialog
        verification_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Verify you're human')]")
        if verification_elements:
            print("Medium human verification detected. Attempting to handle...")
            
            # Try to find and click the checkbox
            try:
                # Wait for the checkbox to be clickable
                checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[@role='checkbox']"))
                )
                checkbox.click()
                print("Clicked verification checkbox")
                time.sleep(3)  # Wait for verification to complete
                
                # Look for and click the continue button if present
                continue_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue')]")
                if continue_buttons:
                    continue_buttons[0].click()
                    print("Clicked continue button")
                    time.sleep(3)
                
                return True
            except Exception as e:
                print(f"Failed to click verification checkbox: {e}")
                return False
    except Exception as e:
        print(f"Error handling Medium verification: {e}")
    
    return True  # Continue if no verification or if verification handling fails

def handle_medium_signin_popup(driver):
    """Handle Medium's sign-in popup if it appears"""
    try:
        # Check for the sign-in popup
        close_buttons = driver.find_elements(By.XPATH, "//button[@aria-label='close']")
        if close_buttons:
            close_buttons[0].click()
            print("Closed Medium sign-in popup")
            time.sleep(1)
            return True
    except Exception as e:
        print(f"Error handling Medium sign-in popup: {e}")
    
    return True  # Continue if no popup or if popup handling fails

def save_page_as_pdf(url, output_path=None, headless=True):
    """
    Save an entire webpage as a PDF file using Chrome.
    
    Args:
        url (str): The URL of the webpage to save.
        output_path (str, optional): The path where the PDF will be saved.
            If not provided, a filename will be generated from the URL.
        headless (bool, optional): Whether to run Chrome in headless mode.
            Set to False if you need to manually interact with the browser.
    
    Returns:
        str: The path to the saved PDF file.
    """
    driver = None
    try:
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        print(f"Fetching page from: {url}")
        
        # Check if it's a Medium URL
        is_medium = is_medium_url(url)
        if is_medium:
            print("Detected Medium article. Using special handling...")
            # For Medium, we might need user interaction, so default to non-headless
            if headless:
                print("Note: For Medium articles, you may need to run with headless=False if verification fails")
        
        # Generate output filename if not provided
        if not output_path:
            # Extract domain and path from URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            
            # Create a filename from the URL path
            path = parsed_url.path.strip('/')
            if not path:
                path = 'index'
            
            # Clean the filename
            filename = f"{domain}-{path}"
            filename = re.sub(r'[^\w\s-]', '', filename).strip().lower()
            filename = re.sub(r'[-\s]+', '-', filename)
            
            # Truncate if too long
            if len(filename) > 100:
                filename = filename[:100]
                
            output_path = f"{filename}.pdf"
        
        print(f"Generating PDF: {output_path}")
        
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")  # Run in headless mode
        chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
        chrome_options.add_argument("--window-size=1920,1080")  # Set window size
        chrome_options.add_argument("--disable-extensions")  # Disable extensions
        chrome_options.add_argument("--disable-dev-shm-usage")  # Disable /dev/shm usage
        chrome_options.add_argument("--no-sandbox")  # Disable sandbox
        
        # Add user agent to appear more like a regular browser
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Add print preferences
        prefs = {
            'printing.print_preview_sticky_settings.appState': json.dumps({
                'recentDestinations': [{
                    'id': 'Save as PDF',
                    'origin': 'local',
                    'account': '',
                }],
                'selectedDestinationId': 'Save as PDF',
                'version': 2,
                'isHeaderFooterEnabled': False,
                'isLandscapeEnabled': False,
                'isCssBackgroundEnabled': True,
                'mediaSize': {'height_microns': 297000, 'width_microns': 210000, 'name': 'ISO_A4'},
            }),
            'savefile.default_directory': os.getcwd(),
            'profile.default_content_setting_values.cookies': 1,  # Allow cookies
            'profile.default_content_setting_values.images': 1,   # Allow images
            'profile.default_content_setting_values.javascript': 1,  # Allow JavaScript
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        # Set up Chrome driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set page load timeout
        driver.set_page_load_timeout(60)  # 60 seconds timeout
        
        # Navigate to the URL
        driver.get(url)
        
        # Wait for the page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Special handling for Medium
        if is_medium:
            # Handle Medium's sign-in popup if it appears
            handle_medium_signin_popup(driver)
            
            # Handle Medium's human verification if it appears
            if not handle_medium_verification(driver):
                print("Warning: Could not handle Medium verification automatically.")
                if headless:
                    print("Try running again with headless=False to manually complete verification.")
                    return None
                else:
                    print("Please complete the verification manually in the browser window.")
                    input("Press Enter when you've completed the verification...")
            
            # Wait longer for Medium content to load
            print("Waiting for Medium content to fully load...")
            time.sleep(10)
            
            # Try to find the article content to confirm it loaded
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
                print("Article content loaded successfully")
            except TimeoutException:
                print("Warning: Could not detect article content. The page might not have loaded properly.")
        
        # Wait for dynamic content to load
        print("Waiting for dynamic content to load...")
        time.sleep(5)
        
        # Scroll to load lazy-loaded content
        print("Scrolling to load all content...")
        scroll_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, scroll_height, 500):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.5)
        
        # Scroll back to top
        driver.execute_script("window.scrollTo(0, 0);")
        
        # Print page to PDF
        print("Generating PDF...")
        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
            'pageSize': 'A4',
            'scale': 1.0,
        }
        
        # Generate PDF
        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        
        # Save PDF to file
        with open(output_path, 'wb') as file:
            file.write(base64.b64decode(pdf['data']))
        
        print(f"\nSuccess! PDF created: {output_path}")
        print(f"Full path: {os.path.abspath(output_path)}")
        
        return output_path
        
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return None
    finally:
        # Close the browser
        if driver:
            driver.quit()

def main():
    """Main function to run the full page PDF generator"""
    print("Daily Bulletin - Full Page PDF Generator")
    print("---------------------------------------")
    
    # Get URL from user
    url = input("Enter article URL: ")
    if not url:
        print("No URL provided. Exiting.")
        return
    
    # Check if it's a Medium URL
    is_medium = is_medium_url(url)
    headless = True
    
    if is_medium:
        print("Medium article detected. You may need to manually complete verification.")
        choice = input("Run in visible browser mode to handle verification manually? (y/n) [y]: ").strip().lower()
        headless = choice != 'y' and choice != ''
    
    # Save the page as PDF
    save_page_as_pdf(url, headless=headless)

if __name__ == "__main__":
    main()
