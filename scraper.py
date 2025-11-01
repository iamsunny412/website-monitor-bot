import os
import asyncio
import json
from playwright.async_api import async_playwright
import requests
import html

async def scrape_wurk_jobs():
    """Scrape job listings from wurk.fun"""
    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to the page
            print("Navigating to wurk.fun...")
            await page.goto("https://wurk.fun/custom-jobs", wait_until="networkidle", timeout=30000)
            
            # Wait for the page to load
            await page.wait_for_timeout(3000)
            
            # Click the "New" toggle button
            print("Clicking 'New' toggle button...")
            toggle_btn = await page.wait_for_selector(".toggle-btn:has-text('New')", timeout=10000)
            await toggle_btn.click()
            
            # Wait for content to update after clicking
            await page.wait_for_timeout(2000)
            
            # Wait for job cards to load
            await page.wait_for_selector(".custom-job-card", timeout=10000)
            
            # Get all job cards
            job_cards = await page.query_selector_all(".custom-job-card")
            print(f"Found {len(job_cards)} job cards")
            
            jobs_data = []
            
            for idx, card in enumerate(job_cards, 1):
                try:
                    # Extract creator name
                    creator_elem = await card.query_selector(".creator-name")
                    creator_name = await creator_elem.inner_text() if creator_elem else "Unknown"
                    
                    # Extract time left
                    timing_elem = await card.query_selector(".stat-timing")
                    time_left = "N/A"
                    if timing_elem:
                        timing_text = await timing_elem.inner_text()
                        # Extract just the time part (e.g., "22h 35m left")
                        time_left = timing_text.strip()
                    
                    print(f"Job {idx}: Creator={creator_name}, Time Left={time_left}")
                    
                    # Extract reward amounts (both USD and SOL)
                    reward_primary = await card.query_selector(".reward-primary")
                    reward_secondary = await card.query_selector(".reward-secondary")
                    
                    reward_text = ""
                    if reward_primary:
                        usd_symbol = await reward_primary.query_selector(".reward-usd-symbol")
                        usd_value = await reward_primary.query_selector(".reward-usd-value")
                        usd_label = await reward_primary.query_selector(".reward-usd-label")
                        
                        if usd_symbol and usd_value and usd_label:
                            usd_s = await usd_symbol.inner_text()
                            usd_v = await usd_value.inner_text()
                            usd_l = await usd_label.inner_text()
                            reward_text = f"{usd_s}{usd_v} {usd_l}"
                    
                    if reward_secondary:
                        sol_value = await reward_secondary.query_selector(".reward-sol-value")
                        sol_label = await reward_secondary.query_selector(".reward-sol-label")
                        
                        if sol_value and sol_label:
                            sol_v = await sol_value.inner_text()
                            sol_l = await sol_label.inner_text()
                            if reward_text:
                                reward_text += f" ({sol_v} {sol_l})"
                            else:
                                reward_text = f"{sol_v} {sol_l}"
                    
                    if not reward_text:
                        reward_text = "N/A"
                    
                    # Extract description
                    desc_elem = await card.query_selector(".description-text")
                    description = await desc_elem.inner_text() if desc_elem else "No description"
                    
                    # Clean up the description (remove extra whitespace, truncate if too long)
                    description = " ".join(description.split())
                    if len(description) > 200:
                        description = description[:197] + "..."
                    
                    jobs_data.append({
                        "creator": creator_name.strip(),
                        "time_left": time_left,
                        "reward": reward_text.strip(),
                        "description": description.strip()
                    })
                    
                except Exception as e:
                    print(f"Error extracting data from job card {idx}: {e}")
                    continue
            
            await browser.close()
            return jobs_data
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            await browser.close()
            return []

def get_job_signature(job):
    """Create a unique signature for a job (excluding time_left)"""
    return f"{job['creator']}|{job['reward']}|{job['description']}"

def load_previous_jobs():
    """Load previously seen jobs from file"""
    try:
        if os.path.exists('previous_jobs.json'):
            with open('previous_jobs.json', 'r') as f:
                data = json.load(f)
                return set(data.get('signatures', []))
        return set()
    except Exception as e:
        print(f"Error loading previous jobs: {e}")
        return set()

def save_current_jobs(jobs_data):
    """Save current jobs to file"""
    try:
        signatures = [get_job_signature(job) for job in jobs_data]
        with open('previous_jobs.json', 'w') as f:
            json.dump({'signatures': signatures}, f)
        print(f"Saved {len(signatures)} job signatures")
    except Exception as e:
        print(f"Error saving jobs: {e}")

def find_new_jobs(current_jobs, previous_signatures):
    """Find jobs that weren't in the previous run"""
    new_jobs = []
    for job in current_jobs:
        signature = get_job_signature(job)
        if signature not in previous_signatures:
            new_jobs.append(job)
    return new_jobs
    """Send formatted job listings to Telegram"""
    if not jobs_data:
        message = "No new jobs found at this time."
    else:
        # Build message with HTML formatting (cleaner and more reliable)
        message_parts = ["🆕 <b>WURK Custom Jobs Update</b> 🆕\n"]
        message_parts.append(f"Found {len(jobs_data)} new job(s)\n")
        message_parts.append("━━━━━━━━━━━━━━━━━━━━\n")
        
        for idx, job in enumerate(jobs_data, 1):
            # HTML escape special characters
            creator = html.escape(job['creator'])
            reward = html.escape(job['reward'])
            description = html.escape(job['description'])
            
            message_parts.append(f"\n<b>Job #{idx}</b>\n")
            message_parts.append(f"👤 <b>Creator:</b> {creator}\n")
            message_parts.append(f"💰 <b>Reward:</b> {reward}\n")
            message_parts.append(f"📝 <b>About:</b> {description}\n")
            
            if idx < len(jobs_data):
                message_parts.append("━━━━━━━━━━━━━━━━━━━━\n")
        
        message = "".join(message_parts)
    
    # Send message via Telegram API
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Message sent successfully to Telegram!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to Telegram: {e}")
        print(f"Response: {response.text if 'response' in locals() else 'No response'}")
        
        # Fallback: try sending without formatting
        try:
            print("Retrying without formatting...")
            # Remove HTML tags
            plain_message = message.replace('<b>', '').replace('</b>', '')
            payload = {
                "chat_id": chat_id,
                "text": plain_message
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("Message sent successfully (plain text)!")
            return True
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            return False

async def main():
    """Main function"""
    # Get Telegram credentials from environment variables
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set as environment variables")
        return
    
    print("Starting WURK job scraper...")
    
    # Load previous jobs
    previous_signatures = load_previous_jobs()
    print(f"Loaded {len(previous_signatures)} previously seen jobs")
    
    # Scrape jobs
    current_jobs = await scrape_wurk_jobs()
    print(f"Scraped {len(current_jobs)} total jobs")
    
    # Find new jobs
    new_jobs = find_new_jobs(current_jobs, previous_signatures)
    print(f"Found {len(new_jobs)} NEW jobs")
    
    # Send to Telegram only if there are new jobs
    if new_jobs:
        print(f"\nNew jobs to send:")
        for i, job in enumerate(new_jobs, 1):
            print(f"  Job {i}: Creator={job['creator']}, Time Left={job['time_left']}, Reward={job['reward']}")
        send_telegram_message(bot_token, chat_id, new_jobs)
    else:
        print("No new jobs to report - skipping Telegram notification")
    
    # Save current jobs for next run
    save_current_jobs(current_jobs)

if __name__ == "__main__":
    asyncio.run(main())
