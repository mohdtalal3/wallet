import streamlit as st
import requests
import json
import os
from collections import defaultdict
import pandas as pd
st.set_page_config(layout="wide")
def fetch_transactions(base_url, addresses, max_buyers):
    page_size = 40
    address_signers = defaultdict(set)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
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
                    st.error(f"Error: Received status code {response.status_code} for address {address}")
                    break

            except Exception as e:
                st.error(f"Error processing address {address}: {str(e)}")
                break

            if len(valid_transactions) >= max_buyers:
                break

    signer_to_addresses = defaultdict(list)
    for address, signers in address_signers.items():
        for signer in signers:
            signer_to_addresses[signer].append(address)

    return {signer: addresses for signer, addresses in signer_to_addresses.items() if len(addresses) > 1}

def main():
    st.title("Solana Wallet Common Signer Analyzer")
    
    st.markdown("""
    ### Instructions:
    1. Enter wallet addresses (one per line) in the text area below
    2. Specify how many buyers to analyze per coin
    3. Click 'Start Scraping' to analyze common signers
    4. Click on signers to view details and open GMGn.ai analysis
    """)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        wallet_addresses = st.text_area(
            "Enter wallet addresses (one per line):",
            height=200,
            help="Enter each Solana wallet address on a new line"
        )
    
    with col2:
        max_buyers = st.number_input(
            "Buyers to analyze per coin",
            min_value=1,
            max_value=1000,
            value=100,
            help="Specify how many buyers to analyze for each coin"
        )
    
    if st.button("Start Scraping"):
        if wallet_addresses.strip():
            addresses = [addr.strip() for addr in wallet_addresses.split('\n') if addr.strip()]
            
            if len(addresses) > 0:
                st.info(f"Starting analysis for {len(addresses)} wallet addresses, analyzing {max_buyers} buyers per coin...")
                
                base_url = "https://api-v2.solscan.io/v2/account/transaction"
                
                with st.spinner("Analyzing wallet addresses..."):
                    common_signers = fetch_transactions(base_url, addresses, max_buyers)
                
                if common_signers:
                    st.success("Analysis complete!")
                    
                    # Create CSV data for download
                    display_data = []
                    for signer, linked_addresses in common_signers.items():
                        display_data.append({
                            "Signer": signer,
                            "Number of Connected Wallets": len(linked_addresses),
                            "Connected Wallets": ", ".join(linked_addresses)
                        })
                    
                    df = pd.DataFrame(display_data)
                    csv = df.to_csv(index=False)
                    
                    # Download button at the top
                    st.download_button(
                        label="Download results as CSV",
                        data=csv,
                        file_name="common_signers_analysis.csv",
                        mime="text/csv"
                    )
                    
                    # Detailed expandable view
                    st.subheader("Analysis Results")
                    for signer, linked_addresses in common_signers.items():
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
            else:
                st.error("Please enter at least one valid wallet address.")
        else:
            st.error("Please enter wallet addresses before starting the analysis.")

if __name__ == "__main__":
    main()