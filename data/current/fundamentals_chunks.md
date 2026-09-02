# Investment OS — Fundamentals chunks for Claude

- Total rows: **504**
- Total columns: **158**
- Total parts: **12**
- Target max bytes per part: **48000**
- Source SHA-256: `204130b00c30f10623e9ffdff2e0be819043857f05b5fa5b7adb3ab0b7569ade`
- Read **all parts** before producing any full-universe ranking.

- Part 01: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_01.csv — rows 1-42 — 47504 bytes — sha256 `5bf26db6f520af5e2cd238f782521e1f27fcb4b9653cb9c4729e4aada587afd8`
- Part 02: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_02.csv — rows 43-83 — 46985 bytes — sha256 `878b1a3adbb9ece66cb7759c0ee210c02e9faeed38699d07e1c01627d4563125`
- Part 03: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_03.csv — rows 84-126 — 47874 bytes — sha256 `708e778e327da0f1c13cb7a52df3a9a031206bda4a54f01518fa65b5f1006859`
- Part 04: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_04.csv — rows 127-168 — 47790 bytes — sha256 `c6bab9f40122e81532c7a2abd06ead25a43b2137de2b087a156ae71ad2939989`
- Part 05: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_05.csv — rows 169-210 — 47027 bytes — sha256 `9b78f37fae6aaf4a9e982ad4cc636519a310dda2ef4bad83b846c9161dd4a170`
- Part 06: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_06.csv — rows 211-254 — 47850 bytes — sha256 `c7d6a011059d0b099e5cf6388837334a6f1ff2bd411c21b06219f88bf591d60b`
- Part 07: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_07.csv — rows 255-296 — 47050 bytes — sha256 `93194e0154ef1096cd3ec22284188f5f09fe6774749e4e1dd6c28e57a405ccaf`
- Part 08: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_08.csv — rows 297-338 — 47128 bytes — sha256 `7747f4330fa47a541e551141abd1fb11d1c6e99dddf02514e9c97d00d2e835f0`
- Part 09: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_09.csv — rows 339-382 — 47926 bytes — sha256 `9c3c7a3ef145f05d9dfe4f6a7437a6cf8f02839e64fa72659af08e6f3fa80981`
- Part 10: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_10.csv — rows 383-425 — 47703 bytes — sha256 `b1064a49fa303a9b661a5c22828960f9f414196ab6fc3a1f8aa1be909730ab47`
- Part 11: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_11.csv — rows 426-469 — 47433 bytes — sha256 `6b54020612ac5390e5b5e46086e222a7fbf4caba394a46b663bbdda21c4c3fc6`
- Part 12: https://raw.githubusercontent.com/flaviomellace-ctrl/investment-os-data-bridge/main/data/current/sp500_fundamentals_part_12.csv — rows 470-504 — 38865 bytes — sha256 `d7f8918a824d88604879dc4e4dd479c868afaf80f764bc56b1e638bf471e0e89`

## Transport validation

- Rows from parts: **504**
- Rows match source: **True**
- Ranges contiguous: **True**
- All parts <= 58000 bytes: **True**

## Regole

- Non costruire ranking da un sottoinsieme dei chunk.
- MISSING non è zero.
- Applicare Sector Fairness Rule.
- I chunk servono solo al trasporto dei dati.
- Per i finalisti verificare gli ultimi filing SEC/Investor Relations.
