# Real-data titration: NASA PCoE "Capacitor Electrical Stress" -- method not applicable atm

Co-authored, 2026-10-31. CC0 (this write-up; the dataset keeps its own license).
Work order: first real-data run of `src/noise_titration.py`, Target B (secondary).

## Result

**Method not applicable atm.** `noise_titration` was not run on this dataset. Two reasons, either sufficient:

```text
1  FORMAT     the three data files are MATLAB 7.3 MAT-files = HDF5 containers.
              The Python standard library has no HDF5 reader; reading them needs h5py/HDF5
              (not stdlib). OBSERVED (file header bytes, below).
2  STRUCTURE  descriptions of the set say each aging checkpoint holds EIS measurements and
              charge/discharge transient signals at three stress voltages (10 V, 12 V, 14 V).
              A transient is a step response, not a steady reading with noise around a mean,
              and EIS gives one impedance spectrum per checkpoint. Neither matches what
              titration needs (dense windows of a steady reading). Source: search-result
              summaries of the NASA PCoE page and its data.phmsociety.org mirror; the pages
              themselves could not be opened from this environment. VERIFY.
```

Not forced. No substitute data was used.

## What was checked

```text
archive URL      https://phm-datasets.s3.amazonaws.com/NASA/12.+Capacitor+Electrical+Stress.zip
reached          yes, 2026-10-31 (HTTP 200; Content-Length 5038942729; Last-Modified 2022-09-18)
downloaded       no; only the zip central directory and the first 4096 bytes of ES10.mat
                 were read, via HTTP range requests (stdlib urllib + zipfile)
contents         12. Capacitor Electrical Stress/ES10.mat   1209388987 bytes
                 12. Capacitor Electrical Stress/ES12.mat   1863271598 bytes
                 12. Capacitor Electrical Stress/ES14.mat   2094950842 bytes
ES10.mat header  'MATLAB 7.3 MAT-file, Platform: PCWIN64, Created on: Tue May 26 10:15:39 2015
                  HDF5 schema 1.00 .'
citation         J. Renwick, C. Kulkarni, J. Celaya, "Capacitor Electrical Stress Data Set",
                 NASA Prognostics Data Repository (per search summary of the NASA page; VERIFY)
license          not verified: www.nasa.gov and data.phmsociety.org are blocked from this
                 environment (proxy 403; web fetch host not resolvable). VERIFY.
```

## What would move this

- An HDF5 reader is allowed for a one-off conversion step (outside the stdlib-only code), or a
  copy of the data in a stdlib-readable format exists.
- Inspecting the HDF5 groups shows a dense steady-state signal per checkpoint (for example a
  long constant-voltage hold). Only then would titration apply as written. Otherwise the noise
  question for capacitors needs a different method (for example the ESR or RC time-constant trend
  the matrix row already cites as ECAP_ESR).

Matrix rows for electrolytic capacitors are unchanged (status DERIVED, source ECAP_ESR).
