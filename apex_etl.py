import os
import glob
import datetime
import pandas as pd
from openpyxl import load_workbook
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
DATA_DIR = "apex_retail"
TARGET_EXCEL = "Apex_Master_Ledger.xlsx"
GOOGLE_SHEET_ID = "YOUR_DEMO_SHEET_ID_HERE"
CREDENTIALS_JSON = "credentials.json"

def normalize_branch(name_str):
    """Data Engineering Concept: Normalizing messy, human-entered strings."""
    s = str(name_str).lower()
    if "north" in s: return "North Store"
    if "south" in s: return "South Store"
    if "east" in s: return "East Store"
    return "External"

def extract_and_clean(file_path):
    """Extracts data safely by bypassing human-readable corporate headers."""
    df = pd.read_excel(file_path, header=5, engine='openpyxl')
    df.columns = df.columns.astype(str).str.strip()
    df = df.dropna(how='all')
    return df

def run_pipeline():
    sending_data = []
    receiving_data = []
    branches = {"north": "North Store", "south": "South Store", "east": "East Store"}

    print("⏳ [STAGE 1] Extracting and transforming regional silos...")

    for folder, standard_name in branches.items():
        # 1. Extract Sending Data
        for file in glob.glob(os.path.join(DATA_DIR, folder, "sending", "*.xlsx")):
            if os.path.basename(file).startswith("~$"): continue

            df = extract_and_clean(file)
            df = df[df['Receipt Type'] == 'Sales']

            df['From'] = standard_name
            # --- FIX: Explicitly cast to datetime ---
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Sending#'] = df['Receipt #']
            sending_data.append(df[['From', 'Date', 'Sending#', 'Total']])

        # 2. Extract Receiving Data
        for file in glob.glob(os.path.join(DATA_DIR, folder, "receiving", "*.xlsx")):
            if os.path.basename(file).startswith("~$"): continue

            df = extract_and_clean(file)
            df = df[df['Type'] == 'Receiving']

            df['From_Normalized'] = df['Vendor'].apply(normalize_branch)
            df['To'] = standard_name
            # --- FIX: Explicitly cast to datetime ---
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Receiving#'] = df['Voucher #']
            df['StockTransfer#'] = df['Invoice #']
            receiving_data.append(df[['From_Normalized', 'To', 'Date', 'StockTransfer#', 'Receiving#', 'Total']])

    master_send = pd.concat(sending_data, ignore_index=True) if sending_data else pd.DataFrame()
    master_recv = pd.concat(receiving_data, ignore_index=True) if receiving_data else pd.DataFrame()

    if master_send.empty or master_recv.empty:
        print("❌ No data found to process.")
        return

    print("⏳ [STAGE 2] Reconciling ledger matches (Idempotent Join)...")
    matched = pd.merge(
        master_send, master_recv,
        left_on=['Sending#', 'From'],
        right_on=['StockTransfer#', 'From_Normalized'],
        how='inner'
    )

    # Clean document IDs
    for col in ["Sending#", "StockTransfer#", "Receiving#"]:
        matched[col] = matched[col].astype(str).str.replace(r'\.0$', '', regex=True)

    print("⏳ [STAGE 3] Local Backup: Non-destructive Excel injection...")
    wb = load_workbook(TARGET_EXCEL)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        tab_matches = matched[matched['To'] == sheet_name].copy()

        # Local Idempotency Check
        existing_vouchers = {str(ws.cell(row=r, column=9).value) for r in range(1, ws.max_row + 1)}
        tab_matches = tab_matches[~tab_matches['Receiving#'].isin(existing_vouchers)]

        if tab_matches.empty: continue

        append_row = max((r for r in range(ws.max_row, 0, -1) if ws.cell(row=r, column=1).value), default=3) + 1
        for _, row in tab_matches.iterrows():
            # --- FIX: Safely format dates, falling back to empty string if missing ---
            sent_dt = row['Date_x'].strftime('%Y-%m-%d') if pd.notna(row['Date_x']) else ""
            recv_dt = row['Date_y'].strftime('%Y-%m-%d') if pd.notna(row['Date_y']) else ""

            record = [row['From'], sent_dt, row['Sending#'], "Sending", row['Total_x'],
                      row['To'], recv_dt, row['StockTransfer#'], row['Receiving#'], "Receiving", row['Total_y']]
            for col_idx, val in enumerate(record, start=1):
                ws.cell(row=append_row, column=col_idx, value=val)
            append_row += 1

        print(f"   ✅ Injected {len(tab_matches)} verified transfers into '{sheet_name}'.")
    wb.save(TARGET_EXCEL)

    print("⏳ [STAGE 4] Cloud Sync: Pushing data to Google Sheets APIs...")
    # Authenticate with GCP
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(CREDENTIALS_JSON, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    for sheet_name in branches.values():
        cloud_matches = matched[matched['To'] == sheet_name].copy()

        # Create sheet if missing
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols=15)
            worksheet.update('A1:K3', [["Apex Corporate Ledger"], ["Sending Info", "", "", "", "", "Receiving Info"], ['From', 'SentOn', 'Sending#', 'OperationType', 'AmountSent', 'To', 'ReceivedOn', 'StockTransfer#', 'Receiving #', 'OperationType', 'AmountReceived']])

        # Cloud Idempotency Check
        gs_data = worksheet.get_all_values()
        cloud_existing_vouchers = {str(row[8]).split('.')[0].strip() for row in gs_data[3:] if len(row) > 8}
        cloud_matches = cloud_matches[~cloud_matches['Receiving#'].isin(cloud_existing_vouchers)]

        if cloud_matches.empty:
            print(f"   📊 Cloud '{sheet_name}' is up to date.")
            continue

        # Format payload for cloud JSON serialization
        records_to_append = cloud_matches[['From', 'Date_x', 'Sending#', 'Total_x', 'To', 'Date_y', 'StockTransfer#', 'Receiving#', 'Total_y']].copy()
        records_to_append.insert(3, 'Op1', 'Sending')
        records_to_append.insert(9, 'Op2', 'Receiving')

        # Catch-All Date Converter for API safety
        records_to_append = records_to_append.map(lambda x: str(x) if isinstance(x, (datetime.datetime, datetime.date, pd.Timestamp)) else x).fillna("")

        payload = records_to_append.values.tolist()
        worksheet.append_rows(payload, value_input_option='USER_ENTERED')
        print(f"   🚀 Synced {len(payload)} verified transfers to Google Sheets -> '{sheet_name}'.")

    print("🏁 Pipeline execution complete! Zero-dollar data stack fully synchronized.")

if __name__ == "__main__":
    run_pipeline()
