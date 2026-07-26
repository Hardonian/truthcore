# Evidence packet export

`truthctl export-evidence --bundle <bundle-dir> --out <packet.zip>` creates a buyer-usable ZIP containing the replay bundle, `evidence-index.json` with SHA-256 hashes, and replay instructions. The packet is an export of observed bundle contents; it does not add customer, revenue, or verification claims.

After unpacking, verify the index hashes and run `truthctl replay --bundle <directory> --out <results>`.
