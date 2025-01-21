import requests
from collections import defaultdict
import time
def fetch_transactions(base_url, addresses, max_buyers, progress_bar, status_text):
    page_size = 40
    address_signers = defaultdict(set)
    
    for idx, address in enumerate(addresses):
        progress = (idx + 1) / len(addresses)
        progress_bar.progress(progress)
        status_text.text(f"Processing address {idx + 1} of {len(addresses)}: {address}")

        transactions = []
        before = None
        valid_transactions = []

        while len(valid_transactions) < max_buyers:
            params = {
                "address": address,
                "page_size": page_size
            }
            if before:
                params["before"] = before

            headers = {
                "accept": "application/json, text/plain, */*",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "referer": "https://solscan.io/",
                "origin": "https://solscan.io"
            }

            try:
                time.sleep(2)
                response = requests.get(base_url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()

                    if data.get("success") and "transactions" in data["data"]:
                        new_transactions = data["data"]["transactions"]

                        for tx in new_transactions:
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
                    else:
                        break
                else:
                    print(f"Error: Received status code {response.status_code} for address {address}")
                    break

            except Exception as e:
                print(f"Error processing address {address}: {str(e)}")
                break

            if len(valid_transactions) >= max_buyers:
                break

    signer_to_addresses = defaultdict(list)
    for address, signers in address_signers.items():
        for signer in signers:
            signer_to_addresses[signer].append(address)

    return {signer: addresses for signer, addresses in signer_to_addresses.items() if len(addresses) > 1}