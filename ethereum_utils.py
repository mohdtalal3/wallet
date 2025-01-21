import requests
from bs4 import BeautifulSoup
import re
import time
from collections import defaultdict
import string
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def update_progress(progress_bar, status_text, current, total, message):
    progress = float(current) / float(total)
    progress_bar.progress(progress)
    status_text.text(message)

def get_total_pages(address):
    url = f"https://etherscan.io/tokentxns?a={address}&ps=100&p=1"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"❌ Failed to fetch total pages for {address}.")
        return 1

    soup = BeautifulSoup(response.text, "html.parser")
    pagination = soup.find("span", class_="page-link text-nowrap")

    if pagination:
        match = re.search(r"Page \d+ of (\d+)", pagination.text)
        if match:
            return int(match.group(1))

    return 1

def scrape_transactions_for_wallet(address, max_transactions, progress_bar, status_text):
    total_pages = get_total_pages(address)
    update_progress(progress_bar, status_text, 0, total_pages, 
                   f"🔍 {address}: Found {total_pages} pages")

    transactions = []
    unique_from_addresses = set()
    fetched_transactions = 0

    for page in range(total_pages, 0, -1):
        if fetched_transactions >= max_transactions:
            break

        update_progress(progress_bar, status_text, total_pages - page + 1, total_pages,
                       f"📄 Scraping Page {page} for {address}...")

        url = f"https://etherscan.io/tokentxns?a={address}&ps=100&p={page}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            print(f"⚠ Failed to fetch page {page} for {address}. Skipping.")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")

        if not table:
            print(f"⚠ No transaction table found on page {page}.")
            continue

        rows = table.find_all("tr")[1:]

        for row in rows:
            if fetched_transactions >= max_transactions:
                break

            cols = row.find_all("td")
            if len(cols) < 9:
                continue

            txn_link_elem = cols[1].find("a")
            txn_hash = txn_link_elem.text.strip() if txn_link_elem else "N/A"
            txn_link = f"https://etherscan.io{txn_link_elem['href']}" if txn_link_elem else "N/A"

            in_out_status_elem = cols[8].find("span")
            in_out_status = in_out_status_elem.text.strip() if in_out_status_elem else "N/A"

            # if in_out_status.upper() != "IN":
            #     continue

            # from_addr_elem = soup.find("a", attrs={"data-highlight-target": True})
            # from_address = from_addr_elem["data-highlight-target"] if from_addr_elem else "N/A"
            from_addr_elem = cols[7].find("a")
            from_address = from_addr_elem["href"].split("/")[-1] if from_addr_elem else "N/A"
            from_address = from_address.replace("#tokentxns", "")
            if from_address in unique_from_addresses:
                continue
            unique_from_addresses.add(from_address)

            method_elem = cols[6].find("span")
            method = method_elem.text.strip() if method_elem else "N/A"
            if method.lower() == "execute":
                continue

            transactions.append({
                "Wallet Address": address,
                "Txn Hash": txn_hash,
                "Txn Link": txn_link,
                "Status": in_out_status,
                "From Address": from_address,
                "Method": method
            })

            fetched_transactions += 1

        time.sleep(3)

    return transactions

def scrape_multiple_wallets(wallet_addresses, max_transactions, progress_bar, status_text):
    wallet_from_addresses = defaultdict(set)
    all_transactions = []

    for idx, wallet in enumerate(wallet_addresses):
        update_progress(progress_bar, status_text, idx + 1, len(wallet_addresses),
                        f"Processing wallet {idx + 1} of {len(wallet_addresses)}: {wallet}")
        
        wallet_transactions = scrape_transactions_for_wallet(wallet, max_transactions, progress_bar, status_text)
        all_transactions.extend(wallet_transactions)

        for txn in wallet_transactions:
            wallet_from_addresses[txn["From Address"]].add(wallet)

    # Filter common_from_addresses
    common_from_addresses = {addr: wallets for addr, wallets in wallet_from_addresses.items() if len(wallets) > 1}

    # Drop the first row from common_from_addresses
    if common_from_addresses:
        common_from_addresses = dict(list(common_from_addresses.items())[1:])

    return all_transactions, common_from_addresses
