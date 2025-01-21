import streamlit as st
import pandas as pd
from ethereum_utils import scrape_multiple_wallets
from solana_utils import fetch_transactions

st.set_page_config(layout="wide")

def main():
    st.title("Blockchain Wallet Analysis Tool")
    
    st.markdown("""
    ### Instructions:
    1. Select blockchain network (Ethereum or Solana)
    2. Enter wallet addresses (one per line)
    3. Specify number of transactions to analyze
    4. Click 'Start Analysis' to begin
    """)
    
    network = st.selectbox(
        "Select Blockchain Network",
        ["Ethereum", "Solana"]
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        wallet_addresses = st.text_area(
            "Enter wallet addresses (one per line):",
            height=200,
            help="Enter each wallet address on a new line"
        )
    
    with col2:
        max_transactions = st.number_input(
            "Transactions to analyze per wallet",
            min_value=1,
            max_value=10000,
            value=100
        )
    
    if st.button("Start Analysis"):
        if not wallet_addresses.strip():
            st.error("Please enter wallet addresses before starting the analysis.")
            return
            
        addresses = [addr.strip() for addr in wallet_addresses.split('\n') if addr.strip()]
        
        if len(addresses) == 0:
            st.error("Please enter at least one valid wallet address.")
            return
            
        st.info(f"Starting analysis for {len(addresses)} wallet addresses, analyzing {max_transactions} transactions per wallet...")
        
        if network == "Ethereum":
            process_ethereum(addresses, max_transactions)
        else:
            process_solana(addresses, max_transactions)

def process_ethereum(addresses, max_transactions):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner("Analyzing Ethereum wallets..."):
        transactions, common_addresses = scrape_multiple_wallets(addresses, max_transactions, progress_bar, status_text)
        
        if transactions:
            progress_bar.progress(1.0)
            status_text.text("Analysis complete!")
            st.success("Analysis complete!")
            
            display_data = []
            for addr, wallets in common_addresses.items():
                display_data.append({
                    "From Address": addr,
                    "Number of Connected Wallets": len(wallets),
                    "Connected Wallets": ", ".join(wallets)
                })
            
            df = pd.DataFrame(display_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="ethereum_analysis.csv",
                mime="text/csv"
            )
            
            st.subheader("Analysis Results")
            for addr, wallets in common_addresses.items():
                with st.expander(f"From Address: {addr} (Connected to {len(wallets)} wallets)"):
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        st.write("Connected to the following wallets:")
                        for idx, wallet in enumerate(wallets, 1):
                            st.code(f"Wallet {idx}: {wallet}")
                    
                    with col2:
                        etherscan_url = f"https://gmgn.ai/sol/address/{addr}"
                        st.markdown(f'''
                            <a href="{etherscan_url}" target="_blank">
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
                                    Open in Etherscan
                                </button>
                            </a>
                            ''', unsafe_allow_html=True)

def process_solana(addresses, max_transactions):
    progress_bar = st.progress(0)
    status_text = st.empty()
    base_url = "https://api-v2.solscan.io/v2/account/transaction"
    
    with st.spinner("Analyzing Solana wallets..."):
        common_signers = fetch_transactions(base_url, addresses, max_transactions, progress_bar, status_text)
        
        if common_signers:
            progress_bar.progress(1.0)
            status_text.text("Analysis complete!")
            st.success("Analysis complete!")
            
            display_data = []
            for signer, linked_addresses in common_signers.items():
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

if __name__ == "__main__":
    main()