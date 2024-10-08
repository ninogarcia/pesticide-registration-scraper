import streamlit as st
import pandas as pd
import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CustomCrawler:
    def __init__(self, search_term):
        self.search_term = search_term
        self.base_url = 'https://www.icama.cn/BasicdataSystem/pesticideRegistrationEn/queryselect_en.do'
        self.total_items_scraped = 0
        self.current_page = 1

    async def run(self, progress_callback=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.base_url)
            await self.search_and_submit(page)
            
            all_data = []
            while True:
                items_scraped, page_data = await self.scrape_page(page)
                all_data.extend(page_data)
                self.total_items_scraped += items_scraped
                
                if progress_callback:
                    progress_callback(f"Scraped page {self.current_page}, total items: {self.total_items_scraped}")
                
                if not await self.next_page(page):
                    logging.info("No more pages. Scraping completed.")
                    break
            
            await browser.close()
            logging.info(f"Total items scraped across all pages: {self.total_items_scraped}")
            return all_data

    async def search_and_submit(self, page):
        await page.fill("#searchForm > div.search_table > table > tbody > tr:nth-child(3) > td.t1 > input[type=text]", self.search_term)
        await page.click("#btnSubmit")
        await page.wait_for_load_state('networkidle')

    async def scrape_item(self, page, link_selector):
        try:
            await page.click(link_selector)
            await page.wait_for_selector("#jbox-iframe")
            
            frame = page.frame_locator("#jbox-iframe").first
            
            data = {}
            data['registered_number'] = await self.get_table_data(frame, "Registered number：")
            data['first_prove'] = await self.get_table_data(frame, "FirstProve：")
            data['period'] = await self.get_table_data(frame, "Period：")
            data['product_name'] = await self.get_table_data(frame, "ProductName：")
            data['toxicity'] = await self.get_table_data(frame, "Toxicity：")
            data['formulation'] = await self.get_table_data(frame, "Formulation：")
            data['registration_certificate_holder'] = await self.get_table_data(frame, "Registration certificate holder：")
            data['remark'] = await self.get_table_data(frame, "Remark：")

            active_ingredients = []
            rows = await frame.locator("table:nth-of-type(2) tr").all()
            for row in rows[2:]:
                cols = await row.locator("td").all()
                if len(cols) == 2:
                    ingredient = await cols[0].inner_text()
                    content = await cols[1].inner_text()
                    active_ingredients.append({
                        "ingredient": ingredient.strip(),
                        "content": content.strip()
                    })
            data['active_ingredients'] = active_ingredients
            
            await page.click("#jbox > table > tbody > tr:nth-child(2) > td:nth-child(2) > div > a")
            await page.wait_for_selector("#jbox-iframe", state="hidden")
            
            return data
        except Exception as e:
            logging.error(f"Error scraping item: {str(e)}")
            return None

    async def get_table_data(self, frame, label):
        element = await frame.locator(f"//td[contains(text(), '{label}')]/following-sibling::td").first.inner_text()
        return element.strip()

    async def scrape_page(self, page):
        items_scraped = 0
        page_data = []
        for i in range(2, 22):
            link_selector = f"#tab > tbody > tr:nth-child({i}) > td.t3 > span > a"
            try:
                await page.wait_for_selector(link_selector, timeout=5000)
            except:
                logging.info(f"No more items found after item {i-2}")
                break

            logging.info(f"Scraping item {i-1}")
            data = await self.scrape_item(page, link_selector)
            if data:
                page_data.append(data)
                items_scraped += 1
            else:
                logging.warning(f"Failed to scrape item {i-1}")
        
        logging.info(f"Total items scraped on this page: {items_scraped}")
        return items_scraped, page_data

    async def next_page(self, page):
        try:
            logging.info(f"Attempting to navigate to the next page (current page: {self.current_page})")
            
            # Wait for the pagination element to be visible
            await page.wait_for_selector("body > div.web_ser_body_right_main_search > div", state="visible", timeout=10000)
            
            # Try to find the "下一页" (Next Page) link
            next_page_link = await page.query_selector("a:has-text('下一页'):not(.disabled)")
            
            if not next_page_link:
                logging.info("Next page link is not available or disabled. This is the last page.")
                return False
            
            # Click the next page link
            await next_page_link.click()
            
            # Wait for the page to load
            await page.wait_for_load_state('networkidle')
            
            # Verify that we've moved to the next page
            new_page_indicator = await page.query_selector("body > div.web_ser_body_right_main_search > div > ul > li.active > a")
            if new_page_indicator:
                new_page_num = await new_page_indicator.inner_text()
                new_page_num = int(new_page_num)
                if new_page_num > self.current_page:
                    self.current_page = new_page_num
                    logging.info(f"Successfully moved to page {self.current_page}")
                    return True
                else:
                    logging.warning(f"Page number didn't increase. Still on page {self.current_page}")
                    return False
            else:
                logging.warning("Couldn't verify new page number")
                return False
            
        except Exception as e:
            logging.error(f"Unexpected error in next_page function: {str(e)}")
            return False
async def main(search_term, progress_callback=None):
    crawler = CustomCrawler(search_term)
    return await crawler.run(progress_callback)

st.set_page_config(page_title="Pesticide Registration Data Scraper", layout="wide")

st.title("Pesticide Registration Data Scraper")

st.markdown("Data source: [ICAMA Pesticide Registration Database](https://www.icama.cn/BasicdataSystem/pesticideRegistrationEn/queryselect_en.do)")

st.sidebar.header("Data Scraper by: Niño Garcia")
st.sidebar.subheader("Contact Details:")
st.sidebar.markdown("[LinkedIn](https://www.linkedin.com/in/ninogarci/)")
st.sidebar.markdown("[Upwork](https://www.upwork.com/freelancers/~01dd78612ac234aadd)")

search_term = st.text_input("Enter Active Ingredient Name in English:")

if st.button("Search"):
    if search_term:
        st.info(f"Searching for: {search_term}")
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(message):
            status_text.text(message)
        
        try:
            results = asyncio.run(main(search_term, progress_callback=update_progress))
            
            if results:
                st.success(f"Found {len(results)} results")
                
                display_data = []
                for item in results:
                    active_ingredients = ", ".join([f"{ai['ingredient']} ({ai['content']})" for ai in item['active_ingredients']])
                    display_data.append({
                        "Registered Number": item['registered_number'],
                        "Product Name": item['product_name'],
                        "Active Ingredients": active_ingredients,
                        "Toxicity": item['toxicity'],
                        "Formulation": item['formulation'],
                        "Registration Holder": item['registration_certificate_holder'],
                        "First Prove": item['first_prove'],
                        "Period": item['period'],
                        "Remark": item['remark']
                    })
                
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("No results found.")
        except Exception as e:
            st.error(f"An error occurred during the search: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()
    else:
        st.warning("Please enter a search term.")

st.markdown("---")
st.markdown("Note: This app fetches live data from the ICAMA database. Search times may vary depending on the number of results.")
