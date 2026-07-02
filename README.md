--
# zero-dollar-etl-pipeline

### Data ETL Pipeline

#### Step 1: Clone & Setup the project

```
git clone https://github.com/parsaloi/zero-dollar-etl-pipeline.git
cd zero-dollar-etl-pipeline
pip install -r requirements.txt
```

--
### GCP Cloud Sync for Data Insights Dashboard

#### Step 2: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and log in with any standard Google account.
2. In the top-left dropdown (next to the Google Cloud logo), click **New Project**.
3. Name it `Data-Eng-Workshop` and click **Create**. (Wait a few seconds for it to finish, then select it from the dropdown).

#### Step 3: Enable the Free APIs

1. In the top search bar, type **Google Sheets API** and hit Enter. Click on it, then click the blue **Enable** button.
2. In the top search bar, type **Google Drive API** and hit Enter. Click on it, then click **Enable**.
*(Why Drive? The Sheets API needs the Drive API to handle file permissions and discoveries).*

#### Step 4: Create the "Robot" User (Service Account)

1. Open the left-hand navigation menu (the hamburger icon) ➔ **IAM & Admin** ➔ **Service Accounts**.
2. Click **+ Create Service Account** at the top.
3. Name it `etl-worker` and click **Create and Continue**.
4. Skip the optional role assignments and click **Done**.

#### Step 5: Generate the Keys

1. You will now see `etl-worker` in the list of Service Accounts. Click on its email address to open it.
2. Go to the **KEYS** tab at the top.
3. Click **Add Key** ➔ **Create new key**.
4. Choose **JSON** and click **Create**.
5. *A file will download to your computer. This is your pipeline's passport.*

#### Step 6: The "Handshake" (Connecting the Sheet)

1. Open a new tab and go to Google Sheets. Create a brand new, blank spreadsheet.
2. Look at the URL of your spreadsheet. Copy the long ID between `/d/` and `/edit`.
3. Open the JSON file you just downloaded in any text editor. Find the line that says `"client_email"` and copy the long email address (it looks like `etl-worker@data-eng-workshop...`).
4. Go back to your Google Sheet, click the big **Share** button in the top right.
5. Paste the Service Account email address, ensure it is set to **Editor**, and click **Send**. *(You just gave your python script permission to write to this specific file).*

#### Step 7: Final Local Configuration

1. Move your downloaded JSON file into the folder you cloned from GitHub.
2. Rename the file to exactly **`credentials.json`**.
3. Open `apex_etl.py` in your code editor.
4. Replace `YOUR_DEMO_SHEET_ID_HERE` with the ID you copied from your Google Sheet's URL. Save the file.

--

#### Step 8: Play time

```
# Create dummy data
python .\setup_demo.py

# Run the ETL pipeline
python apex_etl.py
```


#### 🛠️ Troubleshooting & Common Pitfalls

This project is a real-world Data Engineering pipeline designed to fail gracefully when it encounters common infrastructural or configuration errors. Below are the most common issues encountered during hands-on execution and how to resolve them.

---

##### 1. ❌ [CONFIGURATION ERROR] Default Google Sheet ID detected

**Diagnosis:**
You executed `python apex_etl.py` before replacing the placeholder string with your personal Google Sheet ID.

**The Error Output:**
```
❌ [CONFIGURATION ERROR] Default Google Sheet ID detected.
💡 FIX: Please open 'apex_etl.py', locate 'GOOGLE_SHEET_ID' at the top, and paste the ID...
```

--

Happy Coding!
