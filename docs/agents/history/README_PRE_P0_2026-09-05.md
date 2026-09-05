# bale-auto — local P0 synthetic contract

This extracted transfer package now includes a dependency-free, in-memory P0
demonstration. It uses synthetic Persian text only and has no server, WhatsApp,
GitHub, database, network, or real-data integration.

Run the exact mocked path:

```bash
python3 demo_p0.py
```

Run the synthetic acceptance suite:

```bash
python3 -m unittest discover -s tests -v
```

The demonstrated sequence is: receipt acknowledgement → draft → one material
unit question → explicit confirmation → record → owner-only retrieval. Raw
source text is removed when the synthetic draft is confirmed.
