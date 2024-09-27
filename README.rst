YouTube Uploader
================

`youtube_uploader.py` is a Python script for uploading videos to YouTube, with automatic organization into playlists based on your directory structure.

This script offers several key features:

1. It preserves the layout of your videos directory by organizing uploaded videos into playlists.
2. It can be safely interrupted and restarted without making duplicate uploads.
3. It can be automated to regularly back up your videos directory to YouTube.

Repository: `YouTube Uploader GitHub Repository <https://github.com/Ishuin/Youtube_uploader>`_

Features
--------

- **No Duplicate Uploads**: The script checks for existing uploads, ensuring no duplicates.
- **Organized Playlists**: Automatically organizes videos into playlists based on directory structure.
- **Automation-Friendly**: Can be set up for automatic, regular uploads.

Instructions
============

The script is primarily tested on Windows. The following instructions are tailored for Windows users.

Setup Guide
-----------

Step 0: Prerequisites
~~~~~~~~~~~~~~~~~~~~~

Before running the script, ensure that you have the following:

1. **Python 3.12.5**:

   Verify your Python installation by running ``python -V``. If Python is not installed, download and install it from the official Python website.

2. **Git**:

   Check if Git is installed by running ``git --version``. If Git is not installed, download it from the Git website.

3. **Google Python API Client Library**:

   Install the Google API Client Library using pip: ``pip install google-api-python-client``.

4. **Google OAuth Token**:

   Follow the steps in the **Generating a Google OAuth 2.0 Token** section below to create your token.

Step 1: Clone the Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone the repository to your local machine using the command: ``git clone https://github.com/Ishuin/Youtube_uploader.git``.

Step 2: Install Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Navigate to the project directory and install the required dependencies by running ``pip install -r requirements.txt``.

Step 3: Setup Google OAuth Token
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the steps in the next section to generate your OAuth 2.0 token and place the `token.json` file in the project directory.

Generating a Google OAuth 2.0 Token for Bulk YouTube Uploader
=============================================================

Follow the steps below to generate a Google OAuth 2.0 token required for uploading videos to YouTube using the YouTube Data API v3.

1. **Create a Project on Google Cloud Platform (GCP)**:
   
   - Go to the Google Cloud Console.
   - Create a new project or select an existing one.

2. **Enable YouTube Data API**:

   - Navigate to `APIs & Services > Library`.
   - Search for "YouTube Data API v3" and click on Enable.

3. **Configure OAuth Consent Screen**:

   - Go to `APIs & Services > OAuth consent screen`.
   - Select "External" as the user type.
   - Fill in the required information such as App name, Support email, and Developer contact information.
   - Under "Scopes", add the necessary scope for YouTube uploads: `https://www.googleapis.com/auth/youtube.force-ssl`.

4. **Create OAuth 2.0 Credentials**:

   - Go to `APIs & Services > Credentials`.
   - Click on `+ Create Credentials` and select `OAuth 2.0 Client ID`.
   - For "Application Type", choose "Desktop App".
   - Download the `client_secret_<unique_id>.json` file after the credentials are created.

5. **Install Required Python Libraries**:

   Install the necessary libraries using the command: ``pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client``.

6. **Generate the OAuth 2.0 Token**:

   Use the downloaded `client_secret_<unique_id>.json` file to generate the OAuth 2.0 token.

   **Modification**: When generating the token, ensure the path to your `client_secret_<unique_id>.json` file is correct in your script.

   Save the generated token as `token.json` and place it in the project directory.

7. **Use the OAuth 2.0 Token in Your Script**:

   Modify your script to use the `token.json` file for authentication. Ensure that the file path to the `token.json` file in your code is correctly set to its location in the project directory.

8. **Refresh the Token**:

   The access token in `token.json` expires after a while, but it will automatically refresh if the refresh token is still valid. Ensure your script handles token expiration.

For further details, refer to the `YouTube Data API Documentation <https://developers.google.com/youtube/v3>`_.

License
=======

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

You are free to use, modify, and distribute this software, but any distribution of modified or unmodified versions must include the original license. Any modifications you make must also be open-source and distributed under the same GPL license terms.

For more details, refer to the `GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>`_.
