import streamlit as st
import requests
from collections import defaultdict
import pandas as pd
import scrapy
from scrapy.crawler import CrawlerProcess
from bs4 import BeautifulSoup
import re
import sys
import nest_asyncio
import tempfile

nest_asyncio.apply()
st.set_page_config(layout="wide")

class EtherscanSpider(scrapy.Spider):
    name = 'etherscan_spider'
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': False,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self):
        super(EtherscanSpider, self).__init__()
        self.transactions = defaultdict(list)
        self.processed_count = defaultdict(int)
        self.base_url = "https://etherscan.io/tokentxns"

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(EtherscanSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.addresses = crawler.settings.get('ADDRESSES', [])
        spider.target_transactions = crawler.settings.get('TARGET_TRANSACTIONS', 100)
        spider.progress_bar = crawler.settings.get('PROGRESS_BAR', None)
        spider.status_text = crawler.settings.get('STATUS_TEXT', None)
        return spider

    def start_requests(self):
        for address in self.addresses:
            url = f"{self.base_url}?a={address}&ps=100&p=1"
            yield scrapy.Request(url, callback=self.parse_total_pages, meta={'address': address})

    def parse_total_pages(self, response):
        address = response.meta['address']
        if self.processed_count[address] >= self.target_transactions:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        pagination = soup.find("span", class_="page-link text-nowrap")
        total_pages = 1

        if pagination:
            match = re.search(r"Page \d+ of (\d+)", pagination.text)
            if match:
                total_pages = int(match.group(1))

        if self.status_text:
            self.status_text.text(f"Processing address: {address} - Found {total_pages} pages")

        for page in range(1, total_pages + 1):
            if self.processed_count[address] >= self.target_transactions:
                break
            url = f"{self.base_url}?a={address}&ps=100&p={page}"
            yield scrapy.Request(url, callback=self.parse_page, meta={'address': address})

    def parse_page(self, response):
        address = response.meta['address']
        if self.processed_count[address] >= self.target_transactions:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        
        if not table:
            return

        rows = table.find_all("tr")[1:]
        for row in rows:
            if self.processed_count[address] >= self.target_transactions:
                break

            cols = row.find_all("td")
            if len(cols) > 8:
                txn_link_elem = cols[1].find("a")
                txn_hash = txn_link_elem.text.strip() if txn_link_elem else "N/A"
                txn_link = f"https://etherscan.io{txn_link_elem['href']}" if txn_link_elem else "N/A"
                
                yield scrapy.Request(
                    txn_link,
                    callback=self.parse_transaction,
                    meta={'txn_hash': txn_hash, 'address': address}
                )

    def parse_transaction(self, response):
        address = response.meta['address']
        if self.processed_count[address] >= self.target_transactions:
            return

        txn_hash = response.meta['txn_hash']
        soup = BeautifulSoup(response.text, "html.parser")
        
        from_address_div = soup.find("div", class_="from-address-col")
        if from_address_div:
            from_address = from_address_div.find("a").text.strip()
            
            self.transactions[address].append({
                "tx_hash": txn_hash,
                "from_address": from_address
            })
            self.processed_count[address] += 1
            
            if self.progress_bar:
                total_progress = sum(self.processed_count.values()) / (len(self.addresses) * self.target_transactions)
                self.progress_bar.progress(min(total_progress, 1.0))
                
            if self.status_text:
                self.status_text.text(f"Processed {self.processed_count[address]} transactions for {address}")

def fetch_solana_transactions(base_url, addresses, max_buyers, progress_bar, status_text):
    page_size = 40
    address_signers = defaultdict(set)
    
    for idx, address in enumerate(addresses):
        transactions = []
        before = None
        
        progress = (idx + 1) / len(addresses)
        progress_bar.progress(progress)
        status_text.text(f"Processing address {idx + 1} of {len(addresses)}: {address}")

        headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "referer": "https://solscan.io/",
            "origin": "https://solscan.io"
        }

        valid_transactions = []
        
        while len(valid_transactions) < max_buyers:
            params = {
                "address": address,
                "page_size": page_size
            }
            if before:
                params["before"] = before

            try:
                response = requests.get(base_url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()

                    if not data.get("success") or "transactions" not in data["data"] or not data["data"]["transactions"]:
                        break

                    new_transactions = data["data"]["transactions"]
                    
                    for tx in new_transactions:
                        if len(valid_transactions) >= max_buyers:
                            break
                            
                        is_valid_buy_token = False
                        if "parsedInstruction" in tx:
                            first_instruction = tx["parsedInstruction"][0]
                            if first_instruction.get("type") == "transfer":
                                is_valid_buy_token = True

                        if is_valid_buy_token:
                            valid_transactions.append({
                                "txHash": tx["txHash"],
                                "signer": tx.get("signer", [])
                            })
                            signers = tx.get("signer", [])
                            address_signers[address].update(signers)

                    if new_transactions:
                        before = new_transactions[-1]["txHash"]
                    else:
                        break

            except Exception as e:
                st.error(f"Error processing address {address}: {str(e)}")
                break

    signer_to_addresses = defaultdict(list)
    for address, signers in address_signers.items():
        for signer in signers:
            signer_to_addresses[signer].append(address)

    return {signer: addresses for signer, addresses in signer_to_addresses.items() if len(addresses) > 1}

def main():
    st.title("Blockchain Transaction Analyzer")
    
    blockchain = st.selectbox(
        "Select Blockchain",
        ["Ethereum", "Solana"]
    )
    
    st.markdown("""
    ### Instructions:
    1. Enter wallet addresses (one per line)
    2. Specify number of transactions to analyze
    3. Click 'Start Analysis' to begin
    """)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        wallet_addresses = st.text_area(
            "Enter wallet addresses (one per line):",
            height=200,
            help=f"Enter each {blockchain} wallet address on a new line"
        )
    
    with col2:
        max_transactions = st.number_input(
            "Transactions to analyze per address",
            min_value=1,
            max_value=1000,
            value=100,
            help="Specify how many transactions to analyze for each address"
        )
    
    if st.button("Start Analysis"):
        if wallet_addresses.strip():
            addresses = [addr.strip() for addr in wallet_addresses.split('\n') if addr.strip()]
            
            if len(addresses) > 0:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                if blockchain == "Ethereum":
                    try:
                        with tempfile.NamedTemporaryFile(mode='w+') as tmp:
                            old_stdout = sys.stdout
                            sys.stdout = tmp

                            process = CrawlerProcess({
                                'LOG_ENABLED': False,
                                'COOKIES_ENABLED': False,
                                'ADDRESSES': addresses,
                                'TARGET_TRANSACTIONS': max_transactions,
                                'PROGRESS_BAR': progress_bar,
                                'STATUS_TEXT': status_text
                            })
                            
                            process.crawl(EtherscanSpider)
                            process.start()

                            sys.stdout = old_stdout
                            
                            # Get the spider from the process
                            spider = next(iter(process.crawlers)).spider
                            
                            if spider.transactions:
                                st.success("Analysis complete!")
                                
                                # Create DataFrame
                                display_data = []
                                for address, txns in spider.transactions.items():
                                    for txn in txns:
                                        display_data.append({
                                            "Address": address,
                                            "Transaction Hash": txn['tx_hash'],
                                            "From Address": txn['from_address']
                                        })
                                
                                df = pd.DataFrame(display_data)
                                
                                # Download button
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    label="Download results as CSV",
                                    data=csv,
                                    file_name="ethereum_analysis.csv",
                                    mime="text/csv"
                                )
                                
                                # Display results
                                st.subheader("Analysis Results")
                                st.dataframe(df)
                            else:
                                st.warning("No transactions found for the provided addresses.")
                                
                    except Exception as e:
                        st.error(f"Error during Ethereum analysis: {str(e)}")
                        
                else:  # Solana
                    try:
                        base_url = "https://api-v2.solscan.io/v2/account/transaction"
                        results = fetch_solana_transactions(
                            base_url, 
                            addresses, 
                            max_transactions,
                            progress_bar,
                            status_text
                        )
                        
                        if results:
                            st.success("Analysis complete!")
                            
                            # Create CSV data
                            display_data = []
                            for signer, linked_addresses in results.items():
                                display_data.append({
                                    "Signer": signer,
                                    "Number of Connected Wallets": len(linked_addresses),
                                    "Connected Wallets": ", ".join(linked_addresses)
                                })
                            
                            df = pd.DataFrame(display_data)
                            csv = df.to_csv(index=False)
                            
                            st.download_button(
                                label="Download results as CSV",
                                data=csv,
                                file_name="solana_analysis.csv",
                                mime="text/csv"
                            )
                            
                            st.subheader("Analysis Results")
                            for signer, linked_addresses in results.items():
                                with st.expander(f"Signer: {signer} (Connected to {len(linked_addresses)} wallets)"):
                                    col1, col2 = st.columns([4, 1])
                                    
                                    with col1:
                                        st.write("Connected to the following wallets:")
                                        for idx, addr in enumerate(linked_addresses, 1):
                                            st.code(f"Wallet {idx}: {addr}")
                                    
                                    with col2:
                                        gmgn_url = f"https://gmgn.ai/sol/address/{signer}"
                                        st.markdown(f'''
                                            <a href="{gmgn_url}" target="_blank">
                                                <button style="
                                                    background-color: #4CAF50;
                                                    border: none;
                                                    color: white;
                                                    padding: 10px 20px;
                                                    text-align: center;
                                                    text-decoration: none;
                                                    display: inline-block;
                                                    font-size: 14px;
                                                    margin: 4px 2px;
                                                    cursor: pointer;
                                                    border-radius: 4px;">
                                                    Open in GMGn.ai
                                                </button>
                                            </a>
                                            ''', unsafe_allow_html=True)
                        else:
                            st.warning("No common signers found across the provided addresses.")
                            
                    except Exception as e:
                        st.error(f"Error during Solana analysis: {str(e)}")
            else:
                st.error("Please enter at least one valid wallet address.")
        else:
            st.error("Please enter wallet addresses before starting the analysis.")

if __name__ == "__main__":
    main()