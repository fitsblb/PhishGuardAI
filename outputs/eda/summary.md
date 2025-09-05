# EDA quick summary
- File: data\raw\phisingData.csv
- Shape: (11055, 31)
- Label: Redirect
- Text cols: []
- Nulls (top 10):
having_IP_Address         0
Submitting_to_email       0
Statistical_report        0
Links_pointing_to_page    0
Google_Index              0
Page_Rank                 0
web_traffic               0
DNSRecord                 0
age_of_domain             0
Iframe                    0
- Duplicate rows: 5206
- Time cols: []


https://www.kaggle.com/datasets/hasibur013/phishing-data

URL: The actual web address.
Label: The classification of the URL (0 for legitimate, 1 for phishing).
Length of URL: The total number of characters in the URL.
Number of Dots: Count of '.' characters in the URL.
Presence of IP Address: Boolean indicating if the URL contains an IP address instead of a domain name.
Number of Subdomains: The count of subdomains in the URL.
Path Length: Length of the path after the domain.
Contains HTTPS: Boolean indicating if the URL uses HTTPS.
Special Characters Count: Count of special characters such as '@', '-', '_', etc.
Top-Level Domain (TLD): The TLD of the URL (e.g., .com, .org).
Alexa Rank: The Alexa traffic rank of the domain.
Domain Age: Age of the domain in days.


https://www.kaggle.com/datasets/ndarvind/phiusiil-phishing-url-dataset

PhiUSIIL Phishing URL Dataset is a substantial dataset comprising 134,850 legitimate and 100,945 phishing URLs. Most of the URLs we analyzed while constructing the dataset are the latest URLs. Features are extracted from the source code of the webpage and URL. Features such as CharContinuationRate, URLTitleMatchScore, URLCharProb, and TLDLegitimateProb are derived from existing features.

Class Labels
Label 1 corresponds to a legitimate URL, label 0 to a phishing URL

Citations:
Prasad, A., & Chandra, S. (2023). PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning. Computers & Security, 103545.
doi: https://doi.org/10.1016/j.cose.2023.103545