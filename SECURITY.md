# Security Policy

## Supported Versions

Security fixes target the latest release on `main`.

## Reporting

Please do not open public issues for vulnerabilities, credential handling bugs, or flows that could expose private ebook data. Report them privately to the repository owner through GitHub or another trusted private channel.

Include:

- the Digi2PDF version,
- your operating system,
- whether you used the Python CLI or Windows EXE,
- the exact command or startup path,
- relevant error text with credentials and personal book data removed.

## Credential Handling

Digi2PDF only stores Digi4School credentials after a successful login and explicit confirmation. Stored credentials are delegated to the operating system keychain through `keyring`.

Generated PDFs are local files. Do not upload or redistribute them unless you have the legal right to do so.
