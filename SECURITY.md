# Security Documentation

This document outlines the security measures implemented in the Dexcom CGM Data Manager to protect your sensitive health data.

## Overview

This application handles Protected Health Information (PHI) and implements multiple layers of security to ensure your glucose data remains private and secure.

## Security Measures

### 1. OAuth 2.0 Authentication

**Implementation:**
- Uses industry-standard OAuth 2.0 for authentication with Dexcom API
- CSRF protection via cryptographically secure random state tokens (`secrets.token_urlsafe(32)`)
- State parameter validation to prevent cross-site request forgery attacks
- Localhost-only callback server (binds to `127.0.0.1`)
- Automatic token expiration and refresh

**Code Location:** `dexcom_client.py`

**Security Benefits:**
- No password storage - authentication handled by Dexcom
- Time-limited access tokens (default 2 hours)
- Protection against CSRF attacks

### 2. Secure Credential Storage

**Implementation:**
- API credentials stored in `.env` file (excluded from version control via `.gitignore`)
- OAuth tokens stored in system keyring using `keyring` library
- Database encryption keys stored in system keyring
- Never logs or displays sensitive tokens

**Code Location:** `secure_storage.py`

**Platform-Specific Storage:**
- **macOS**: Keychain
- **Linux**: Secret Service API (GNOME Keyring, KWallet)
- **Windows**: Windows Credential Locker

**Security Benefits:**
- Credentials protected by OS-level security
- Encrypted at rest by the operating system
- Requires OS authentication to access

### 3. Database Encryption

**Implementation:**
- Uses Fernet (symmetric encryption) from the `cryptography` library
- AES-128 encryption with HMAC authentication
- Encryption keys generated using `Fernet.generate_key()` (cryptographically secure)
- Keys stored in system keyring, never on disk

**Code Location:** `database_encryption.py`

**What's Encrypted:**
- Sensitive health data fields can be encrypted at application level
- Encryption key unique to each installation
- Automatic encryption/decryption transparent to application logic

**Security Benefits:**
- Data protected at rest
- Even with database file access, data is unreadable without key
- HMAC prevents tampering

### 4. Secure File Permissions

**Implementation:**
- Database files automatically set to `0600` (owner read/write only) on Unix systems
- `.env` file should be manually set to `0600`
- On Windows, uses `icacls` to restrict access to current user only

**Code Location:** `database_encryption.py` (`set_secure_file_permissions()`)

**Security Benefits:**
- Other users on the system cannot read your health data
- Prevents accidental exposure via shared directories

### 5. Input Validation

**Implementation:**
- Validates all date inputs against ISO 8601 format
- Prevents SQL injection through parameterized queries
- Filename sanitization to prevent path traversal attacks
- Range checking on all user inputs

**Code Location:** `input_validation.py`

**Protections Against:**
- Date injection attacks
- Path traversal (e.g., `../../etc/passwd`)
- Invalid data causing crashes
- SQL injection

### 6. Network Security

**Implementation:**
- HTTPS/TLS 1.2+ for all API communications (enforced by Dexcom)
- Request timeouts to prevent hanging connections
- Explicit certificate verification (default in `requests` library)
- No proxy support (prevents MitM attacks)

**Code Location:** `dexcom_client.py`

**Security Benefits:**
- All data encrypted in transit
- Protection against eavesdropping
- Server authentication via TLS certificates

### 7. Error Handling

**Implementation:**
- Sanitized error messages that don't leak sensitive data
- No API tokens in logs or error messages
- Graceful degradation without exposing internals

**Security Benefits:**
- Prevents information disclosure
- Attackers can't gather system details from errors

## Security Best Practices

### For Users

1. **Protect Your .env File:**
   ```bash
   chmod 600 .env
   ```

2. **Use Strong API Credentials:**
   - Treat your Client ID and Secret like passwords
   - Never commit `.env` to version control
   - Rotate credentials if compromised

3. **Secure Your System:**
   - Use full-disk encryption
   - Keep OS and Python packages updated
   - Use a firewall
   - Don't run as root/administrator

4. **Database Security:**
   ```bash
   chmod 600 dexcom_data.db
   ```

5. **Regular Security Updates:**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

6. **Audit Access:**
   - Review who has access to your Dexcom developer application
   - Revoke access at https://developer.dexcom.com/ if needed

7. **Use Production Environment Carefully:**
   - Test with sandbox first
   - Understand implications of granting access to real health data

### For Developers

1. **Never Log Sensitive Data:**
   - No tokens in logs
   - No glucose values in debug output
   - No API credentials in error messages

2. **Use Parameterized Queries:**
   - All DuckDB queries use parameterization
   - Never string concatenation for SQL

3. **Validate All Inputs:**
   - Use `InputValidator` for all user inputs
   - Never trust data from external sources

4. **Keep Dependencies Updated:**
   ```bash
   pip list --outdated
   ```

5. **Code Review Checklist:**
   - [ ] No hardcoded credentials
   - [ ] All inputs validated
   - [ ] Errors don't leak info
   - [ ] Sensitive data encrypted
   - [ ] File permissions set correctly

## Threat Model

### Protected Against

✅ **CSRF Attacks** - Random state parameter validation
✅ **Credential Theft** - Keyring storage
✅ **Data at Rest** - Database encryption
✅ **Path Traversal** - Filename validation
✅ **SQL Injection** - Parameterized queries
✅ **Eavesdropping** - TLS encryption
✅ **Unauthorized File Access** - File permissions

### NOT Protected Against

⚠️ **Malware on Your System** - If your system is compromised, data may be accessible
⚠️ **Physical Access** - Physical access to unlocked system grants access
⚠️ **OS Keyring Compromise** - If OS authentication is bypassed, tokens accessible
⚠️ **Memory Dumps** - Tokens in memory during execution
⚠️ **Shoulder Surfing** - Visualizations displayed on screen

## Compliance Considerations

### HIPAA (United States)

This application stores Protected Health Information (PHI):

- **Encryption:** Data encrypted at rest and in transit ✓
- **Access Controls:** OS-level authentication required ✓
- **Audit Logs:** Not currently implemented ✗
- **Data Minimization:** Only fetches requested date ranges ✓

**Note:** This is a personal tool. If used in a healthcare setting, additional HIPAA safeguards may be required including:
- Audit logging
- Business Associate Agreements with Dexcom
- Risk assessments
- Incident response procedures

### GDPR (European Union)

If handling EU citizens' data:

- **Right to Access:** Data exportable via DuckDB queries ✓
- **Right to Erasure:** Database can be deleted ✓
- **Data Portability:** Can export to CSV/JSON ✓
- **Consent:** User explicitly authenticates via OAuth ✓

## Incident Response

### If Your Credentials Are Compromised

1. **Immediately revoke access** at https://developer.dexcom.com/
2. **Clear stored tokens:**
   ```python
   from secure_storage import SecureStorage
   SecureStorage.clear_tokens()
   ```
3. **Delete `.env` file and create new one with new credentials**
4. **Rotate your Dexcom developer credentials**

### If Your Database Is Compromised

1. **Delete the database file:** `rm dexcom_data.db`
2. **Generate new encryption key** (automatic on next run)
3. **Re-fetch data from Dexcom**

### If You Suspect Unauthorized Access

1. Check Dexcom developer portal for unusual API activity
2. Review OAuth authorizations in your Dexcom account
3. Check system logs for unauthorized access
4. Consider changing your Dexcom account password

## Security Testing

### Recommended Tests

```bash
# Check file permissions
ls -la dexcom_data.db .env

# Verify .env not in git
git status --ignored

# Check for outdated dependencies with known vulnerabilities
pip install safety
safety check

# Verify encryption is working
python -c "from database_encryption import DataEncryption; e = DataEncryption(); print('✓ Encryption initialized')"
```

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT open a public GitHub issue**
2. Contact the maintainer directly
3. Provide details:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Dexcom API Security](https://developer.dexcom.com/docs/dexcom/authentication/)
- [Python Cryptography Documentation](https://cryptography.io/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Version History

- **v1.0** (Initial) - Basic OAuth, HTTPS
- **v2.0** (Current) - Added CSRF protection, keyring storage, database encryption, input validation, file permissions

---

**Last Updated:** 2025-11-13
**Security Review:** Recommended annually or after major changes
