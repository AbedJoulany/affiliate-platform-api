# Facebook Page connection (manual MVP)

The connection flow accepts a Facebook Page ID and Page access token from an
authorized workspace owner. The token is validated server-side and stored only
as an AES-256-GCM encrypted envelope. It is never returned by the API or
displayed again in the UI.

Generate a local encryption key with PowerShell and keep it outside Git:

```powershell
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

Set the resulting value as `FACEBOOK_TOKEN_ENCRYPTION_KEY` in the local secret
environment. The application accepts padded or unpadded URL-safe Base64, but
the decoded value must be exactly 32 bytes. It fails closed when the key is
missing or invalid.

The key is not recoverable from the database. If it is lost, existing Page
tokens cannot be decrypted; the affected Page connection must be removed and
re-created with a newly issued Page access token. Never commit the key or put
it in frontend configuration.
