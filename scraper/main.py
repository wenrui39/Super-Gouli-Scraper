from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from markitdown import MarkItDown

app = Flask(__name__)
md = MarkItDown()

def get_clean_markdown(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a real User-Agent to avoid being blocked
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        try:
            # Increase timeout to 30s for heavy sites
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Get raw HTML
            html_content = page.content()
            
            # Use MarkItDown to convert HTML to clean Markdown
            # This handles the "noise" reduction automatically
            result = md.convert_url(url)
            
            return {
                "success": True,
                "url": url,
                "markdown": result.text_content,
                "metadata": {"title": page.title()}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            browser.close()

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    result = get_clean_markdown(url)
    return jsonify(result)

if __name__ == '__main__':
    # Listen on all interfaces so n8n (in Docker or another VM) can reach it
    app.run(host='0.0.0.0', port=5000)