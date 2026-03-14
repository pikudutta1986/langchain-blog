# credentials/

Place your GCP service account JSON key file here and name it `service_account.json`.

This directory is bind-mounted into the container at `/app/credentials/` (read-only).
The path is referenced by the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

## How to create a service account key

1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Select your project (`GCP_PROJECT_ID` in `.env`)
3. Create a service account with the **Vertex AI User** role
4. Click **Keys → Add Key → Create new key → JSON**
5. Save the downloaded file here as `service_account.json`

> ⚠️ Never commit `service_account.json` to version control.
> It is already listed in `.gitignore`.
