# MathType (MTEF v5) to LibreOffice Math: measurement harness

Prototype used to measure how well MathType 4-7 equations ("Equation.DSMT4" OLE objects, MTEF
version 5) convert to editable LibreOffice Math (StarMath) formulas. Upstream
`starmath/source/mathtype.cxx` only reads MTEF v2/v3 ("Equation.3"); version 5 is rejected.
`mtef5_starmath.py` is the reference for the C++ port: same record reader, same StarMath output.

Corpus: `tests/corpus/stem/manifest.json` (files are not redistributable; download each into its
own directory and check sha256; never run macros).

| Step | Script | Notes |
|---|---|---|
| Download corpus | `fetch-stem-corpus.py <manifest> <dir>` | one directory per file, sha256 checked |
| Extract equations | `extract-mathtype-equations.py <doc> <outdir>` | stdlib OLE reader (`cfb_reader.py`), writes `Equation Native` streams and `index.json` |
| Convert | `measure-mathtype-conversion.py <outroot> results.jsonl` | constructs, approximations ("minor"), failures |
| Check in LibreOffice | `check-starmath-content.py <port> results.jsonl checked.jsonl <tmp>` | letters/digits/=/+ of the rendered MathML must equal the MTEF source |
| .docx round trip | `check-starmath-docx-roundtrip.py <port> checked.jsonl <outdir>` | Math objects saved as OMML and reopened |
| Visual sample | `sample-equation-previews.py`, `render-equation-comparison.py` | original WMF preview next to the converted formula |

The LibreOffice scripts talk UNO to an office started with
`--accept=socket,host=127.0.0.1,port=<port>;urp;` and a scratch profile.
