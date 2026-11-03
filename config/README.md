`scripts/setup.py` creates `local/`. Git ignores it and Compose mounts it
read-only. It can contain `ca.pem`, the public certificate of a verified
private CA. Keep private keys and tokens in their designated secret files.
